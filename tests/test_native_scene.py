import unittest

from scripts.msx.native_contract import Snapshot
from scripts.msx.native_scene import compose_scene, dirty_regions, scene_from_snapshot, tile_pixels, verify_tile_cache, verify_scene_cache, radar_from_snapshot, verify_radar_cache
from scripts.msx.native_video import flipped_pens, native_palette, black_tables
from scripts.msx.screen5 import expand


class NativeSceneTests(unittest.TestCase):
    def test_bitmap_radar_checks_all_pixels_across_both_world_seams(self):
        video, shadow = bytearray(4096), bytearray(392)
        shadow[0x130], shadow[0x140] = 58, 204
        video[0x35], video[0x835], shadow[5] = 224, 157, 1
        snapshot = Snapshot(1, 'post-game-irq', bytes(video), bytes(2048), bytes(shadow))
        vram = bytearray(b'\x33'*131072)
        def pixel(x, y, color):
            at = 32768+(y & 255)*128+(x & 255)//2
            shift = 0 if x & 1 else 4
            vram[at] = (vram[at] & ~(15 << shift)) | (color << shift)
        for y in range(235, 295):
            for x in range(254, 304):
                pixel(x, y, 11)
        for y in (237, 238):
            for x in (1, 2):
                pixel(x, y, 13)
        self.assertEqual(verify_radar_cache(snapshot, bytes(vram), 1)['different_pixels'], 0)
        scene = verify_scene_cache(snapshot, bytes(vram), 1, bytes((3,))*16384,
                                   bytes(16384), bytes(range(4))*64, bytes(range(16)), radar=True)
        self.assertTrue(scene['bitmap_scene_verified'])
        pixel(40, 20, 3)  # Far outside the 200-pixel game viewport, inside radar.
        report = verify_radar_cache(snapshot, bytes(vram), 1)
        self.assertEqual((report['compared_pixels'], report['different_pixels']), (3000, 1))

    def test_radar_reads_original_dot_high_bit_and_remaining_flag_cells(self):
        video, work, shadow = bytearray(4096), bytearray(2048), bytearray(392)
        video[0x34:0x37] = bytes((224, 30, 32))
        video[0x834:0x837] = bytes((157, 47, 157))
        shadow[4] = 1
        video[0x992:0x994] = (0x8100).to_bytes(2, 'little')
        for i, address in enumerate((0x9800, 0x9eff, 0x9821, 0x9f00)):
            video[0x100+2*i:0x102+2*i] = address.to_bytes(2, 'little')
        work[0], work[0x6ff], work[0x21] = 1, 4, 0
        def read():
            return radar_from_snapshot(Snapshot(1, 'post-game-irq', bytes(video), bytes(work), bytes(shadow)))
        result = read()
        self.assertEqual(result['player'], (0, 0))
        self.assertEqual(result['enemies'], ((62, 110),)+(None,)*7)
        self.assertEqual(result['flags'], ((0, 0), (62, 110))+(None,)*8)
        work[0] = 0  # Collection is read from the original collision grid.
        self.assertIsNone(read()['flags'][0])
        shadow[4] = 0  # Same low X with the opposite ninth bit is off radar.
        self.assertIsNone(read()['player'])
        video[0x992:0x994] = (0x8fed).to_bytes(2, 'little')
        self.assertEqual(read()['flags'], (None,)*10)

    def test_full_scene_oracle_checks_wrap_priority_and_opaque_actor_black(self):
        ram = bytearray(4096)
        ram[0xc00:] = bytes((64,))*1024
        ram[0x14:0x16] = bytes((4, 12))
        ram[0x814] = 219  # source Y=6: actor begins at visible upper-left
        shadow = bytearray(392)
        shadow[0x130], shadow[0x140] = 240, 230
        sprites = bytearray(16384)
        sprites[256], sprites[271] = 1, 2
        translation = bytes((0, 11, *range(2, 11), 1, *range(12, 16)))
        vram = bytearray(b'\x33'*131072)
        def pixel(wx, wy, color):
            at = 32768+(wy & 255)*128+(wx & 255)//2
            shift = 0 if wx & 1 else 4
            vram[at] = (vram[at] & ~(15 << shift)) | (color << shift)
        pixel(249, 252, 11)
        pixel(264, 252, 2)
        def verify():
            snapshot = Snapshot(1, 'post-game-irq', bytes(ram), bytes(2048), bytes(shadow))
            return verify_scene_cache(snapshot, bytes(vram), 1, bytes((3,))*16384,
                                      bytes(sprites), bytes(range(4))*64, translation)
        self.assertTrue(verify()['bitmap_scene_verified'])
        pixel(249, 252, 3)  # Transparent black must not replace opaque black.
        self.assertEqual(verify()['different_pixels'], 1)
        index = (252//8)*32+249//8
        ram[0xc00+index] |= 32
        self.assertTrue(verify()['bitmap_scene_verified'])
        ram[0xc00+index] &= ~32
        ram[0x14] |= 3  # Both source flips move the colored endpoints.
        pixel(264, 252, 3)
        pixel(249, 267, 2)
        pixel(264, 267, 11)
        self.assertTrue(verify()['bitmap_scene_verified'])

    def test_black_tables_require_every_used_pen_to_be_black(self):
        tiles = bytes((1, 2)) * 32 + bytes(16384-64)
        lookup = bytearray(256)
        lookup[4+2] = 3
        masks, black = black_tables(tiles, bytes(lookup), bytes(range(16)))
        self.assertEqual(masks[0], 6)
        self.assertEqual(masks[0] & ~black[0], 0)
        self.assertNotEqual(masks[0] & ~black[1], 0)
        self.assertEqual(masks[1], 1)
    def test_cache_checks_completed_tiles_and_reports_pending_work_separately(self):
        video = bytes(4096)
        vram = bytearray(131072)
        dirty = bytearray(b'\xff' * 128)
        dirty[0] = 0xfe
        report = verify_tile_cache(video, bytes(vram), bytes(dirty), bytes(16384), bytes(256), bytes(range(16)))
        self.assertEqual((report['compared_tiles'], report['pending_tiles'], report['different_pixels']), (1, 1023, 0))
        self.assertFalse(report['rendered_rgb_verified'])
        vram[65536] = 0xbb  # Opaque black has the same RGB as black index zero.
        self.assertEqual(verify_tile_cache(video, bytes(vram), bytes(dirty), bytes(16384), bytes(256), bytes(range(16)))['different_pixels'], 0)
        vram[65536] = 0x10
        report = verify_tile_cache(video, bytes(vram), bytes(dirty), bytes(16384), bytes(256), bytes(range(16)))
        self.assertEqual(report['different_pixels'], 1)
        self.assertEqual(report['first_difference'], dict(tile=0, x=0, y=0, expected=0, actual=1))
        with self.assertRaises(ValueError):
            verify_tile_cache(video, bytes(vram), bytes(127), bytes(16384), bytes(256), bytes(range(16)))

    def test_palette_retains_opaque_black_and_all_distinct_source_colors(self):
        hud_colors = [(n % 7 + 1, n // 7 + 1, 0) for n in range(16)]
        for n in (11, 14, 15):
            hud_colors[n] = (0, 0, 0)
        original = [(0, 0, 0), (0, 0, 0)] + [c for n, c in enumerate(hud_colors) if n not in (11, 14, 15)]
        original.insert(4, (7, 7, 7))
        lookup = list(range(16)) * 16
        encoded = bytes(v for r, g, b in hud_colors for v in ((r << 4) | b, g))
        result, translation, pairs = native_palette(dict(rgb=[list(expand(c)) for c in original], lookup=lookup), encoded)
        self.assertEqual(len(set(translation)), 16)
        self.assertEqual((translation[0], translation[1]), (0, 11))
        colors = [(result[n] >> 4, result[n+1], result[n] & 7) for n in range(0, 32, 2)]
        self.assertEqual([colors[n] for n in translation], original)
        for palette in range(64):
            for pair in range(16):
                self.assertEqual(pairs[palette*16+pair],
                                 translation[lookup[palette*4+(pair >> 2)]]*16 +
                                 translation[lookup[palette*4+(pair & 3)]])

    def test_resource_orientations_preserve_all_pixels_and_dimensions(self):
        for size in (8, 16):
            source = bytes((x+2*y) % 4 for y in range(size) for x in range(size))
            packed = flipped_pens(source, size)
            self.assertEqual(len(packed), size*size)
            decoded = bytes((v >> shift) & 3 for v in packed for shift in (6, 4, 2, 0))
            for flags in range(4):
                expected = bytes(source[(size-1-y if flags & 2 else y)*size +
                                        (size-1-x if flags & 1 else x)]
                                 for y in range(size) for x in range(size))
                self.assertEqual(decoded[flags*size*size:(flags+1)*size*size], expected)
        with self.assertRaises(ValueError):
            flipped_pens(b'\x04' * 64, 8)

    def test_dirty_bounds_keep_old_and_new_coverage_and_clip(self):
        old = ((-5, 1, 4, 6), (6, 2, 12, 8))
        new = ((2, 3, 8, 9), (30, 30, 40, 40))
        regions = dirty_regions(old, new, (0, 0, 10, 10))
        expected = {(x, y) for r in old + new for y in range(max(0, r[1]), min(10, r[3]))
                    for x in range(max(0, r[0]), min(10, r[2]))}
        actual = {(x, y) for r in regions for y in range(r[1], r[3]) for x in range(r[0], r[2])}
        self.assertTrue(expected <= actual)
        self.assertTrue(all(0 <= r[0] < r[2] <= 10 and 0 <= r[1] < r[3] <= 10 for r in regions))

    def test_actor_order_flips_clipping_and_opaque_black(self):
        palette = bytes(c for n in range(16) for c in (n, n, n))
        first = dict(bounds=(-1, 0, 1, 2), pixels=bytes((2, 0, 3, 1)), transparent=0,
                     flip_x=True, flip_y=True)
        second = dict(bounds=(0, 1, 2, 2), pixels=bytes((0, 4)), transparent=0)
        image = compose_scene(bytes((7,)) * 16, 4, 4, (first, second), (0, 0), palette)
        self.assertEqual(image.getpixel((0, 0)), (3, 3, 3))
        self.assertEqual(image.getpixel((0, 1)), (2, 2, 2))
        self.assertEqual(image.getpixel((1, 1)), (4, 4, 4))
        black = dict(bounds=(0, 0, 1, 1), pixels=b'\x01', transparent=0)
        self.assertEqual(compose_scene(bytes((7,)) * 16, 4, 4, (black,), (0, 0), palette)
                         .getpixel((0, 0)), (1, 1, 1))

    def test_mutated_flag_does_not_reappear_after_actor_restore_or_scroll(self):
        palette = bytes(c for n in range(16) for c in (n, n, n))
        world = bytearray(32)
        world[9] = 5
        actors = (dict(bounds=(0, 0, 3, 2), pixels=bytes((2,)) * 6, transparent=0),
                  dict(bounds=(1, 0, 4, 2), pixels=bytes((3,)) * 6, transparent=0))
        before = compose_scene(bytes(world), 8, 4, actors, (0, 0), palette)
        world[9] = 0
        after = compose_scene(bytes(world), 8, 4, (), (0, 0), palette)
        restored = before.copy()
        for rect in dirty_regions(tuple(a['bounds'] for a in actors), (), (0, 0, 8, 4)):
            restored.paste(after.crop(rect), rect[:2])
        self.assertEqual(restored.tobytes(), after.tobytes())
        self.assertEqual(compose_scene(bytes(world), 8, 4, (), (8, 4), palette).tobytes(), after.tobytes())
        self.assertEqual(after.getpixel((1, 1)), (0, 0, 0))

    def test_tile_attribute_flips_and_lookup(self):
        tiles = bytes((x + 2*y) % 4 for y in range(8) for x in range(8))
        lookup = bytes(range(16)) * 16
        normal = tile_pixels(tiles, lookup, 0, 0x41)
        flipped = tile_pixels(tiles, lookup, 0, 0x81)
        self.assertEqual(normal[0], 4)
        self.assertEqual(flipped, bytes(normal[(7-y)*8 + 7-x] for y in range(8) for x in range(8)))

    def test_scene_is_read_only_and_rejects_invalid_hud_pointer(self):
        video = bytearray(4096)
        for offset in (0x988, 0x98e, 0x990):
            video[offset:offset+2] = b'\x00\x82'
        video[0x14:0x16] = bytes((0x0d, 20))
        video[0x814] = 200
        shadows = bytearray(392)
        shadows[0x130], shadows[0x140] = 250, 240
        snapshot = Snapshot(1, 'post-game-irq', bytes(video), bytes(2048), bytes(shadows))
        scene = scene_from_snapshot(snapshot)
        self.assertEqual(scene['camera'], (3, 6))
        self.assertEqual(len(scene['actors']), 6)
        actor = scene['actors'][-1]
        self.assertEqual((actor['code'], actor['flip_x'], actor['flip_y']), (3, True, False))
        self.assertEqual(snapshot.video, bytes(video))
        video[0x990:0x992] = b'\xff\xff'
        with self.assertRaisesRegex(ValueError, 'pointer'):
            scene_from_snapshot(Snapshot(2, 'post-game-irq', bytes(video), bytes(2048), bytes(shadows)))


if __name__ == '__main__':
    unittest.main()
