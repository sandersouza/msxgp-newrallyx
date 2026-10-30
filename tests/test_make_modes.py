"""Public entry points must select an explicit renderer and fresh build."""
import subprocess
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MakeModes(unittest.TestCase):
    def commands(self, *options):
        return subprocess.check_output(['make', '-n', 'run', *options], cwd=ROOT, text=True)

    def test_default_builds_optimized_before_launch(self):
        commands = self.commands()
        self.assertIn('build.py --full-session', commands)
        self.assertIn('full-session-64k/fixed-hud.rom', commands)
        self.assertLess(commands.index('build.py'), commands.index('project.py run'))

    def test_default_uses_consolidated_screen4_sources(self):
        commands = self.commands()
        self.assertIn('src/screen4/build.py --full-session', commands)
        self.assertIn('src/screen4/session_build.py --export', commands)
        self.assertNotIn('experiments/fixed-hud/', commands)

    def test_test_mode_has_distinct_artifact(self):
        commands = self.commands('TEST_MODE=1')
        self.assertIn('NRX_TEST_MODE="1"', commands)
        self.assertIn('full-session-test-64k/fixed-hud.rom', commands)

    def test_default_is_64k_and_mapper_selects_preserved_128k_profile(self):
        commands = self.commands()
        self.assertIn('NRX_RAM_KIB="64"', commands)
        self.assertIn('full-session-64k/fixed-hud.rom', commands)
        self.assertLess(commands.index('build.py'), commands.index('project.py run'))
        commands = self.commands('MAPPER=1', 'TEST_MODE=1')
        self.assertIn('NRX_RAM_KIB="128"',commands)
        self.assertIn('full-session-test/fixed-hud.rom', commands)

    def test_64k_selection_reaches_launcher_environment_even_with_stale_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'src/screen4').mkdir(parents=True)
            shutil.copyfile(ROOT/'Makefile',root/'Makefile')
            shutil.copyfile(ROOT/'src/screen4/targets.mk',root/'src/screen4/targets.mk')
            spy = root/'spy.py'
            spy.write_text('import json,os,sys\nfrom pathlib import Path\n'
                'with Path("calls.jsonl").open("a") as f:\n'
                ' f.write(json.dumps(dict(argv=sys.argv[1:],ram=os.getenv("NRX_REFERENCE_RAM_KIB")))+"\\n")\n')
            for options,ram in (((), '64'),(('MAPPER=0',),'64'),(('MAPPER=1',),'128')):
                with self.subTest(options=options):
                    result = subprocess.run(['make','run',*options,f'PYTHON={sys.executable} {spy}'],
                        cwd=root,capture_output=True,text=True,
                        env=dict(os.environ,NRX_REFERENCE_RAM_KIB='128'))
                    self.assertEqual(result.returncode,0,result.stderr)
                    calls=[json.loads(line) for line in (root/'calls.jsonl').read_text().splitlines()]
                    launch=calls[-1]
                    self.assertEqual(launch['argv'][:3],['-B','scripts/project.py','run'])
                    self.assertEqual(launch['ram'],ram)
                    self.assertIn('full-session'+('-64k' if ram=='64' else '')+'/fixed-hud.rom',launch['argv'][-1])

            for options in (('LEGACY=1',),('LATEST=1',),('CHECKPOINT=synthetic',)):
                result=subprocess.run(['make','run',*options,f'PYTHON={sys.executable} {spy}'],
                    cwd=root,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads((root/'calls.jsonl').read_text().splitlines()[-1])['ram'],'128')

    def test_legacy_uses_original_screen5_builder(self):
        for option in ('LEGACY=1', 'legacy=1'):
            commands = self.commands(option)
            self.assertIn('project.py build', commands)
            self.assertIn('--full-game --audio', commands)
            self.assertNotIn('build.py --full-session', commands)

    def test_explicit_rom_does_not_build_another_cartridge(self):
        commands = self.commands('ROM=references/custom.rom')
        self.assertIn('--rom "references/custom.rom"', commands)
        self.assertNotIn('project.py build', commands)
        self.assertNotIn('build.py --full-session', commands)

    def test_latest_does_not_pass_the_optimized_default_rom(self):
        commands = self.commands('LATEST=1')
        self.assertIn('run --latest', commands)
        self.assertNotIn('--rom', commands)
        self.assertNotIn('build.py --full-session', commands)


if __name__ == '__main__':
    unittest.main()
