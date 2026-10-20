import unittest
from scripts.scenes.layout import Layout, compose, proposals
from test_scene_render import scene
from scripts.scenes.render import render


class LayoutTests(unittest.TestCase):
    def test_proposals_preserve_sizes_and_required_information(self):
        assets,capture,_=scene(); frame=render(capture,assets)
        for layout in proposals():
            if layout.name=='compact': continue # semantic repacking has separate tests
            preview=compose(frame,capture,layout)
            self.assertEqual(preview.image.size,(256,212))
            self.assertEqual(set(preview.transforms['blocks']),
                             {'score','fuel','radar','lives','round'})
            for block in preview.transforms['blocks'].values():
                s,d=block['source'],block['destination']
                self.assertEqual([s[2]-s[0],s[3]-s[1]],[d[2]-d[0],d[3]-d[1]])
            self.assertEqual(capture.state['registers']['scroll_x'],0)

    def test_rejects_missing_overlap_crop_or_resize(self):
        assets,capture,_=scene(); frame=render(capture,assets)
        import copy
        for mutation in ('missing','overlap','crop','resize'):
            layout=copy.deepcopy(proposals()[0])
            if mutation=='missing': del layout.blocks['fuel']
            if mutation=='overlap': layout.blocks['fuel']['destination']=[192,0,256,16]
            if mutation=='crop': layout.blocks['round']['destination']=[192,204,256,220]
            if mutation=='resize': layout.blocks['radar']['destination'][2]-=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                compose(frame,capture,layout)

    def test_camera_transforms_objects_and_negative_camera_rejected(self):
        assets,capture,ram=scene()
        pixels=bytearray(assets.pixels['sprites']); pixels[256:512]=bytes([1]*256)
        assets.pixels['sprites']=bytes(pixels)
        ram[0x1e]=4; ram[0x1f]=20; ram[0x81e]=205; ram[0x81f]=0
        capture.video=bytes(ram)
        layout=proposals()[0]; preview=compose(render(capture,assets),capture,layout)
        obj=next(o for o in preview.objects if o.kind=='sprite' and o.id==30)
        self.assertEqual(obj.rect,(4,14,20,30))
        layout.maze['source'][0]=-1
        with self.assertRaises(ValueError): compose(render(capture,assets),capture,layout)
