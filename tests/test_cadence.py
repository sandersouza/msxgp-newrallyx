"""Elapsed-time evidence must retain stalls and distinguish rendering cadence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.msx.cadence import analyze,analyze_scroll


class CadenceTests(unittest.TestCase):
    def test_scroll_wrap_and_state_gaps_are_not_camera_jumps(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'camera.tsv'
            path.write_text('0 2 0 0 253 253 0 0 0\n.02 2 0 0 3 3 0 0 0\n.04 2 1 0 80 80 0 0 0\n1 2 0 0 90 90 0 0 0\n1.02 2 0 0 111 111 0 0 0\n')
            r=analyze_scroll(path)
            self.assertEqual(r['adjacent_active_frames'],2)
            self.assertEqual(r['maximum_vertical_step'],21)
            self.assertEqual(r['steps_over_six_pixels'],1)

    def report(self,rows):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'cadence.tsv'
            path.write_text('\n'.join(' '.join(map(str,r)) for r in rows))
            return analyze(path)['rounds'][0]

    def test_physical_camera_updates_are_distinct_from_native_batching(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'camera.tsv'
            def run(smooth):
                path.write_text('\n'.join(f'{n*.02} 2 0 0 {(n*3 if smooth else n//2*6)%256} 0 0 0 {n//2*6}' for n in range(100)))
                return analyze_scroll(path)['moving_vertical_rounds'][0]['vertical_update_hz']
            self.assertAlmostEqual(run(True),50)
            self.assertAlmostEqual(run(False),25)

    def test_wall_time_stalls_are_included_even_when_longer_than_a_refresh(self):
        rows=[[0,2,0,0,0,0,7,0,0,0,0,0],
              [.02,2,0,0,1,0,7,1,0,0,0,1],
              [.52,2,0,0,1,1,7,0,12,1,2,26],
              [.54,2,0,0,5,1,7,4,8,0,2,27]]
        r=self.report(rows)
        self.assertAlmostEqual(r['native_hz'],5/.54)
        self.assertAlmostEqual(r['longest_hold_ms'],500)
        self.assertEqual(r['discarded_ticks'],2)
        self.assertEqual(r['foreground_loops'],3)
        self.assertEqual(r['enemy_counts'],[7])
        self.assertEqual(r['loops_over_40_ms'],1)
        self.assertAlmostEqual(r['percentile_99_loop_ms'],500)

    def test_challenge_interstitial_is_separate_from_active_gameplay(self):
        rows=[[0,4,0,0,0,0,3,0,0,0,0,0,0],
              [.02,4,0,0,1,0,3,1,0,0,0,1,0],
              [.04,4,0,0,1,0,3,0,0,0,0,2,7],
              [6.44,4,0,0,1,0,3,0,0,0,0,130,7],
              [6.46,4,0,0,1,0,3,0,0,0,0,131,0],
              [6.48,4,0,0,2,0,3,1,0,0,0,132,0]]
        r=self.report(rows)
        self.assertAlmostEqual(r['active_seconds'],.04)
        self.assertAlmostEqual(r['native_hz'],50)
        self.assertEqual(r['discarded_ticks'],0)

    def test_counter_wrap_and_death_time_are_handled_separately(self):
        rows=[[0,2,0,0,65535,65535,3,1,0,0],
              [.02,2,0,0,1,0,3,2,0,0],
              [.04,2,1,0,2,0,3,1,0,0],
              [1.04,2,0,0,3,0,3,1,0,0],
              [1.06,2,0,0,4,0,3,1,0,0]]
        r=self.report(rows)
        self.assertAlmostEqual(r['active_seconds'],.04)
        self.assertAlmostEqual(r['native_hz'],75)
        self.assertIsNone(r['discarded_ticks'])

    def test_long_window_exposes_sustained_slowdown(self):
        rows=[[n/30,2,0,0,n,0,7,1,0,0] for n in range(301)]
        r=self.report(rows)
        self.assertAlmostEqual(r['native_hz'],30)
        self.assertAlmostEqual(r['minimum_five_second_native_hz'],30)

    def test_presentation_pauses_remain_visible_with_caught_up_native_ticks(self):
        # Two due native ticks can hide a missed display refresh in the average.
        rows=[[0,2,0,0,0,0,2,0,0,0],
              [.02,2,0,0,1,0,2,1,0,0],
              [.06,2,0,0,4,0,2,3,0,0],
              [.08,2,0,0,5,0,2,1,0,0]]
        r=self.report(rows)
        self.assertAlmostEqual(r['native_hz'],62.5)
        self.assertAlmostEqual(r['presentation_loop_hz'],37.5)
        self.assertEqual(r['loops_over_30_ms'],1)
        self.assertAlmostEqual(r['percentile_95_loop_ms'],40)
        self.assertEqual(r['loops_over_40_ms'],0)

    def test_invalid_counter_jump_is_not_silently_excluded(self):
        with self.assertRaisesRegex(ValueError,'discontinuity'):
            self.report([[0,2,0,0,1,0,1,1,0,0],[1,2,0,0,100,0,1,1,0,0]])
