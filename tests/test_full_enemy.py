"""Hardware allocation tests for complete-car population rendering."""
import unittest
from scripts.msx.full_enemy import pattern_plan


class FullEnemyTests(unittest.TestCase):
    def test_seven_complete_car_caches_fit_with_both_radar_phases_and_player(self):
        common,victims=pattern_plan()
        self.assertEqual(len(common),3)
        self.assertEqual(len(victims),7)
        self.assertEqual(sum(8 for _ in common)+sum(8 for _ in victims),80)
        self.assertTrue(all(base%8==0 for base in victims))
        self.assertEqual(16+2+len(victims)*2,32)

    def test_linked_radar_pattern_cannot_share_a_complete_car_cache(self):
        with self.assertRaisesRegex(ValueError,'overlaps'):
            pattern_plan(radar_pattern=232)
