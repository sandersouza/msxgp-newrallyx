import tempfile
from pathlib import Path
import unittest
from scripts.msx.presentation_cadence import analyze


class PresentationCadenceTests(unittest.TestCase):
    def measure(self,text):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace';path.write_text(text)
            return analyze(path,1/60)['rounds'][0]

    def test_repeated_missed_slots_are_not_hidden_by_average_logic_rate(self):
        report=self.measure('0 2 commit 1 0 0 0 0\n.0333333333 2 commit 3 0 0 0 0\n.1 2 commit 7 0 0 0 0\n')
        self.assertEqual(report['intervals_in_refreshes'],{2:1,4:1})
        self.assertEqual(report['missed_slots_percent'],50)

    def test_inactive_preparation_breaks_commit_segment(self):
        report=self.measure('0 2 commit 1 0 0 0 0\n.0333333333 2 commit 3 0 0 0 0\n.1 2 start 7 1 0 0 0\n5 2 commit 45 0 0 0 0\n5.0333333333 2 commit 47 0 0 0 0\n')
        self.assertEqual(report['intervals'],2)
        self.assertEqual(report['missed_slots_percent'],0)
        self.assertLess(report['maximum_gap_ms'],34)
