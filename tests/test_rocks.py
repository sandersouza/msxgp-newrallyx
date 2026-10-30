"""Synthetic original-pointer validation; no original game data."""
import unittest
from src.toolchain.msx.rocks import cells_from_placement


def placement(addresses=(0x9821,0x9842)):
    video=bytearray(4096)
    video[0x251]=2;video[0x28f]=0x30
    video[0x996:0x998]=(0x8208).to_bytes(2,'little')
    for i,address in enumerate(addresses):
        video[0x208+i*2:0x20a+i*2]=address.to_bytes(2,'little')
    return bytes(video)


class RockTests(unittest.TestCase):
    def test_original_pointers_add_only_rocks_and_preserve_existing_objects(self):
        base=bytearray(1792);base[7]=1;base[8]=0x87
        cells,positions=cells_from_placement(bytes(base),placement())
        self.assertEqual({i for i,(a,b) in enumerate(zip(base,cells)) if a!=b},{33,66})
        self.assertEqual((cells[33],cells[66]),(3,3))
        self.assertEqual(positions[0],dict(cell_x=1,cell_y=1,world_origin=[48,48]))

    def test_duplicate_out_of_bounds_or_occupied_cells_are_rejected(self):
        for addresses in ((0x9821,0x9821),(0x97ff,0x9842),(0x9821,0x9f00)):
            with self.assertRaises(ValueError):cells_from_placement(bytes(1792),placement(addresses))
        for value in (1,2,4,0x87):
            base=bytearray(1792);base[33]=value
            with self.assertRaises(ValueError):cells_from_placement(bytes(base),placement())

    def test_wrong_count_map_or_pointer_table_is_rejected(self):
        for offset,value in ((0x251,0),(0x28f,0x31),(0x997,0x7f)):
            data=bytearray(placement());data[offset]=value
            with self.assertRaises(ValueError):cells_from_placement(bytes(1792),bytes(data))

class RockAcquisitionTests(unittest.TestCase):
    def test_first_acquisition_creates_a_new_bundle(self):
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from src.toolchain.msx import rocks
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def emulate(command,**kwargs):
                pending=Path(kwargs['env']['ROCKS_OUTPUT'])
                (pending/'complete').write_text('ok')
            with patch.object(rocks,'validate_roms',return_value={}),patch.object(rocks,'input_records',return_value=[]),patch.object(rocks,'require_ignored'),patch.object(rocks,'digest',return_value='synthetic'),patch.object(rocks,'verify_capture',return_value=(b'cells',[],42)),patch.object(rocks,'seal'),patch.object(rocks.subprocess,'check_output',return_value='0.289 synthetic'),patch.object(rocks.subprocess,'run',side_effect=emulate):
                cells,positions,checked,cache=rocks.acquire(root,b'',b'')
            self.assertEqual((cells,positions,checked),(b'cells',[],42))
            self.assertEqual(cache,root/'assets/arcade/native/rocks-v1')
            self.assertTrue((cache/'capture.json').is_file())
