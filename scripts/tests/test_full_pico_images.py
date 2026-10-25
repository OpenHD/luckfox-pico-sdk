import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
from pathlib import Path
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, REPO / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


targets = module('select_pico_targets')
components = module('record_pico_components')


class PicoImageTest(unittest.TestCase):
    def test_matrix_contains_all_six_actual_board_configurations(self):
        rows = targets.select('all')['include']
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({row['id'] for row in rows}), 6)
        for row in rows:
            board = (REPO / 'project/cfg/BoardConfig_IPC' / row['board_config']).read_text()
            self.assertIn('export RK_BOOT_MEDIUM=' + row['boot_medium'], board)
            self.assertEqual(targets.select(row['id'])['include'], [row])
        self.assertEqual(sum(row['boot_medium'] == 'emmc' for row in rows), 3)
        with self.assertRaises(ValueError):
            targets.select('aura')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'
        self.update = Path(self.temp.name) / 'update.pico-ohd'
        self.commits = dict(sdk='1' * 40, openhd='2' * 40, sysutils='3' * 40, devourer='4' * 40)
        self.files = {
            'usr/bin/openhd': b'ARM fixture Devourer identified packet-address=mb-valid',
            'usr/bin/openhd_sys_utils': b'ARM fixture SysUtils',
            'usr/lib/libdependency.so.1': b'runtime dependency',
        }
        for name, data in self.files.items():
            self.write(name, data)
        for name in ('S97openhd-slots', 'S98openhd-sysutils', 'S99openhd'):
            self.write('etc/init.d/' + name)
        for name in ('lib/modprobe.d/openhd-devourer-eu.conf',
                     'lib/udev/rules.d/70-openhd-devourer-eu.rules',
                     'usr/local/share/OpenHD/SysUtils/wifi_cards.json'):
            self.write(name)
        self.write('etc/openhd-pico-base-id', b'5' * 64 + b'\n')
        self.bundle()

    def write(self, name, data=b'fixture'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755)

    def bundle(self):
        manifest = dict(base_id='5' * 64, source_commits={key: self.commits[key]
                        for key in ('openhd', 'sysutils')},
                        files={name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()})
        data = json.dumps(manifest).encode()
        with tarfile.open(self.update, 'w:gz') as archive:
            info = tarfile.TarInfo('manifest.json')
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))

    def inspect(self):
        return components.inspect(self.root, self.update, 'luckfox-pico-ultra-w', self.commits)

    def test_records_sources_and_runtime_library_inventory_without_webui(self):
        actual = self.inspect()
        self.assertEqual(actual['source_commits'], self.commits)
        self.assertTrue(actual['devourer'])
        self.assertFalse(actual['webui'])
        self.assertIn('usr/lib/libdependency.so.1', actual['runtime_files'])

    def test_accepts_toolchain_libraries_in_lib(self):
        (self.root / 'usr/lib/libdependency.so.1').unlink()
        self.write('lib/libdependency.so.1', self.files['usr/lib/libdependency.so.1'])
        self.inspect()

    def test_rejects_missing_library_and_changed_application(self):
        for name in ('usr/lib/libdependency.so.1', 'usr/bin/openhd'):
            with self.subTest(name=name):
                self.write(name, b'changed')
                with self.assertRaises(ValueError):
                    self.inspect()
                self.write(name, self.files[name])

    def test_resolves_absolute_library_symlinks_inside_target_root(self):
        library = self.root / 'usr/lib/libdependency.so.1'
        library.unlink()
        self.write('lib/libdependency-real.so', self.files['usr/lib/libdependency.so.1'])
        library.symlink_to('/lib/libdependency-real.so')
        self.inspect()

    def test_rejects_webui_and_conflicting_broadcast_driver(self):
        for name in ('usr/bin/openhd-webui', 'lib/modules/5.10/88x2eu.ko'):
            with self.subTest(name=name):
                self.write(name)
                with self.assertRaises(ValueError):
                    self.inspect()
                (self.root / name).unlink()

    def test_rejects_old_venc_packet_address(self):
        self.files['usr/bin/openhd'] = b'ARM fixture Devourer identified'
        self.write('usr/bin/openhd', self.files['usr/bin/openhd'])
        self.bundle()
        with self.assertRaisesRegex(ValueError, 'packet-address fix'):
            self.inspect()

    def test_rejects_openhd_without_devourer(self):
        self.files['usr/bin/openhd'] = b'ARM fixture without radio backend'
        self.write('usr/bin/openhd', self.files['usr/bin/openhd'])
        self.bundle()
        with self.assertRaisesRegex(ValueError, 'Devourer'):
            self.inspect()

    def test_rejects_source_commit_mismatch(self):
        self.commits['openhd'] = '9' * 40
        with self.assertRaisesRegex(ValueError, 'sources'):
            self.inspect()

    @unittest.skipUnless(shutil.which('mkfs.ext4') and shutil.which('debugfs'), 'ext4 tools required')
    def test_embeds_the_verified_manifest_into_the_real_rootfs_image(self):
        image = Path(self.temp.name) / 'rootfs.img'
        with image.open('wb') as stream:
            stream.truncate(8 * 1024 * 1024)
        subprocess.run(['mkfs.ext4', '-q', '-F', '-d', str(self.root), str(image)], check=True)
        output = Path(self.temp.name) / 'components.json'
        components.record(self.root, image, self.update, output,
                          'luckfox-pico-ultra-w', self.commits)
        actual = subprocess.check_output(['debugfs', '-R',
            'cat /etc/openhd-image-components.json', str(image)])
        self.assertEqual(actual, output.read_bytes())


if __name__ == '__main__':
    unittest.main()
