#!/usr/bin/env python3
"""Verify and record the applications actually installed in a Pico image."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tarfile

_spec = importlib.util.spec_from_file_location('pico_package', Path(__file__).with_name('package-pico-update.py'))
_package = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_package)


def inspect(root, update, target, commits):
    root = root.resolve()
    if not re.fullmatch(r'luckfox-pico-[a-z0-9-]+', target):
        raise ValueError('Invalid Pico target')
    if any(not re.fullmatch('[0-9a-f]{40}', value) for value in commits.values()):
        raise ValueError('Complete source commits are required')
    with tarfile.open(update, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('manifest.json'))
    if manifest['source_commits'] != {key: commits[key] for key in ('openhd', 'sysutils')}:
        raise ValueError('Application update sources differ from the image sources')
    if (root / 'etc/openhd-pico-base-id').read_text().strip() != manifest['base_id']:
        raise ValueError('Application update base identity differs from the image')
    for name, expected in manifest['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid component file path')
        path = root / relative
        # The paired update normalizes libraries to usr/lib; the base rootfs
        # may keep the libc/toolchain libraries in lib instead.
        if not path.exists() and not path.is_symlink() and relative.parent == Path('usr/lib'):
            path = root / 'lib' / relative.name
        if hashlib.sha256(_package.target_file(root, path).read_bytes()).hexdigest() != expected:
            raise ValueError('Image component differs from verified payload: ' + name)
    required = ('usr/bin/openhd', 'usr/bin/openhd_sys_utils')
    for name in required:
        if name not in manifest['files'] or not (root / name).stat().st_mode & 0o111:
            raise ValueError('Missing executable application: ' + name)
    for name in ('S97openhd-slots', 'S98openhd-sysutils', 'S99openhd'):
        if not (root / 'etc/init.d' / name).is_file():
            raise ValueError('Missing application startup: ' + name)
    if b'Devourer identified' not in (root / 'usr/bin/openhd').read_bytes():
        raise ValueError('OpenHD does not contain Devourer radio discovery')
    for name in ('lib/modprobe.d/openhd-devourer-eu.conf',
                 'lib/udev/rules.d/70-openhd-devourer-eu.rules',
                 'usr/local/share/OpenHD/SysUtils/wifi_cards.json'):
        if not (root / name).is_file():
            raise ValueError('Missing SysUtils radio configuration: ' + name)
    for path in root.rglob('*'):
        if 'webui' in path.name.lower():
            raise ValueError('WebUI must not be installed in Pico images: ' + str(path))
        if re.search(r'(?:88xxau|8812au|88x2(?:bu|cu|eu)|8812eu|8822eu|8852bu).*\.ko(?:\.|$)',
                     path.name, re.I):
            raise ValueError('Legacy broadcast driver conflicts with Devourer: ' + str(path))
    return dict(schema=1, platform='luckfox-pico', target=target, webui=False,
                devourer=True, source_commits=commits, base_id=manifest['base_id'],
                runtime_files=manifest['files'])


def record(root, image, update, output, target, commits):
    manifest = inspect(root, update, target, commits)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    destination = root / 'etc/openhd-image-components.json'
    destination.write_bytes(output.read_bytes())
    # The vendor build has already generated rootfs.img. Put the same manifest
    # into that ext4 image and read it back before assembling the GPT disk.
    subprocess.run(['debugfs', '-w', '-R',
                    f'write "{output.resolve()}" /etc/openhd-image-components.json', str(image)], check=True)
    actual = subprocess.check_output(['debugfs', '-R',
                                    'cat /etc/openhd-image-components.json', str(image)])
    if actual != output.read_bytes():
        raise ValueError('Component manifest was not embedded in the root filesystem')
    print('Verified OpenHD, SysUtils, runtime dependency payload and Devourer; WebUI absent')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rootfs', type=Path)
    parser.add_argument('image', type=Path)
    parser.add_argument('update', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--target', required=True)
    for component in ('sdk', 'openhd', 'sysutils', 'devourer'):
        parser.add_argument('--' + component + '-commit', required=True)
    args = parser.parse_args()
    record(args.rootfs, args.image, args.update, args.output, args.target,
           {name: getattr(args, name + '_commit') for name in ('sdk', 'openhd', 'sysutils', 'devourer')})
