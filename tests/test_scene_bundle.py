import json
import tempfile
import unittest
from pathlib import Path
from scene_fixtures import assets_at, capture_at, json_write, seal
from scripts.scenes.bundle import load_assets, load_capture


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets_path = assets_at(self.root/'assets')
        self.path = capture_at(self.root/'case', self.assets_path)
        self.assets = load_assets(self.assets_path)

    def test_valid_bundle(self):
        capture = load_capture(self.path, self.assets)
        self.assertEqual(len(capture.video), 4096)
        self.assertEqual(capture.state['visible'], [0,16,288,240])

    def test_invalid_state(self):
        original = json.loads((self.path/'capture.json').read_text())
        for key, value in [('schema_version',2), ('state_frame',True),
                ('bitmap_frame',11), ('phase','frame_done'), ('initialized',False),
                ('visible',[0,0,288,224]), ('assets_sha256','0'*64),
                ('registers',{'scroll_x':256,'scroll_y':0,'flip':0})]:
            with self.subTest(key=key):
                json_write(self.path/'capture.json', dict(original, **{key:value}))
                seal(self.path)
                with self.assertRaises(ValueError):
                    load_capture(self.path, self.assets)

    def test_corrupt_missing_and_extra_payload(self):
        (self.path/'video.bin').write_bytes(bytes(4095))
        with self.assertRaises(ValueError):
            load_capture(self.path, self.assets)
        seal(self.path)
        with self.assertRaises(ValueError):
            load_capture(self.path, self.assets)
        (self.path/'extra.bin').write_bytes(b'x')
        seal(self.path)
        with self.assertRaises(ValueError):
            load_capture(self.path, self.assets)

    def test_manifest_traversal_and_asset_corruption(self):
        manifest = json.loads((self.path/'manifest.json').read_text())
        manifest['outputs'][0]['path'] = '../outside'
        json_write(self.path/'manifest.json', manifest)
        with self.assertRaises(ValueError):
            load_capture(self.path, self.assets)
        (self.assets_path/'tiles/indices.bin').write_bytes(bytes(16384))
        with self.assertRaises(ValueError):
            load_assets(self.assets_path)

    def test_non_object_metadata_and_unlisted_symlink_rejected(self):
        json_write(self.path/'manifest.json',[])
        with self.assertRaises(ValueError): load_capture(self.path,self.assets)
        seal(self.path)
        (self.path/'alias').symlink_to(self.assets_path,target_is_directory=True)
        with self.assertRaises(ValueError): load_capture(self.path,self.assets)

    def test_required_time_and_replay_frame(self):
        original=json.loads((self.path/'capture.json').read_text())
        for key,value in [('emulated_time',None),('emulated_time','NaN'),
                          ('replay_frame',None),('replay_frame',True),('replay_frame',0)]:
            state=dict(original)
            if value is None: del state[key]
            else: state[key]=value
            json_write(self.path/'capture.json',state); seal(self.path)
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                load_capture(self.path,self.assets)

    def test_mame_formatted_emulated_time_is_retained(self):
        state=json.loads((self.path/'capture.json').read_text())
        state['emulated_time']='0036.299,999,999'
        json_write(self.path/'capture.json',state); seal(self.path)
        self.assertEqual(load_capture(self.path,self.assets).state['emulated_time'],'0036.299,999,999')
