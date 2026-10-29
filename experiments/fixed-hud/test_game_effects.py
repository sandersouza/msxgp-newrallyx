"""Synthetic contracts for the authorized effect-only color conversion."""
import unittest
from effect_codec import adapt


PALETTE=bytes(v for i in range(16) for v in (((i&7)<<4)|(i&7),i&7))


class Effects(unittest.TestCase):
    def test_two_color_rows_remain_exact(self):
        tile=bytes([1,2]*32)
        result,changed=adapt([tile],PALETTE)
        self.assertEqual(result,[tile])
        self.assertEqual(changed,0)

    def test_conversion_preserves_geometry_and_retained_source_colors(self):
        tile=bytes([1,1,1,1,2,2,2,3]*8)
        result,changed=adapt([tile],PALETTE)
        self.assertEqual(changed,8)
        self.assertEqual(len(result[0]),64)
        for y in range(8):self.assertEqual(set(result[0][y*8:y*8+8]),{1,2})

    def test_rejects_non_native_tile_dimensions(self):
        with self.assertRaises(ValueError):adapt([bytes(63)],bytes(32))
