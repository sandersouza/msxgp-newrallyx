import unittest
from PIL import Image
from src.toolchain.scenes.bundle import Assets, Capture
from src.toolchain.scenes.render import render


def scene():
    palette=dict(rgb=[[i*7]*3 for i in range(32)],lookup=[i%16 for i in range(256)])
    pixels=dict(tiles=bytes(16384),sprites=bytes(16384),dots=bytes([3]*128))
    assets=Assets(pixels,palette,{}, {},'')
    ram=bytearray(4096); ram[0x800:]=bytes([0x40])*2048
    # Put all objects outside the visible rectangle.
    for i in range(0x14,0x20):
        ram[0x800+i]=0; ram[0x820+i]=0
    capture=Capture(dict(registers=dict(scroll_x=0,scroll_y=0,flip=0),shadow_factor=.6),
                    bytes(ram),bytes(16),Image.new('RGB',(288,224)))
    return assets,capture,ram


class RenderTests(unittest.TestCase):
    def test_asymmetric_tile_flips_origin_and_scroll(self):
        assets,capture,ram=scene()
        pixels=bytearray(assets.pixels['tiles']); pixels[64]=1; pixels[127]=2
        assets.pixels['tiles']=bytes(pixels)
        ram[0x440]=1
        for attr, points in [(0x40,[(3,0,1),(10,7,2)]),
                             (0,[(10,0,1),(3,7,2)]),
                             (0xc0,[(3,7,1),(10,0,2)]),
                             (0x80,[(10,7,1),(3,0,2)])]:
            ram[0xc40]=attr; capture.video=bytes(ram)
            frame=render(capture,assets)
            for x,y,index in points:
                self.assertEqual(frame.indices[y*288+x],index)
        capture.state['registers']['scroll_x']=255
        ram[0xc40]=0x40; capture.video=bytes(ram)
        self.assertEqual(render(capture,assets).indices[4],1)

    def test_foreground_addressing_and_priority(self):
        assets,capture,ram=scene()
        tiles=bytearray(assets.pixels['tiles']); tiles[64:128]=bytes([2]*64)
        assets.pixels['tiles']=bytes(tiles)
        ram[2*32+4]=1  # x=224 modulo 64 = 32 -> column 4
        ram[0x800+2*32+4]=0x60
        capture.video=bytes(ram)
        frame=render(capture,assets)
        self.assertEqual(frame.indices[224],2)
        self.assertEqual(frame.priority[224],1)
        self.assertEqual(frame.indices[223],0)

    def test_sprite_order_transparency_clipping_and_tile_priority(self):
        assets,capture,ram=scene()
        sprites=bytearray(assets.pixels['sprites'])
        sprites[256:512]=bytes([1]*256); sprites[512:768]=bytes([2]*256)
        assets.pixels['sprites']=bytes(sprites)
        for offset,code in [(0x1e,1),(0x1c,2)]:
            ram[offset]=code*4; ram[offset+1]=10
            ram[0x800+offset]=221; ram[0x801+offset]=0
        capture.video=bytes(ram)
        self.assertEqual(render(capture,assets).indices[4*288+10],1)
        ram[0x1e]=0 # transparent source index zero allows next sprite
        capture.video=bytes(ram)
        self.assertEqual(render(capture,assets).indices[4*288+10],2)
        ram[0xc41]=0x60 # high-priority tile at source x8..15,y16..23
        capture.video=bytes(ram)
        self.assertEqual(render(capture,assets).indices[4*288+11],0)

    def test_asymmetric_sprite_flips_and_high_x_bit(self):
        assets,capture,ram=scene()
        sprites=bytearray(assets.pixels['sprites']); sprites[256]=1; sprites[511]=2
        assets.pixels['sprites']=bytes(sprites)
        ram[0x1e]=4|3; ram[0x1f]=10; ram[0x81e]=221; ram[0x81f]=0
        capture.video=bytes(ram)
        frame=render(capture,assets)
        self.assertEqual(frame.indices[19*288+25],1)
        self.assertEqual(frame.indices[4*288+10],2)
        ram[0x81f]=0x80; capture.video=bytes(ram)
        self.assertEqual(render(capture,assets).indices[19*288+281],1)

    def test_dot_code_transparency_and_shadow_rounding(self):
        assets,capture,ram=scene()
        dots=bytearray(assets.pixels['dots']); dots[7*16]=0
        assets.pixels['dots']=bytes(dots)
        ram[0x834]=233; ram[0x34]=10
        capture.video=bytes(ram); capture.radar=bytes([0]*4+[1]+[0]*11)
        frame=render(capture,assets)
        self.assertEqual(frame.indices[4*288+10],16)
        self.assertEqual(frame.image.getpixel((10,4)),(67,67,67)) # floor(112*.6)
        self.assertEqual(frame.indices[4*288+11],0)

    def test_global_flip_background_and_foreground_clips(self):
        assets,capture,ram=scene()
        tiles=bytearray(assets.pixels['tiles']); tiles[64:128]=bytes([2]*64)
        assets.pixels['tiles']=bytes(tiles)
        ram[0x400+29*32+3]=1
        capture.video=bytes(ram); capture.state['registers']['flip']=1
        frame=render(capture,assets)
        self.assertEqual(frame.indices[260],2)
        self.assertEqual(frame.indices[63],0)

    def test_vertical_wrap_and_foreground_repeat(self):
        assets,capture,ram=scene()
        tiles=bytearray(assets.pixels['tiles']); tiles[64:128]=bytes([1]*64)
        assets.pixels['tiles']=bytes(tiles)
        ram[0x400]=1; ram[2*32]=1
        capture.state['registers']['scroll_y']=240
        capture.video=bytes(ram)
        frame=render(capture,assets)
        self.assertEqual(frame.indices[3],1) # native y16 + 240 wraps to row zero
        self.assertEqual(frame.indices[256],1) # repeated foreground column zero

    def test_lookup_transparency_uses_indirect_color_not_source_pen(self):
        assets,capture,ram=scene()
        # Sprite source pen zero is opaque; pen one maps to transparent index zero.
        assets.palette['lookup'][0]=5; assets.palette['lookup'][1]=0
        sprites=bytearray(assets.pixels['sprites']); sprites[256]=1
        assets.pixels['sprites']=bytes(sprites)
        ram[0x1e]=4; ram[0x1f]=10; ram[0x81e]=221; ram[0x81f]=0
        capture.video=bytes(ram)
        frame=render(capture,assets)
        obj=next(o for o in frame.objects if o.kind=='sprite' and o.id==30)
        self.assertEqual(obj.colors[:2],bytes([255,5]))

    def test_dot_over_sprite_pen_table_override_and_repeat_shadow(self):
        assets,capture,ram=scene()
        sprites=bytearray(assets.pixels['sprites']); sprites[256:512]=bytes([1]*256)
        assets.pixels['sprites']=bytes(sprites)
        dots=bytearray(assets.pixels['dots']); dots[7*16]=0
        assets.pixels['dots']=bytes(dots)
        assets.palette['lookup'][21]=9 # pen 5 shadows to pen 21, not RGB scaling
        ram[0x1e]=4; ram[0x1f]=10; ram[0x81e]=221; ram[0x81f]=1
        radar=bytearray(16)
        for offset in (0x14,0x15):
            ram[0x20+offset]=10; ram[0x820+offset]=233; radar[offset&15]=1
        capture.video=bytes(ram); capture.radar=bytes(radar)
        frame=render(capture,assets)
        self.assertEqual(frame.indices[4*288+10],9)
        self.assertEqual(frame.shadow[4*288+10],0)
        self.assertEqual(frame.image.getpixel((10,4)),(63,63,63))
