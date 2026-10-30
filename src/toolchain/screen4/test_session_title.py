"""Title layout contracts use synthetic glyphs rather than original ROM data."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import unittest
from PIL import Image
from session_title import compose,shift_reveal,import_logo,import_brand,CAPTION


class Title(unittest.TestCase):
    def test_layout_preserves_shifted_pixels_brand_and_footer_boundaries(self):
        pixels=bytearray([7])*(256*212)
        pixels[16*256+100]=2
        for letter in range(5):
            for y in range(8):
                for x in range(4):pixels[(200+y)*256+100+letter*6+x]=2
        font=bytes([0xf8]*2048)
        brand=bytes((x+y)%2 for y in range(10) for x in range(144))
        result,meta,patches=compose(pixels,font,dict(RED=2,WHITE=15,BLACK=0),(brand,144,10,57,199))
        self.assertEqual(result[8*256+100],2)
        self.assertEqual(meta['caption'],CAPTION)
        self.assertEqual(meta['brand'],'namco')
        self.assertEqual(meta['brand_y'],199)
        self.assertEqual(meta['brand_x'],57)
        self.assertEqual(meta['brand_width'],144)
        self.assertTrue(all(result[(199+y)*256+57+x]==(2 if brand[y*144+x] else 7) for y in range(10) for x in range(144)))
        self.assertEqual(meta['caption_y'],186)
        self.assertEqual(meta['shift_y'],-8)
        self.assertEqual(len(patches),2)
        allowed=set(meta['blink_pixels'])
        changed=set()
        for patch in patches:
            x,y,w,h=patch['rect']
            for i,(on,off) in enumerate(zip(patch['on'],patch['off'])):
                if on!=off:changed.add((y+i//w)*256+x+i%w)
        self.assertEqual(changed,allowed)
        self.assertTrue(changed)
        self.assertTrue(all(186<=p//256<194 for p in changed))

    def test_signature_keeps_every_native_pixel_and_four_pixel_bottom_margin(self):
        source=Image.new('RGBA',(56,8),(0,0,0,0))
        ink={(x,y) for y in range(8) for x in range(56) if (x+3*y)%7==0}
        for point in ink:source.putpixel(point,(200,0,0,255))
        mask,meta=import_brand(source)
        self.assertEqual((meta['x'],meta['y'],meta['width'],meta['height']),(100,200,56,8))
        self.assertEqual({(x,y) for y in range(8) for x in range(56) if mask[y*56+x]},ink)
        self.assertEqual(meta['source_size'],[56,8])
        self.assertEqual(212-meta['y']-meta['height'],4)

    def test_signature_never_silently_resizes_an_oversized_input(self):
        with self.assertRaises(ValueError):import_brand(Image.new('RGBA',(300,10)))

    def test_every_original_reveal_moves_exactly_eight_pixels(self):
        source='UI_CastReveal:\n    dw UI_Reveal0,6551\n    db 8,16,12\n    dw UI_Reveal1,21586\n    db 4,8,4\nUI_CastRevealEnd:\n'
        moved=shift_reveal(source)
        self.assertIn('UI_Reveal0,5527',moved)
        self.assertIn('UI_Reveal1,20562',moved)
        self.assertEqual(moved.count('db '),2)

    def test_logo_preserves_every_final_size_monochrome_pixel(self):
        source=Image.new('1',(54,20),0)
        ink={(x,y) for y in range(20) for x in range(54) if (x+3*y)%7==0}|{(0,0),(53,19)}
        for point in ink:source.putpixel(point,255)
        pixels,meta=import_logo(source,dict(WHITE=15,BLACK=0))
        self.assertEqual(meta['source_crop'],[0,0,54,20])
        self.assertEqual(meta['scale_divisor'],1)
        self.assertEqual(meta['rect'],[194,8,54,20])
        self.assertEqual(len(pixels),54*20)
        self.assertEqual({(x,y) for y in range(20) for x in range(54) if pixels[y*54+x]==15},ink)

    def test_logo_rejects_resizing_and_implicit_color_reduction(self):
        with self.assertRaisesRegex(ValueError,'54x20'):import_logo(Image.new('1',(162,60)),dict(WHITE=15,BLACK=0))
        with self.assertRaisesRegex(ValueError,'1-bit'):import_logo(Image.new('RGB',(54,20)),dict(WHITE=15,BLACK=0))


if __name__=='__main__':unittest.main()
