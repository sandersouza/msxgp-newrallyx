"""Verify persisted assets reproduce actual cartridge bytes and preserve edits."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from src.toolchain.msx.resource_assets import publish


class ResourceAssetsTests(unittest.TestCase):
    def test_exact_linked_offsets_and_preserve_modified_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);rom=root/'game.rom'
            data=bytes(16384)+bytes([17])*16384+bytes([39])*16384
            rom.write_bytes(data)
            target=publish(root,rom)
            manifest=json.loads((target/'manifest.json').read_text())
            self.assertEqual(manifest['rom_sha256'],hashlib.sha256(data).hexdigest())
            self.assertFalse((target/'bank-000.bin').exists())
            for entry in manifest['resources']:
                self.assertEqual((target/entry['path']).read_bytes(),data[entry['rom_offset']:entry['rom_offset']+entry['bytes']])
            self.assertEqual(publish(root,rom),target)
            changed=target/'bank-001.bin';changed.write_bytes(b'keep')
            with self.assertRaises(ValueError):publish(root,rom)
            self.assertEqual(changed.read_bytes(),b'keep')

    def test_invalid_rom_and_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);rom=root/'game.rom';rom.write_bytes(b'short')
            with self.assertRaises(ValueError):publish(root,rom)
            with self.assertRaises(ValueError):publish(root,rom,'../escape')
            rom.write_bytes(bytes(2097152+16384))
            with self.assertRaises(ValueError):publish(root,rom)
