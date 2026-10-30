import unittest

from src.toolchain.msx.native_scanout import compose
from src.toolchain.msx.raster_scroll import palette_rgb


class NativeScanoutTests(unittest.TestCase):
    def inputs(self):
        vram, hud = bytearray(131072), bytearray(1140)
        hud[0x100] = 216
        palette = bytes(v for n in range(16) for v in ((n & 7)*16, (n >> 1) & 7))
        return vram, hud, palette

    def test_bitmap_wraps_within_one_page_and_preserves_the_complete_border(self):
        vram, hud, palette = self.inputs()
        vram[:32768] = b'\x11'*32768
        vram[32768:65536] = b'\x22'*32768
        hud[0x1a] = 31
        image = compose(bytes(vram), bytes(hud), 0, palette, bytes(48), bytes(48))
        colors = palette_rgb(palette)
        self.assertEqual(image.size, (320, 240))
        # The useful picture starts four pixels inside the nominal active area.
        self.assertEqual(image.getpixel((35, 25)), colors[0])
        self.assertEqual(image.getpixel((36, 25)), colors[1])
        self.assertEqual(image.getpixel((283, 25)), colors[1])
        self.assertEqual(image.getpixel((284, 25)), colors[0])

    def test_first_sprite_wins_and_transparent_slots_still_count_towards_eight(self):
        vram, hud, palette = self.inputs()
        for slot in range(9):
            hud[0x100+slot*4:0x104+slot*4] = bytes((19, 16, slot*4, 0))
            vram[0x1f800+slot*32] = 128
        hud[0x100+9*4] = 216
        vram[0x1f400], vram[0x1f410] = 1, 2
        image = compose(bytes(vram), bytes(hud), 0, palette, bytes(48), bytes(48))
        self.assertEqual(image.getpixel((44, 34)), palette_rgb(palette)[1])
        vram[0x1f400:0x1f480] = bytes(128)
        vram[0x1f480] = 2
        image = compose(bytes(vram), bytes(hud), 0, palette, bytes(48), bytes(48))
        self.assertEqual(image.getpixel((44, 34)), palette_rgb(palette)[0])


if __name__ == '__main__':
    unittest.main()
