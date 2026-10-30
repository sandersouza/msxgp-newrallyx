"""Synthetic startup stream contracts; no original arcade data."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import unittest
from session_boot import encode_delta,decode_delta,plan_frames,enabled

class BootStream(unittest.TestCase):
    def test_single_include_selects_both_resources_and_code(self):
        self.assertTrue(enabled('    INCLUDE "session-boot.inc"', '1'))
        self.assertFalse(enabled('; INCLUDE "session-boot.inc"', '1'))
        self.assertFalse(enabled('    INCLUDE "session-boot.inc"', '0'))
        self.assertFalse(enabled('', '1'))

    def test_sparse_delta_preserves_both_background_and_literal_zero(self):
        old=bytes([0x77])*27136
        new=bytearray(old)
        new[2:8]=bytes([0,1,2,3,4,5]);new[256:1024]=bytes([0x22])*768
        stream,cost=encode_delta(old,new)
        self.assertEqual(decode_delta(old,stream),bytes(new))
        self.assertLess(len(stream),60)
        self.assertGreater(cost,768*21)

    def test_unchanged_page_has_only_end_marker(self):
        stream,cost=encode_delta(bytes(27136),bytes(27136))
        self.assertEqual(stream,b'\0')
        self.assertEqual(decode_delta(bytes(27136),stream),bytes(27136))

    def test_forced_status_bytes_erase_runtime_digits_on_reused_page(self):
        old=bytes(27136)
        runtime=bytearray(old);runtime[512:520]=bytes([0x77])*8
        stream,_=encode_delta(old,old,force=range(512,520))
        self.assertEqual(decode_delta(bytes(runtime),stream),old)

    def test_planner_restores_both_pages_after_dynamic_status(self):
        blank=bytes(27136);first=bytearray(blank);first[100]=0x11
        last=bytearray(blank);last[200]=0x22
        frames=[blank]*10+[bytes(first)]*20+[bytes(last)]*30+[blank]*30
        plan=plan_frames(frames,len(frames),status_frames=range(10,30),status_bytes=range(512,520))
        pages=[blank,blank]
        for i,r in enumerate(plan):
            pages[i%2]=decode_delta(pages[i%2],r['data'])
            self.assertEqual(pages[i%2],frames[r['native_frame']])
            if r['native_frame'] in range(10,30):
                changed=bytearray(pages[i%2]);changed[512:520]=bytes([0x77])*8
                pages[i%2]=bytes(changed)

    def test_planner_keeps_original_deadlines_and_lossless_published_states(self):
        frames=[bytes([0])*27136 for _ in range(90)]
        frames[10:30]=[bytes([0x11])*27136]*20
        frames[30:]=[bytes([0x22])*27136]*60
        plan=plan_frames(frames,90)
        pages=[bytes(27136),bytes(27136)]
        last=-1
        for i,r in enumerate(plan):
            n=r['native_frame'];self.assertGreater(n,last);last=n
            pages[i%2]=decode_delta(pages[i%2],r['data'])
            self.assertEqual(pages[i%2],frames[n])
            self.assertEqual(r['tick'],round(n*59.922743063/ (2000/33)))
        self.assertEqual(plan[0]['native_frame'],0)
        self.assertGreaterEqual(plan[-1]['native_frame'],30)
        self.assertEqual(pages[(len(plan)-1)%2],frames[-1])

if __name__=='__main__':unittest.main()
