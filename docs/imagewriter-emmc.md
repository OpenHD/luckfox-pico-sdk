# eMMC images in OpenHD ImageWriter

Pico Ultra, Ultra W and Zero are eMMC targets. Their base-image artifacts
contain `firmware.zip` for ImageWriter's Rockchip USB flashing workflow.
Select that ZIP, or select the whole GitHub artifact ZIP; ImageWriter discovers
the nested `firmware.zip` automatically.

The firmware ZIP contains the matching SDK `download.bin` loader, `.env.txt`
flash metadata, and `disk.img`. Its flash plan writes the complete GPT disk
image at LBA zero, preserving both partition tables, bootloader data, and all
filesystems. The flash-plan metadata is separate from the device's original
boot environment embedded in the disk image. This avoids losing the GPT when
only individual filesystem images are written to a blank eMMC.

The accompanying `.img.xz` is the raw disk image for disk/card writers. It
cannot be used as a partition firmware ZIP in the Rockchip USB page.
SD-card targets retain their SD image format.

The manifest records the board configuration, SDK commit, image checksum and
loader checksum. Packaging rejects SD configurations, missing loaders and
incomplete GPT disk images. A successful build/package check does not prove a
physical eMMC flash or boot.
