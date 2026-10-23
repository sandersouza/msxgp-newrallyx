"""Synthetic capture validation; no original graphic payloads or ROM fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.msx.death import verify_capture


def synthetic_capture(path):
    for n in range(64):
        data=bytearray(4096);data[0x400:0x800]=bytes([0x81])*1024
        x=((396+n%8-9)//8-3)%32
        y=((1236-n//8-8)//8-10)%32
        for i in range(9):
            at=((y+i//3)%32)*32+(x+i%3)%32
            data[0x400+at]=0xb4+i;data[0xc00+at]=0x46
        (path/f'effect-{n:02d}.bin').write_bytes(data)
    (path/'hold-ticks.txt').write_text('120\n')


class DeathTests(unittest.TestCase):
    def test_all_fine_phases_and_original_wait_threshold_are_required(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp);synthetic_capture(path)
            pairs,ticks=verify_capture(path)
            self.assertEqual((len(pairs),ticks),(9,120))
            (path/'hold-ticks.txt').write_text('119\n')
            with self.assertRaises(ValueError):verify_capture(path)

    def test_missing_effect_pixel_metadata_or_wrong_tile_order_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp);synthetic_capture(path)
            target=path/'effect-63.bin';original=target.read_bytes()
            at=original.index(0xb4,0x400,0x800)
            for address,value in ((at,0x81),(at+0x800,0x45)):
                corrupt=bytearray(original);corrupt[address]=value;target.write_bytes(corrupt)
                with self.assertRaises(ValueError):verify_capture(path)
