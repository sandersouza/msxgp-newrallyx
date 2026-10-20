import tempfile
import unittest
from pathlib import Path
from scene_fixtures import assets_at, capture_at, json_write, seal
from scripts.scenes.bundle import load_assets
from scripts.scenes.record import validate_replay, finalize_case


class RecordTests(unittest.TestCase):
    def test_narrow_acquisition_unignore_is_rejected(self):
        from graphics_fixtures import temporary_repo
        from scripts.scenes.record import check_acquisition_paths
        root,_,_=temporary_repo(self)
        (root/'.gitignore').write_text('/references/**\n!/references/**/\n!/references/scenes/**/video.bin\n')
        with self.assertRaises(ValueError):
            check_acquisition_paths(root,root/'references/scenes/.acquisition-test',[20])

    def test_replay_requires_ordered_valid_inputs(self):
        self.assertEqual(validate_replay([{'frame':1,'field':'Coin 1','value':1}]),
                         [{'frame':1,'field':'Coin 1','value':1}])
        for events in [[{'frame':True,'field':'Coin 1','value':1}],
                       [{'frame':1,'field':'bogus','value':1}],
                       [{'frame':0,'field':'Coin 1','value':1}],
                       [{'frame':2,'field':'Coin 1','value':1}, {'frame':1,'field':'Coin 1','value':0}]]:
            with self.assertRaises(ValueError):
                validate_replay(events)

    def test_unfinished_or_reset_capture_fails(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            assets=load_assets(assets_at(root/'assets'))
            case=capture_at(root/'case',root/'assets')
            with self.assertRaises(ValueError):
                finalize_case(case,assets)
            (case/'complete').write_text('ok')
            finalize_case(case,assets)
            state=json.loads((case/'capture.json').read_text())
            state['initialized']=False
            json_write(case/'capture.json',state)
            (case/'complete').write_text('ok')
            with self.assertRaises(ValueError):
                finalize_case(case,assets)

    def test_wrong_mame_version_fails_before_running_game(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import subprocess
        from graphics_fixtures import temporary_repo
        from scripts.scenes.record import capture_gameplay
        root,_,_=temporary_repo(self)
        assets=assets_at(root/'references/assets/test')
        replay=root/'replay.json'; json_write(replay,[])
        real_run=subprocess.run
        def version_only(command,**kwargs):
            if command==['mame','-help']:
                return SimpleNamespace(stdout='MAME v0.290 (test)')
            return real_run(command,**kwargs)
        with patch('scripts.scenes.record.subprocess.run',side_effect=version_only):
            with self.assertRaisesRegex(ValueError,'0.289'):
                capture_gameplay(root,assets,root/'references/scenes/test',replay,[10])
