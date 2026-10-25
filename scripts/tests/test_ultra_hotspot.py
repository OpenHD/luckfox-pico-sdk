import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

HELPER = Path(__file__).resolve().parents[2] / 'project/cfg/BoardConfig_IPC/overlay/overlay-luckfox-buildroot-init/usr/sbin/openhd-pico-hotspot'
loader = importlib.machinery.SourceFileLoader('hotspot', str(HELPER))
spec = importlib.util.spec_from_loader(loader.name, loader)
hotspot = importlib.util.module_from_spec(spec)
loader.exec_module(hotspot)

class UltraHotspotTests(unittest.TestCase):
    def test_only_ultra_models(self):
        for model in ('Luckfox Pico Ultra', 'Luckfox Pico Ultra W'):
            self.assertTrue(hotspot.allowed_board(model + '\0'))
        for model in ('Luckfox Pico Zero', 'Luckfox Pico Pro Max', 'Luckfox Pico Plus', '', 'Raspberry Pi'):
            self.assertFalse(hotspot.allowed_board(model))

    def test_rejects_ambiguous_or_unsafe_interface(self):
        self.assertEqual(hotspot.interface_from_config('interface=wlan0\nssid2=4142\n'), 'wlan0')
        for content in ('interface=wlan0;reboot', 'interface=../../eth0', 'interface=wlan0\ninterface=eth0', ''):
            with self.assertRaises(ValueError):
                hotspot.interface_from_config(content)
