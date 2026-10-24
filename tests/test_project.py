"""Exercise the developer build/run contract without proprietary game inputs."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import project
from scripts.msx.checkpoints import resolve_latest
from scripts.scenes.storage import seal

ROOT = Path(__file__).resolve().parents[1]


class ProjectTests(unittest.TestCase):
    def test_make_run_builds_only_when_missing_and_stops_on_build_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'scripts').mkdir()
            shutil.copyfile(ROOT/'Makefile', root/'Makefile')
            (root/'scripts/project.py').write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "command = sys.argv[1]\n"
                "with Path('calls').open('a') as log: log.write(command+'\\n')\n"
                "rom = Path('references/build/newrallyx.rom')\n"
                "if command == 'build':\n"
                "    if Path('fail-build').exists(): sys.exit(2)\n"
                "    rom.parent.mkdir(parents=True, exist_ok=True)\n"
                "    rom.write_bytes(b'AB synthetic ROM')\n"
                "else:\n"
                "    assert rom.is_file()\n"
            )

            def make_run():
                return subprocess.run(['make', 'run', f'PYTHON={sys.executable}'],
                                      cwd=root, capture_output=True, text=True)

            self.assertEqual(make_run().returncode, 0)
            rom = root/project.ROM
            rom.write_bytes(b'AB existing ROM')
            self.assertEqual(make_run().returncode, 0)
            self.assertEqual(rom.read_bytes(), b'AB existing ROM')
            self.assertEqual((root/'calls').read_text().splitlines(), ['build', 'run', 'run'])
            rom.unlink()
            (root/'fail-build').touch()
            self.assertNotEqual(make_run().returncode, 0)
            self.assertEqual((root/'calls').read_text().splitlines(), ['build', 'run', 'run', 'build'])

    def test_rebuild_publishes_successful_rom_and_preserves_previous_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root/'.gitignore').write_text('/references/**\n')
            bundles = []

            def builder(root, args):
                self.assertEqual(args.stage, 12)
                bundles.append(args.output)
                args.output.mkdir(parents=True)
                rom = args.output/'raster-scroll.rom'
                rom.write_bytes(b'AB synthetic ROM')
                seal(args.output)
                return rom

            with patch.object(project, 'build_rom', side_effect=builder):
                project.build(root)
                project.build(root)
            self.assertNotEqual(bundles[0], bundles[1])
            self.assertEqual((root/project.ROM).read_bytes(), b'AB synthetic ROM')
            self.assertTrue(all((p/'raster-scroll.rom').is_file() for p in bundles))
            with patch.object(project, 'build_rom', side_effect=ValueError('Assembly failed')):
                with self.assertRaisesRegex(ValueError, 'Assembly failed'):
                    project.build(root)
            self.assertEqual((root/project.ROM).read_bytes(), b'AB synthetic ROM')
            self.assertEqual(list((root/'references/build').glob('*.tmp')), [])

    def test_repeated_launches_use_default_rom_and_separate_sessions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch.object(project, 'run_emulator') as emulator:
                project.run(root)
                project.run(root)
            first, second = [call.args[1] for call in emulator.call_args_list]
            self.assertEqual(first.rom, root/project.ROM)
            self.assertNotEqual(first.output, second.output)
            self.assertEqual(first.bios, root/'references/msxbios')

    def test_build_flags_use_only_selected_player_baseline_and_preserve_latest_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root/'.gitignore').write_text('/references/**\n')
            default = root/project.ROM
            default.parent.mkdir(parents=True)
            default.write_bytes(b'AB default reference')

            def builder(root, args):
                args.output.mkdir()
                rom = args.output/'raster-scroll.rom'
                rom.write_bytes(b'AB HUD off' if args.no_hud else b'AB HUD on')
                seal(args.output)
                return rom

            with patch.object(project, 'build_rom', side_effect=builder) as renderer:
                rom = project.build(root, no_hud=True)
                self.assertTrue(renderer.call_args.args[1].no_hud)
                self.assertEqual(resolve_latest(root), rom)
                rom_on = project.build(root, native=True)
                self.assertFalse(renderer.call_args.args[1].no_hud)
                self.assertEqual(resolve_latest(root), rom_on)
                rom_blitter=project.build(root,stage=0,player_blitter=True,radar_blitter=True)
                self.assertTrue(renderer.call_args.args[1].player_blitter)
                self.assertTrue(renderer.call_args.args[1].radar_blitter)
                self.assertEqual(renderer.call_args.args[1].cache_columns,48)
                self.assertEqual(resolve_latest(root),rom_blitter)
                rom_flicker=project.build(root,stage=9,hz=60,sprite_flicker=True,flicker_stress=True)
                self.assertEqual(renderer.call_args.args[1].hz,60)
                self.assertTrue(renderer.call_args.args[1].sprite_flicker)
                self.assertTrue(renderer.call_args.args[1].flicker_stress)
                self.assertEqual(resolve_latest(root),rom_flicker)
                rom_population=project.build(root,stage=9,enemies=3)
                self.assertEqual(renderer.call_args.args[1].enemies,3)
                self.assertFalse(renderer.call_args.args[1].no_hud)
                self.assertEqual(resolve_latest(root),rom_population)
                renderer.side_effect = ValueError('Assembly failed')
                with self.assertRaisesRegex(ValueError, 'Assembly failed'):
                    project.build(root, no_hud=True)
                self.assertEqual(resolve_latest(root), rom_population)
            self.assertEqual(default.read_bytes(), b'AB HUD on')

    def test_make_no_hud_native_and_latest_flags_reach_cli_without_default_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'scripts').mkdir()
            shutil.copyfile(ROOT/'Makefile', root/'Makefile')
            (root/'scripts/project.py').write_text(
                "import json,sys\nfrom pathlib import Path\n"
                "with Path('calls').open('a') as log: log.write(json.dumps(sys.argv[1:])+'\\n')\n")
            for args in [('build', 'NO_HUD=1'), ('build', 'NATIVE=1'), ('run', 'LATEST=1'), ('build','STAGE=1'),('build','STAGE=0','PLAYER_BLITTER=1','RADAR_BLITTER=1'),('build','STAGE=9','HZ=60','SPRITE_FLICKER=1','FLICKER_STRESS=1'),('build','STAGE=9','ENEMIES=3')]:
                result = subprocess.run(['make', *args, f'PYTHON={sys.executable}'],
                                        cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in (root/'calls').read_text().splitlines()]
            self.assertEqual(calls, [['build', '--no-hud','--stage','12'],
                                    ['build', '--native','--stage','12'], ['run', '--latest'],
                                    ['build','--stage','1'],['build','--player-blitter','--radar-blitter','--stage','0'],
                                    ['build','--sprite-flicker','--flicker-stress','--hz','60','--stage','9'],
                                    ['build','--stage','9','--enemies','3']])


if __name__ == '__main__':
    unittest.main()
