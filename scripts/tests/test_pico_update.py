import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pico_update', REPO /
    'sysdrv/tools/board/buildroot/package/OpenHD/pico-update.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)
spec = importlib.util.spec_from_file_location('package_pico', REPO / 'scripts/package-pico-update.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'etc').mkdir()
        (self.root / 'etc/openhd-pico-base-id').write_text('test-base')
        self.slots = update.Slots(self.root)
        self.sync = patch.object(update.os, 'sync')
        self.sync.start()
        self.addCleanup(self.sync.stop)

    def bundle(self, base_id='test-base', corrupt=False, extra=None):
        elf = b'\x7fELF\x01\x01' + bytes(12) + b'\x28\x00' + b'payload'
        files = {'usr/bin/' + name: elf for name in ('openhd', 'openhd_sys_utils')}
        manifest = dict(schema=1, platform='luckfox-pico', architecture='armhf',
                        base_id=base_id, files={n: hashlib.sha256(b).hexdigest()
                                               for n, b in files.items()})
        if corrupt:
            files['usr/bin/openhd'] += b'corrupt'
        files['manifest.json'] = json.dumps(manifest).encode()
        archive = self.root / 'update.pico-ohd'
        with tarfile.open(archive, 'w:gz') as output:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.mode = 0o755
                info.size = len(data)
                output.addfile(info, io.BytesIO(data))
            if extra:
                output.addfile(extra)
        return archive

    def test_trial_confirmation_and_second_slot(self):
        self.slots.install(self.bundle())
        self.assertFalse(self.slots.read()['tried'])
        self.slots.boot()
        self.assertEqual((self.slots.runtime / 'current').resolve(), self.slots.store / 'a')
        self.slots.confirm()
        self.assertEqual(self.slots.boot()['active'], 'a')
        self.slots.install(self.bundle())
        self.assertEqual(self.slots.boot()['pending'], 'b')
        self.assertEqual(self.slots.boot()['active'], 'a')
        self.assertEqual((self.slots.runtime / 'current').resolve(), self.slots.store / 'a')

    def test_first_trial_rolls_back_to_factory(self):
        self.slots.install(self.bundle())
        self.slots.boot()
        self.slots.boot()
        self.assertEqual((self.slots.runtime / 'current').resolve(), self.root)

    def test_reject_bad_bundle_without_changing_state(self):
        for args in (dict(base_id='x21'), dict(corrupt=True)):
            with self.assertRaises(ValueError):
                self.slots.install(self.bundle(**args))
            self.assertFalse(self.slots.statefile.exists())

    def test_reject_paths_links_and_missing_files(self):
        for name, kind in (('../escape', tarfile.REGTYPE),
                           ('usr/lib/escape', tarfile.SYMTYPE),
                           ('/etc/passwd', tarfile.REGTYPE)):
            member = tarfile.TarInfo(name)
            member.type = kind
            member.linkname = '/etc/passwd'
            with self.assertRaises(ValueError):
                self.slots.install(self.bundle(extra=member))
        self.assertFalse((self.root / 'escape').exists())

    def test_pending_trial_blocks_reinstall_and_early_confirm(self):
        self.slots.install(self.bundle())
        with self.assertRaises(ValueError):
            self.slots.confirm()
        with self.assertRaises(ValueError):
            self.slots.install(self.bundle())

    def test_interrupted_install_preserves_active_slot(self):
        self.slots.install(self.bundle())
        self.slots.boot()
        self.slots.confirm()
        original = self.slots.write
        self.slots.write = lambda state: (_ for _ in ()).throw(OSError('power loss'))
        with self.assertRaises(OSError):
            self.slots.install(self.bundle())
        self.slots.write = original
        self.assertEqual(self.slots.boot()['active'], 'a')

    def test_packager_includes_transitive_libraries(self):
        archive = self.bundle()
        with tarfile.open(archive) as source:
            source.extractall(self.root)
        (self.root / 'usr/lib').mkdir()
        (self.root / 'lib').mkdir()
        (self.root / 'usr/lib/libfirst.so.1').write_bytes(b'library1')
        (self.root / 'usr/lib/libfirst.so').symlink_to('/usr/lib/libfirst.so.1')
        (self.root / 'lib/libsecond.so').write_bytes(b'library2')
        def dependencies(command, **kwargs):
            name = Path(command[-1]).name
            return ('(NEEDED) [libfirst.so]' if name in ('openhd', 'openhd_sys_utils') else
                    '(NEEDED) [libsecond.so]' if name == 'libfirst.so.1' else '')
        output = self.root / 'paired.pico-ohd'
        with patch.object(builder.subprocess, 'check_output', side_effect=dependencies):
            builder.package(self.root, output, 'readelf', dict(openhd='1', sysutils='2'))
        self.slots.install(output)
        self.assertEqual((self.slots.store / 'a/usr/lib/libsecond.so').read_bytes(), b'library2')


if __name__ == '__main__':
    unittest.main()
