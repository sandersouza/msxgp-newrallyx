"""Synthetic transfer/atlas/capacity regressions, with no contributor bytes."""
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from compact_transfer import optimize,events,old_long_cycles,exact_long_cycles
from compact_boot_atlas import prepare
from megaram_package import capacity


class Transfers(unittest.TestCase):
    def test_mixed_program_preserves_operations_and_bounded_cost(self):
        for n in range(16,256):
            # Both source-byte specializations and known post-copy pointers.
            code=b'\xf3\x0e\x98\x21\x00\x80'+bytes((6,n,0xcd,0x12,0x34))
            code+=b'\x21'+(0x8000+n).to_bytes(2,'little')+b'\xed\xa3'*7
            code+=b'\x21'+(0x8107+n).to_bytes(2,'little')+b'\xed\xa3'*2+b'\xfb\xc3\x78\x56'
            compact,report=optimize(code)
            self.assertEqual(events(code),events(compact))
            self.assertLessEqual(len(compact),len(code))
            self.assertGreaterEqual(report['cycles_saved'],0)
            self.assertGreater(old_long_cycles(n),exact_long_cycles(n))

    def test_first_source_load_is_required_and_bad_streams_rejected(self):
        code=b'\x21\x00\x80\xed\xa3\xc3\0\0'
        self.assertEqual(optimize(code)[0],code)
        for bad in [b'',b'\xed\xa0\xc3\0\0',b'\x21\0',b'\x06\x10\xc3\0\0',b'\xed\xa3\xc3\0\0']:
            with self.assertRaises(ValueError):optimize(bad)


class MegaCapacity(unittest.TestCase):
    def test_tier_boundaries_and_768_probe_expose_512_alias(self):
        for pages,kib in [(2,128),(16,128),(17,256),(32,256),(33,512),(64,512),(65,768),(93,768),(96,768),(97,1024),(128,1024)]:
            actual,middle,last=capacity(pages)
            self.assertEqual(actual,kib)
            self.assertLessEqual(pages*8,kib)
            self.assertEqual(last,kib//8-1)
            if kib==768:
                self.assertEqual(middle,64)
                self.assertEqual(middle%64,0)
                self.assertEqual(last%64,31)
        for pages in [0,1,129]:
            with self.assertRaises(ValueError):capacity(pages)


class BootAtlas(unittest.TestCase):
    def test_sparse_long_skips_repeat_strips_and_all_color_codecs(self):
        frames=[]
        for i in range(71):
            pixels=bytearray(27136)
            # Long skipped rows before the repeated strip caught a run-length
            # variable accidentally reused by skip-block encoding.
            y=96 if i%4<2 else 184
            for row in range(8):
                pixels[(y+row)*128:(y+row)*128+128]=bytes((0x11+(i//2%3)*0x11,))*128
                pixels[row*128:row*128+4]=bytes((0x12,0x21,0x12,0x21))
                pixels[row*128+4:row*128+8]=bytes((0x12,0x34,0x31,0x24))
                pixels[row*128+8:row*128+12]=bytes((0x12,0x34,0x56,0x78))
            frames.append(bytes(pixels))
        streams=[[(0,f,False)] for f in frames]
        with patch('renderer_image_build.replay',side_effect=streams):
            atlas=prepare(bytes(2*16384),{'banks':{'SESSION_BOOT_BANK':0}},
                {'hardware_status':{'descriptor_index':3,'rectangles':[[0,96,256,8]]}})
        report=atlas['report']
        self.assertEqual(report['frame_hashes'],[hashlib.sha256(f).hexdigest() for f in frames])
        self.assertTrue(report['all_dictionary_records_and_full_frames_exact'])
        self.assertGreater(report['repeat_strips'],0)
        self.assertEqual({p[0]>>6 for p in atlas['tiles']},{0,1,3})
        self.assertIn(b'\xff'+bytes((0x12,0x34,0x56,0x78))*8,atlas['tiles'])
        self.assertTrue(any((int.from_bytes(c[j:j+2],'little')&2047)==2047 for c in atlas['commands'] for j in range(2,len(c),2)))
        self.assertTrue(any((int.from_bytes(c[j:j+2],'little')&2047)==2046 for c in atlas['commands'] for j in range(2,len(c),2)))


if __name__=='__main__':unittest.main()
