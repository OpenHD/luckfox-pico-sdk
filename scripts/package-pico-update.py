#!/usr/bin/env python3
"""Bundle paired applications and their ELF dependency closure from one rootfs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile


def target_file(root, path):
    for _ in range(40):
        if not path.is_symlink():
            return path
        link = path.readlink()
        path = root / str(link).lstrip('/') if link.is_absolute() else path.parent / link
        path = Path(os.path.normpath(path))
        if not path.is_relative_to(root):
            raise ValueError('Library symlink escapes target root')
    raise ValueError('Library symlink loop')


def package(root, output, readelf, commits):
    root = root.resolve()
    base_id = (root / 'etc/openhd-pico-base-id').read_text().strip()
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})(?:-rv1106-pro-max-sd)?', base_id):
        raise ValueError('Missing or invalid base image identity')
    with tempfile.TemporaryDirectory() as work:
        stage = Path(work)
        queue = []
        for binary in ('openhd', 'openhd_sys_utils'):
            source = root / 'usr/bin' / binary
            header = source.read_bytes()[:20]
            if header[:6] != b'\x7fELF\x01\x01' or header[18:20] != b'\x28\x00':
                raise ValueError('Expected ARM ELF executable: ' + binary)
            target = stage / 'usr/bin' / binary
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o755)
            queue.append(source)
        copied = set()
        while queue:
            source = queue.pop()
            dynamic = subprocess.check_output([readelf, '-d', str(source)], text=True)
            for library in re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic):
                if library in copied:
                    continue
                if '/' in library:
                    raise ValueError('Unexpected ELF dependency path')
                found = next((p for folder in ('usr/lib', 'lib')
                              if (p := root / folder / library).exists() or p.is_symlink()), None)
                if found is None:
                    raise ValueError('Missing runtime library: ' + library)
                source = target_file(root, found)
                target = stage / 'usr/lib' / library
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                target.chmod(0o755)
                copied.add(library)
                queue.append(source)
        manifest = dict(schema=1, platform='luckfox-pico', architecture='armhf',
                        base_id=base_id, source_commits=commits,
                        files={str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(stage.rglob('*')) if p.is_file()})
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, 'w:gz') as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.add(path, arcname=str(path.relative_to(stage)))
        output.with_suffix(output.suffix + '.sha256').write_text(
            hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rootfs', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--readelf', default='readelf')
    parser.add_argument('--openhd-commit', required=True)
    parser.add_argument('--sysutils-commit', required=True)
    args = parser.parse_args()
    package(args.rootfs, args.output, args.readelf,
            dict(openhd=args.openhd_commit, sysutils=args.sysutils_commit))
