"""Synthetic projection, transparent composition and mode-2 sprite limits."""
import unittest
from scripts.msx import sprite_radar as radar
from scripts.msx.raster_scroll import BODY_TOP, LIFE_SPLIT, MASK_ROWS, sprite_attributes


def decode(raw):
    return {(x,y) for y in range(16) for x in range(16)
            if raw[(x//8)*16+y] & (128 >> (x%8))}


class SpriteRadarTests(unittest.TestCase):
    def test_projection_keeps_native_markers_inside_white_outline(self):
        self.assertEqual(radar.project(224,80), (2,2))
        for x in range(224,289):
            for y in range(80,193):
                px,py = radar.project(x,y)
                self.assertTrue(2 <= px <= radar.WIDTH-3)
                self.assertTrue(2 <= py <= radar.HEIGHT-3)
        pixels = radar.bitmap([(4,6)])
        self.assertEqual(sum(pixels), 2*(radar.WIDTH+radar.HEIGHT)-8+4)
        self.assertEqual(pixels[10*radar.WIDTH+10], 0)
        self.assertTrue(all(pixels[y*radar.WIDTH] for y in range(1,radar.HEIGHT-1)))

    def test_dynamic_point_patterns_keep_all_four_pixels_at_byte_crossings(self):
        for x in range(2, radar.WIDTH-2):
            for y in range(2, radar.HEIGHT-2):
                raw = radar.point_patterns(x,y)
                for shift in (0,1):
                    self.assertEqual(decode(raw[shift*32:shift*32+32]),
                                     {(x%8+dx,y%8+dy+shift) for dx in (0,1) for dy in (0,1)})

    def test_frame_and_points_remain_fixed_through_every_r23_phase(self):
        flags = [(2,2),(15,14),(16,15),(30,44),(45,55)]
        pixels = radar.bitmap(flags)
        static = radar.patterns(pixels)
        points = dict(player=[15,15], enemy=[31,47])
        patterns = bytes(160)+static+radar.point_patterns(*points['player'])+radar.point_patterns(*points['enemy'])
        expected_frame = {(radar.X+x,radar.Y+y) for y in range(radar.HEIGHT)
                          for x in range(radar.WIDTH) if pixels[y*radar.WIDTH+x]}
        for cy in range(256):
            actual = [set(),set(),set()]
            attrs = radar.attributes(cy,**points)
            for i in range(14):
                y,x,p,_ = attrs[i*4:i*4+4]
                self.assertNotEqual(y,216)
                for sx,sy in decode(patterns[p*8:p*8+32]):
                    actual[0 if i < 12 else i-11].add((x+sx,(y+1-(cy-BODY_TOP)+sy)&255))
            self.assertEqual(actual[0], expected_frame)
            for layer, point in enumerate(points.values(),1):
                self.assertEqual(actual[layer], {(radar.X+point[0]+dx,radar.Y+point[1]+dy)
                                                for dx in (0,1) for dy in (0,1)})

    def test_entire_population_fits_sat_and_eight_sprite_scanline_limit(self):
        # Reserve BOTH point slots on EVERY radar row: stronger than a fixed capture.
        for cy in range(256):
            attrs = sprite_attributes(cy,2,dict(player=[2,2],enemy=[2,2]))
            self.assertEqual(len(attrs),69)
            counts = [0]*256
            for i in list(range(12))+list(range(14,17)):
                y = attrs[i*4]
                for row in range(16):
                    counts[(y+1-(cy-BODY_TOP)+row)&255] += 1
            for y in range(radar.Y,radar.Y+radar.HEIGHT+15):
                counts[y] += 2
            for y in range(108,124):
                counts[y] += 2
            self.assertLessEqual(max(counts[BODY_TOP:LIFE_SPLIT]),8)
            lower = sprite_attributes(cy,2,dict(player=[2,2],enemy=[2,2]),footer=True)
            lower_counts = [0]*256
            for i in range(17):
                for row in range(16):
                    lower_counts[(lower[i*4]+1-(cy-BODY_TOP)+row)&255] += 1
            self.assertLessEqual(max(lower_counts[LIFE_SPLIT:212]),8)
            for lives in range(10):
                short = sprite_attributes(cy,lives,dict(player=[2,2],enemy=[2,2]),footer=True)
                self.assertEqual(short[-1],216)
                self.assertEqual(len(short),69)

    def test_transparent_background_and_white_frame_survive_marker_overlap(self):
        canvas = bytearray([7])*(256*212)
        radar.paint(canvas,[(4,4)],[4,4],[10,10],8,9,11)
        def at(x,y): return canvas[(radar.Y+y)*256+radar.X+x]
        self.assertEqual(at(4,4),8)
        self.assertEqual(at(10,10),9)
        self.assertEqual(at(20,20),7)
        self.assertEqual(at(0,10),8)


if __name__ == '__main__':
    unittest.main()
