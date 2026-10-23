"""Synthetic relocation, color-combination and native coordinate contracts."""
import unittest
from scripts.msx.player import palette,relocate,coordinates,atlas,atlas_with_tiles,padded_world
from scripts.msx.raster_scroll import palette_rgb
from scripts.msx.screen5 import rgb333


class PlayerTests(unittest.TestCase):
    def test_enemy_or_planes_preserve_scenery_rgb(self):
        colors=[(i*16,i*8,i*4) for i in range(16)]
        for i,c in {5:(33,71,222),13:(255,255,151),1:(0,0,151),6:(255,0,0),14:(0,0,0)}.items():colors[i]=c
        encoded=bytes(v for c in colors for r,g,b in [rgb333(c)] for v in (r<<4|b,g))
        changed,[pixels]=palette(encoded,[bytes(range(16))],enemy=True)
        before,after=palette_rgb(encoded),palette_rgb(changed)
        self.assertEqual([before[i] for i in range(16)],[after[i] for i in pixels])
        self.assertEqual(after[6],before[6]);self.assertEqual(after[10],before[1])
        self.assertEqual(after[6|10],(0,0,0))
    def test_indexed_immediate_and_displacement_are_not_relocated_as_an_address(self):
        rom=bytearray(16384)
        rom[0xafd:0xb01]=bytes((0xd7,0,0x20,5))
        rom[0xac8:0xacc]=bytes((0xdd,0x36,0,0x88))
        linked,_=relocate(bytes(rom),'ld (ix+000h),088h ;0ac8 dd 36 00 88 ',enemies=True)
        self.assertEqual(linked[0xac8:0xacc],rom[0xac8:0xacc])
    def test_viewport_oracle_repeats_flowers_instead_of_reading_the_next_maze_row(self):
        world=bytes(range(54))
        pixels,width,height=padded_world(world,6,9,pad=4,flower=3)
        self.assertEqual((width,height),(14,17))
        def at(x,y):return pixels[(y+4)*width+x+4]
        self.assertEqual((at(5,4),at(6,4),at(7,4)),(29,6,7))
        self.assertEqual((at(-1,4),at(2,-1),at(2,9)),(8,14,2))
        self.assertEqual(at(4,7),46)
        with self.assertRaises(ValueError):padded_world(world,6,8)
    def test_score_linker_relocates_source_arithmetic_and_replaces_only_interfaces(self):
        rom=bytearray(16384)
        rom[0x210f:0x2112]=bytes((0x2a,0x90,0x89))
        rom[0x20b7:0x20ba]=bytes((0xcd,0x2f,0x0b))
        rom[0x24c5:0x24cd]=bytes(range(8))
        linked,patches=relocate(bytes(rom),'ld hl,(08990h) ;210f 2a 90 89 \ncall 00b2fh ;20b7 cd 2f 0b ',
            scoring=True,score_tables=(0x24c5,))
        self.assertEqual(linked[0x210f:0x2112],bytes((0x2a,0x90,0xe9)))
        self.assertEqual(linked[0x20b7:0x20ba],bytes((0xcd,0x2f,0x8b)))
        self.assertEqual(linked[0x24c5:0x24cd],bytes(range(8)))
        self.assertEqual((linked[0xb2f],linked[0x1aca],linked[0x1e6b]),(0xc9,0xc9,0xff))
    def test_effect_tiles_reuse_exact_atlas_pixels_and_preserve_world_addresses(self):
        world=bytes(816*1392)
        plain=atlas(world)
        graphics,banks,count,ids=atlas_with_tiles(world,(bytes([3])*64,bytes(64),bytes([3])*64))
        self.assertEqual((count,ids),(2,[1,0,1]))
        self.assertEqual(banks,plain[1])
        self.assertEqual(graphics[4:8],bytes([0x33])*4)
        with self.assertRaises(ValueError):atlas_with_tiles(world,(bytes(63),))
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

    def test_command_atlas_second_row_keeps_distinct_source_tiles(self):
        world=bytearray(816*1392)
        for n in range(40):
            world[n*8]=n%16
            world[n*8+1]=n//16
        for row,n in ((64,33),(128,34),(173,35)):
            world[row*8*816+8]=n%16
            world[row*8*816+9]=n//16
        graphics,banks,count=atlas(world)
        self.assertEqual((count,len(graphics)),(40,2048))
        for n in range(40):
            self.assertEqual(banks[0][n*2:n*2+2],bytes(((n%32)*8,16+(n//32)*8)))
            at=(n//32*8)*128+(n%32)*4
            self.assertEqual(graphics[at],(n%16)<<4 | n//16)
        self.assertEqual(len(banks),4)
        for row,n in ((64,33),(128,34),(173,35)):
            at=row%64*256+2
            self.assertEqual(banks[row//64][at:at+2],bytes(((n%32)*8,24)))

    def test_uniform_tags_preserve_textures_and_flag_owners(self):
        from scripts.msx.player import uniform_source_tags
        graphics=bytearray(2048)
        for row in range(8):
            graphics[row*128:row*128+4]=bytes([0x66])*4
            graphics[row*128+4:row*128+8]=bytes([0x67])*4
            graphics[1024+row*128:1024+row*128+4]=bytes([0xaa])*4
        bank=bytes([0,16,8,16,1,16,0,24,0,0])
        self.assertEqual(uniform_source_tags(graphics,[bank]),
                         [bytes([0x62,0,8,16,1,16,0xa2,0,0,0])])
        self.assertEqual(bank,bytes([0,16,8,16,1,16,0,24,0,0]))

    def test_scenery_color_merge_retains_original_object_pixels(self):
        from scripts.msx.player import merge_scenery_color
        world=bytes([10,3,10,10,10,10,10,10,10,10,10,10,10,10,10,10])
        result=merge_scenery_color(world,10,7,[(1,1,2,2)],width=4)
        self.assertEqual(result,bytes([7,3,7,7,7,10,10,7,7,10,10,7,7,7,7,7]))
        self.assertEqual(world[0],10)
        with self.assertRaises(ValueError):merge_scenery_color(world,10,7,[(3,0,2,1)],width=4)

    def test_forced_source_addresses_reserve_full_atlas_with_one_tile(self):
        graphics,banks,count,_=atlas_with_tiles(bytes([6])*(816*1392),force_source_xy=True)
        self.assertEqual((count,len(graphics),len(banks)),(1,2048,4))
        self.assertEqual(banks[0][:4],bytes([0,16,0,16]))
