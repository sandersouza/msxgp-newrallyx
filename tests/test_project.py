"""Exercise the developer build/run contract without proprietary game inputs."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import project

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
                bundles.append(args.output)
                args.output.mkdir(parents=True)
                rom = args.output/'raster-scroll.rom'
                rom.write_bytes(b'AB synthetic ROM')
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


if __name__ == '__main__':
    unittest.main()
