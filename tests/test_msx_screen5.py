"""Synthetic SCREEN 5 data only; no arcade ROMs or BIOS required."""
import unittest
from PIL import Image
from scripts.msx.screen5 import BITMAP_SIZE, LEVELS, convert, pack
from scripts.msx.emulator import tcl


class Screen5Tests(unittest.TestCase):
    def test_high_nibble_is_left_pixel_and_rows_are_128_bytes(self):
        indices=[0]*(256*212)
        indices[0:4]=[1,2,3,4]
        indices[256:258]=[14,15]
        data=pack(indices)
        self.assertEqual(len(data),BITMAP_SIZE)
        self.assertEqual(data[:2],b'\x12\x34')
        self.assertEqual(data[128],0xef)
        self.assertEqual(data[-1],0)

    def test_invalid_indices_and_dimensions_are_rejected(self):
        for indices in ([0], [16]*(256*212), [-1]*(256*212), [True]*(256*212)):
            with self.assertRaises(ValueError): pack(indices)
        with self.assertRaises(ValueError):
            convert([Image.new('RGB',(256,192))]*2)

    def test_common_palette_is_order_independent_and_correct_rbg_encoding(self):
        image=Image.new('RGB',(256,212),(255,0,0))
        image.putpixel((200,40),(0,255,255))
        other=Image.new('RGB',(256,212),(0,0,0))
        palette,scenes,colors=convert([image,other])
        reverse=convert([other,image])
        self.assertEqual(palette,reverse[0])
        self.assertEqual(len(palette),32)
        self.assertEqual(palette[:6],bytes([0,0,7,7,0x70,0]))
        self.assertEqual(scenes[0][0][40*128+100],0x12)
        self.assertEqual(scenes[0][1].getpixel((200,40)),(0,255,255))
        self.assertEqual(scenes[0][2]['max_channel_error'],0)
        self.assertEqual(LEVELS,(0,32,74,106,148,180,222,255))

    def test_quantization_collisions_and_palette_overflow_need_review(self):
        image=Image.new('RGB',(256,212))
        image.putpixel((1,0),(1,0,0))
        with self.assertRaisesRegex(ValueError,'merge'): convert([image,image])
        for i in range(17): image.putpixel((i,0),(i*15,0,0))
        with self.assertRaisesRegex(ValueError,'exceed'): convert([image,image])

    def test_tcl_paths_cannot_substitute_commands_or_variables(self):
        self.assertEqual(tcl('a $b [exit] "c"'), '"a \\$b \\[exit\\] \\"c\\""')


if __name__ == '__main__': unittest.main()
