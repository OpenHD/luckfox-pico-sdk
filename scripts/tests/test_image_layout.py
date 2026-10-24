import importlib.util
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('image_layout', REPO / 'scripts/check_image_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class ImageLayoutTest(unittest.TestCase):
    def setUp(self):
        self.image = (REPO / 'genimage.cfg').read_text()
        self.boards = REPO / 'project/cfg/BoardConfig_IPC'
        self.reference = (self.boards /
            'BoardConfig-EMMC-Buildroot-RV1106_Luckfox_Pico_Ultra-IPC.mk').read_text()

    def test_every_ci_image_board_matches_packaging_layout(self):
        workflow = (REPO / '.github/workflows/build.yml').read_text()
        boards = set(re.findall(r'BoardConfig-[A-Za-z0-9_\-]+\.mk', workflow))
        self.assertEqual(len(boards), 6)
        for board in sorted(boards):
            with self.subTest(board=board):
                layout.check_layout((self.boards / board).read_text(), self.image)

    def test_reject_legacy_emmc_environment_region(self):
        legacy = self.reference.replace('15K@17K(env)', '32K(env)')
        with self.assertRaisesRegex(ValueError, 'env: board offset'):
            layout.check_layout(legacy, self.image)

    def test_reject_partition_size_drift(self):
        for changed in ('512M(oem)', '1G(rootfs)', '256M(ohd_config)'):
            with self.subTest(partition=changed):
                mismatch = self.reference.replace(changed, '64M' + changed[changed.index('('):])
                with self.assertRaisesRegex(ValueError, 'board size'):
                    layout.check_layout(mismatch, self.image)

    def test_reject_missing_shared_config_partition(self):
        mismatch = self.reference.replace(',256M(ohd_config)', '')
        with self.assertRaises(ValueError):
            layout.check_layout(mismatch, self.image)


if __name__ == '__main__':
    unittest.main()
