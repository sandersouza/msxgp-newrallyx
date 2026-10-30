"""Synthetic graph allocation protects coexistence and exact glyph identity."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import unittest
from hud_tile_layout import arrange


def payload(keys):
    return bytes(i%len(keys) for i in range(224))+b''.join(k[:8] for k in keys)+b''.join(k[8:] for k in keys)


class LayoutTests(unittest.TestCase):
    def test_shared_and_mutually_exclusive_tiles_reuse_slots(self):
        a,b,c=bytes([255])*8+bytes([0x11])*8,bytes(8)+bytes([0x22])*8,bytes([0x55])*8+bytes([0x33])*8
        result,groups,report=arrange([payload([a,b]),payload([a,c])],{'0':[],'1':[]})
        self.assertEqual(report['allocated_slots'],2)
        self.assertEqual(result[0][:224],result[1][:224])
        self.assertEqual(result[0][224:232]+result[0][240:248],a)
        self.assertEqual(groups,{'0':[],'1':[]})

    def test_coexisting_keys_never_alias_and_flag_ids_follow_mapping(self):
        keys=[bytes([i])*8+bytes([i*17])*8 for i in range(8)]
        variants={str(n):[dict(entry=0,slots=[0],ids=[96,97])] for n in range(2)}
        result,groups,report=arrange([payload(keys),payload(keys[::-1])],variants)
        self.assertEqual(report['allocated_slots'],8)
        for n,source in enumerate((keys,keys[::-1])):
            names=result[n][:224];self.assertEqual(len(set(names)),8)
            for old,key in enumerate(source):
                slot=names[old]
                self.assertEqual(result[n][224+slot*8:232+slot*8]+result[n][288+slot*8:296+slot*8],key)
            self.assertEqual(groups[str(n)][0]['ids'],[96+names[0],96+names[1]])
