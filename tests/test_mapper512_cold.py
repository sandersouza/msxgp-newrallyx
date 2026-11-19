"""Synthetic memory-lifetime checks; no original game or OS bytes."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mapper512_cold import allocate_context


class ColdContext(unittest.TestCase):
    def test_reserved_bridge_is_excluded_and_os_source_never_crosses_a_page(self):
        rows=allocate_context([(11,0,16384),(12,0,16384),(30,0,16384)])
        self.assertEqual(sum(r[2] for r in rows),32768)
        for bank,offset,n,source in rows:
            self.assertTrue(source<16384 and source+n<=16384 or source>=0xc000 and source+n<=65536)
            if bank==30:self.assertTrue(offset+n<=0x1000 or offset>=0x3e40)

    def test_live_bytes_and_small_holes_are_not_counted_as_storage(self):
        with self.assertRaises(ValueError):allocate_context([(11,0,16384),(30,0x1000,0x2e40),(12,0,15)])

    def test_aliasing_and_invalid_declared_holes_are_rejected(self):
        for regions in [[(11,0,16384)]*2,[(32,0,16384)],[(11,-1,16384)],[(11,0,16385)]]:
            with self.assertRaises(ValueError):allocate_context(regions)

    def test_world_shadow_has_a_distinct_lifetime_and_logical_source_page(self):
        rows=allocate_context([(11,0,16384),(12,0,16384),(13,0,16384)],size=49152)
        self.assertEqual(rows,[(11,0,16384,0),(12,0,16384,0xc000),(13,0,16384,0)])

    def test_world_shadow_cannot_be_claimed_from_the_already_reserved_os_pages(self):
        with self.assertRaises(ValueError):allocate_context([(11,0,16384),(12,0,16384)],size=49152)


if __name__=='__main__':unittest.main()
