import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import subprocess
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pico_nand as nand


class NandTest(unittest.TestCase):
    def test_layout_and_reserved_space(self):
        self.assertEqual(max(o + s for o, s in nand.PARTITIONS.values()), 120 << 20)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in nand.PARTITIONS:
                (root / (name + '.img')).write_bytes(b'UBI#' + b'\0' * (nand.PEB - 4))
            nand.check_images(root)
            with (root / 'rootfs.img').open('r+b') as stream:
                stream.truncate(nand.PARTITIONS['rootfs'][1] - 23 * nand.PEB)
            with self.assertRaisesRegex(ValueError, 'UBI reserve'):
                nand.check_images(root)

    def archive(self, path, members):
        with tarfile.open(path, 'w:xz') as archive:
            for name, link in members:
                entry = tarfile.TarInfo(name)
                if link is None:
                    entry.size = 1; entry.mode = 0o755
                    archive.addfile(entry, io.BytesIO(b'x'))
                else:
                    entry.type = tarfile.SYMTYPE; entry.linkname = link
                    archive.addfile(entry)

    def test_seed_allows_target_absolute_links_without_following_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); archive = root / 'seed.tar.xz'
            self.archive(archive, [('usr/bin/test', None), ('Config', '/userdata/Config')])
            nand.extract_seed(archive, root / 'out')
            self.assertTrue((root / 'out/usr/bin/test').stat().st_mode & 0o111)
            self.assertEqual((root / 'out/Config').readlink(), Path('/userdata/Config'))

    def test_reject_seed_path_and_symlink_parent_escapes(self):
        for members in [[('../outside', None)], [('/outside', None)],
                        [('a', '/tmp'), ('a/link', '/outside')]]:
            with self.subTest(members=members), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); archive = root / 'seed.tar.xz'
                self.archive(archive, members)
                with self.assertRaises(ValueError):
                    nand.extract_seed(archive, root / 'out')

    def test_config_symlink_becomes_a_real_persistent_mountpoint(self):
        repo = Path(__file__).resolve().parents[2]
        source = (repo / 'project/cfg/BoardConfig_IPC/overlay/overlay-openhd-pico-nand/etc/init.d/S25openhd-nand').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            userdata = root / 'userdata/Config'; userdata.mkdir(parents=True)
            (userdata / 'saved.json').write_text('persistent settings')
            config = root / 'Config'; config.symlink_to('/userdata/Config')
            commands = root / 'bin'; commands.mkdir()
            for name, content in {
                'mountpoint': '#!/bin/sh\n[ -f "$TEST_ROOT/mounted" ]\n',
                'mount': '#!/bin/sh\nprintf "%s\\n" "$*" > "$TEST_ROOT/mounted"\n'
            }.items():
                path = commands / name; path.write_text(content); path.chmod(0o755)
            script = root / 'start.sh'
            # Execute the production shell logic against an isolated filesystem.
            source = source.replace('/userdata/Config', '@@USER_CONFIG@@').replace('/Config', str(config)).replace('@@USER_CONFIG@@', str(userdata))
            source = source.replace('/tmp/Videos', str(root / 'Videos')).replace('/var/log', str(root / 'log'))
            script.write_text(source)
            env = dict(os.environ, TEST_ROOT=str(root), PATH=str(commands) + ':' + os.environ['PATH'])
            # The relocated expected link target follows the same rewrite.
            config.unlink(); config.symlink_to(userdata)
            for _ in range(2):
                subprocess.run(['sh', str(script), 'start'], env=env, check=True)
            self.assertTrue(config.is_dir())
            self.assertFalse(config.is_symlink())
            self.assertIn('--bind', (root / 'mounted').read_text())
            self.assertEqual((userdata / 'saved.json').read_text(), 'persistent settings')

    def test_profile_is_native_minimal_and_does_not_change_sd_mini(self):
        repo = Path(__file__).resolve().parents[2]
        config = (repo / 'sysdrv/tools/board/buildroot/luckfox_pico_nand_defconfig').read_text()
        self.assertNotIn('GSTREAMER', config)
        self.assertNotIn('PYTHON', config)
        board = (repo / 'project/cfg/BoardConfig_IPC/BoardConfig-SPI_NAND-Buildroot-RV1103_Luckfox_Pico_Mini_OpenHD-IPC.mk').read_text()
        self.assertIn('79M(rootfs)', board)
        self.assertIn('luckfox_pico_nand_defconfig', board)
        self.assertIn('mis5001_CMK-OT2115-PC1_30IRC-F16.json', board)
        self.assertIn('RK_ENABLE_GDB=n', board)


if __name__ == '__main__':
    unittest.main()
