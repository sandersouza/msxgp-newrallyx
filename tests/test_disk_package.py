"""Synthetic payloads only: disk packaging must never corrupt bank data."""
import importlib.util
import unittest
from pathlib import Path


class DiskPackageTests(unittest.TestCase):
    def module(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/disk_package.py'
        self.assertTrue(path.is_file(), 'disk package builder is missing')
        spec = importlib.util.spec_from_file_location('disk_package', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_bank_codec_preserves_literal_and_overlapping_match_bytes(self):
        module = self.module()
        for data in (bytes(16384), bytes(range(256))*64,
                     (b'ABACA'*3277)[:16384]):
            packed = module.compress_bank(data)
            self.assertEqual(module.decompress_bank(packed), data)
            self.assertLess(len(packed), len(data))

    def test_malformed_distance_and_truncated_stream_are_rejected(self):
        module = self.module()
        for data in (b'\x80\x01\x00', b'\x04AB', b'\x80', b''):
            with self.assertRaises(ValueError):
                module.decompress_bank(data)

    def test_only_authored_bank_instructions_are_changed(self):
        module = self.module()
        source = '    ld ($7000),a ; switch\n    db $32,0,$70\n'
        self.assertEqual(module.mapper_source(source),
                         '    out ($fe),a ; switch\n    db $32,0,$70\n')


if __name__ == '__main__':
    unittest.main()
