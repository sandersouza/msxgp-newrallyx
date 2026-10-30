"""Synthetic guards and boundary matrix for the selected enemy oracle."""
import unittest
from src.toolchain.msx.player import relocate,clipped_masks
from src.toolchain.msx.enemy_verify import cases_for,RECORD
from src.toolchain.msx.enemy_presentation_verify import cases_for as presentation_cases


class EnemyTests(unittest.TestCase):
    def test_precomputed_masks_clip_the_complete_left_edge_in_both_planes(self):
        original=bytes([255])*64
        for clip in range(16):
            actual=clipped_masks(original,clip)
            for plane in range(2):
                for row in range(16):
                    line=(actual[plane*32+row]<<8)|actual[plane*32+16+row]
                    self.assertEqual(line,65535>>clip)
        with self.assertRaises(ValueError):clipped_masks(bytes(63),1)
        with self.assertRaises(ValueError):clipped_masks(original,16)
    def test_presentation_matrix_covers_both_cache_edges_and_forbidden_y(self):
        flags=list(range(12));cases=presentation_cases(flags)
        self.assertEqual(len(cases),1928)
        self.assertEqual({r[1] for r in cases},{-8,-7,0,7,8,9,124,248,255,256})
        self.assertTrue(all((f,-7,0,217,1,0,0) in cases for f in flags))
        self.assertTrue(all((0,124,108,0,v,d,c) in cases for v in (0,1) for d in (0,1) for c in (0,1)))
    def test_component_matrix_contains_motion_facing_and_hidden_contact_boundaries(self):
        cases=cases_for()
        self.assertEqual(len(cases),2643)
        self.assertEqual(sum(c[0]==0 for c in cases),2400)
        self.assertEqual(sum(c[0]==1 for c in cases),242)
        self.assertEqual({c[1] for c in cases if c[0]==0},{223,247,239,251})
        self.assertEqual(sum(c[2] for c in cases if c[0]==0),600)
        self.assertTrue(all((1,x,y,1,0) in cases for kind,x,y,h,z in cases if kind==1 and h==0))
        self.assertEqual(RECORD,448)

    def test_enemy_rst_trampoline_is_guarded_and_stays_inside_the_native_bank(self):
        rom=bytearray(16384)
        with self.assertRaisesRegex(ValueError,'RST-10'):relocate(bytes(rom),'',enemies=True)
        rom[0xafd:0xb01]=bytes((0xd7,0,0x20,5))
        linked,patches=relocate(bytes(rom),'',enemies=True)
        self.assertEqual(linked[0xafd:0xb00],bytes((0xc3,0,0xbf)))
        self.assertEqual(linked[0x3f00:0x3f09],bytes((0xcd,0x10,0x80,0xc2,6,0x8b,0xc3,1,0x8b)))
        self.assertTrue(all(linked[a]==0xc9 for a in (0x2eb,0x3c3,0xbd1,0x124f,0x1273,0x127e,0x12a8)))
        self.assertEqual(linked[0x18c1:0x18c7],bytes((0x3e,1,0x32,0xd0,0xc5,0xc9)))
