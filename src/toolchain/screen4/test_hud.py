"""Synthetic-only HUD contracts: saturation, alignment and complete life icons."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import unittest

from hud import display_values, compose_hud


class DisplayLimits(unittest.TestCase):
    def test_saturates_without_decimal_wrap(self):
        for high, score, rnd, lives in ((999999,999999,99,4),
                                        (1000000,1000000,100,5),
                                        (999999999,999999999,255,255)):
            shown = display_values(high,score,rnd,lives)
            self.assertEqual(shown, ('999999','999999','99',4))

    def test_values_below_the_limits_remain_distinct(self):
        self.assertEqual(display_values(20000,17,9,3),('020000','000017','9',3))
        self.assertEqual(display_values(999998,999998,98,0),('999998','999998','98',0))


class Composition(unittest.TestCase):
    def render(self, rnd=1, lives=4):
        # 16x16 source with transparent padding, preserving a 10x10 silhouette.
        life = bytes(3<=x<=12 and 1<=y<=10 for y in range(16) for x in range(16))
        return compose_hud(lambda char: bytes([1])*64, life, [],
                           dict(black=0,white=1,yellow=2,blue=3,red=4,cyan=5,green=6),
                           round_number=rnd,lives=lives)

    def test_footer_at_bottom_and_number_flush_right(self):
        image = self.render(rnd=7,lives=0)
        for y in range(204,212):
            self.assertEqual(image[y*48:y*48+24],bytes([1])*24)
            self.assertEqual(image[y*48+24:y*48+40],bytes([0])*16)
            self.assertEqual(image[y*48+40:y*48+48],bytes([1])*8)
        image = self.render(rnd=100,lives=0)
        self.assertTrue(all(image[y*48+32:y*48+48]==bytes([1])*16 for y in range(204,212)))

    def test_radar_moves_up_eight_pixels_at_same_height(self):
        image = self.render(lives=0)
        self.assertTrue(all(image[y*48:(y+1)*48]==bytes([3])*48 for y in range(68,180)))
        self.assertEqual(image[180*48:184*48],bytes(4*48))

    def test_four_complete_unscaled_cars_and_no_fifth(self):
        for count in (0,1,3,4,5,100):
            image = self.render(lives=count)
            points={(x,y) for y in range(180,204) for x in range(48) if image[y*48+x]==2}
            expected={(i*11+x,184+y) for i in range(min(count,4))
                      for y in range(1,11) for x in range(3,13)}
            self.assertEqual(points, expected)


if __name__ == '__main__':
    unittest.main()
