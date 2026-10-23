"""Synthetic boundary coverage and evidence integrity for the fuel oracle."""
import struct
import unittest
from scripts.msx.fuel_verify import cases_for,encode_case,compare,RECORD
from scripts.msx.player import relocate


class FuelTests(unittest.TestCase):
    def test_cases_cover_all_converter_branches_last_flag_and_full_depletion(self):
        cases=cases_for()
        self.assertEqual({c[1] for c in cases if c[0]==1},{2,5,9,13})
        self.assertTrue(any(c[0]==0 and c[2]==600 and c[8]>600*9+64 for c in cases))
        self.assertTrue(any(c[3]==10 for c in cases))
        self.assertTrue(any(not c[4] and c[0]==1 for c in cases))
        for c in cases:
            raw=encode_case(c)
            self.assertEqual(len(raw),28)
            self.assertEqual(raw[2]+raw[3]*10,c[2])

    def test_trace_requires_complete_consecutive_matching_cases(self):
        r=struct.pack('<HH',0,0)+bytes(RECORD-5)+bytes((1,))
        self.assertEqual(compare([None],r,r),1)
        for original,actual in ((b'',b''),(r,r[:-1]),(r[:-1]+b'\0',r[:-1]+b'\0'),
                                (struct.pack('<HH',0,1)+r[4:],struct.pack('<HH',0,1)+r[4:]),
                                (r,r[:-2]+b'\1\1')):
            with self.assertRaises(ValueError):compare([None],original,actual)

    def test_fuel_linker_relocates_native_ram_and_both_gauge_tables(self):
        rom=bytearray(16384)
        rom[0x1ecc:0x1ecf]=bytes((0x3a,0x21,0x80))
        rom[0x1eec:0x1eef]=bytes((0x21,0x6f,0x22))
        rom[0x1ef3:0x1ef6]=bytes((0x21,0x77,0x22))
        rom[0x226f:0x227f]=bytes(range(16))
        listing='ld a,(08021h) ;1ecc 3a 21 80 \nld hl,0226fh ;1eec 21 6f 22 \nld hl,02277h ;1ef3 21 77 22 '
        plain,_=relocate(bytes(rom),listing)
        actual,_=relocate(bytes(rom),listing,fuel=True)
        self.assertEqual(plain[0x1ecc:0x1ecf],b'\xff'*3)
        self.assertEqual(actual[0x1ecc:0x1ecf],bytes((0x3a,0x21,0xe0)))
        self.assertEqual(actual[0x1eec:0x1eef],bytes((0x21,0x6f,0xa2)))
        self.assertEqual(actual[0x1ef3:0x1ef6],bytes((0x21,0x77,0xa2)))
        self.assertEqual(actual[0x226f:0x227f],bytes(range(16)))
