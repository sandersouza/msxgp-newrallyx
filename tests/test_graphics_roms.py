"""Synthetic inventories exercise validation without original game data."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.graphics import roms


class RomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'sample.rom'
        self.path.write_bytes(b'123456789')
        self.metadata = {'roms': [{'name': 'sample.rom', 'size': 9,
            'crc32': 'cbf43926', 'sha1': 'f7c3bc1d808e04732adf679965ccc34ca7ae3441'}]}

    def test_verified_bytes_survive_source_change_and_extras(self):
        (self.root / 'unrelated').write_bytes(b'extra')
        buffers = roms.validate_roms(self.root, self.metadata)
        self.path.write_bytes(b'987654321')
        self.assertEqual(buffers, {'sample.rom': b'123456789'})
        self.assertEqual(roms.input_records(buffers), self.metadata['roms'])

    def test_missing_size_checksum_directory_and_symlink_fail(self):
        for kind in ('missing', 'size', 'checksum', 'directory', 'symlink'):
            with self.subTest(kind=kind):
                if self.path.is_dir():
                    self.path.rmdir()
                elif self.path.exists() or self.path.is_symlink():
                    self.path.unlink()
                if kind == 'size':
                    self.path.write_bytes(b'x')
                elif kind == 'checksum':
                    self.path.write_bytes(b'987654321')
                elif kind == 'directory':
                    self.path.mkdir()
                elif kind == 'symlink':
                    other = self.root / 'other'
                    other.write_bytes(b'123456789')
                    self.path.symlink_to(other)
                with self.assertRaisesRegex(ValueError, 'sample.rom'):
                    roms.validate_roms(self.root, self.metadata)

    def test_unsafe_or_malformed_metadata_is_rejected(self):
        for field, value in [('name', '../sample.rom'), ('size', -1),
                             ('crc32', 'invalid'), ('sha1', 'invalid')]:
            with self.subTest(field=field):
                record = dict(self.metadata['roms'][0], **{field: value})
                with self.assertRaises(ValueError):
                    roms.validate_roms(self.root, {'roms': [record]})

    def test_bundled_inventory_has_full_set_and_source_pin(self):
        metadata = roms.load_metadata()
        self.assertEqual(metadata['set'], 'nrallyx')
        self.assertEqual(len(metadata['roms']), 13)
        self.assertEqual(metadata['source']['commit'],
                         'f34f02505e32c1993c6a782b6814232cbfc74e36')
        for entry in metadata['roms']:
            self.assertEqual(sum(x['size'] for x in entry['loads']), entry['size'])

    def test_malformed_inventory_and_load_segments_fail_cleanly(self):
        for metadata in (None, [], {'roms':[None]},
                         {'roms':[dict(self.metadata['roms'][0], region=None, loads=[])]},
                         {'roms':[dict(self.metadata['roms'][0], region='gfx1',
                            loads=[dict(file_offset=-1,region_offset=0,size=9)])]}):
            with self.subTest(metadata=metadata):
                with self.assertRaises(ValueError):
                    roms.validate_roms(self.root,metadata)


if __name__ == '__main__':
    unittest.main()
