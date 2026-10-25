"""Exercise boot-medium selection from the generated mount script."""
from pathlib import Path
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[2]


class BootDiskTest(unittest.TestCase):
    def test_generated_mount_script_selects_its_boot_medium(self):
        source = (REPO / 'project/build.sh').read_text()
        function = source.split('\nlinkdev() {\n', 1)[1].split('    BYNAME=', 1)[0]
        script = 'linkdev() {\n' + function + '\nprintf "%s" "$DEVBASE"\n}\n'
        for medium, argument, expected in (
            ('emmc', '', '/dev/mmcblk0'),
            ('sd_card', '', '/dev/mmcblk1'),
            ('emmc', '/dev/mmcblk2', '/dev/mmcblk2'),
            ('spi_nand', '', ''),
        ):
            with self.subTest(medium=medium, argument=argument):
                result = subprocess.run(
                    ['sh', '-c', script + 'bootmedium="$1"; linkdev "$2"',
                     'boot-disk-check', medium, argument],
                    capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout, expected)


if __name__ == '__main__':
    unittest.main()
