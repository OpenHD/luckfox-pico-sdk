#!/usr/bin/env python3
"""Check the resolved kernel and rootfs needed for Pico maintenance access."""
import argparse
import os
from pathlib import Path
import re
import subprocess

REQUIRED = (
    'CONFIG_USB', 'CONFIG_USB_DWC3', 'CONFIG_USB_DWC3_DUAL_ROLE',
    'CONFIG_USB_XHCI_HCD', 'CONFIG_USB_XHCI_PLATFORM',
    'CONFIG_USB_GADGET', 'CONFIG_CONFIGFS_FS', 'CONFIG_USB_CONFIGFS',
    'CONFIG_USB_CONFIGFS_F_FS', 'CONFIG_USB_CONFIGFS_RNDIS',
)


def check(kernel_config, rootfs, dtb=None):
    settings = set(kernel_config.read_text().splitlines())
    missing = [symbol for symbol in REQUIRED if symbol + '=y' not in settings]
    if missing:
        raise ValueError('USB maintenance support missing from resolved kernel: ' + ', '.join(missing))
    for name in ('usr/bin/adbd', 'etc/init.d/S50usbdevice'):
        path = rootfs / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError('Missing executable USB maintenance component: ' + name)
    interfaces = (rootfs / 'etc/network/interfaces').read_text()
    if not re.search(r'^auto\s+eth0\s*$', interfaces, re.M) or not re.search(
            r'^iface\s+eth0\s+inet\s+dhcp\s*$', interfaces, re.M):
        raise ValueError('Ethernet maintenance DHCP is missing from the base rootfs')
    if dtb is not None:
        mode = subprocess.check_output(
            ['fdtget', str(dtb), '/usbdrd/usb@ffb00000', 'dr_mode'], text=True).strip()
        if mode != 'host':
            raise ValueError('USB broadcast radio requires host mode; built DTB uses ' + mode)
    print('Verified built-in DWC3 host/device, ADB FunctionFS, RNDIS, executable ADB startup and Ethernet DHCP')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel_config', type=Path)
    parser.add_argument('rootfs', type=Path)
    parser.add_argument('--dtb', type=Path, required=True)
    args = parser.parse_args()
    check(args.kernel_config, args.rootfs, args.dtb)
