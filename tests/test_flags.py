"""Synthetic flag pointer/order and compact atlas ownership contracts."""
import unittest
from src.toolchain.msx.flags import records,encode_owners
from src.toolchain.msx.flags_verify import analyze


class FlagTests(unittest.TestCase):
    def test_original_mutation_oracle_detects_repeat_collection_and_wrong_kind(self):
        records=[dict(kind=k) for k in [1]*8+[4,2]]
        active=[0,0]+[1]*9;board=[0]+[f['kind'] for f in records[1:]]
        original=bytes([1]+active+board+[0]+active+board+[1]+active+board)
        cases=[(0x9821,0,0,r) for r in (1,0,1)]
        rows=[[i,1,1,1]+active+[100] for i in range(3)]
        self.assertEqual(analyze(cases,records,original,rows)['collection_events'],2)
        rows[1][1]=2
        with self.assertRaises(ValueError):analyze(cases,records,original,rows)
    def test_original_order_preserves_kind_and_maps_to_existing_hud_slots(self):
        video=bytearray(4096);cells=bytearray(1792)
        video[0x992:0x994]=(0x8100).to_bytes(2,'little')
        addresses=[0x9820+i*33 for i in reversed(range(10))]
        for i,a in enumerate(addresses):
            video[0x100+i*2:0x102+i*2]=a.to_bytes(2,'little')
            cells[a-0x9800]=1 if i<8 else (4 if i==8 else 2)
        flags=records(video,cells)
        self.assertEqual([f['hud_slot'] for f in flags],list(reversed(range(10))))
        self.assertEqual([f['kind'] for f in flags],[1]*8+[4,2])
        video[0x100:0x102]=video[0x102:0x104]
        with self.assertRaises(ValueError):records(video,cells)

    def test_marker_recovers_every_source_row_and_slot_without_changing_other_tiles(self):
        raw=bytes(v for i in range(32768) for v in (i%32*8,16+(i%2)*8))
        flags=[dict(tile_x=i*3,tile_y=1) for i in range(10)]
        banks=encode_owners([raw[i:i+16384] for i in range(0,65536,16384)],flags)
        encoded=b''.join(banks)
        marked=set()
        for owner,f in enumerate(flags,1):
            for y in range(3):
                for x in range(3):
                    at=(f['tile_y']+y)*256+(f['tile_x']+x)*2;marked.add(at)
                    sx,sy=encoded[at:at+2]
                    self.assertEqual((sx&1,sy>>4),(1,owner))
                    self.assertEqual((sx&254,(sy&15)|16),tuple(raw[at:at+2]))
        self.assertEqual(len(marked),90)
        self.assertTrue(all(encoded[i:i+2]==raw[i:i+2] for i in range(0,65536,2) if i not in marked))
