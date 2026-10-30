"""Synthetic effect visibility across native ring and radar-cell boundaries."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src.toolchain.msx.full_effects import visible_smoke,mask_pixel,analyze
from src.toolchain.msx.smoke import ring_index
from src.toolchain.msx.sprite_radar import bitmap,patterns,WIDTH,HEIGHT


class FullEffectsTests(unittest.TestCase):
    def test_actual_radar_mask_and_smoke_must_follow_native_state(self):
        syms=dict(Radar_Base=0xc800,hud_flags=0xc350,
                  Radar_PublishedPoints=0xdb40,Radar_StagedPoints=0xcd40)
        state=bytearray(12288);points=[(2+i*4,4+i*4) for i in range(10)]
        state[0x1fd0:0x1fe4]=bytes(v for p in points for v in p)
        state[0x501:0x50b]=bytes([0]+[1]*9)
        state[0x350:0x364]=b'\xff\xff'+state[0x1fd2:0x1fe4]
        state[0x1b40:0x1c00]=state[0xd40:0xe00]=bytes([255])*192
        state[0x2400+ring_index(10,10)]=189
        stale=patterns(bitmap([points[0]]))
        ready=bytearray(state);ready[0x1300+10*64+10]=1
        with TemporaryDirectory() as name:
            path=Path(name);(path/'effects-times.tsv').write_text('0\n0.1\n0.4\n')
            (path/'effects.bin').write_bytes((state+stale)*3)
            result=analyze(path,syms)
            self.assertFalse(result['passed'])
            self.assertEqual(result['maximum_flag_lag_ms'],400)
            self.assertEqual(result['maximum_smoke_lag_ms'],400)
            # Bookkeeping already removed the flag above; only actual VRAM was stale.
            (path/'effects.bin').write_bytes(state+stale+(ready+bytes(768))*2)
            result=analyze(path,syms)
            self.assertTrue(result['passed'])
            self.assertEqual(result['maximum_flag_lag_ms'],100)
            self.assertEqual(result['maximum_smoke_lag_ms'],100)
            (path/'effects-uploads.tsv').write_text('0.1 1 0\n0.101 1 128\n')
            result=analyze(path,syms)
            self.assertFalse(result['passed'])
            self.assertEqual(result['unsafe_publications'],2)
            self.assertEqual(result['repeated_publications_in_refresh'],1)
            (path/'effects-uploads.tsv').write_text('0.1 1 1\n0.12 2 3\n')
            self.assertTrue(analyze(path,syms)['passed'])

    def test_live_smoke_coordinates_follow_the_wrapped_native_window(self):
        state=bytearray(12288)
        state[0x702:0x704]=bytes((245,250))
        state[0xb0:0xb2]=(-88).to_bytes(2,'little',signed=True)
        state[0xb2:0xb4]=(-48).to_bytes(2,'little',signed=True)
        state[0x2400+ring_index(12,18)]=189
        state[0x2400+ring_index(21,18)]=190  # Beyond the right of the viewport.
        self.assertEqual(list(visible_smoke(state)),[(12,18,0)])

    def test_radar_cell_reads_respect_staggered_origins_and_both_halves(self):
        flags=[(15,14),(16,15),(31,30),(32,45)]
        pixels=bitmap(flags);masks=patterns(pixels)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                self.assertEqual(mask_pixel(masks,x,y),bool(pixels[y*WIDTH+x]),(x,y))
