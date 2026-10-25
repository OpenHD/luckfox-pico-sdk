# RV1106 Pico Pro/Max SDR on SD card

The image workflow builds OpenHD `openhd-3.0` and SysUtils `dev-release`
from their current branch heads in the same SDK. Their exact commits are
recorded in the paired update manifest. The checked-out sources are passed
to Buildroot; there is no second independent source download in CI.

Broadcast USB radios use Devourer. The old AU/BU/EU kernel drivers are neither
built nor loaded. Onboard Wi-Fi and the existing camera configuration remain
in the vendor SDK. SysUtils receives its Wi-Fi database and USB ownership
policy, and the image includes libusb, librtlsdr, ncurses and host Python for
the current OpenHD build.

The six OpenHD image targets use USB **host mode** for Devourer broadcast
radios, including Ultra W and Zero. Connect the radio with the appropriate
host adapter and power supply. Ethernet DHCP, SSH and network ADB remain the
maintenance path. The same connector cannot simultaneously operate as an
ADB/RNDIS peripheral and a USB radio host. Onboard SDIO Wi-Fi is independent.

**Ultra/Ultra W USB-A:** the board's hardware switch disconnects USB-A data
when USB-C provides power. Power the board through PoE or its supported GPIO
power input and disconnect USB-C to use a radio in USB-A. Software host mode
does not override this switch. See [Luckfox's USB guide](https://wiki.luckfox.com/Luckfox-Pico-Ultra/USB/).

SDK CI verifies the resolved DTB is in host mode. ImageBuilder verifies the
boot partition again and requires the corrected VENC packet-address backend.
Old peripheral-mode bases must be rebuilt before application assembly.

Changing applications alone does not update this device-tree setting: install
a new board-specific firmware image to switch an existing peripheral image.

## Ultra onboard hotspot

Only Ultra-family Pico boards offer the hotspot controls; the onboard SDIO
radio is reserved for this purpose. USB Devourer radios cannot be selected as
hotspot interfaces. On Buildroot, OpenHD starts hostapd and dnsmasq directly,
without NetworkManager. It reports enabled only after hostapd reaches ENABLED
and DHCP is running. Clients use `192.168.3.1`; the default password remains
`openhdopenhd`. The configured SSID/password and on/off setting are preserved.

## Application updates

`OpenHD-Pico-RV1106.pico-ohd` contains OpenHD, SysUtils and their transitive
ELF runtime libraries. The factory pair stays in `/usr/bin`; application
slots `a` and `b` live on the mounted `/userdata` partition. Both init scripts
use the same selection in `/run/openhd/current` and its library directory.

On the Pico, as root:

```sh
openhd-pico-update status
openhd-pico-update install /Config/OpenHD-Pico-RV1106.pico-ohd
reboot
```

The next boot tries the new pair. After checking SysUtils, telemetry, radio
discovery and the required live functions, accept it:

```sh
openhd-pico-update confirm
```

If the trial is not confirmed, the following reboot selects the previously
accepted pair. The first trial falls back to the factory applications.
For an explicit rollback, run `openhd-pico-update rollback` and reboot.
Service restarts alone do not change the selection.

Installation checks platform, ARM ELF headers, executable permissions,
the complete file inventory, SHA-256 checksums, available space, and base-image
identity. It rejects path traversal, links, special files and overlapping
updates. Slot files are flushed before atomically recording the pending trial.
An interrupted install leaves the accepted slot selected. Keep trusted copies
of these archives; embedded hashes detect corruption, not publisher identity.

The base identity is the SDK revision plus board/storage identity in CI.
Application rebuilds against that same base can be installed. A changed SDK
requires a new SD image. New runtime data files, GStreamer plugins, services,
kernel modules and shared system configuration remain part of that base.

These are **application A/B slots**, not X21 NAND or full Linux boot slots.
The kernel, bootloader, rootfs and partition table are not updated by this
format. There is no automatic reboot watchdog or QOpenHD/ImageWriter update
integration yet. Do not feed X21 `.ohd`/`.ohd_base` files or the old generic
Luckfox `mtd9` update to this SD image.

## Building and validation

Use a native Linux filesystem, including WSL's Linux disk, for a full clone
and build. A Windows checkout loses case-distinct kernel header names and may
materialize symlinks such as `build.sh` as plain files. The old Wi-Fi
submodules are unnecessary for this image; OpenHD's own recursive submodules,
including the private video-crypto sources, remain required.

For a local Linux build, export absolute `OPENHD_LOCAL_SITE` and
`OPENHD_SYSUTILS_LOCAL_SITE` paths to complete current source checkouts.
Set `OPENHD_PICO_BASE_ID` to the SDK revision plus `-rv1106-pro-max-sd`.
Select lunch options `4`, `0`, `0`, then build media, the image, and run
`finish-ohd.sh`, as shown in the workflow.

Run the update lifecycle tests with:

```sh
python3 -m unittest discover -s scripts/tests -v
```

Tests cover confirmation, both slots, rollback to factory, checksum/base
rejection, unsafe archive paths and links, an interrupted installation, and
transitive library packaging. They do not establish a bootable image or
hardware/RF behavior. Bench-test the built image and two update cycles before
using the rollback mechanism operationally.
