"""Synthetic invariants for graphics aliases and cold fragment relocation."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import unittest

from hud_programs import compile_packet
from rom_pack import BANK_BYTES, free_ranges, pack_transfers, pack_replay
from rom_pack_verify import cold_records


class GraphicsPacking(unittest.TestCase):
    def test_same_bank_alias_removes_literals_and_keeps_transfer_instructions(self):
        packet=bytes((0,3,20))+bytes(range(20))+bytes(3)
        inline,old_relocs=compile_packet(packet,0x8000,back_address=0xc027,packed8=True)
        alias,relocs=compile_packet(packet,0x8000,back_address=0xc027,packed8=True,
                                   source_tables=[(0x300,0x8500,bytes(range(20)))])
        self.assertEqual(len(inline)-len(alias),20)
        self.assertEqual(relocs,old_relocs)
        # The source operand is the only changed instruction operand.
        at=inline.index(b'\xfb\x21')+2
        self.assertEqual(inline[:at],alias[:at])
        self.assertEqual(inline[at+2:len(alias)],alias[at+2:])
        self.assertEqual(alias[at:at+2],b'\0\x85')

    def test_alias_rejects_missing_mismatched_and_cross_bank_sources(self):
        packet=bytes((0,3,3))+b'ABC'+bytes(3)
        for tables in ([],[(0x300,0x8500,b'ABD')],[(0x300,0xbfff,b'ABC')]):
            with self.subTest(tables=tables),self.assertRaises(ValueError):
                compile_packet(packet,0x8000,packed8=True,source_tables=tables)

    def test_packer_preserves_protected_bytes_and_has_no_slow_fallback(self):
        image=bytearray(b'\xff'*BANK_BYTES)
        image[0x100:0x103]=b'ABC'
        before=bytes(image)
        packet=bytes((0,3,3))+b'ABC'+bytes(3)
        holes=free_ranges([(0,0x200),(0x300,BANK_BYTES)])
        pointers,relocs,used=pack_transfers(image,1,[packet,packet],[(0x300,0x8100,b'ABC')],holes)
        self.assertEqual(len(pointers),1)
        self.assertEqual(image[:0x200],before[:0x200])
        self.assertEqual(image[0x300:],before[0x300:])
        self.assertTrue(all(0x200<=r['offset']<0x300 for r in relocs))
        self.assertGreater(used,0)
        with self.assertRaises(ValueError):
            pack_transfers(image,1,[packet],[(0x300,0x8100,b'ABC')],[[0x200,0x201]])
        for holes in ([[0,0x200]],[[0x200,BANK_BYTES+1]],[[0x200,0x250],[0x240,0x300]]):
            with self.subTest(holes=holes),self.assertRaises(ValueError):
                pack_transfers(image,1,[packet],[(0x300,0x8100,b'ABC')],holes)


class ColdPacking(unittest.TestCase):
    def test_chain_and_literal_addresses_relocate_and_preserve_frame_entries(self):
        image=bytearray(b'\xff'*(2*BANK_BYTES))
        command=bytes((1,10,0,8))+b'abcdefgh'
        records=[dict(data=command+command+b'\0'),dict(data=command+b'\0')]
        pointers,report=pack_replay(records,image,[(1,100,124),(2,200,224)])
        self.assertEqual(pointers,{0:(1,0x8064),1:(2,0x80c8)})
        self.assertEqual(report['literal_reuses'],1)
        self.assertEqual(report['chains'],1)
        self.assertEqual(image[112:118],bytes((4,10,0,8,104,128)))
        self.assertEqual(image[119:123],bytes((3,2,200,128)))
        self.assertEqual(image[BANK_BYTES+200:BANK_BYTES+213],command+b'\0')
        self.assertEqual(image[:100],b'\xff'*100)
        resident=bytearray(BANK_BYTES)
        for i,(bank,address) in pointers.items():
            resident[0x1000+i*5:0x1005+i*5]=bytes((bank,address&255,address>>8,i,0))
        decoded=cold_records(dict(rom=resident+image,session={'banks':{'SESSION_BOOT_BANK':0}},boot={'frame_count':2}))
        self.assertEqual(decoded,[(0,[(10,b'abcdefgh')]*2),(1,[(10,b'abcdefgh')])])

    def test_independent_replay_decoder_rejects_cyclic_and_out_of_bank_pointers(self):
        rom=bytearray(2*BANK_BYTES)
        rom[0x1000:0x1005]=bytes((1,0,128,0,0))
        bundle=dict(rom=rom,session={'banks':{'SESSION_BOOT_BANK':0}},boot={'frame_count':1})
        rom[BANK_BYTES:BANK_BYTES+4]=bytes((3,1,0,128))
        with self.assertRaises(ValueError):cold_records(bundle)
        rom[BANK_BYTES:BANK_BYTES+7]=bytes((4,0,0,4,255,191,0))
        with self.assertRaises(ValueError):cold_records(bundle)

    def test_overflow_malformed_commands_and_overlapping_holes_are_rejected(self):
        image=bytearray(b'\xff'*BANK_BYTES)
        for records,holes in (([dict(data=b'\0')],[(1,0,4)]),
                              ([dict(data=b'\x01\0')],[(1,0,100)]),
                              ([dict(data=bytes((2,0,0,1,0)))],[(1,0,100)]),
                              ([dict(data=b'\0')],[(1,0,10),(1,5,20)])):
            with self.subTest(records=records,holes=holes),self.assertRaises(ValueError):
                pack_replay(records,image,holes)


if __name__=='__main__':
    unittest.main()
