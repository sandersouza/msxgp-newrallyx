"""Behavioral contracts for exact, optional uniform radar source metadata."""
import unittest
from pathlib import Path
import tempfile
from game_radar_source_cache import (BANK_BYTES, PHASE_BANK_FIRST, TABLE_OFFSET,
                                     append_metadata, uniform_source_colors)


class UniformRadarSource(unittest.TestCase):
    def test_only_exact_ff_pattern_and_uniform_nonzero_color_qualify(self):
        # A partial pattern or nonuniform color must retain the original clone.
        patterns = bytes([255])*16 + bytes([255])*7 + bytes([254]) + bytes([255])*16
        colors = bytes([0xaa])*8 + bytes([0])*8 + bytes([0xaa])*8 + bytes([0xaa])*7 + bytes([0xbb]) + bytes([0xbb])*8
        actual = uniform_source_colors(patterns, colors, 5)
        self.assertEqual(actual, bytes([0xaa, 0, 0, 0, 0xbb])+bytes(59))

    def test_phase_metadata_preserves_every_other_bank_byte(self):
        banks = bytearray((PHASE_BANK_FIRST+64)*BANK_BYTES)
        for phase in range(64):
            at = (PHASE_BANK_FIRST+phase)*BANK_BYTES
            banks[at+0x900] = 2
            banks[at+0x100:at+0x110] = b'\xff'*16
            banks[at+0x500:at+0x508] = bytes((phase+1,))*8
            banks[at+0x508:at+0x510] = bytes(range(8))
        original = bytes(banks)
        with tempfile.TemporaryDirectory() as directory:
            result = append_metadata(banks, Path(directory))
        self.assertEqual(bytes(banks), original)
        for phase in range(64):
            at = (PHASE_BANK_FIRST+phase)*BANK_BYTES+TABLE_OFFSET
            self.assertEqual(result[at:at+64], bytes((phase+1,))+bytes(63))
            result[at:at+64] = original[at:at+64]
        self.assertEqual(result, original)

    def test_overlapping_metadata_is_rejected(self):
        banks = bytearray((PHASE_BANK_FIRST+64)*BANK_BYTES)
        banks[PHASE_BANK_FIRST*BANK_BYTES+TABLE_OFFSET] = 0x42
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AssertionError, 'overlaps'):
                append_metadata(banks, Path(directory))


if __name__ == '__main__':
    unittest.main()
