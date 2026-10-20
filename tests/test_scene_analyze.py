import unittest
from PIL import Image
from scripts.scenes.layout import Preview
from scripts.scenes.render import Object
from scripts.scenes.analyze import analyze
from test_scene_render import scene


def preview():
    return Preview(Image.new('RGB',(256,212)),bytes(256*212),bytes(256*212),
                   bytes(256*212),[],{'size':[256,212],'blocks':{},'maze':{'destination':[0,0,256,212]}})


class AnalyzeTests(unittest.TestCase):
    def test_pattern_rows_and_foreground_separation(self):
        assets,_,_=scene(); p=preview()
        bg=bytearray(p.background); bg[0:8]=bytes([0,1,0,1,0,1,0,1]); p.background=bytes(bg)
        result=analyze(p,assets)
        self.assertEqual(result['screen4']['violating_rows'],0)
        bg[2]=2; p.background=bytes(bg)
        result=analyze(p,assets)
        self.assertEqual(result['screen4']['violating_rows'],1)
        self.assertEqual(result['screen4']['violations'][0],{'x':0,'y':0,'indices':[0,1,2]})

    def test_palette_rgb_duplicates_and_screen5_budget(self):
        assets,_,_=scene(); p=preview()
        idx=bytearray(p.indices); idx[:17]=bytes(range(17)); p.indices=bytes(idx)
        image=p.image.copy()
        for i in range(17): image.putpixel((i,0),(i*7,)*3)
        p.image=image
        result=analyze(p,assets)
        self.assertFalse(result['screen5']['fits_palette_budget'])
        self.assertEqual(result['palette']['rgb_count'],17)
        assets.palette['rgb'][1]=assets.palette['rgb'][0]
        p.image=Image.new('RGB',(256,212))
        result=analyze(p,assets)
        self.assertEqual(result['palette']['source_index_count'],17)
        self.assertEqual(result['palette']['rgb_count'],1)

    def test_color_layers_clipping_transparency_and_scanline_limit(self):
        assets,_,_=scene(); p=preview()
        # First row color 1, remaining rows color 2: per-row color changes share one entry.
        colors=bytes([1]*8+[2]*8)*16
        p.objects=[Object('sprite',i,1,(i*16,0,i*16+16,16),colors) for i in range(5)]
        p.objects.append(Object('sprite',99,0,(0,0,16,16),bytes([255]*256)))
        result=analyze(p,assets)['sprites']
        self.assertEqual(result['estimated_entries'],10)
        self.assertEqual(result['peak_entries_per_scanline'],10)
        self.assertEqual(result['over_limit_scanlines'],list(range(16)))
        self.assertEqual(result['visible_source_objects'],5)
        p.objects=[Object('sprite',1,0,(-8,-8,8,8),colors)]
        result=analyze(p,assets)['sprites']
        self.assertEqual(result['peak_entries_per_scanline'],1)
        self.assertEqual(result['visible_source_objects'],1)
        self.assertEqual(result['bounding_box_occupancy'][0],1)

    def test_dot_shadow_is_reported_as_effect(self):
        assets,_,_=scene(); p=preview()
        shadow=bytearray(p.shadow); shadow[0]=1; p.shadow=bytes(shadow)
        p.objects=[Object('dot',1,1,(0,0,4,4),bytes([16]*16))]
        result=analyze(p,assets)
        self.assertEqual(result['effects']['shadow_pixels'],1)
        self.assertEqual(result['sprites']['estimated_entries'],1)
        self.assertIn('software',result['effects']['assumption'])
