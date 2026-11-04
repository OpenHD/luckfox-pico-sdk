#!/usr/bin/env python3
"""Publish an application-free NAND seed and immutable board partitions."""
import argparse
import json
from pathlib import Path
import tarfile
import zipfile
from pico_nand import TARGET, FILES, PARTITIONS, CAPACITY, PAGE, PEB, check_images, check_root, check_boot, digest, make_rootfs


def package(root, images, board, output, commit, kernel_config):
    check_root(root)
    check_images(images)
    check_boot(images / 'boot.img')
    make_rootfs(root, images / 'rootfs.img')
    config = kernel_config.read_text().splitlines()
    for flag in ('MTD_SPI_NAND', 'SPI_ROCKCHIP_SFC', 'MTD_UBI', 'UBIFS_FS'):
        if 'CONFIG_' + flag + '=y' not in config:
            raise ValueError('NAND support missing from built kernel: ' + flag)
    output.mkdir(parents=True, exist_ok=True)
    prefix = 'openhd-base-' + TARGET
    seed = output / (prefix + '.rootfs.tar.xz')
    # devtmpfs supplies /dev at boot; avoid device nodes in the reusable seed.
    def seed_filter(info):
        if not (info.isdir() or info.isfile() or info.issym() or info.islnk()):
            return None
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        return info
    with tarfile.open(seed, 'w:xz') as archive:
        archive.add(root, arcname='.', filter=seed_filter)
    firmware = output / (prefix + '-firmware.zip')
    with zipfile.ZipFile(firmware, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in FILES:
            archive.write(images / name, name)
    manifest = dict(schema=2, type='openhd-base-image', target=TARGET,
        name='Luckfox Pico Mini B NAND', boot_medium='spi_nand', board_config=board.resolve().name,
        architecture='arm', runtime_abi='armv7a-hardfloat-uclibc', sdk_commit=commit,
        image=firmware.name, sha256=digest(firmware), rootfs_seed=seed.name,
        rootfs_seed_sha256=digest(seed), usb_role='host', usb_role_switching=True,
        provisioning='ubi-static-rootfs-v1', application_slots=False,
        openhd_preinstalled=False, nand_capacity=CAPACITY, nand_page_size=PAGE,
        nand_eraseblock_size=PEB, partitions={n: dict(offset=o, size=s) for n, (o, s) in PARTITIONS.items()},
        board_files={name: digest(images / name) for name in FILES if name != 'rootfs.img'})
    metadata = output / (prefix + '.json')
    metadata.write_text(json.dumps(manifest, indent=2) + '\n')
    (output / (prefix + '.sha256')).write_text(''.join(
        digest(p) + '  ' + p.name + '\n' for p in (firmware, seed, metadata)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'images', 'board', 'output', 'kernel-config'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--sdk-commit', required=True)
    a = p.parse_args()
    package(a.root, a.images, a.board, a.output, a.sdk_commit, a.kernel_config)
