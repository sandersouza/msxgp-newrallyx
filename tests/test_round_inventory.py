"""Synthetic validation of round acquisition; no original program or graphics."""
from types import SimpleNamespace
import unittest

from scripts.msx.round_inventory import analyze


class RoundInventoryTests(unittest.TestCase):
    def setUp(self):
        self.program = bytearray(16384)
        self.video = bytearray(4096)
        self.work = bytearray(2048)
        self.video[0x28f] = 0x30
        self.video[0x2d6] = 0x5c
        self.video[0x1b0] = 2
        self.video[0x992:0x994] = (0x8300).to_bytes(2, 'little')
        self.video[0x996:0x998] = (0x8340).to_bytes(2, 'little')
        for i, kind in enumerate([1]*8+[4, 2]):
            self.video[0x300+i*2:0x302+i*2] = (0x9800+i).to_bytes(2, 'little')
            self.work[i] = kind
        self.assets = SimpleNamespace(pixels={'tiles': bytes(256*64)},
                                      palette={'lookup': [0]*256, 'rgb': [[0, 0, 0]]})

    def analyze(self):
        return analyze(self.program, self.video, self.work, self.assets)

    def test_source_round_number_and_complete_map_coverage(self):
        result = self.analyze()
        self.assertEqual(result['round_byte'], 2)
        self.assertEqual(result['displayed_round'], 1)
        self.assertEqual(result['checked_cells'], 1792)
        self.assertEqual(len(result['flags']), 10)
        self.assertEqual(result['scenery_color_indices'], [0])

    def test_rejects_lost_objects_and_parameter_count_disagreement(self):
        self.video[0x251] = 1
        with self.assertRaisesRegex(ValueError, 'rock count'):
            self.analyze()
        self.work[32] = 3
        self.video[0x340:0x342] = (0x9820).to_bytes(2, 'little')
        self.assertEqual(self.analyze()['rocks'], 1)
        self.work[9] = 0
        with self.assertRaisesRegex(ValueError, 'flag type'):
            self.analyze()
        self.work[9] = 2
        self.work[33] = 1
        with self.assertRaisesRegex(ValueError, 'flag count'):
            self.analyze()

    def test_rejects_rock_pointer_disagreement_even_when_counts_match(self):
        self.video[0x251] = 1
        self.work[32] = 3
        self.video[0x340:0x342] = (0x9821).to_bytes(2, 'little')
        with self.assertRaisesRegex(ValueError, 'rock pointer'):
            self.analyze()

    def test_rejects_objects_placed_on_a_wall(self):
        self.program[0x3000] = 0x80
        with self.assertRaisesRegex(ValueError, 'object overlaps'):
            self.analyze()

    def test_rejects_missing_terrain(self):
        self.program[0x3004] = 0x80
        with self.assertRaisesRegex(ValueError, 'terrain mismatch'):
            self.analyze()

    def test_rejects_incomplete_capture_and_unexpected_page(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            analyze(self.program, self.video, b'', self.assets)
        self.video[0x28f] = 0x34
        with self.assertRaisesRegex(ValueError, 'terrain page'):
            self.analyze()


if __name__ == '__main__':
    unittest.main()
