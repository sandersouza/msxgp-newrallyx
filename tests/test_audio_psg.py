import unittest

from src.toolchain.msx.audio_psg import PSG_CLOCK, period, period_banks, volume_curve


class AudioPSGTests(unittest.TestCase):
    def test_all_periods_are_nearest_representable_divisors(self):
        for word in range(1, 65536):
            ideal = PSG_CLOCK * 4096 / (96000 * word)
            result = period(word)
            self.assertTrue(1 <= result <= 4095)
            for candidate in (result-1, result+1):
                if 1 <= candidate <= 4095:
                    self.assertLessEqual(abs(result-ideal), abs(candidate-ideal))
        self.assertEqual(period(0), 0)

    def test_bank_boundaries_keep_the_full_phase_word(self):
        banks = period_banks()
        self.assertEqual([len(b) for b in banks], [16384]*8)
        for word in (0, 1, 8191, 8192, 16383, 32768, 65535):
            at = (word & 8191)*2
            self.assertEqual(int.from_bytes(banks[word >> 13][at:at+2], 'little'), period(word))

    def test_volume_curve_is_silent_at_zero_and_monotone(self):
        curve = volume_curve()
        self.assertEqual(curve[0], 0)
        self.assertEqual(curve[-1], 15)
        self.assertEqual(list(curve), sorted(curve))
        self.assertGreater(curve[1], 1)
