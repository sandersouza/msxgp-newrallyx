"""Reject scanline evidence that silently advances at VBlank speed or loses ticks."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.msx.native_verify import analyze_fine_clock, analyze_fine_math
from scripts.msx.native_deadline import deadline_state, analyze_deadline_math, analyze_deadlines


class NativeFineClockTests(unittest.TestCase):
    def test_deadline_phase_clamping_and_accepted_tick_conservation(self):
        self.assertEqual(deadline_state(1,313),(260,29001,0,313))
        self.assertEqual(deadline_state(2,313),(206,27602,206,519))
        self.assertEqual(deadline_state(2,262),(257,27602,0,524))
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            t1,t2 = (1+n*228/3579545 for n in (313,519))
            good = ('event\tsequence\tline\terror\ttarget\tclaimed\tpending\taccepted\tarmed\ttime\n'
                    'sync\t0\t0\t0\t0\t0\t0\t0\t0\t1.0\n'
                    f'deadline\t1\t260\t29001\t0\t0\t0\t0\t0\t{t1}\n'
                    f'deadline\t2\t206\t27602\t206\t1\t0\t1\t1\t{t2}\n')
            final = dict(claimed=2,pending=0,accepted=2,deadlines=2)
            (out/'fine.tsv').write_text(good)
            (out/'fine-final.json').write_text(json.dumps(final))
            self.assertEqual(analyze_deadlines(out,313,2)['accepted'],2)
            for bad in (good.replace('27602','27603'),good.replace('206\t1\t0\t1','206\t1\t0\t0'),
                        good.replace('206\t1\t0\t1\t1','206\t1\t0\t1\t0'),
                        good.replace(str(t2),str(t2+0.02)),good.replace(str(t2),'nan'),
                        good.replace('deadline\t2','deadline\t3'),good.splitlines(True)[0]):
                (out/'fine.tsv').write_text(bad)
                with self.assertRaisesRegex(ValueError,'deadline'):
                    analyze_deadlines(out,313,2)
            (out/'fine.tsv').write_text(good)
            for bad in (dict(final,claimed=True),dict(final,pending=1),dict(final,accepted=1)):
                (out/'fine-final.json').write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'deadline'):
                    analyze_deadlines(out,313,2)

    def test_deadline_arithmetic_requires_all_actual_cases_and_fractional_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            good = dict(cases=100000,frame_lines=313,deadline=25904602%313,error=800)
            (out/'fine-math.json').write_text(json.dumps(good))
            self.assertEqual(analyze_deadline_math(out,313),good)
            for key,value in (('cases',99999),('frame_lines',262),('error',0),('deadline',True)):
                (out/'fine-math.json').write_text(json.dumps(dict(good,**{key:value})))
                with self.assertRaisesRegex(ValueError,'deadline'):
                    analyze_deadline_math(out,313)

    def test_three_quanta_reconcile_one_pal_frame_and_reject_wrong_clock_or_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            t1 = 1+19152/3579545
            t2 = t1+23028/3579545
            good = ('claimed\tquantum\tnext\tpending\tremainder\ttime\n'
                    '0\t58368000\t2\t0\t0\t1.0\n'
                    f'0\t38304000\t0\t0\t58368000\t{t1}\n'
                    f'0\t46056000\t1\t0\t96672000\t{t2}\n')
            final = dict(claimed=1,pending=0,remainder=24603015)
            (out/'fine.tsv').write_text(good)
            (out/'fine-final.json').write_text(json.dumps(final))
            report = analyze_fine_clock(out,71364,1)
            self.assertEqual((report['ticks'],report['remainder'],report['samples']),
                             (1,24603015,3))
            for bad in (good.replace('58368000\t'+str(t1),'142728000\t'+str(t1)),
                        good.replace('96672000','96672001'),
                        good.replace('38304000\t0\t0','38304000\t0\t1'),
                        good.replace(str(t2),str(t2+0.02)),
                        good.replace(str(t2),'nan'),good.splitlines(True)[0]):
                (out/'fine.tsv').write_text(bad)
                with self.assertRaisesRegex(ValueError,'fine-clock'):
                    analyze_fine_clock(out,71364,1)
            (out/'fine.tsv').write_text(good)
            for bad in (dict(final,claimed=True),dict(final,pending=1),dict(final,remainder=0)):
                (out/'fine-final.json').write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'fine-clock'):
                    analyze_fine_clock(out,71364,1)

    def test_long_run_requires_real_armed_path_exact_remainder_and_all_frames(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            good = dict(frames=100000,complete=True,frame_cycles=71364,
                        ticks=120827,remainder=112437405)
            (out/'fine-math.json').write_text(json.dumps(good))
            self.assertEqual(analyze_fine_math(out,71364),good)
            for key,value in (('frames',99999),('complete',1),('frame_cycles',59736),
                              ('ticks',362482),('remainder',0)):
                (out/'fine-math.json').write_text(json.dumps(dict(good,**{key:value})))
                with self.assertRaisesRegex(ValueError,'fine-clock'):
                    analyze_fine_math(out,71364)
