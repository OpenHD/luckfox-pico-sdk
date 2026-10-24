import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('firmware_package', REPO / 'scripts/package_imagewriter_firmware.py')
firmware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firmware)


def disk_image():
    image = bytearray(256 * 512)
    image[510:512] = b'\x55\xaa'
    entries = bytearray(128 * 128)
    entries[:16] = b'\x01' * 16
    struct.pack_into('<QQ', entries, 32, 34, 222)
    entries[56:68] = 'rootfs'.encode('utf-16-le')
    image[1024:1024 + len(entries)] = entries
    image[223 * 512:255 * 512] = entries
    for current, backup, table in ((1, 255, 2), (255, 1, 223)):
        header = bytearray(512)
        struct.pack_into('<8sIIIIQQQQ16sQIII', header, 0, b'EFI PART', 0x10000,
                         92, 0, 0, current, backup, 34, 222, b'\x02' * 16,
                         table, 128, 128, zlib.crc32(entries))
        struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
        image[current * 512:(current + 1) * 512] = header
    return image


class ImageWriterFirmwareTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.disk = root / 'sdcard.img'
        self.disk.write_bytes(disk_image())
        self.loader = root / 'download.bin'
        self.loader.write_bytes(b'LDR ' + b'\x10' * 64)
        self.board = root / 'BoardConfig-EMMC-RV1106_Ultra.mk'
        self.board.write_text('export RK_BOOT_MEDIUM=emmc\n')
        self.output = root / 'firmware.zip'

    def package(self):
        firmware.package(self.disk, self.loader, self.board, self.output, '1' * 40)

    def test_self_contained_full_disk_flash_plan(self):
        self.package()
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(set(archive.namelist()), {'.env.txt', 'disk.img', 'download.bin', 'firmware-manifest.json'})
            self.assertIn(f'blkdevparts=mmcblk0:{self.disk.stat().st_size}@0(disk)\n', archive.read('.env.txt').decode())
            self.assertEqual(archive.read('disk.img'), self.disk.read_bytes())
            self.assertEqual(archive.read('download.bin'), self.loader.read_bytes())
            manifest = json.loads(archive.read('firmware-manifest.json'))
            self.assertEqual(manifest['image_sha256'], hashlib.sha256(self.disk.read_bytes()).hexdigest())
            self.assertEqual(manifest['board_config'], self.board.name)
            self.assertEqual(manifest['boot_medium'], 'emmc')
        checksum, name = self.output.with_suffix('.zip.sha256').read_text().split()
        self.assertEqual(name, 'firmware.zip')
        self.assertEqual(checksum, hashlib.sha256(self.output.read_bytes()).hexdigest())

    def test_sd_configuration_is_not_packaged_as_emmc(self):
        self.board.write_text('export RK_BOOT_MEDIUM=sd_card\n')
        with self.assertRaisesRegex(ValueError, 'eMMC'):
            self.package()

    def test_requires_matching_loader_instead_of_a_fallback(self):
        self.loader.write_bytes(b'not a Rockchip loader')
        with self.assertRaisesRegex(ValueError, 'loader'):
            self.package()

    def test_rejects_truncated_or_damaged_gpt_images(self):
        for change in ('truncate', 'header', 'table'):
            with self.subTest(change=change):
                image = disk_image()
                if change == 'truncate':
                    image = image[:-512]
                elif change == 'header':
                    image[512 + 40] ^= 1
                else:
                    image[1024] ^= 1
                self.disk.write_bytes(image)
                with self.assertRaises(ValueError):
                    self.package()

    def test_github_wrapper_has_one_discoverable_firmware_zip(self):
        self.package()
        wrapper = self.output.parent / 'github-artifact.zip'
        with zipfile.ZipFile(wrapper, 'w') as archive:
            archive.write(self.output, 'firmware.zip')
            archive.writestr('openhd-base.img.xz', b'not the USB payload')
        with zipfile.ZipFile(wrapper) as archive:
            self.assertEqual([n for n in archive.namelist() if n.endswith('firmware.zip')], ['firmware.zip'])


if __name__ == '__main__':
    unittest.main()
