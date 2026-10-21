"""Synthetic font, outline, bounded viewport and sprite-sentinel coverage."""
from types import SimpleNamespace
import unittest

from scripts.msx.raster_scroll import (BODY_TOP, LIFE_X, LIFE_Y, LIFE_PATTERN, MASK_ROWS, compose, header,
    index_for, outlined_life, palette_rgb, sprite_attributes, sprite_pattern)
from scripts.msx import sprite_lives as counter
from scripts.msx.screen5 import rgb333


def fixture():
    colors = [(255, 151, 71), (0, 0, 0), (222, 222, 222), (255, 0, 0),
              (0, 151, 222), (255, 255, 0)] + [(0, 0, 0)]*10
    palette = bytes(v for color in colors for r, g, b in [rgb333(color)] for v in (r << 4 | b, g))
    pixels = bytes(int(x == code % 8 or y == code//8 % 8)
                   for code in range(256) for y in range(8) for x in range(8))
    lookup = [0]*256
    lookup[38*4+1] = 15
    return palette, SimpleNamespace(pixels={'tiles': pixels}, palette={'lookup': lookup})


class RasterScrollTests(unittest.TestCase):
    def test_single_line_score_fields_do_not_modify_labels_or_each_other(self):
        palette, assets = fixture()
        base = header(assets, palette)
        self.assertEqual(len(base), 256*8)
        black = index_for(palette, (0, 0, 0))
        for y in range(8):
            self.assertEqual(base[y*256:y*256+8], bytes([black])*8)
            self.assertEqual(base[y*256+248:(y+1)*256], bytes([black])*8)
        for changed, allowed in ((header(assets, palette, score=5000), (200, 248)),
                                 (header(assets, palette, high=25000), (72, 120))):
            positions = [i % 256 for i, (a, b) in enumerate(zip(base, changed)) if a != b]
            self.assertTrue(positions)
            self.assertTrue(all(allowed[0] <= x < allowed[1] for x in positions))
        with self.assertRaisesRegex(ValueError, '32-cell'):
            header(assets, palette, score=1000000)

    def test_outline_keeps_silhouette_and_includes_diagonal_neighbors(self):
        mask = bytes(int((x, y) in ((3, 2), (4, 2), (4, 3)))
                     for y in range(16) for x in range(16))
        outline = outlined_life(mask)
        self.assertTrue(all(not pixel or outline[i] for i, pixel in enumerate(mask)))
        self.assertEqual(outline[1*16+2], 1)
        self.assertEqual(outline[4*16+5], 1)
        self.assertEqual(outline[4*16+6], 0)
        with self.assertRaisesRegex(ValueError, 'padding'):
            outlined_life(bytes([1])+bytes(255))

    def test_life_screen_pixels_are_fixed_for_every_vertical_scroll_and_sentinel(self):
        mask = bytes(int(3 <= x <= 12 and 1 <= y <= 10)
                     for y in range(16) for x in range(16))
        outline = outlined_life(mask)
        _, assets = fixture()
        digits = counter.digit_masks(assets)
        for cy in range(256):
            for lives in range(10):
                digit = counter.digit_bitmap(digits,lives)
                patterns = b''.join(sprite_pattern(p,phase) for phase in (0,1) for p in (mask,outline))
                patterns += sprite_pattern(digit)+sprite_pattern(digit,1)
                attributes = sprite_attributes(cy, lives, footer=True)
                self.assertEqual(attributes[-1], 216)
                self.assertEqual(len(attributes), len(MASK_ROWS)*4+12+1)
                attributes = attributes[len(MASK_ROWS)*4:]
                actual = [set(),set(),set()]
                for slot in range(3):
                    y, x, pattern, _ = attributes[slot*4:slot*4+4]
                    self.assertNotEqual(y, 216)
                    offset = (pattern-LIFE_PATTERN)*8
                    raw = patterns[offset:offset+32]
                    for sy in range(16):
                        for sx in range(16):
                            if raw[(sx//8)*16+sy] & (128 >> (sx%8)):
                                actual[slot].add((x+sx,(y+1-(cy-BODY_TOP)+sy)&255))
                for slot,(bitmap,ox) in enumerate(((mask,LIFE_X[0]),(outline,LIFE_X[0]),(digit,LIFE_X[1]))):
                    expected = {(ox+x,LIFE_Y+y) for y in range(16) for x in range(16) if bitmap[y*16+x]}
                    self.assertEqual(actual[slot],expected)

    def test_right_mask_covers_every_visible_row_at_all_vertical_phases(self):
        for cy in range(256):
            attributes = sprite_attributes(cy, lives=0)
            covered = set()
            for slot in range(len(MASK_ROWS)):
                y, x, pattern, _ = attributes[slot*4:slot*4+4]
                self.assertNotEqual(y, 216)
                self.assertEqual((x, pattern), (248, 16))
                covered.update((y+1-(cy-BODY_TOP)+row) & 255 for row in range(16))
            self.assertTrue(set(range(BODY_TOP, 212)) <= covered)

    def test_screen_oracle_crops_world_without_moving_header_or_mask(self):
        palette, assets = fixture()
        world = bytes((x//7+y//11) % 6 for y in range(512) for x in range(512))
        hud = header(assets, palette)
        empty = bytes(256)
        image = compose(world, hud, empty, palette, cx=255, cy=255, lives=0, width=512)
        colors = palette_rgb(palette)
        self.assertEqual(image.getpixel((8, BODY_TOP)), colors[world[255*512+255]])
        self.assertEqual(image.getpixel((247, BODY_TOP+1)), colors[world[256*512+494]])
        self.assertEqual(image.getpixel((255, BODY_TOP+1)), colors[index_for(palette, (0, 0, 0))])
        self.assertEqual(image.getpixel((0, 100)), colors[index_for(palette, (0, 0, 0))])
        self.assertEqual(image.getpixel((10, 2)), colors[hud[2*256+10]])


if __name__ == '__main__':
    unittest.main()
