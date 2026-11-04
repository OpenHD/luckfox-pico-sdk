"""Shared 128 MiB Pico Mini NAND layout, safe seeds and firmware packaging."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import tarfile
import tempfile
import zipfile
import zlib

TARGET = 'luckfox-pico-mini-nand'
CAPACITY = 128 << 20
PAGE = 2048
PEB = 128 << 10
LEB = PEB - 2 * PAGE
PROVISION_LEBS = 2
PARTITIONS = {
    'env': (0, 256 << 10), 'idblock': (256 << 10, 256 << 10),
    'uboot': (512 << 10, 512 << 10), 'boot': (1 << 20, 8 << 20),
    'oem': (9 << 20, 24 << 20), 'userdata': (33 << 20, 8 << 20),
    'rootfs': (41 << 20, 79 << 20),
}
FILES = tuple(name + '.img' for name in PARTITIONS) + ('download.bin', '.env.txt')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def check_images(images):
    for name, (_, limit) in PARTITIONS.items():
        p = images / (name + '.img')
        if not p.is_file() or not 0 < p.stat().st_size <= limit:
            raise ValueError('Missing or oversized NAND partition: ' + name)
    if sum(size for _, size in PARTITIONS.values()) != 120 << 20:
        raise ValueError('NAND layout must retain 8 MiB outside its partitions')
    for name in ('rootfs', 'oem', 'userdata'):
        p = images / (name + '.img')
        with p.open('rb') as stream:
            magic = stream.read(4)
        if magic != b'UBI#':
            raise ValueError('NAND filesystem is not a UBI image: ' + name)
        # Reserve physical eraseblocks for UBI metadata and bad-block handling.
        allocated = p.stat().st_size
        with p.open('rb') as stream:
            while allocated >= PEB:
                stream.seek(allocated - PEB)
                if stream.read(PEB) != b'\xff' * PEB:
                    break
                allocated -= PEB
        if allocated > PARTITIONS[name][1] - 24 * PEB:
            raise ValueError('NAND image leaves insufficient UBI reserve: ' + name)


def check_root(root, applications=False):
    for name in ('usr/sbin/openhd-pico-usb-role', 'etc/init.d/S25openhd-pico-usb'):
        path = root / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError('Missing selectable Pico USB role startup: ' + name)
    if list(root.rglob('libgst*.so*')) or list(root.glob('usr/bin/python*')):
        raise ValueError('Minimal NAND filesystem must not contain GStreamer or Python')
    if (root / 'etc/init.d/S97openhd-slots').exists() or (root / 'usr/sbin/openhd-pico-update').exists():
        raise ValueError('Application slots are not supported by the NAND layout')
    mount = root / 'etc/init.d/S20linkmount'
    if not mount.is_file() or '/sys/class/mtd/mtd[0-9]*' not in mount.read_text():
        raise ValueError('NAND OEM/userdata partition discovery is missing')
    for name in ('usr/bin/openhd', 'usr/bin/openhd_sys_utils'):
        if (root / name).is_file() != applications:
            raise ValueError('Unexpected application presence in NAND rootfs: ' + name)


def check_boot(image):
    with tempfile.TemporaryDirectory() as directory:
        dtb = Path(directory) / 'boot.dtb'
        subprocess.run(['dumpimage', '-T', 'flat_dt', '-p', '0', '-o', str(dtb), str(image)], check=True)
        mode = subprocess.check_output(['fdtget', '-t', 's', str(dtb),
            '/usbdrd/usb@ffb00000', 'dr_mode'], text=True).strip()
        if mode != 'otg':
            raise ValueError('NAND boot image must support selectable host/device USB roles')


def extract_seed(archive, destination):
    """Create links last, so a tar member cannot write through a target symlink."""
    destination.mkdir(parents=True, exist_ok=True)
    def safe(name):
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('NAND seed path escapes root')
        result = destination.joinpath(*path.parts)
        for parent in result.parents:
            if parent == destination:
                break
            if parent.is_symlink():
                raise ValueError('NAND seed path traverses a symlink')
        return result
    with tarfile.open(archive, 'r:*') as tar:
        members = tar.getmembers()
        for member in members:
            safe(member.name)
            if not (member.isdir() or member.isfile() or member.issym() or member.islnk()):
                raise ValueError('Special files are not allowed in NAND rootfs seeds')
        for member in members:
            if not (member.isdir() or member.isfile()):
                continue
            target = safe(member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open('wb') as stream:
                    shutil.copyfileobj(source, stream)
            target.chmod(member.mode & 0o7777)
        for member in members:
            if member.islnk():
                target, source = safe(member.name), safe(member.linkname)
                if not source.is_file() or source.is_symlink():
                    raise ValueError('Invalid NAND seed hardlink')
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(source, target)
        for member in members:
            if member.issym():
                target = safe(member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(member.linkname)


def make_rootfs(root, output):
    size = PARTITIONS['rootfs'][1]
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        ubifs = work / 'rootfs.ubifs'
        subprocess.run(['mkfs.ubifs', '-F', '-U', '-x', 'lzo', '-m', str(PAGE),
                        '-e', str(LEB), '-c', str(size // LEB), '-r', str(root),
                        '-o', str(ubifs)], check=True)
        config = work / 'ubinize.cfg'
        capsule = work / 'provision.bin'
        body = struct.pack('>I', 0)
        capsule.write_bytes(b'OHDCFG1\0' + struct.pack('>II', len(body), zlib.crc32(body)) + body)
        # Explicit dynamic volume size leaves room for the static configuration
        # volume and 24 eraseblocks of UBI metadata/bad-block reserve.
        root_lebs = size // PEB - 24 - PROVISION_LEBS
        config.write_text('[rootfs]\nmode=ubi\nimage=' + str(ubifs) +
                          '\nvol_id=0\nvol_type=dynamic\nvol_name=rootfs\nvol_flags=autoresize\nvol_size=' + str(root_lebs * LEB) +
                          '\n[provision]\nmode=ubi\nimage=' + str(capsule) +
                          '\nvol_id=1\nvol_type=static\nvol_name=openhd-provision\nvol_size=' + str(PROVISION_LEBS * LEB) + '\n')
        subprocess.run(['ubinize', '-o', str(output), '-m', str(PAGE),
                        '-p', str(PEB), str(config)], check=True)
        with output.open('ab') as stream:
            stream.write(b'\xff' * (size - output.stat().st_size))


def package_firmware(images, output, tools):
    check_images(images)
    # Keep the vendor container format: the environment supplies NAND offsets.
    package = images / 'package-file'
    package.write_text('bootloader\tdownload.bin\n' +
                       ''.join(name + '\t' + name + '.img\n' for name in PARTITIONS) +
                       'package-file\tpackage-file\n')
    temporary = images / 'update_tmp.img'
    try:
        subprocess.run([str(tools / 'afptool'), '-pack', str(images), str(temporary)], check=True)
        subprocess.run([str(tools / 'rkImageMaker'), '-RK1106', str(images / 'download.bin'),
                        str(temporary), str(images / 'update.img'), '-os_type:androidos'], check=True)
        if (images / 'update.img').read_bytes()[:4] != b'RKFW':
            raise ValueError('Invalid Rockchip firmware container')
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in (*FILES, 'update.img'):
                archive.write(images / name, name)
    finally:
        temporary.unlink(missing_ok=True)
        package.unlink(missing_ok=True)
