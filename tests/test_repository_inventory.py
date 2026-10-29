"""Guard the audit's conservative treatment of generated and ambiguous sources."""
from pathlib import Path
import unittest

from scripts.repository_inventory import static_references


class InventoryReferencesTest(unittest.TestCase):
    def test_package_and_sibling_imports(self):
        paths = list(map(Path, ['scripts/project.py', 'scripts/msx/build.py',
                               'experiments/fixed-hud/session_build.py',
                               'experiments/fixed-hud/build_profiles.py']))
        refs = static_references(paths, {
            'scripts/project.py': 'from scripts.msx.build import destination\n',
            'experiments/fixed-hud/session_build.py': 'from build_profiles import source_view\n'})
        self.assertIn(('scripts/project.py', 'python-import'), refs['scripts/msx/build.py'])
        self.assertIn(('experiments/fixed-hud/session_build.py', 'python-import'),
                      refs['experiments/fixed-hud/build_profiles.py'])

    def test_ambiguous_include_retains_both_and_marks_uncertainty(self):
        paths = list(map(Path, ['src/main.asm', 'src/hud.inc', 'experiments/hud.inc']))
        refs = static_references(paths, {'src/main.asm': '    INCLUDE "hud.inc"\n'})
        for target in ('src/hud.inc', 'experiments/hud.inc'):
            self.assertIn(('src/main.asm', 'assembly-include-candidate'), refs[target])

    def test_staging_and_documentation_remain_distinct_from_imports(self):
        paths = list(map(Path, ['build.py', 'src/native.inc', 'docs/setup.md']))
        refs = static_references(paths, {
            'build.py': 'sources = ("native.inc",)\n',
            'docs/setup.md': '`python build.py` stages `native.inc`.\n'})
        self.assertEqual(refs['src/native.inc'], {('build.py', 'filename-mention'),
                                                ('docs/setup.md', 'filename-mention')})
        self.assertNotIn('docs/setup.md', refs)


if __name__ == '__main__':
    unittest.main()
