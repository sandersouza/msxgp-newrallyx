"""Protected content stays local; only empty reference placeholders are public."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class PrivateAssetsTests(unittest.TestCase):
    def test_original_and_converted_payloads_are_ignored_at_any_depth(self):
        names=['assets/namco-title-56x8.png','assets/arcade/nrallyx/tiles/indices.bin','assets/arcade/msx/default/manifest.json',
               'references/roms/nrallyx/nrx_prg1.1d','references/msxbios/panasonic/bios.rom',
               'references/new-tool/nested/capture.png','references/assets/new/palette.json']
        result=subprocess.run(['git','check-ignore','--no-index','-z','--stdin'],cwd=ROOT,
            input='\0'.join(names)+'\0',capture_output=True,text=True,check=True)
        self.assertEqual(set(result.stdout.split('\0'))-{''},set(names))

    def test_index_contains_no_private_payloads(self):
        names=subprocess.check_output(['git','ls-files','-z','--','assets/namco-title-56x8.png','assets/arcade','references'],cwd=ROOT).decode().split('\0')
        for name in filter(None,names):
            self.assertTrue(name.startswith('references/') and Path(name).name=='.gitkeep',name)
            self.assertEqual((ROOT/name).read_bytes(),b'',name)

    def test_reference_tree_markers_are_empty_and_visible_to_git(self):
        for path in (ROOT/'references').rglob('.gitkeep'):
            self.assertEqual(path.read_bytes(),b'')
            result=subprocess.run(['git','check-ignore','--no-index',str(path.relative_to(ROOT))],cwd=ROOT,capture_output=True)
            self.assertEqual(result.returncode,1,str(path))
