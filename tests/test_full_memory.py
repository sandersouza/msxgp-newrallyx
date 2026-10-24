"""Synthetic allocator contracts for buffers near the IM2 jump and stack."""
import unittest
from scripts.msx.full_memory import layout


class FullMemoryTests(unittest.TestCase):
    def symbols(self):
        return dict(RADAR_PLAYER_PATTERN=240,Full_EnemyHotStart=0xc680,Full_EnemyHotEnd=0xc700,
            hud_score_pending=0xd110,hud_fuel_payload=0xd180,Full_Shadow=0xd230,
            Full_AITable0=0xd2a8,Full_AIBefore=0xd2c4,Full_AITick=0xd2cb,
            Smoke_Display=0xd300,Smoke_DisplayRows=0xdb00,
            Radar_PublishedPoints=0xdb40,Round_Objects=0xdc00,
            Flag_Records=0xdf80,Full_IDBank=0xdfbc,Full_RadarFlags=0xdfd0,
            Full_AIValid=0xe3f1,Full_LoadStart=0xf000,Full_LoadEnd=0xf2ed)

    def test_disjoint_layout_retains_stack_and_native_input(self):
        result=layout(self.symbols())
        self.assertEqual(result['cold_code_stack_gap'],147)
        self.assertEqual(result['native_borrowed_bytes']['tile_division'],[0xe300,0xe3f0])

    def test_rejects_overlap_and_cold_stack_encroachment(self):
        symbols=self.symbols();symbols['Full_AITick']=0xd2d2
        with self.assertRaisesRegex(ValueError,'overlap'):layout(symbols)
        symbols=self.symbols();symbols['Full_LoadEnd']=0xf310
        with self.assertRaisesRegex(ValueError,'stack'):layout(symbols)
        symbols=self.symbols();symbols['Full_EnemyHotEnd']=0xc701
        with self.assertRaisesRegex(ValueError,'space'):layout(symbols)
