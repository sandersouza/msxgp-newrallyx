"""Authored object-placement fixtures; no original payloads."""
import unittest
from scripts.msx.round_objects import owners, at


class RoundObjectsTests(unittest.TestCase):
    def seed(self, relocated=False):
        video = bytearray(4096); base = 0xe000 if relocated else 0x8000
        video[0x992:0x994] = (base+0x100).to_bytes(2,'little')
        video[0x996:0x998] = (base+0x140).to_bytes(2,'little')
        for i,cell in enumerate((0,1,30,31,32,33,1023,1024,1790,1791)):
            video[0x100+i*2:0x102+i*2] = (0x9800+cell).to_bytes(2,'little')
        video[0x251] = 2
        video[0x140:0x144] = (0x9802).to_bytes(2,'little')+(0x9e00).to_bytes(2,'little')
        return video

    def test_both_nibbles_and_extreme_rows_preserve_source_identifiers(self):
        packed = owners(self.seed())
        self.assertEqual(len(packed),896)
        self.assertEqual(packed[:2], bytes((0x21,0x0f)))
        self.assertEqual([at(packed,c) for c in (0,1,2,3,1790,1791)], [1,2,15,0,9,10])
        self.assertEqual(owners(self.seed(True), relocated=True), packed)

    def test_rejects_overlap_bad_pointers_and_outside_cells(self):
        video = self.seed(); video[0x140:0x142] = (0x9800).to_bytes(2,'little')
        with self.assertRaisesRegex(ValueError, 'overlaps'): owners(video)
        video = self.seed(); video[0x100:0x102] = (0x9f00).to_bytes(2,'little')
        with self.assertRaisesRegex(ValueError, 'leaves'): owners(video)
        video = self.seed(); video[0x992:0x994] = (0x7fff).to_bytes(2,'little')
        with self.assertRaisesRegex(ValueError, 'table'): owners(video)
        with self.assertRaises(ValueError): at(bytes(896),1792)
