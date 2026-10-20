import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('lua'),'Optional standalone Lua interpreter for lifecycle harness')
class RecorderLifecycleTests(unittest.TestCase):
    def test_real_recorder_rejects_tap_loss_reset_and_incomplete_initialization(self):
        root=Path(__file__).resolve().parents[1]
        for scenario in ['normal','initial-change','read-change','loss','reset','uninitialized']:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                work=Path(temp); case=work/'frame-00002'; case.mkdir()
                (work/'run.lua').write_text('return {destination='+json.dumps(str(work))+
                    ',frames={2},inputs={},header="{\\\"schema_version\\\":1"}\n')
                result=subprocess.run(['lua',str(root/'tests/fixtures/scene-capture-harness.lua'),
                    str(root/'scripts/scenes/capture.lua'),str(work),scenario],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                if scenario in ('normal','initial-change','read-change'):
                    self.assertEqual((case/'complete').read_text(),'ok')
                else:
                    self.assertFalse((case/'complete').exists())
                    self.assertTrue((work/'failure.txt').exists())
