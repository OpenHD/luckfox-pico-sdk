# Pico Mini B NAND base

`luckfox-pico-mini-nand` is the 128 MiB Mini **B** NAND target. Mini A has no
onboard NAND. It is separate from the existing `luckfox-pico-mini` SD target.

The board defaults to USB **host** mode for Devourer radios. ImageWriter's
"Enable Ethernet link over USB" option selects device mode for computer video
and telemetry. The DT enables dual-role operation; early boot selects host and
SysUtils applies the provisioned choice before radio detection. Supply power
through the board's supported input and use a suitable USB host adapter. That
connector cannot provide USB Ethernet/ADB while it is a radio host. UART and
MaskROM remain recovery paths. The role helper verifies the selected role.

The minimal Buildroot profile omits GStreamer, Python, samples, GDB and
application update slots. A current paired OpenHD/SysUtils application archive
supplies Devourer, its policy/helpers, native Rockit VI/VENC and RKAIQ libraries.
Only the OpenHD MIS5001 tuning is installed; the application default is H.264
1280x720 at 60 fps. The camera driver retains its high frame rate sensor mode.

The physical partition layout occupies 120 MiB: environment/bootloaders 1 MiB,
boot 8 MiB, OEM 24 MiB, userdata 8 MiB and rootfs 79 MiB. Eight MiB remains
unallocated, in addition to UBI's internal metadata/bad-block reserve. OEM and
userdata are discovered from `/sys/class/mtd`, not GPT, and mounted with UBIFS.
The rootfs UBI image reserves a separate 248 KiB static `openhd-provision`
volume for ImageWriter settings. ImageWriter edits only this volume, preserving
UBIFS/application bytes and both volume tables. SysUtils imports its capsule
once into `/Config` and persists the Ethernet/USB choice across reboots.

## Build a reusable base

Use a Linux filesystem for the checkout (including WSL's Linux disk); Windows
checkouts lose case-distinct kernel headers. Install the dependencies from
`.github/workflows/build.yml`, then select the explicit NAND profile:

```sh
ln -rfs project/cfg/BoardConfig_IPC/BoardConfig-SPI_NAND-Buildroot-RV1103_Luckfox_Pico_Mini_OpenHD-IPC.mk .BoardConfig.mk
./build.sh uboot
./build.sh driver
./build.sh rootfs
./build.sh media
./build.sh firmware
python3 scripts/package_pico_nand_base.py \
  --root output/out/rootfs_uclibc_rv1106 --images output/image \
  --board .BoardConfig.mk --kernel-config sysdrv/source/objs_kernel/.config \
  --sdk-commit "$(git rev-parse HEAD)" --output deploy
```

SDK CI builds this as the seventh board base on push, or explicitly through
`workflow_dispatch` with `target=luckfox-pico-mini-nand`. The default manual
`target=sdk` still builds the reusable cross SDK.

The base artifact contains an application-free rootfs seed, immutable board
partition firmware ZIP, checksums and metadata. ImageBuilder reuses that base,
overlays current native applications, builds a size-checked UBIFS rootfs and
packages `firmware.zip` containing the Rockchip `update.img` and partition files.
No kernel or SDK rebuild is needed for ordinary application updates. A new
base must be published when board support changes. There are no `.pico-ohd`
application slot updates for this small NAND target.

Use a Rockchip NAND flashing tool with the matching `download.bin`/`update.img`.
This is not a raw SD/eMMC disk image. The new partition offsets differ from
stock firmware, so install the complete firmware rather than writing individual
images at stock offsets.

A local NAND prototype was flashed with all seven partition readbacks verified,
booted OpenHD/SysUtils and encoded MIS5001 720p at approximately 58–59 fps using
the native backend. This establishes the size/runtime approach; a host-mode
USB radio/RF test and CI publication are separate validation steps.
