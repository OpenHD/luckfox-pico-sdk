#!/bin/bash
set -euo pipefail
root="${RK_PROJECT_PACKAGE_ROOTFS_DIR:?}"
sdk="$(cd "$(dirname "$0")/../../.." && pwd)"
install -Dm755 "$sdk/sysdrv/tools/board/android-tools/S50usbdevice" "$root/etc/init.d/S50usbdevice"
install -Dm755 "$(dirname "$0")/overlay/overlay-luckfox-buildroot-init/etc/init.d/S50sshd" "$root/etc/init.d/S50sshd"
mkdir -p "$root/userdata" "$root/oem" "$root/usr/local/share/OpenHD/SysUtils"
ln -sfn /userdata/Config "$root/Config"
ln -sfn /tmp/Videos "$root/Videos"

install -Dm755 "$(dirname "$0")/overlay/overlay-openhd-pico-nand/etc/init.d/S25openhd-nand" "$root/etc/init.d/S25openhd-nand"
