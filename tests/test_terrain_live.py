from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.msx.terrain_live import analyze, camera_bounds, STATE, POINTS


class LiveTerrainTests(unittest.TestCase):
    def test_camera_rejects_outside_flowers_at_each_edge(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'samples'
            records=[]
            for x,y in [(0,0),(568,1191),(-1,0),(569,0),(0,-1),(0,1192)]:
                row=bytearray(STATE+len(POINTS))
                row[0xb0:0xb2]=x.to_bytes(2,'little',signed=True)
                row[0xb2:0xb4]=y.to_bytes(2,'little',signed=True)
                records.append(row)
            path.write_bytes(b''.join(records))
            result=camera_bounds(path)
        self.assertFalse(result['passed'])
        self.assertEqual(result['violations'],4)
        self.assertEqual(result['first_failures'][0]['sample'],2)

    def observe(self, directory, *, corrupt=False, smoke=False,popup=False,expired=False,wrong_popup=False):
        root=Path(directory);(root/'palette.bin').write_bytes(b'')
        state=bytearray(STATE)
        state[0x2992:0x2994]=(0xe1c8).to_bytes(2,'little')
        state[0x2996:0x2998]=(0xe208).to_bytes(2,'little')
        state[0xb0:0xb2]=(1).to_bytes(2,'little')
        state[0xb2:0xb4]=(256).to_bytes(2,'little')
        samples=bytearray([0x66]*len(POINTS))
        good=state+samples
        if corrupt:samples[100]=0x11
        if popup:
            x,y=POINTS[100]
            state[0x1fe4]=int(not expired)
            state[0x1fe6]=(x+1)//8;state[0x1fe7]=(y+256)//8
            state[0x1feb:0x1fed]=(0xa000).to_bytes(2,'little')
            (root/'raster-scroll.sym').write_text('FLAG_POPUPS: EQU 0x00000001\nPopup_Pixels: EQU 0x0000A000\n')
            (root/'flag-popup-pixels.bin').write_bytes(bytes([0x22 if wrong_popup else 0x11])*96)
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
        self.assertEqual(result['failed_frames'],1)
        self.assertEqual(result['maximum_mismatches'],1)
        self.assertEqual(result['first_failures'][0]['sample'],1)
        self.assertEqual(result['first_failures'][0]['mismatches'],1)

    def test_odd_x_y_wrap_and_published_smoke_do_not_create_false_failures(self):
        with TemporaryDirectory() as directory:
            result=self.observe(directory,corrupt=True,smoke=True)
        self.assertTrue(result['passed'])
        self.assertGreater(result['ignored_dynamic_pixels'],0)

    def test_popup_accepts_exact_label_but_rejects_wrong_or_expired_pixels(self):
        for expired,wrong,passed in [(False,False,True),(True,False,False),(False,True,False)]:
            with self.subTest(expired=expired,wrong=wrong),TemporaryDirectory() as directory:
                result=self.observe(directory,corrupt=True,popup=True,expired=expired,wrong_popup=wrong)
                self.assertEqual(result['passed'],passed)
