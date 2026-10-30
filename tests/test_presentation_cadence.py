import tempfile
from pathlib import Path
import unittest
from src.toolchain.msx.presentation_cadence import analyze


class PresentationCadenceTests(unittest.TestCase):
    def measure(self,text):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace';path.write_text(text)
            return analyze(path,1/60)['rounds'][0]

    def test_repeated_missed_slots_are_not_hidden_by_average_logic_rate(self):
        report=self.measure('0 2 commit 1 0 0 0 0\n.0333333333 2 commit 3 0 0 0 0\n.1 2 commit 7 0 0 0 0\n')
        self.assertEqual(report['intervals_in_refreshes'],{2:1,4:1})
        self.assertEqual(report['missed_slots_percent'],50)

    def test_three_refresh_late_packet_still_counts_as_a_missed_slot(self):
        report=self.measure('0 2 commit 1 0 0 0 0\n.05 2 commit 4 0 0 0 0\n.0833333333 2 commit 6 0 0 0 0\n')
        self.assertEqual(report['intervals_in_refreshes'],{2:1,3:1})
        self.assertEqual(report['missed_slots_percent'],50)

    def test_inactive_preparation_breaks_commit_segment(self):
        report=self.measure('0 2 commit 1 0 0 0 0\n.0333333333 2 commit 3 0 0 0 0\n.1 2 start 7 1 0 0 0\n5 2 commit 45 0 0 0 0\n5.0333333333 2 commit 47 0 0 0 0\n')
        self.assertEqual(report['intervals'],2)
        self.assertEqual(report['missed_slots_percent'],0)
        self.assertLess(report['maximum_gap_ms'],34)

    def population_report(self,commits,populations):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace';path.write_text(commits)
            population=Path(tmp)/'population';population.write_text(populations)
            return analyze(path,1/60,population)

    def test_easy_population_cannot_hide_a_slow_loaded_segment(self):
        commits='0 2 commit 1 0 0 0 0\n'+''.join(
            f'{i/30} 2 commit {i*2+1} 0 0 0 0\n' for i in range(2,42))
        report=self.population_report(commits,
            '0 2 0 0 0 0 7 0 0 0\n.1 2 0 0 6 0 1 0 0 0\n')
        loaded=next(r for r in report['populations'] if r['enemy_count']==7)
        easy=next(r for r in report['populations'] if r['enemy_count']==1)
        self.assertLess(report['rounds'][0]['missed_slots_percent'],5)
        self.assertEqual(loaded['missed_slots_percent'],100)
        self.assertEqual(easy['missed_slots_percent'],0)

    def test_population_measurement_keeps_long_active_stalls(self):
        report=self.population_report('0 2 commit 1 0 0 0 0\n.4 2 commit 25 0 0 0 0\n',
            '0 2 0 0 0 0 7 0 0 0\n')
        self.assertEqual(report['populations'][0]['maximum_gap_ms'],400)

    def test_population_death_sample_breaks_the_segment(self):
        report=self.population_report('0 2 commit 1 0 0 0 0\n.1 2 commit 7 0 0 0 0\n.2 2 commit 13 0 0 0 0\n.2333333 2 commit 15 0 0 0 0\n',
            '0 2 0 0 0 0 7 0 0 0\n.05 2 1 0 3 0 7 0 0 0\n.15 2 0 0 9 0 7 0 0 0\n')
        self.assertEqual(report['populations'][0]['intervals'],1)
