"""Synthetic map-selector tests: no original ROM bytes or extracted fixtures."""
import unittest
from src.toolchain.msx import stage_one as stage


class StageOneTests(unittest.TestCase):
    def test_msb_first_layout_and_neighbor_edges(self):
        rom=bytearray(16384)
        rom[0x2531:0x253a]=bytes([1,2,4,8,0,16,32,64,128])
        rom[0x3000]=0x81  # isolated cells x=0 and x=7, first row
        cells=stage.cells_from_rom(rom,0x30)
        self.assertEqual(len(cells),32*56)
        self.assertEqual(cells[0],1|2|4|8|32)
        self.assertEqual(cells[7],1|2|4)
        self.assertEqual(cells[1:7],bytes(6))
        self.assertEqual(cells[32:],bytes(32*55))

    def test_wall_masks_select_shape_and_preserve_flip(self):
        rom=bytearray(16384)
        cells=bytearray(1792)
        cells[3*32+2]=0x88
        # row 1, column 2: authored synthetic flip plus three neighbor masks
        i=0x2505+(1*3+2)*4
        rom[i:i+4]=bytes([0x80,0x80,0x10,0x08])
        rom[0x2529+5]=0x55
        self.assertEqual(stage.tile(rom,cells,2*3+2,3*3+1,0x0d,0x5c),(0x55,0x8d))

    def test_object_subtile_uses_code_palette_and_both_flips(self):
        rom=bytearray(16384);cells=bytearray(1792);cells[0]=4
        rom[0x2552+4*9+8]=0xe7
        self.assertEqual(stage.tile(rom,cells,2,2,0x0d,0x5c),(0x87,0xd6))

    def test_exterior_repeats_native_flower_subtiles_at_negative_coordinates(self):
        rom=bytes(16384);cells=bytes(1792)
        self.assertEqual(stage.tile(rom,cells,-1,-1,13,0x5c),(0x64,0x51))
        self.assertEqual(stage.tile(rom,cells,96,0,13,0x65),(0x65,0x52))
        self.assertEqual(stage.tile(rom,cells,0,168,13,0x6e),(0x6e,0x53))

    def test_tile_banks_keep_pixel_order_and_four_row_bank_boundary(self):
        world=bytearray(stage.WIDTH*stage.HEIGHT)
        for y in range(8):
            world[y*stage.WIDTH:y*stage.WIDTH+8]=bytes(range(8))
            world[(32+y)*stage.WIDTH+8:(32+y)*stage.WIDTH+16]=bytes([9]*8)
        banks=stage.tile_banks(world)
        self.assertEqual(len(banks),44)
        for y in range(8):
            self.assertEqual(banks[0][y*512:y*512+4],bytes([0x01,0x23,0x45,0x67]))
            self.assertEqual(banks[1][y*512+4:y*512+8],bytes([0x99])*4)
            self.assertEqual(banks[0][y*512+stage.WIDTH//2:(y+1)*512],bytes(512-stage.WIDTH//2))


if __name__=='__main__': unittest.main()
