"""One outlined portrait and one fixed slot regenerated from native digit assets."""
import unittest
from scripts.msx import sprite_lives as counter
from scripts.msx.raster_scroll import outlined_life
from tests.test_raster_scroll import fixture


class SpriteLivesTests(unittest.TestCase):
    def test_digit_uses_native_font_pixels_in_one_unchanged_attribute_slot(self):
        _,assets = fixture()
        digits = counter.digit_masks(assets)
        self.assertEqual(len(digits),80)
        attrs = counter.attributes(0)
        for n in range(10):
            mask = counter.digit_bitmap(digits,n)
            expected = {(x,y+3) for y in range(8) for x in range(8)
                        if assets.pixels['tiles'][n*64+y*8+x]}
            actual = {(x,y) for y in range(16) for x in range(16) if mask[y*16+x]}
            self.assertEqual(actual,expected)
            self.assertEqual(len(attrs),12)
            self.assertEqual(attrs[-2],counter.COUNT_PATTERN)
        for n in (-1,10):
            with self.assertRaises(ValueError):
                counter.digit_bitmap(digits,n)

    def test_zero_still_draws_the_original_size_car_outline_and_white_digit(self):
        _,assets = fixture()
        digits = counter.digit_masks(assets)
        life = bytes(int(3 <= x <= 12 and 1 <= y <= 10) for y in range(16) for x in range(16))
        canvas = bytearray([7])*(256*212)
        counter.paint(canvas,life,outlined_life(life),digits,0,12,11,8)
        self.assertEqual(canvas[(counter.Y+1)*256+counter.X+3],12)
        self.assertEqual(canvas[counter.Y*256+counter.X+2],11)
        glyph = counter.digit_bitmap(digits,0)
        for y in range(16):
            for x in range(16):
                if glyph[y*16+x]:
                    self.assertEqual(canvas[(counter.Y+y)*256+counter.NUMBER_X+x],8)


if __name__ == '__main__':
    unittest.main()
