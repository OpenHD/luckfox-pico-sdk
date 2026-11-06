import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class UsbGadgetStartTest(unittest.TestCase):
    def test_device_role_starts_missing_gadget_and_preserves_bound_gadget(self):
        repo = Path(__file__).resolve().parents[2]
        script = (repo / 'sysdrv/tools/board/android-tools/openhd-pico-usb-role').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('sys/kernel/debug/usb/controller', 'sys/kernel/config/usb_gadget/rockchip', 'run/openhd', 'etc/init.d'):
                (root / name).mkdir(parents=True)
            (root / 'sys/kernel/debug/usb/controller/mode').write_text('device\n')
            udc = root / 'sys/kernel/config/usb_gadget/rockchip/UDC'
            udc.write_text('')
            (root / 'mounts').write_text('debugfs ' + str(root / 'sys/kernel/debug') + ' debugfs rw 0 0\n')
            log = root / 'calls'
            service = root / 'etc/init.d/S50usbdevice'
            service.write_text('#!/bin/sh\necho "$1" >> "' + str(log) + '"\n')
            service.chmod(0o755)
            script = script.replace('/sys/kernel/', str(root / 'sys/kernel') + '/')
            script = script.replace('/run/openhd', str(root / 'run/openhd'))
            script = script.replace('/etc/init.d/S50usbdevice', str(service)).replace('/proc/mounts', str(root / 'mounts'))
            path = root / 'role.sh'; path.write_text(script)
            subprocess.run(['sh', str(path), 'device'], check=True)
            self.assertEqual(log.read_text(), 'start\n')
            udc.write_text('ffb00000.usb\n')
            subprocess.run(['sh', str(path), 'device'], check=True)
            self.assertEqual(log.read_text(), 'start\n')


if __name__ == '__main__':
    unittest.main()
