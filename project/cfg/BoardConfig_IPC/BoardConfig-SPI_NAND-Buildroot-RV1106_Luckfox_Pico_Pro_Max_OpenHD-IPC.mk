#!/bin/bash
# Native OpenHD NAND image for Pico Pro (RV1106G2) and Max (RV1106G3).
# Keep the proven 120 MiB minimal partition layout and provisioning geometry.
# The remaining space on the 256 MiB NAND is deliberately unallocated.
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/BoardConfig-SPI_NAND-Buildroot-RV1103_Luckfox_Pico_Mini_OpenHD-IPC.mk"
export LF_ORIGIN_BOARD_CONFIG=BoardConfig-SPI_NAND-Buildroot-RV1106_Luckfox_Pico_Pro_Max_OpenHD-IPC.mk
export RK_KERNEL_DTS=rv1106g-luckfox-pico-pro-max.dts
export RK_BOOT_MEDIUM=spi_nand
