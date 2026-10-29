"""Exact pixels, fixed color bytes and bounded identities across fine phases."""
import random
import unittest

from edge import edge_tiles
from game_boundary_stable import family


class StableBoundaryTests(unittest.TestCase):
    def test_all_rows_and_phases_preserve_source_edge_pixels(self):
        rng = random.Random(8031)
        # Every pixel position, palette ordering, constant and two-color row.
        sources = []
        for n in range(40):
            tile = bytearray()
            for y in range(8):
                a, b = rng.randrange(16), rng.randrange(16)
                tile.extend(a if rng.randrange(2) else b for x in range(8))
            sources.append(bytes(tile))
        sources += sources[:4]  # Deduplicate full signatures, not one phase.
        for which, slot in ((0, 160), (1, 208)):
            phases = family(sources, which, slot)
            self.assertEqual(len({p[0] for p in phases}), 1)
            self.assertEqual(len({p[2] for p in phases}), 1)
            for fx, (names, patterns, colors, count) in enumerate(phases):
                self.assertLessEqual(count, 48)
                self.assertEqual(names[:4], names[-4:])
                for source, name in zip(sources, names):
                    at = (name-slot)*8
                    actual = bytes(colors[at+y] >> 4 if patterns[at+y] & (128 >> x)
                                   else colors[at+y] & 15 for y in range(8) for x in range(8))
                    self.assertEqual(actual, edge_tiles(source, fx)[which])

    def test_all_black_and_same_color_rows(self):
        for color in range(16):
            for which, slot in ((0, 160), (1, 208)):
                phases = family([bytes([color])*64], which, slot)
                self.assertTrue(all(p[3] == 1 for p in phases))
                self.assertEqual(len({p[2] for p in phases}), 1)


if __name__ == '__main__':
    unittest.main()
