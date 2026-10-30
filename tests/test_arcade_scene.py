import contextlib
import io
import json
import unittest
from graphics_fixtures import temporary_repo
from scene_fixtures import assets_at, capture_at, seal
from PIL import Image
from scripts.arcade_scene import main


class CliTests(unittest.TestCase):
    def test_default_layout_is_approved_compact(self):
        from src.toolchain.scenes.bundle import load_assets, load_capture
        from src.toolchain.scenes.render import render
        root,_,_=temporary_repo(self)
        assets=assets_at(root/'references/assets/test',blank=True)
        capture=capture_at(root/'references/scenes/input',assets)
        loaded=load_assets(assets)
        render(load_capture(capture,loaded),loaded).image.save(capture/'reference.png')
        seal(capture)
        output=root/'references/scenes/default'
        with contextlib.redirect_stdout(io.StringIO()):
            result=main(['analyze','--assets',str(assets),'--capture',str(capture),
                         '--output',str(output),'--root',str(root)])
        self.assertEqual(result,0)
        layout=json.loads((output/'layout.json').read_text())
        self.assertEqual(layout['name'],'compact')
        self.assertEqual(layout['status'],'approved')
        self.assertEqual(layout['maze']['destination'],[0,0,200,212])
        self.assertEqual(layout['compact']['title'],'HISCORE')
        self.assertIn('radar_projection',json.loads((output/'constraints.json').read_text()))

    def test_preview_emits_reference_input_without_constraint_report(self):
        from src.toolchain.scenes.bundle import load_assets, load_capture
        from src.toolchain.scenes.render import render
        root,_,_=temporary_repo(self)
        assets=assets_at(root/'references/assets/test',blank=True)
        capture=capture_at(root/'references/scenes/input',assets)
        loaded=load_assets(assets)
        render(load_capture(capture,loaded),loaded).image.save(capture/'reference.png')
        seal(capture)
        output=root/'references/scenes/preview'
        with contextlib.redirect_stdout(io.StringIO()):
            result=main(['preview','--assets',str(assets),'--capture',str(capture),
                         '--output',str(output),'--root',str(root)])
        self.assertEqual(result,0)
        with Image.open(output/'preview.png') as image:
            self.assertEqual(image.size,(256,212))
        self.assertEqual(json.loads((output/'layout.json').read_text())['status'],'approved')
        self.assertFalse((output/'constraints.json').exists())

    def test_mismatch_publishes_diagnostics_and_nonzero_exit(self):
        root,_,_=temporary_repo(self)
        assets=assets_at(root/'references/assets/test')
        capture=capture_at(root/'references/scenes/input',assets)
        reference=Image.new('RGB',(288,224))
        reference.putpixel((0,0),(255,0,0))
        reference.save(capture/'reference.png'); seal(capture)
        output=root/'references/scenes/comparison'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result=main(['reconstruct','--assets',str(assets),'--capture',str(capture),
                         '--output',str(output),'--root',str(root)])
        self.assertEqual(result,1)
        self.assertGreater(json.loads((output/'comparison.json').read_text())['mismatches'],0)
        before=(output/'comparison.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['reconstruct','--assets',str(assets),'--capture',str(capture),
                '--output',str(output),'--root',str(root)]),2)
        self.assertEqual((output/'comparison.json').read_bytes(),before)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result=main(['reconstruct','--assets',str(assets),'--capture',str(capture),
                         '--output',str(output),'--root',str(root),'--overwrite'])
        self.assertEqual(result,1)  # same pixel differences, not an output-exists error
        self.assertEqual((output/'comparison.json').read_bytes(),before)
