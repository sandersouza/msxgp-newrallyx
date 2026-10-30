"""Authored gauge pixels, footprint and lossless sprite-Y compensation."""
import unittest
from src.toolchain.msx import sprite_fuel as fuel, sprite_radar as radar
from src.toolchain.msx.raster_scroll import BODY_TOP
from tests.test_sprite_radar import decode


class SpriteFuelTests(unittest.TestCase):
    def test_icon_and_bar_match_radar_width_and_leave_transparent_spacing(self):
        self.assertEqual((fuel.X, fuel.WIDTH), (radar.X, radar.WIDTH))
        self.assertEqual(fuel.Y, radar.Y+radar.HEIGHT+4)
        canvas = bytearray([7])*(256*212)
        fuel.paint_pixels(canvas, 30, 8, 12)
        colors = set(canvas[fuel.Y*256:(fuel.Y+16)*256])
        self.assertEqual(colors,{7,8,12})
        for y in range(16):
            self.assertEqual(canvas[(fuel.Y+y)*256+fuel.X+15],7)
        self.assertEqual(canvas[(fuel.Y+12)*256+fuel.X],8)
        self.assertEqual(canvas[(fuel.Y+3)*256+fuel.X+47],12)

    def test_fuel_levels_only_erase_fill_and_preserve_the_yellow_outline(self):
        states = []
        for amount in fuel.LEVELS:
            canvas=bytearray(256*212)
            fuel.paint_pixels(canvas,amount,8,12)
            states.append(bytes(canvas[(fuel.Y+y)*256+fuel.X+16+x]==12
                                for y in range(16) for x in range(32)))
        self.assertEqual([sum(p) for p in states], sorted([sum(p) for p in states],reverse=True))
        for pixels in states:
            self.assertTrue(all(pixels[3*32+x] and pixels[10*32+x] for x in range(32)))
            self.assertTrue(all(pixels[y*32] and pixels[y*32+31] for y in range(4,10)))
        self.assertFalse(states[-1][5*32+10])
        for before, after in zip(states,states[1:]):
            self.assertTrue(all(a >= b for a,b in zip(before,after)))
        for invalid in (-1,31):
            with self.assertRaises(ValueError): fuel.gauge_patterns(invalid)

    def test_all_levels_and_vertical_phases_preserve_every_screen_pixel(self):
        for amount in fuel.LEVELS:
            raw = fuel.icon_patterns()+fuel.gauge_patterns(amount)
            canvas=bytearray(256*212)
            fuel.paint_pixels(canvas,amount,8,12)
            expected=[{(x,y) for y in range(212) for x in range(256)
                       if canvas[y*256+x]==color} for color in (8,12)]
            for cy in range(256):
                attributes = fuel.attributes(cy)
                actual = [set(),set()]
                for i in range(3):
                    y,x,p,_ = attributes[i*4:i*4+4]
                    self.assertNotEqual(y,216)
                    start = p*8-fuel.ICON_PATTERN*8
                    for sx,sy in decode(raw[start:start+32]):
                        actual[int(i>0)].add((x+sx,(y+1-(cy-BODY_TOP)+sy)&255))
                self.assertEqual(actual,expected)


if __name__ == '__main__':
    unittest.main()
