"""Reject device-mode regressions in the six OpenHD board targets."""
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('usb_check', REPO / 'scripts/check_usb_gadget.py')
usb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usb)

class UsbHostTest(unittest.TestCase):
    def test_all_openhd_boards_select_host(self):
        for chip, board in [('rv1103g', 'mini'), ('rv1103g', 'plus'),
                            ('rv1106g', 'pro-max'), ('rv1106g', 'ultra'),
                            ('rv1106g', 'ultra-w'), ('rv1106g', 'zero')]:
            with self.subTest(board=board):
                source = (REPO / 'sysdrv/source/kernel/arch/arm/boot/dts' /
                          (chip + '-luckfox-pico-' + board + '.dts')).read_text()
                block = source.split('&usbdrd_dwc3 {', 1)[1].split('};', 1)[0]
                self.assertEqual(re.findall(r'^\s*dr_mode\s*=\s*"(.*?)";', block, re.M), ['host'])

    def test_built_dtb_rejects_peripheral(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('usr/bin/adbd', 'etc/init.d/S50usbdevice'):
                p = root / name; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('#!/bin/sh\n'); p.chmod(0o755)
            network = root / 'etc/network/interfaces'; network.parent.mkdir(parents=True)
            network.write_text('auto eth0\niface eth0 inet dhcp\n')
            config = root / 'kernel.config'
            config.write_text(''.join(symbol + '=y\n' for symbol in usb.REQUIRED))
            for mode in ('host', 'peripheral'):
                source = root / 'test.dts'; dtb = root / 'test.dtb'
                source.write_text('/dts-v1/; / { usbdrd { usb@ffb00000 { dr_mode = "' + mode + '"; }; }; };')
                subprocess.run(['dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o', str(dtb), str(source)], check=True)
                if mode == 'host':
                    usb.check(config, root, dtb)
                else:
                    with self.assertRaisesRegex(ValueError, 'host mode'):
                        usb.check(config, root, dtb)

if __name__ == '__main__':
    unittest.main()
