from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.msx.terrain_live import analyze, STATE, POINTS


class LiveTerrainTests(unittest.TestCase):
    def observe(self, directory, *, corrupt=False, smoke=False):
        root=Path(directory);(root/'palette.bin').write_bytes(b'')
        state=bytearray(STATE)
        state[0x2992:0x2994]=(0xe1c8).to_bytes(2,'little')
        state[0x2996:0x2998]=(0xe208).to_bytes(2,'little')
        state[0xb0:0xb2]=(1).to_bytes(2,'little')
        state[0xb2:0xb4]=(256).to_bytes(2,'little')
        samples=bytearray([0x66]*len(POINTS))
        good=state+samples
        if corrupt:samples[100]=0x11
        if smoke:
            x,y=POINTS[100]
            state[0x1300+((256+y)//8%32)*64+((1+x)//8%64)]=1
        (root/'samples').write_bytes(good+state+samples+good)
        with patch('scripts.msx.stage_one.acquire',return_value=(b'',None)), \
             patch('scripts.scenes.bundle.load_assets',return_value={}), \
             patch('scripts.full_game_probe.world',return_value=b''), \
             patch('scripts.msx.player.padded_world',return_value=(bytes([6])*1024**2,1024,1024)):
            return analyze(root,root,root/'samples')

    def test_a_transient_corrupt_middle_frame_is_retained(self):
        with TemporaryDirectory() as directory:
            result=self.observe(directory,corrupt=True)
        self.assertFalse(result['passed'])
        self.assertEqual(result['frames'],3)
        self.assertEqual(result['first_failures'][0]['sample'],1)
        self.assertEqual(result['first_failures'][0]['mismatches'],1)

    def test_odd_x_y_wrap_and_published_smoke_do_not_create_false_failures(self):
        with TemporaryDirectory() as directory:
            result=self.observe(directory,corrupt=True,smoke=True)
        self.assertTrue(result['passed'])
        self.assertGreater(result['ignored_dynamic_pixels'],0)
