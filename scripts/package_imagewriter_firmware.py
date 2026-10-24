#!/usr/bin/env python3
"""Wrap an eMMC GPT disk image for ImageWriter's existing Rockchip USB path."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile
import zlib


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def check_disk(image):
    size = image.stat().st_size
    if size % 512 or size < 34 * 512 or size // 512 > 0xffffffff:
        raise ValueError('Disk image must contain complete addressable sectors')
    with image.open('rb') as stream:
        first = stream.read(1024)
        if first[510:512] != b'\x55\xaa' or first[512:520] != b'EFI PART':
            raise ValueError('Expected a complete GPT disk image')
        header = bytearray(first[512:])
        header_size = struct.unpack_from('<I', header, 12)[0]
        if not 92 <= header_size <= 512:
            raise ValueError('Invalid GPT header size')
        expected = struct.unpack_from('<I', header, 16)[0]
        struct.pack_into('<I', header, 16, 0)
        if zlib.crc32(header[:header_size]) != expected:
            raise ValueError('Invalid GPT header checksum')
        if struct.unpack_from('<Q', header, 32)[0] != size // 512 - 1:
            raise ValueError('Disk image does not include its backup GPT')
        lba, count, entry_size, expected = struct.unpack_from('<QIII', header, 72)
        if count == 0 or entry_size < 128 or count * entry_size > 1024 * 1024:
            raise ValueError('Invalid GPT partition inventory')
        stream.seek(lba * 512)
        entries = stream.read(count * entry_size)
        if len(entries) != count * entry_size or zlib.crc32(entries) != expected:
            raise ValueError('Invalid GPT partition checksum')
        stream.seek(size - 512)
        if stream.read(8) != b'EFI PART':
            raise ValueError('Missing backup GPT header')
    return size


def package(image, loader, board_config, output, sdk_commit):
    board_config = board_config.resolve()
    board = board_config.read_text()
    if not re.search(r'^export RK_BOOT_MEDIUM=[\"\']?emmc[\"\']?\s*$', board, re.M):
        raise ValueError('Rockchip USB firmware packages require an eMMC board configuration')
    if not re.fullmatch('[0-9a-f]{40}', sdk_commit):
        raise ValueError('A complete SDK commit is required')
    with loader.open('rb') as stream:
        if stream.read(4) != b'LDR ' or loader.stat().st_size <= 4:
            raise ValueError('Missing or invalid matching SDK download.bin loader')
    size = check_disk(image)
    manifest = dict(schema=1, type='rockchip-full-disk', boot_medium='emmc',
                    board_config=board_config.name, sdk_commit=sdk_commit,
                    image='disk.img', image_size=size, image_sha256=digest(image),
                    loader='download.bin', loader_sha256=digest(loader))
    # This is a USB flash plan, not the boot environment inside disk.img.
    # A single LBA-zero target preserves both GPTs and all boot/config regions.
    environment = ('# ImageWriter full-disk USB flash plan\n'
                   f'blkdevparts=mmcblk0:{size}@0(disk)\n')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        archive.writestr('.env.txt', environment)
        archive.write(image, 'disk.img')
        archive.write(loader, 'download.bin')
        archive.writestr('firmware-manifest.json', json.dumps(manifest, indent=2) + '\n')
    output.with_suffix(output.suffix + '.sha256').write_text(digest(output) + '  ' + output.name + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--loader', required=True, type=Path)
    parser.add_argument('--board-config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sdk-commit', required=True)
    args = parser.parse_args()
    package(args.image, args.loader, args.board_config, args.output, args.sdk_commit)
