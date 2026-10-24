"""Independent pixel decoding of exact three-tile lookup/atlas contracts."""
import unittest
from scripts.msx.tile_strips import encode,candidates


class TileStripTests(unittest.TestCase):
    def test_source_addresses_reconstruct_every_synthetic_strip(self):
        width=height=48
        world=bytes((x//3+y//5)%16 for y in range(height) for x in range(width))
        for axis,data in encode(world,width=width,height=height).items():
            tw,th=(24,8) if axis=='horizontal' else (8,24)
            stride=128 if axis=='horizontal' else 256
            origin=data['vram']//128
            for y in range(0,height,th):
                for x in range(0,width,tw):
                    at=y//th*stride+x//tw*2;sx,sy=data['table'][at:at+2]
                    sy=(sy-origin)%256
                    pixels=bytes((data['pixels'][(sy+row)*128+(sx+col)//2] >> (0 if (sx+col)&1 else 4))&15
                                 for row in range(th) for col in range(tw))
                    expected=b''.join(world[(y+row)*width+x:(y+row)*width+x+tw] for row in range(th))
                    self.assertEqual(pixels,expected)

    def test_partial_world_cells_are_rejected(self):
        with self.assertRaises(ValueError):encode(bytes(32*48),width=32,height=48)

    def test_candidate_tags_keep_uniform_fills_and_flag_owners_out_of_strips(self):
        data=bytearray(bytes((0x62,0))*32768)
        # One textured tile makes its horizontal and vertical cell mixed.
        data[256+2:256+4]=bytes((8,16))
        # A flag owner excludes both complete strips containing it.
        data[768+6:768+8]=bytes((17,0x38))
        banks=[bytes(data[i:i+16384]) for i in range(0,65536,16384)]
        tagged=b''.join(candidates(banks))
        self.assertEqual(tagged[256],0x66)
        self.assertEqual(tagged[3],1)
        self.assertEqual(tagged[0:2],bytes((0x62,0)))
        self.assertEqual(tagged[768+6:768+8],bytes((17,0x38)))
        self.assertEqual(tagged[768+4],0x62)
        # Metadata never changes the original solid color or source address.
        for at in range(0,len(data),2):
            self.assertEqual(tagged[at]&0xfb,data[at])
            self.assertEqual(tagged[at+1]&0xfe,data[at+1])

    def test_candidate_tags_reject_partial_address_tables(self):
        with self.assertRaises(ValueError):candidates([bytes(16384)])
