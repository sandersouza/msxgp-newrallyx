"""Synthetic event/oracle contracts; actual original data stays ignored."""
import unittest
from scripts.msx.rock_collision_verify import analyze,cases_for
from scripts.msx.rock_route_verify import route
from scripts.msx.player import relocate


class RockCollisionTests(unittest.TestCase):
    def test_contact_repeats_leave_reentry_and_switch_have_exact_entry_counts(self):
        rocks=[0x9821,0x9842]
        cells=[rocks[0],rocks[0],0x9830,rocks[0],rocks[1],0x9830]
        original=b''.join(bytes((int(c in rocks),))+c.to_bytes(2,'little') for c in cells)
        rows=[[0,1,1,rocks[0],rocks[0],100], [1,1,1,rocks[0],rocks[0],80],
              [2,0,1,0x9830,rocks[0],70], [3,1,2,rocks[0],rocks[0],100],
              [4,2,3,rocks[1],rocks[1],120], [5,0,3,0x9830,rocks[1],80]]
        cases=[(c,0,0) for c in cells]
        self.assertEqual(analyze(cases,rocks,original,rows)['entry_events'],3)
        rows[1][2]=2
        with self.assertRaisesRegex(ValueError,'mismatch'):analyze(cases,rocks,original,rows)

    def test_restart_resets_contact_counter_and_last_cell(self):
        rocks=[0x9821,0x9842];cases=[(rocks[0],0,0),(0x9830,0,0)]
        original=bytes((1,0x21,0x98,0,0x30,0x98))
        rows=[[0,1,1,rocks[0],rocks[0],100],[1,0,0,0x9830,0,80]]
        analyze(cases,rocks,original,rows,resets={1})
        with self.assertRaises(ValueError):analyze(cases,rocks,original,rows)

    def test_case_matrix_covers_both_sides_of_signed_twelve_pixel_boundary(self):
        cases=cases_for([0x9b71,0x9a38])
        self.assertEqual(len(cases),2196)
        self.assertTrue({-13,-12,12,13}.issubset({x for _,x,_ in cases}))
        self.assertTrue({-13,-12,12,13}.issubset({y for _,_,y in cases}))

    def test_selective_geometry_relocation_excludes_flags_and_death(self):
        rom=bytearray(16384);rom[0x1774:0x1778]=bytes((0xdd,0x21,0x40,0x80))
        linked,patches=relocate(bytes(rom),'ld ix,08040h ;1774 dd 21 40 80 ',rock_collision=True)
        self.assertEqual(linked[0x1774:0x1778],bytes((0xdd,0x21,0x40,0xe0)))
        self.assertEqual(linked[0x17a6],0xc9)
        self.assertEqual(linked[0x1baa],0xff)
        self.assertEqual(linked[0x19a1],0xff)

    def test_keyboard_route_avoids_walls_without_treating_objects_as_walls(self):
        cells=bytearray([0x87])*1792
        for x,y in [(1,1),(1,2),(2,2),(3,2)]:cells[y*32+x]=0
        cells[2*32+3]=3
        self.assertEqual(route(cells,(1,1),(3,2)),[(1,1),(1,2),(2,2),(3,2)])
        with self.assertRaises(ValueError):route(cells,(1,1),(4,2))
