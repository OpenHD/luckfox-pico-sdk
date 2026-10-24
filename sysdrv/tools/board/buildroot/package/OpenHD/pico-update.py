#!/usr/bin/env python3
"""Paired application slots for Pico SD images. Does not write boot partitions."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile


class Slots:
    def __init__(self, root=Path('/')):
        self.root = Path(root)
        self.store = self.root / 'userdata/openhd-slots'
        self.runtime = self.root / 'run/openhd'
        self.store.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.statefile = self.store / 'state.json'

    def read(self):
        if not self.statefile.exists():
            return dict(active='factory', previous='factory', pending=None, tried=False)
        state = json.loads(self.statefile.read_text())
        for key in ('active', 'previous'):
            if state[key] not in ('factory', 'a', 'b'):
                raise ValueError('Invalid slot state')
        if state['pending'] not in (None, 'a', 'b'):
            raise ValueError('Invalid pending slot')
        return state

    def write(self, state):
        temporary = self.store / 'state.new'
        with temporary.open('w') as stream:
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.statefile)
        os.sync()

    def select(self, slot):
        target = self.root if slot == 'factory' else self.store / slot
        temporary = self.runtime / 'current.new'
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(target)
        os.replace(temporary, self.runtime / 'current')

    def boot(self):
        state = self.read()
        if state['pending']:
            if state['tried']:
                state.update(active=state['previous'], pending=None, tried=False)
            else:
                state['tried'] = True
            self.write(state)
        self.select(state['pending'] or state['active'])
        return state

    def install(self, archive):
        state = self.read()
        if state['pending']:
            raise ValueError('Confirm or roll back the pending trial first')
        slot = 'b' if state['active'] == 'a' else 'a'
        if (self.runtime / 'current').resolve() == self.store / slot:
            raise ValueError('Reboot before replacing the running slot')
        with tempfile.TemporaryDirectory(prefix='staging-', dir=self.store) as work:
            stage = Path(work)
            with tarfile.open(archive, 'r:gz') as bundle:
                members = bundle.getmembers()
                names = set()
                total = 0
                for member in members:
                    path = PurePosixPath(member.name)
                    name = str(path)
                    if path.is_absolute() or '..' in path.parts or name in names:
                        raise ValueError('Unsafe or duplicate bundle path')
                    if not (member.isfile() or member.isdir()):
                        raise ValueError('Bundle links and special files are forbidden')
                    if member.isfile() and not (name in ('manifest.json',) or
                            name.startswith('usr/bin/') or name.startswith('usr/lib/')):
                        raise ValueError('Unexpected bundle file')
                    total += member.size
                    if total > 256 * 1024 * 1024:
                        raise ValueError('Bundle exceeds 256 MiB unpacked limit')
                    names.add(name)
                if shutil.disk_usage(self.store).free < total + 16 * 1024 * 1024:
                    raise ValueError('Not enough space for inactive slot')
                for member in members:
                    destination = stage / member.name
                    if member.isdir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with bundle.extractfile(member) as source, destination.open('wb') as out:
                            shutil.copyfileobj(source, out)
                        destination.chmod(member.mode & 0o755)
            manifest = json.loads((stage / 'manifest.json').read_text())
            base_id = (self.root / 'etc/openhd-pico-base-id').read_text().strip()
            if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})(?:-rv1106-pro-max-sd)?', base_id):
                raise ValueError('Missing or invalid factory base image identity')
            if (manifest['schema'], manifest['platform'], manifest['architecture'],
                    manifest['base_id']) != (1, 'luckfox-pico', 'armhf', base_id):
                raise ValueError('Bundle does not match this Pico base image')
            actual = {str(p.relative_to(stage)) for p in stage.rglob('*')
                      if p.is_file() and p != stage / 'manifest.json'}
            if actual != set(manifest['files']):
                raise ValueError('Bundle file inventory differs from manifest')
            for name, digest in manifest['files'].items():
                if hashlib.sha256((stage / name).read_bytes()).hexdigest() != digest:
                    raise ValueError('Checksum mismatch: ' + name)
            for binary in ('openhd', 'openhd_sys_utils'):
                path = stage / 'usr/bin' / binary
                header = path.read_bytes()[:20]
                if (len(header) < 20 or header[:6] != b'\x7fELF\x01\x01' or
                        header[18:20] != b'\x28\x00' or not os.access(path, os.X_OK)):
                    raise ValueError('Missing executable ARM binary: ' + binary)
            destination = self.store / slot
            if destination.exists():
                shutil.rmtree(destination)
            os.rename(stage, destination)
            # TemporaryDirectory tolerates its staging path having been renamed.
            os.sync()
        state.update(previous=state['active'], pending=slot, tried=False)
        self.write(state)
        return state

    def confirm(self):
        state = self.read()
        if not state['pending'] or not state['tried']:
            raise ValueError('No booted trial to confirm')
        state.update(active=state['pending'], pending=None, tried=False)
        self.write(state)
        return state

    def rollback(self):
        state = self.read()
        state.update(active=state['previous'], pending=None, tried=False)
        self.write(state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'boot', 'confirm', 'rollback', 'status'])
    parser.add_argument('archive', nargs='?')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run as root')
    # Refuse to create volatile slots when the persistent partition did not mount.
    if not os.path.ismount('/userdata'):
        parser.error('/userdata must be a mounted persistent filesystem')
    slots = Slots()
    with (slots.store / 'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == 'install':
            if not args.archive:
                parser.error('install requires an archive')
            result = slots.install(args.archive)
        else:
            result = slots.read() if args.command == 'status' else getattr(slots, args.command)()
        print(json.dumps(result))


if __name__ == '__main__':
    main()
