"""Hand-derived bit probes and PROMs; no original ROM bytes."""
import unittest
from src.toolchain.graphics import decode


class DecodeTests(unittest.TestCase):
    def test_zero_regions_and_sizes(self):
        result = decode.decode_graphics(bytes(4096), bytes(256))
        self.assertEqual(result, {'tiles': bytes(16384),
                                 'sprites': bytes(16384), 'dots': bytes(128)})
        for sizes in ((4095, 256), (4096, 255), (4097, 256)):
            with self.assertRaises(ValueError):
                decode.decode_graphics(bytes(sizes[0]), bytes(sizes[1]))

    def test_planes_x_offsets_quadrants_and_last_ids(self):
        gfx = bytearray(4096)
        gfx[8] = 0x80       # plane 0 -> weight 2 at (0,0)
        gfx[0] = 0x08       # plane 1 -> weight 1 at tile (4,0), sprite (12,0)
        gfx[16] = 0x80      # sprite (4,0), next tile (4,0)
        gfx[24] = 0x80      # sprite (8,0)
        gfx[40] = 0x80      # sprite (0,8)
        gfx[4095] = 0x11    # tile 255 (7,7); sprite 63 (11,15)
        result = decode.decode_graphics(bytes(gfx), bytes(256))
        tile, sprite = result['tiles'], result['sprites']
        self.assertEqual(list(tile[:8]), [2, 0, 0, 0, 1, 0, 0, 0])
        self.assertEqual([sprite[x] for x in (0, 4, 8, 12)], [2, 2, 2, 1])
        self.assertEqual(sprite[8 * 16], 2)
        self.assertEqual(tile[255 * 64 + 7 * 8 + 3], 3)
        self.assertEqual(sprite[63 * 256 + 15 * 16 + 11], 3)

    def test_dot_planes_and_boundaries(self):
        gfx = bytearray(256)
        gfx[0] = 2
        gfx[1] = 1
        gfx[16] = 3
        gfx[127] = 3
        dots = decode.decode_graphics(bytes(4096), bytes(gfx))['dots']
        self.assertEqual(dots[:4], bytes([2, 1, 0, 0]))
        self.assertEqual(dots[16], 3)
        self.assertEqual(dots[127], 3)

    def test_asymmetric_flips(self):
        pixels = bytes([0, 1, 2, 3, 0, 1])
        self.assertEqual(decode.flip_pixels(pixels, 3, 2, True, False), bytes([2,1,0,1,0,3]))
        self.assertEqual(decode.flip_pixels(pixels, 3, 2, False, True), bytes([3,0,1,0,1,2]))
        self.assertEqual(decode.flip_pixels(pixels, 3, 2, True, True), bytes([1,0,3,2,1,0]))

    def test_rgb_network_rounding_and_lookup_transparency(self):
        prom = bytes([0, 1, 2, 4, 8, 16, 32, 64, 128, 255] + [0] * 22)
        lookup = bytes([1, 0, 31, 2] * 64)
        palette = decode.decode_palette(prom, lookup)
        self.assertEqual(palette['rgb'][:10], [[0,0,0], [33,0,0], [71,0,0],
            [151,0,0], [0,33,0], [0,71,0], [0,151,0], [0,0,71],
            [0,0,151], [255,255,222]])
        self.assertEqual(palette['lookup'][:4], [1,0,15,2])
        self.assertEqual(palette['variants'], [[1,0,15,2]] * 64)
        self.assertEqual(palette['sprite_alpha'], [[255,0,255,255]] * 64)
        # Indirect index 15 is black in this synthetic palette but stays opaque.
        self.assertEqual(palette['rgb'][15], [0,0,0])
        self.assertEqual(palette['dot_indices'], [16,17,18,19])
        self.assertEqual(palette['dot_alpha'], [255,255,255,0])
        with self.assertRaises(ValueError):
            decode.decode_palette(bytes(31), bytes(256))


if __name__ == '__main__':
    unittest.main()
