"""Exercise real cleanup in temporary projects, including symlink boundaries."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.clean import clean

ROOT = Path(__file__).resolve().parents[1]


class CleanTests(unittest.TestCase):
    def test_playable_delivery_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'dist').mkdir();(root/'dist/newrallyx.rom').write_bytes(b'generated')
            self.assertEqual(clean(root),[])
            self.assertEqual((root/'dist/newrallyx.rom').read_bytes(),b'generated')

    def test_raw_measurements_sessions_and_baselines_are_disposable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('references/build/game/profile/measured.rom','references/sessions/run/cartridge.rom',
                         'references/baselines/frozen.rom'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'keep')
            self.assertEqual(len(clean(root)),3)
            self.assertFalse((root/'references/build').exists())
            self.assertFalse((root/'references/sessions').exists())
            self.assertFalse((root/'references/baselines').exists())

    def test_make_preview_and_clean_preserve_inputs_tools_and_external_symlink_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'scripts').mkdir()
            shutil.copyfile(ROOT/'Makefile',root/'Makefile')
            shutil.copyfile(ROOT/'scripts/clean.py',root/'scripts/clean.py')
            protected = [root/p for p in ('references/roms/game.rom','references/msxbios/bios.rom',
                'references/assets/indices.bin','assets/arcade/scenes/capture/frame.bin',
                'assets/arcade/msx/default/bank-001.bin',
                '.venv/pyvenv.cfg','.tools/assembler')]
            for path in protected:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'keep')
            build = root/'references/build'
            (build/'game/session').mkdir(parents=True)
            (build/'game/game.rom').write_bytes(b'generated')
            (build/'game/session/report.json').write_text('{}')
            (build/'game-hidden-output').write_text('generated')
            (build/'.gitkeep').touch()
            (build/'game-linked-inputs').symlink_to(root/'references/roms',target_is_directory=True)
            (build/'game/linked-bios').symlink_to(root/'references/msxbios',target_is_directory=True)
            preview = subprocess.run([sys.executable,'-B','scripts/clean.py','--dry-run'],
                                     cwd=root,capture_output=True,text=True,check=True)
            self.assertIn('Would remove 1 generated artifact roots',preview.stdout)
            self.assertTrue((build/'game/game.rom').is_file())
            subprocess.run(['make','clean'],cwd=root,capture_output=True,text=True,check=True)
            self.assertEqual(list(build.iterdir()),[build/'.gitkeep'])
            self.assertTrue(all(path.read_bytes()==b'keep' for path in protected))
            self.assertEqual(clean(root),[])

    def test_missing_build_is_a_noop_and_symlinked_roots_are_refused(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root,external = Path(temp),Path(outside)
            self.assertEqual(clean(root),[])
            (external/'keep.bin').write_bytes(b'keep')
            (root/'references').symlink_to(external,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):
                clean(root)
            (root/'references').unlink()
            (root/'references').mkdir()
            (root/'references/build').symlink_to(external,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):
                clean(root)
            self.assertEqual((external/'keep.bin').read_bytes(),b'keep')


if __name__=='__main__':
    unittest.main()
