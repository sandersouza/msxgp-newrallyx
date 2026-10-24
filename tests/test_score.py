"""Synthetic input/carry/threshold coverage for the independent score oracle."""
import unittest
from scripts.msx.score_verify import packet,cases_for,DIGITS


class ScoreTests(unittest.TestCase):
    def test_score_fixtures_preserve_decimal_value_and_original_fixed_ones(self):
        for value in (0,90,100,19990,20000,80000,99999990):
            raw=packet(value)
            self.assertEqual(int(''.join(str(raw[i]&15) for i in DIGITS)),value)
            self.assertEqual(raw[3],0x30)
        for value in (-10,1,100000000):
            with self.assertRaises(ValueError):packet(value)

    def test_oracle_matrix_includes_repeat_events_midgroup_records_and_awarded_lives(self):
        cases=cases_for()
        self.assertTrue(any(not reset for reset,*_ in cases))
        self.assertEqual({kind for _,_,kind,*_ in cases},{1,2,4})
        self.assertTrue({2,8,10}.issubset({c[4] for c in cases}))
        self.assertTrue(any(c[6]==packet(19950) and c[7]==packet(20000) for c in cases))
