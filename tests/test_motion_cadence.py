"""Native throughput cannot hide repeated physical frames with movement debt."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from src.toolchain.msx.motion_cadence import analyze


class PhysicalMotionTests(unittest.TestCase):
    def report(self,positions,*,loading=False,projection=None):
        with TemporaryDirectory() as d:
            p=Path(d)/'motion.tsv'
            rows=[]
            for n,x in enumerate(positions):
                rows.append([n/60,3,0,0,x,0,124+n*2,105,255,0,544,0,n, int(loading and n in range(4,10)),0,0,0,0])
                if projection is not None:rows[-1].extend((projection[n],105))
            p.write_text('\n'.join(' '.join(map(str,row)) for row in rows))
            return analyze(p,1/60)['rounds'][0]

    def test_continuous_native_motion_does_not_exclude_a_frozen_camera(self):
        r=self.report([0,2,4,6]+[6]*6+[20,22,24])
        self.assertAlmostEqual(r['maximum_owed_repeat_ms'],100)
        self.assertGreater(r['percentile_95_update_interval_ms'],100)

    def test_loading_does_not_count_as_gameplay_stutter(self):
        r=self.report([0,2,4,6]+[6]*6+[20,22,24],loading=True)
        self.assertEqual(r['maximum_owed_repeat_ms'],0)

    def test_regular_half_rate_is_distinct_from_irregular_updates(self):
        r=self.report([n//2*4 for n in range(60)])
        self.assertAlmostEqual(r['update_hz'],29/59*60)
        self.assertEqual(r['update_intervals_in_refreshes'],{2:28})

    def test_a_bounded_camera_with_a_moving_car_is_not_a_frozen_frame(self):
        r=self.report([0]*60,projection=[124+n//2*4 for n in range(60)])
        self.assertAlmostEqual(r['update_hz'],29/59*60)
        self.assertLessEqual(r['maximum_owed_repeat_ms'],1000/60)


if __name__=='__main__':unittest.main()
