"""Synthetic transfer/codec tests for the read-only size audit."""
import unittest

from hud_programs import compile_packet
from rom_audit import (BANK_BYTES, decode_transfer, free_ranges, place_code,
                       verify_literal_aliases, replay_commands, pack_replay_model)

EXIT = 0x4444
TRANSFER = 0x5555


def emitted(rom,bank,address,packet):
    data,relocations=compile_packet(packet,address,packed8=True,back_address=0xc027)
    data=bytearray(data)
    for at,name in relocations:
        data[at:at+2]=(EXIT if name=='hud_upload.done' else TRANSFER).to_bytes(2,'little')
    begin=bank*BANK_BYTES+address-0x8000
    rom[begin:begin+len(data)]=data
    return decode_transfer(rom,bank,address,exit_address=EXIT,transfer_address=TRANSFER)


class TransferAuditTests(unittest.TestCase):
    def packet(self):
        return bytes((0,3,5))+b'abcde'+bytes((0,0x43,20))+bytes(range(20))+bytes(3)

    def test_relocation_normalization_and_literal_accounting(self):
        rom=bytearray(b'\xff'*(3*BANK_BYTES))
        first=emitted(rom,1,0x8000,self.packet())
        second=emitted(rom,2,0x8100,self.packet())
        self.assertEqual(first['normalized_sha256'],second['normalized_sha256'])
        self.assertEqual(first['literal_bytes'],25)
        self.assertEqual(first['total_bytes'],first['code_bytes']+25)
        self.assertEqual([s['destination'] for s in first['literal_spans']],[0x300,0x2300])
        self.assertEqual(first['estimated_instruction_cycles'],second['estimated_instruction_cycles'])

    def test_raw_table_reuse_is_byte_exact_and_rejects_wrong_table(self):
        rom=bytearray(b'\xff'*(3*BANK_BYTES))
        program=emitted(rom,1,0x8000,self.packet())
        rom[2*BANK_BYTES+0x100:2*BANK_BYTES+0x105]=b'abcde'
        rom[2*BANK_BYTES+0x500:2*BANK_BYTES+0x514]=bytes(range(20))
        ranges=((0x300,0x100,5),(0x2300,0x500,20))
        self.assertEqual(verify_literal_aliases(rom,program,2,ranges),25)
        rom[2*BANK_BYTES+0x100]^=1
        with self.assertRaises(ValueError):verify_literal_aliases(rom,program,2,ranges)

    def test_unknown_opcode_and_bank_boundary_are_rejected(self):
        rom=bytearray(b'\xff'*(2*BANK_BYTES))
        emitted(rom,1,0x8000,self.packet())
        rom[BANK_BYTES+2]=0x76
        with self.assertRaises(ValueError):
            decode_transfer(rom,1,0x8000,exit_address=EXIT,transfer_address=TRANSFER)
        rom[-4:]=b'\x0e\x98\x3a\0'
        with self.assertRaises(ValueError):
            decode_transfer(rom,1,0xbffc,exit_address=EXIT,transfer_address=TRANSFER)

    def test_protected_ranges_and_unplaceable_code_are_preserved(self):
        self.assertEqual(free_ranges([(2,6),(4,8)],10),[[0,2],[8,10]])
        programs={1:dict(code_bytes=4),2:dict(code_bytes=5),3:dict(code_bytes=20)}
        gaps,spill,used=place_code(programs,[1,2,3],[[0,6],[10,16]])
        self.assertEqual(spill,[3])
        self.assertEqual(used,9)
        self.assertEqual(sum(end-start for start,end in gaps),3)


class ReplayAuditTests(unittest.TestCase):
    def test_raw_and_reused_literal_streams_have_equal_commands(self):
        rom=bytearray(2*BANK_BYTES)
        rom[0x1000:0x100a]=bytes((1,0,128,0,0,1,16,128,10,0))
        rom[BANK_BYTES:BANK_BYTES+8]=bytes((1,0,0,3))+b'ABC'+b'\0'
        rom[BANK_BYTES+16:BANK_BYTES+23]=bytes((4,0,0,3,4,128,0))
        result=replay_commands(rom,{'banks':{'SESSION_BOOT_BANK':0}},
                               {'frame_count':2,'unshared_stream_bytes':16,'compressed_bytes':15})
        self.assertEqual(result['records'][0],result['records'][1])
        self.assertEqual(result['banks'],[1])

    def test_cyclic_replay_chain_is_rejected(self):
        rom=bytearray(2*BANK_BYTES)
        rom[0x1000:0x1005]=bytes((1,0,128,0,0))
        rom[BANK_BYTES:BANK_BYTES+4]=bytes((3,1,0,128))
        with self.assertRaises(ValueError):
            replay_commands(rom,{'banks':{'SESSION_BOOT_BANK':0}},
                            {'frame_count':1,'unshared_stream_bytes':0,'compressed_bytes':0})

    def test_repacking_resets_bank_local_reuse_and_reports_overflow(self):
        records=[[(1,b'abcdefgh'),(1,b'abcdefgh'),(0,None)]]
        shared=pack_replay_model(records,[(1,0,24)])
        self.assertTrue(shared['fits'])
        self.assertEqual(shared['literal_reuses'],1)
        split=pack_replay_model(records,[(1,0,16),(2,0,16),(3,0,16)])
        self.assertTrue(split['fits'])
        self.assertEqual(split['literal_reuses'],0)
        self.assertEqual(split['chains'],2)
        self.assertFalse(pack_replay_model(records,[(1,0,16)])['fits'])


if __name__=='__main__':
    unittest.main()
