"""Public entry points must select an explicit renderer and fresh build."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MakeModes(unittest.TestCase):
    def commands(self, *options):
        return subprocess.check_output(['make', '-n', 'run', *options], cwd=ROOT, text=True)

    def test_default_builds_optimized_before_launch(self):
        commands = self.commands()
        self.assertIn('build.py --full-session', commands)
        self.assertIn('full-session/fixed-hud.rom', commands)
        self.assertLess(commands.index('build.py'), commands.index('project.py run'))

    def test_test_mode_has_distinct_artifact(self):
        commands = self.commands('TEST_MODE=1')
        self.assertIn('NRX_TEST_MODE="1"', commands)
        self.assertIn('full-session-test/fixed-hud.rom', commands)

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
