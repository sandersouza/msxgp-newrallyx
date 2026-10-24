"""Synthetic relocation guards and original-smoke scenario coverage."""
import unittest

from scripts.msx.player import relocate
from scripts.msx.smoke_verify import cases_for,RECORD
from scripts.msx.smoke import eligibility,anchor,ring_index,published_tiles,paint,verify_logical_rows


class SmokeTests(unittest.TestCase):
    def test_cache_backpressure_requires_frozen_native_motion_and_counts_reset_boundaries(self):
        from scripts.msx.smoke import held_refresh_metrics
        size=4215;records=[bytearray(size) for _ in range(5)]
        for r,tick in zip(records,(10,10,11,0,0)):r[4160:4162]=tick.to_bytes(2,'little')
        counts=b''.join(i.to_bytes(2,'little') for i in (0,1,1,0,1))
        result=held_refresh_metrics(counts,b''.join(records),size)
        self.assertEqual(result['held_refreshes'],2)
        self.assertEqual(result['longest_consecutive_refreshes'],1)
        records[1][0x6d]=1
        with self.assertRaisesRegex(ValueError,'advanced native motion'):
            held_refresh_metrics(counts,b''.join(records),size)
        records[1][0x6d]=0;records[1][4160]=11
        with self.assertRaisesRegex(ValueError,'advanced native motion'):
            held_refresh_metrics(counts,b''.join(records),size)

    def test_empty_native_rows_cannot_hide_original_clouds(self):
        codes=bytearray(1024);rows=bytearray(32)
        verify_logical_rows(codes,rows)
        rows[31]=1;verify_logical_rows(codes,rows)
        codes[31*32]=189;verify_logical_rows(codes,rows)
        rows[31]=0
        with self.assertRaisesRegex(ValueError,'hides live original cloud'):
            verify_logical_rows(codes,rows)
    def test_permission_map_distinguishes_flag_removal_and_preserves_padding(self):
        original=[(129,149),(129,21),(128,149),(129,149)]
        self.assertEqual(eligibility(original,[(129,149)]*4,width=4,height=1,stride=8),bytes((235,0)))
        with self.assertRaises(ValueError):eligibility(original,[],width=4,height=1,stride=8)

    def test_publication_tags_disambiguate_both_world_wraps(self):
        for x in (0,31,32,63,64,101):
            for y in (0,31,32,63,64,95,127,128,173):
                for code in range(9):
                    data=bytearray(2048)
                    data[(y&31)*64+(x&63)]=((x&64)<<1)|((y&224)>>1)|(code+1)
                    self.assertEqual(published_tiles(data),[(x,y,code)])
        data=bytearray(2048);data[0]=10
        with self.assertRaises(ValueError):published_tiles(data)
        with self.assertRaises(ValueError):published_tiles(bytes(1024))

    def test_paint_uses_complete_original_size_tiles_and_native_anchor(self):
        data=bytearray(2048);data[65]=5
        world=bytearray(32*32);paint(world,32,0,data,b''.join(bytes([i+1])*64 for i in range(9)))
        self.assertEqual(sum(p==5 for p in world),64)
        self.assertEqual(world[8*32+8:8*32+16],bytes([5])*8)
        self.assertEqual(anchor(396,1236,240),(48,156))
        self.assertEqual(anchor(396,1236,242),(48,151))
        self.assertIsNone(anchor(396,1236,241))
        self.assertEqual(ring_index(48,156),((156-10)&31)*32+((48-3)&31))

    def test_matrix_covers_resource_edges_tile_wrap_and_complete_stun_recovery(self):
        flags=list(range(240,252));cases=cases_for(flags)
        self.assertEqual(len(cases),len(set(cases)))
        self.assertEqual({c[0] for c in cases},{0,1,2})
        self.assertEqual({c[4] for c in cases if c[0]==0},{0,1,2,9,10,11,12,60})
        self.assertEqual({c[9] for c in cases if c[0]==2},{128,129,188,189,190,197,198,255})
        self.assertTrue(all(any(c[0]==0 and c[8]==f and c[11]==phase and c[13]==edge
            for c in cases) for f in flags for phase in range(8) for edge in (0,248)))
        self.assertTrue(all(any(c[0]==1 and c[8]==f and c[15:]==(age,dx,dy)
            for c in cases) for f in flags for age in (0,1,2,4,135,136) for dx in range(3) for dy in range(3)))
        self.assertEqual(RECORD,2086)

    def test_smoke_relocation_guards_buffers_and_animation_table_without_rom_data(self):
        program=bytearray(16384)
        program[0xafd:0xb01]=bytes((0xd7,0,0x20,5))
        program[0x1045:0x1047]=bytes((0x26,0x21))
        program[0x1027:0x1029]=bytes((0xf6,0x8c))
        program[0x188:0x18b]=bytes((0x21,0x3a,0x25))
        listing='ld hl,0253ah ;0188 21 3a 25 \n'
        linked,_=relocate(bytes(program),listing,fuel=True,enemies=True,smoke=True)
        self.assertEqual(linked[0x1046],0x39)
        self.assertEqual(linked[0x1028],0xec)
        self.assertEqual(linked[0x189:0x18b],bytes((0x3a,0xa5)))
        program[0x1c9:0x1cc]=bytes((6,3,0x54))
        program[0x1a0:0x1a4]=bytes((0xdd,0x36,0x15,0))
        linked,_=relocate(bytes(program),listing,fuel=True,enemies=True,smoke=True,smoke_notify=True)
        self.assertEqual(linked[0x1c9:0x1cc],bytes((0xcd,0xb0,0xc7)))
        self.assertEqual(linked[0x1a0:0x1a4],bytes((0xcd,0xb3,0xc7,0)))
        program[0x1046]=0x20
        with self.assertRaisesRegex(ValueError,'tile-buffer addressing changed'):
            relocate(bytes(program),listing,fuel=True,enemies=True,smoke=True)
        with self.assertRaisesRegex(ValueError,'requires fuel and enemy'):
            relocate(bytes(program),listing,smoke=True)

    def test_parameter_page_store_is_guarded_and_rom_pointer_is_relocated(self):
        program=bytearray(16384)
        program[0x1b2f:0x1b34]=bytes((0xf6,0x30,0x32,0x8f,0x82))
        program[0x1b34:0x1b36]=bytes((0xd6,0x23))
        program[0x1b8f:0x1b92]=bytes((0x21,0xdd,0x23))
        listing='ld hl,023ddh ;1b8f 21 dd 23 \n'
        linked,patches=relocate(bytes(program),listing,parameters=True)
        self.assertEqual(linked[0x1b90:0x1b92],bytes((0xdd,0xa3)))
        self.assertEqual(linked[0x1b34:0x1b36],program[0x1b34:0x1b36])
        self.assertTrue(any(p.get('kind')=='terrain-page-store-only-relocation' for p in patches))
        program[0x1b30]=0x31
        with self.assertRaisesRegex(ValueError,'terrain-page instruction changed'):
            relocate(bytes(program),listing,parameters=True)
