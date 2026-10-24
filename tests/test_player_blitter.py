"""Safety boundaries for opaque copies over certified uniform road tiles."""
import unittest
from scripts.msx.player_blitter import road_tiles,opaque_atlas


class PlayerBlitterTests(unittest.TestCase):
    def test_one_obstacle_pixel_prevents_the_whole_tile_certificate(self):
        world=bytearray([7])*256;world[7*16+7]=4
        table=road_tiles(world,7,width=16,height=16)
        self.assertEqual([table[i] for i in (0,1,128,129)],[0,1,1,1])
        self.assertFalse(any(table[256:]))
        with self.assertRaises(ValueError):road_tiles(bytes(63),7,width=8,height=8)

    def test_both_horizontal_parities_preserve_every_car_pixel_and_padding(self):
        cars=bytes((i%15+1 if i%3 else 0) for i in range(12*256))
        raw=opaque_atlas(cars,7)
        pixels=bytes(value for byte in raw for value in (byte>>4,byte&15))
        self.assertEqual(len(raw),3456)
        for phase in (0,1):
            for frame in range(12):
                for y in range(16):
                    row=pixels[phase*3456+y*216+frame*18:][:18]
                    self.assertEqual(row[phase:phase+16],bytes(c or 7 for c in cars[frame*256+y*16:][:16]))
                    self.assertEqual(row[:phase]+row[phase+16:],bytes([7])*2)

    def test_collectible_owner_overrides_are_bounded_to_the_original_three_by_three_cell(self):
        table=road_tiles(bytes([4])*1024,7,width=32,height=32,flags=[dict(tile_x=1,tile_y=1)])
        self.assertEqual([table[y*128+x] for y in range(4) for x in range(4)],
                         [0,0,0,0,0,2,2,2,0,2,2,2,0,2,2,2])

    def test_flag_presentation_has_a_strict_one_refresh_bound_and_resets_cleanly(self):
        from scripts.msx.flags import verify_display_snapshots
        active=bytes((0,))+bytes([1])*10
        collected=bytes((0,0))+bytes([1])*9
        verify_display_snapshots(active+collected+collected+active,active+active+collected+active,[1,2,3,0])
        with self.assertRaisesRegex(ValueError,'one refresh'):
            verify_display_snapshots(active+collected+collected,active+active+active,[1,2,3])
