"""Synthetic bounds, source-event and executable-closure tests; no game payload."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mapper512_integrate import put,compile_packets,verify_closures,common_free_regions
from mapper512_backend import suffix_windows
from compact_transfer import optimize,events


class Mapper512Integration(unittest.TestCase):
    def test_common_holes_use_all_families_and_never_cross_physical_banks(self):
        a=bytearray(32);b=bytearray(32)
        a[3]=1;b[4]=1;a[25]=1
        self.assertEqual(common_free_regions([a,b],16),[(0,0,3),(0,5,11),(1,0,9),(1,10,6)])

    def test_invalid_live_mask_shapes_are_rejected(self):
        for masks in [[],[bytes(31)],[bytes(32),bytes(16)]]:
            with self.assertRaises(ValueError):common_free_regions(masks,16)
        for size in [0,-16]:
            with self.assertRaises(ValueError):common_free_regions([bytes(32)],size)

    def test_declared_live_bytes_cannot_alias_even_when_both_payloads_are_ff(self):
        data=bytearray(b'\xff'*32);busy=bytearray(32)
        put(data,busy,4,b'\xff'*8)
        with self.assertRaises(ValueError):put(data,busy,8,b'\xff'*8)
        put(data,busy,12,b'\0'*4)
        self.assertEqual(sum(busy),12)

    def test_field_bounds_reject_negative_or_overflow_without_mutation(self):
        data=bytearray(32);busy=bytearray(32)
        for at,value in [(-1,b'x'),(32,b'x'),(31,b'xx')]:
            with self.assertRaises(ValueError):put(data,busy,at,value)
        self.assertEqual(data,bytearray(32));self.assertEqual(sum(busy),0)

    def test_edge_name_alignment_preserves_ordered_pixels_controls_and_b(self):
        raw=bytearray(4096);raw[0xa00:0xa02]=b'\1\1';record=dict(kind='edge',data=raw)
        header=bytes.fromhex('0e98 f3 3a27c0 f600 d399 3e8e d399 3e10 d399 3e43 d399 fb')
        code=header+b'\x21\0\x82'+b'\xed\xa3'*3+b'\x21\0\x84'+b'\xed\xa3'*3+b'\xc3\0\xd0'
        baseline,_=optimize(code);case=dict(record=0,code=code,baseline=baseline,writes=True)
        compile_packets([case],[record])
        full=header[:14]+case['hot'];writes,_,b=events(full)
        self.assertEqual([v[1] for v in writes if v[0]=='data'],list(range(0x8040,0x8043))+list(range(0x8240,0x8243)))
        self.assertEqual(b,events(baseline)[2])

    def test_linked_closures_have_exact_paths_and_corrupted_jumps_are_rejected(self):
        programs=[b'\x3e'+bytes([i])+b'\xed\xa3'*9+b'\xc3\0\xd0' for i in range(20)]
        windows=suffix_windows(programs,limit=160,exit_address=0xd180)
        self.assertEqual(verify_closures(windows,0xd180),20)
        window=windows[0];image=bytearray(window['data'])
        at=next(i for i in range(len(image)-2) if image[i:i+3]==b'\xc3\x80\xd1')
        image[at+1:at+3]=b'\0\x30';window['data']=bytes(image)
        with self.assertRaises(AssertionError):verify_closures(windows,0xd180)


if __name__=='__main__':unittest.main()
