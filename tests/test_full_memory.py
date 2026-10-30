"""Synthetic allocator contracts for buffers near the IM2 jump and stack."""
import unittest
from src.toolchain.msx.full_memory import layout


class FullMemoryTests(unittest.TestCase):
    def symbols(self):
        return dict(RADAR_PLAYER_PATTERN=240,Full_EnemyHotStart=0xc680,Full_EnemyHotEnd=0xc700,
            Enemy_Visible=0xc5d2,Full_RadarIRQStart=0xc5d2,Full_RadarIRQEnd=0xc63a,
            Enemy_HitAddress=0xc63c,Full_RegisteredMask=0xc678,Stage_PreferRows=0xc679,
            Full_EnemySATCursor=0xc67a,
            Full_EnemySATDirty=0xc67b,
            Full_RegisteredCurrent=0xc67d,
            Stage_GuardClosed=0xc67c,
            hud_score_pending=0xd110,hud_fuel_payload=0xd180,Full_Shadow=0xd230,
            Full_AITable0=0xd2a8,Full_AIBefore=0xd2c4,Full_AITick=0xd2cb,
            Smoke_Display=0xd300,Smoke_DisplayRows=0xdb00,
            Radar_PublishedPoints=0xdb40,Full_EnemyRecords=0xce20,Round_Objects=0xdc00,
            Flag_Records=0xdf80,Full_IDBank=0xdfbc,Full_RadarFlags=0xdfd0,
            Full_AIValid=0xe3f1,Full_LoadStart=0xf000,Full_LoadEnd=0xf2ed)

    def test_disjoint_layout_retains_stack_and_native_input(self):
        result=layout(self.symbols())
        self.assertEqual(result['cold_code_stack_gap'],147)
        self.assertEqual(result['native_borrowed_bytes']['tile_division'],[0xe300,0xe3f0])

    def test_rejects_overlap_and_cold_stack_encroachment(self):
        symbols=self.symbols();symbols['Stage_GuardClosed']=0xc5e8
        with self.assertRaisesRegex(ValueError,'overlap'):layout(symbols)
        symbols=self.symbols();symbols['Full_AITick']=0xd2d2
        with self.assertRaisesRegex(ValueError,'overlap'):layout(symbols)
        symbols=self.symbols();symbols['Full_LoadEnd']=0xf310
        with self.assertRaisesRegex(ValueError,'stack'):layout(symbols)
        symbols=self.symbols();symbols['Full_EnemyHotEnd']=0xc701
        with self.assertRaisesRegex(ValueError,'space'):layout(symbols)

    def test_overlay_code_cannot_overwrite_world_tile_owners(self):
        symbols=self.symbols()
        symbols.update(Full_CacheEngineStart=0x1000,Full_CacheEngineEnd=0x1fff)
        self.assertEqual(layout(symbols)['terrain_mapper']['tile_owners'],[0x2000,0x3000])
        symbols['Full_CacheEngineEnd']=0x2001
        with self.assertRaisesRegex(ValueError,'overlay'):layout(symbols)

    def test_presentation_code_preserves_native_pointer_tables_and_smoke(self):
        symbols=self.symbols()
        symbols.update(Full_PresentStart=0xea00,Full_PresentEnd=0xebf0)
        layout(symbols)
        symbols['Full_PresentStart']=0xe800
        with self.assertRaisesRegex(ValueError,'native E988'):layout(symbols)
        symbols.update(Full_PresentStart=0xea00,Full_PresentEnd=0xec01)
        with self.assertRaisesRegex(ValueError,'smoke attributes'):layout(symbols)

    def test_radar_priority_cannot_overwrite_visibility_snapshots(self):
        symbols=self.symbols();symbols['Radar_Urgent']=0xce18
        layout(symbols)
        symbols['Radar_Urgent']=0xce17
        with self.assertRaisesRegex(ValueError,'overlap'):layout(symbols)
        symbols.update(Radar_Urgent=0xce18,Radar_Cleanup=0xce1a)
        layout(symbols)
        symbols['Radar_Cleanup']=0xce19
        with self.assertRaisesRegex(ValueError,'overlap'):layout(symbols)
        symbols['Radar_Cleanup']=0xce1f
        with self.assertRaisesRegex(ValueError,'overlap'):layout(symbols)
