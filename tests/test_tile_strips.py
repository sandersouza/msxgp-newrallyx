"""Independent pixel decoding of exact three-tile lookup/atlas contracts."""
import unittest
from src.toolchain.msx.tile_strips import encode,candidates,encode_cells


class TileStripTests(unittest.TestCase):
    def test_extra_object_cells_retain_exact_pixels_and_deduplicate(self):
        image=bytes((x*y+x//3+y//5)%16 for y in range(24) for x in range(24))
        data=encode_cells(bytes(24*24),width=24,height=24,extra_cells=(image,image))
        self.assertEqual(data['unique'],2)
        self.assertEqual(data['extra_sources'][:2],data['extra_sources'][2:])
        sx,sy=data['extra_sources'][:2];sy=(sy-data['vram']//128)%256
        actual=bytes((data['pixels'][(sy+y)*128+(sx+x)//2]>>(0 if (sx+x)&1 else 4))&15
            for y in range(24) for x in range(24))
        self.assertEqual(actual,image)

    def test_complete_cells_reconstruct_every_synthetic_source_pixel(self):
        width,height=96,72
        world=bytes((x//5+y//7+x*y)%16 for y in range(height) for x in range(width))
        data=encode_cells(world,width=width,height=height)
        origin=data['vram']//128
        for y in range(0,height,24):
            for x in range(0,width,24):
                at=y//24*128+x//24*2
                sx,sy=data['table'][at:at+2];sy=(sy-origin)%256
                actual=(bytes([data['table'][at+1]&15])*576 if sx==1 else
                    bytes((data['pixels'][(sy+r)*128+(sx+c)//2]>>(0 if (sx+c)&1 else 4))&15
                        for r in range(24) for c in range(24)))
                expected=b''.join(world[(y+r)*width+x:(y+r)*width+x+24] for r in range(24))
                self.assertEqual(actual,expected)

    def test_uniform_complete_cells_use_their_exact_packed_fill_color(self):
        world=bytes(color for y in range(24) for color in range(16) for x in range(24))
        data=encode_cells(world,width=384,height=24)
        for color in range(16):self.assertEqual(data['table'][color*2:color*2+2],bytes((1,color*17)))

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

    def test_overlapping_two_cell_strips_reconstruct_every_source_pixel(self):
        width=height=96
        world=bytes((x//7+y//11+x*y)%16 for y in range(height) for x in range(width))
        for axis,data in encode(world,width=width,height=height,origins=(584,792),cells=2).items():
            tw,th=(48,8) if axis=='horizontal' else (8,48)
            dx,dy=(24,8) if axis=='horizontal' else (8,24)
            stride=128 if axis=='horizontal' else 256
            origin=data['vram']//128
            for y in range(0,height-th+1,dy):
                for x in range(0,width-tw+1,dx):
                    at=y//dy*stride+x//dx*2;sx,sy=data['table'][at:at+2]
                    sy=(sy-origin)%256
                    actual=bytes((data['pixels'][(sy+r)*128+(sx+c)//2]>>(0 if (sx+c)&1 else 4))&15
                        for r in range(th) for c in range(tw))
                    expected=b''.join(world[(y+r)*width+x:(y+r)*width+x+tw] for r in range(th))
                    self.assertEqual(actual,expected)

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
