"""Preparation stages fail closed and complete before a linker can consume them."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from src.toolchain.graphics import prepare


class PrepareAssetsTests(unittest.TestCase):
    def test_missing_graphics_are_extracted_then_checked_against_roms(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'assets/arcade/nrallyx'
            assets=Mock(manifest={'inputs':['verified']})
            with patch.object(prepare,'validate_roms',return_value={}),patch.object(prepare,'input_records',return_value=['verified']),patch.object(prepare,'promote',return_value=target),patch.object(prepare,'load_assets',return_value=assets),patch('scripts.extract_graphics.main',return_value=0) as extract:
                self.assertIs(prepare.graphics(root),assets)
                extract.assert_called_once_with(['--input',str(root/'references/roms/nrallyx'),'--output',str(target)])

    def test_existing_graphics_are_verified_without_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'assets/arcade/nrallyx';target.mkdir(parents=True)
            with patch.object(prepare,'validate_roms',return_value={}),patch.object(prepare,'input_records',return_value=['current']),patch.object(prepare,'promote',return_value=target),patch.object(prepare,'load_assets',return_value=Mock(manifest={'inputs':['old']})),patch('scripts.extract_graphics.main') as extract:
                with self.assertRaisesRegex(ValueError,'differ'):prepare.graphics(root)
                extract.assert_not_called()
                self.assertTrue(target.is_dir())

    def test_missing_scenes_are_captured_and_analyzed_before_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('scripts.arcade_scene.main',return_value=0) as cli,patch.object(prepare,'verify_manifest'),patch.object(prepare,'load_capture') as load,patch('src.toolchain.msx.inputs.load_huds') as hud:
                prepare.scenes(root,Mock())
                self.assertEqual([c.args[0][0] for c in cli.call_args_list],['capture','analyze','analyze'])
                self.assertEqual(load.call_count,5)
                hud.assert_called_once_with(root/'assets/arcade/scenes/normal',root/'assets/arcade/scenes/overlap')

    def test_failed_capture_stops_before_analysis(self):
        with patch('scripts.arcade_scene.main',return_value=2) as cli:
            with self.assertRaisesRegex(ValueError,'capture failed'):prepare.scenes(Path('/missing'),Mock())
            self.assertEqual(cli.call_count,1)

    def test_all_prepares_in_order_and_stops_on_invalid_graphics(self):
        events=[]
        with patch.object(prepare,'graphics',side_effect=lambda r:events.append('graphics')),patch.object(prepare,'scenes',side_effect=lambda *a:events.append('scenes')),patch.object(prepare,'native',side_effect=lambda r:events.append('native')),patch('src.toolchain.screen4.title_reference.ensure',side_effect=lambda r:events.append('title')):
            prepare.prepare(Path.cwd())
        self.assertEqual(events,['graphics','scenes','native','title'])
        with patch.object(prepare,'graphics',side_effect=ValueError('invalid ROM')),patch.object(prepare,'scenes') as scenes:
            with self.assertRaises(ValueError):prepare.prepare(Path.cwd())
            scenes.assert_not_called()
