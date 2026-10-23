"""Synthetic color adaptation and both-page/four-group cache contracts."""
import unittest
from scripts.msx.tilemap import encode,CacheDecoder


def palette():
    colors=[(0,0),(0,0),(0x77,7),(0x70,0)]+[(i,i%8) for i in range(4,16)]
    return bytes(v for pair in colors for v in pair)


class TileMapTests(unittest.TestCase):
    def test_two_color_rows_are_exact_and_only_the_minority_pixel_is_adapted(self):
        world=bytes((1,1,1,1,2,2,2,3))+bytes([2])*56
        data=encode(world,palette(),width=8,height=8)
        self.assertEqual(data['changed_pixels'],1)
        self.assertEqual(data['world'],bytes((1,1,1,1,2,2,2,1))+world[8:])
        for row in range(8):
            ink=data['colors'][row];bits=data['patterns'][row]
            decoded=bytes(ink>>4 if bits&(128>>x) else ink&15 for x in range(8))
            self.assertEqual(decoded,data['world'][row*8:row*8+8])
        self.assertEqual(data['patterns'][:2048]*4,data['patterns'])
        self.assertEqual(data['colors'][:2048]*4,data['colors'])

    def test_cache_decoder_covers_both_pages_and_the_fourth_vertical_group(self):
        world=bytes([1])*8+bytes([2])*8
        world*=8
        data=encode(world,palette(),width=16,height=8)
        self.assertEqual((data['tiles'],data['changed_pixels']),(2,0))
        vram=bytearray(65536);vram[:8192]=data['patterns'];vram[0x4000:0x6000]=data['colors']
        vram[0x2000+7*32+31]=1
        vram[0xa000+31*32]=1
        decoder=CacheDecoder(data['patterns'],data['colors']);image=decoder.decode(vram)
        for y in range(8):
            self.assertEqual(image[(56+y)*128+31*4:(56+y)*128+32*4],bytes([0x22])*4)
            self.assertEqual(image[32768+(248+y)*128:32768+(248+y)*128+4],bytes([0x22])*4)
        vram[0xa000+31*32]=0;image=decoder.decode(vram)
        self.assertEqual(image[32768+248*128:32768+248*128+4],bytes([0x11])*4)
        vram[0x4000]^=1
        with self.assertRaisesRegex(ValueError,'tables changed'):decoder.decode(vram)

    def test_partial_tiles_and_pattern_overflow_are_rejected(self):
        with self.assertRaises(ValueError):encode(bytes(63),palette(),width=8,height=8)
