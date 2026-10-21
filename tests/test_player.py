"""Synthetic relocation, color-combination and native coordinate contracts."""
import unittest
from scripts.msx.player import palette,relocate,coordinates,atlas
from scripts.msx.raster_scroll import palette_rgb
from scripts.msx.screen5 import rgb333


class PlayerTests(unittest.TestCase):
    def test_relocation_changes_addresses_but_retains_velocity_constants(self):
        program=bytearray(16384)
        records=((0x006f,b'\x2a\x69\x80','ld hl,(08069h)'),
                 (0x0072,b'\xcd\x3e\x0f','call 00f3eh'),
                 (0x1146,b'\x21\x80\xff','ld hl,0ff80h'),
                 (0x10de,b'\xfb','ei'))
        listing=[]
        for address,data,text in records:
            program[address:address+len(data)]=data
            listing.append(f'{text}\t;{address:04x}\t{data.hex(" ")}\t.')
        linked,_=relocate(bytes(program),'\n'.join(listing))
        self.assertEqual(linked[0x6f:0x75],b'\x2a\x69\xe0\xcd\x3e\x8f')
        self.assertEqual(linked[0x1146:0x1149],b'\x21\x80\xff')
        self.assertEqual(linked[0x10de],0x00)
        self.assertEqual(linked[0xc2c],0xc9)

    def test_two_sprite_planes_preserve_all_colors_without_changing_rgb(self):
        colors=[(i*16,i*8,i*4) for i in range(16)]
        colors[5]=(33,71,222);colors[13]=(255,255,151);colors[11]=(0,0,0)
        encoded=bytes(v for c in colors for r,g,b in [rgb333(c)] for v in (r<<4|b,g))
        changed,[pixels]=palette(encoded,[bytes(range(16))])
        before,after=palette_rgb(encoded),palette_rgb(changed)
        self.assertEqual([before[i] for i in range(16)],[after[i] for i in pixels])
        self.assertEqual(after[3],before[5]);self.assertEqual(after[9],before[13])
        self.assertEqual(after[3|9],before[11])

    def test_native_cells_and_signed_offsets_keep_world_coordinates(self):
        ram=bytearray(4096);ram[0x70]=15;ram[0x72]=50
        ram[0x6d]=255;ram[0x6f]=7
        self.assertEqual(coordinates(ram),(395,1229))

    def test_command_atlas_preserves_tile_pixels_and_row_addressing(self):
        world=bytearray(816*1392)
        for y in range(8):world[y*816:y*816+8]=bytes([1])*8
        graphics,banks,count=atlas(world)
        self.assertEqual(count,2)
        for y in range(8):self.assertEqual(graphics[y*128:y*128+4],bytes([0x11])*4)
        self.assertEqual(banks[0][0],0)
        self.assertEqual(banks[0][1],1)
        self.assertEqual(banks[1][0],1)
