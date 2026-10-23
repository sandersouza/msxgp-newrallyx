import unittest

from scripts.msx.native_sprites import planes, compile_actors, ACTOR_PATTERN_BASE
from scripts.msx.native_contract import Snapshot


class NativeSpritePlanesTests(unittest.TestCase):
    def decode(self, encoded):
        result = bytearray(256)
        for pattern, colors in reversed(encoded):
            for y in range(16):
                for x in range(16):
                    if pattern[(x//8)*16+y] & (128 >> (x & 7)):
                        result[y*16+x] = colors[y] & 15
        # A CC plane combines with its immediately preceding base plane.
        for at, (pattern, colors) in enumerate(encoded):
            if colors[0] & 64:
                base = encoded[at-1][0]
                for y in range(16):
                    for x in range(16):
                        bit, index = 128 >> (x & 7), (x//8)*16+y
                        if pattern[index] & bit and base[index] & bit:
                            result[y*16+x] = (colors[y] | encoded[at-1][1][y]) & 15
        return bytes(result)

    def test_or_palette_preserves_all_pixels_with_two_planes(self):
        source = bytes((0, 3, 9, 11)[(x+3*y) & 3]
                       for y in range(16) for x in range(16))
        encoded = planes(source)
        self.assertEqual(len(encoded), 2)
        self.assertTrue(encoded[1][1][0] & 64)
        self.assertEqual(self.decode(encoded), source)

    def test_other_palette_uses_three_exact_layers_and_four_colors_refuse(self):
        source = bytes((0, 13, 1, 11)[(x+3*y) & 3]
                       for y in range(16) for x in range(16))
        encoded = planes(source)
        self.assertEqual(len(encoded), 3)
        self.assertEqual(self.decode(encoded), source)
        self.assertIsNone(planes(bytes((1, 2, 4, 8))*64))
        self.assertEqual(planes(bytes(256)), [])

    def fixture(self):
        video, shadows, hud = bytearray(4096), bytearray(392), bytearray(1140)
        hud[0x1c] = 11
        for slot in range(17):
            hud[0x100+slot*4] = 225
        for slot in range(3):
            hud[0x290+slot*4] = 225
        sprites = bytes((x+y) & 3 for y in range(16) for x in range(16))+bytes(16384-256)
        lookup = bytearray(256)
        lookup[4:8], lookup[8:12] = bytes((0, 3, 9, 11)), bytes((0, 13, 1, 11))
        return video, shadows, hud, sprites, bytes(lookup)

    def compile(self, fixture):
        video, shadows, hud, sprites, lookup = fixture
        snap = Snapshot(0, 'post-game-irq', bytes(video), bytes(2048), bytes(shadows))
        return compile_actors(snap, sprites, lookup, bytes(range(16)), bytes(hud))

    def test_actor_priority_and_radar_mask_preserve_original_dimensions(self):
        f = self.fixture()
        video = f[0]
        video[0x1f], video[0x81e], video[0x81f] = 52, 179, 1
        video[0xc00+7*32+6] = 32
        result = self.compile(f)
        self.assertTrue(result['supported'])
        self.assertGreaterEqual(result['attributes'][2], 180)
        self.assertEqual(ACTOR_PATTERN_BASE & 3, 0)
        pixels = result['actors'][0]['pixels']
        self.assertEqual(len(pixels), 256)
        self.assertTrue(all(pixels[y*16+x] == 0 for y in range(2) for x in range(7)))
        self.assertNotEqual(pixels[3*16+2], 0)
        # Only four right-edge pixels enter the maze, and all lie under radar.
        video[0x1f], video[0x81e], video[0x834] = 208, 199, 100
        self.assertEqual(self.compile(f)['slots'], 0)
        snapshot = Snapshot(0, 'post-game-irq', bytes(video), bytes(2048), bytes(f[1]))
        bare = compile_actors(snapshot, f[3], f[4], bytes(range(16)), bytes(f[2]), hud_enabled=False)
        self.assertTrue(bare['supported'])
        self.assertGreater(bare['slots'], 0)  # No invisible radar may clip actors.

    def test_line_and_total_slot_overflow_require_bitmap_fallback(self):
        for palette, reason in ((1, 'eight sprites per line exceeded'),
                                (2, 'thirteen actor slots exceeded')):
            f = self.fixture()
            for n, offset in enumerate(range(0x14, 0x20, 2)):
                f[0][offset+1] = 24+n*24
                f[0][0x800+offset] = 179
                f[0][0x801+offset] = palette
            result = self.compile(f)
            self.assertFalse(result['supported'])
            self.assertEqual(result['reason'], reason)

    def test_reserved_y_requires_bitmap_fallback(self):
        f = self.fixture()
        f[0][0x1f], f[0][0x81e], f[0][0x81f] = 52, 24, 1
        self.assertEqual(self.compile(f)['reason'], 'reserved terminator Y')
