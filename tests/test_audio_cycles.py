from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.msx.audio_cycles import summarize


class AudioCycleTests(unittest.TestCase):
    def test_nested_and_repeated_calls_do_not_double_count_self_cost(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'calls').write_text('Audio_RuntimeControl Audio_RuntimeStep 0 20 20\n'+
                'Audio_ReadTone Audio_MusicTick 0 5 5\n'*3+
                'Audio_MusicTick Audio_RuntimeStep 0 30 30\n'
                'Audio_RuntimeStep Audio_Work 0 75 70\n'
                'Audio_Work renderer 0 110 90\n')
            (root/'packets').write_text('0 2 commit 0 0 0 0 0\n')
            result=summarize(root/'calls',root/'packets',1/60)
            rows={r['routine']:r for r in result['routines']}
            self.assertEqual(rows['Audio_Work']['mean_self_cycles'],20)
            self.assertEqual(rows['Audio_RuntimeStep']['mean_self_cycles'],20)
            self.assertEqual(rows['Audio_MusicTick']['mean_self_cycles'],15)
            self.assertEqual(rows['Audio_ReadTone']['calls_per_presented_packet'],3)
            self.assertEqual(rows['Audio_ReadTone']['mean_self_cycles'],15)
            self.assertAlmostEqual(result['mean_budget_after_audio_only'],3579545/30-90)
