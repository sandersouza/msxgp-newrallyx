"""Clock/input/state contracts use authored synthetic data, never game payloads."""
from dataclasses import FrozenInstanceError, replace
import unittest

from scripts.msx.native_contract import (
    Exclusion, Snapshot, advance_clock, first_difference, input_bytes,
)


class NativeClockTests(unittest.TestCase):
    def test_exact_long_run_at_both_refresh_modes(self):
        # Independently calculated integer results for 100,000 complete frames.
        for cycles, expected_ticks, expected_remainder, counts in (
                (71364, 120827, 112437405, {1, 2}),
                (59736, 101140, 39017100, {1, 2})):
            with self.subTest(cycles=cycles):
                ticks = remainder = 0
                observed = set()
                for _ in range(100000):
                    due, remainder = advance_clock(remainder, cycles)
                    ticks += due
                    observed.add(due)
                self.assertEqual(ticks, expected_ticks)
                self.assertEqual(remainder, expected_remainder)
                self.assertEqual(observed, counts)

    def test_threshold_and_preserved_remainder(self):
        self.assertEqual(advance_clock(0, 59062), (0, 118124000))
        self.assertEqual(advance_clock(118124000, 1), (1, 1015))
        self.assertEqual(advance_clock(1015, 0), (0, 1015))
        self.assertEqual(advance_clock(0, 0), (0, 0))

    def test_invalid_clock_values_are_rejected(self):
        for remainder, elapsed in ((-1, 0), (118124985, 0), (0, -1),
                                   (True, 0), (0, False), (1.5, 0), (0, '1')):
            with self.subTest(remainder=remainder, elapsed=elapsed), self.assertRaises(ValueError):
                advance_clock(remainder, elapsed)


class NativeInputTests(unittest.TestCase):
    def test_pinned_active_low_input_bits(self):
        for pressed, expected in (((), 0xff), (('coin',), 0x7f), (('start',), 0xbf),
                                   (('smoke',), 0xfd), (('up',), 0xdf),
                                   (('down',), 0xef), (('right',), 0xf7),
                                   (('left',), 0xfb), (('up', 'right', 'smoke'), 0xd5),
                                   (('up', 'down', 'left', 'right'), 0xc3),
                                   (('coin', 'start', 'smoke'), 0x3d)):
            with self.subTest(pressed=pressed):
                self.assertEqual(input_bytes(frozenset(pressed), 0xc3),
                                 bytes((expected, 0xff, 0xc3)))

    def test_release_and_repeated_levels_preserve_original_edge_handling(self):
        schedule = ((), ('coin',), ('coin',), (), ('start',), ())
        self.assertEqual([input_bytes(frozenset(keys), 0)[0] for keys in schedule],
                         [0xff, 0x7f, 0x7f, 0xff, 0xbf, 0xff])

    def test_dip_is_raw_and_sources_are_unchanged(self):
        pressed = frozenset(('coin', 'up'))
        for dip in (0, 1, 0xc3, 255):
            self.assertEqual(input_bytes(pressed, dip), bytes((0x5f, 0xff, dip)))
        self.assertEqual(pressed, frozenset(('coin', 'up')))

    def test_invalid_input_names_and_dip_values_are_rejected(self):
        for keys, dip in ((frozenset(('pause',)), 0), ('coin', 0),
                          (frozenset(), -1), (frozenset(), 256),
                          (frozenset(), True), (frozenset(), '3')):
            with self.subTest(keys=keys, dip=dip), self.assertRaises(ValueError):
                input_bytes(keys, dip)


class NativeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = Snapshot(7, 'post-game-irq', bytes(4096), bytes(2048), bytes(392))

    def test_equal_snapshots_have_no_difference_and_are_immutable(self):
        self.assertIsNone(first_difference(self.snapshot, replace(self.snapshot)))
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.tick = 8

    def test_first_difference_uses_original_sparse_memory_addresses(self):
        for region, size, index, address in (
                ('video', 4096, 0, 0x8000), ('video', 4096, 4095, 0x8fff),
                ('work', 2048, 0, 0x9800), ('work', 2048, 2047, 0x9fff),
                ('shadows', 392, 0, 0xa000), ('shadows', 392, 391, 0xa187)):
            payload = bytearray(size)
            payload[index] = 42
            actual = replace(self.snapshot, **{region: bytes(payload)})
            with self.subTest(address=address):
                self.assertEqual(first_difference(self.snapshot, actual),
                                 dict(tick=7, region=region, address=address, expected=0, actual=42))

    def test_first_difference_is_ordered_not_dependent_on_exclusion_order(self):
        actual = replace(self.snapshot, video=b'\x01\x02' + bytes(4094),
                         work=b'\x03' + bytes(2047))
        self.assertEqual(first_difference(self.snapshot, actual)['address'], 0x8000)
        exclusion = Exclusion(0x8000, 'Synthetic scratch byte', 'synthetic-case-1')
        self.assertEqual(first_difference(self.snapshot, actual, (exclusion,))['address'], 0x8001)
        self.assertEqual(actual.video[:2], b'\x01\x02')

    def test_exclusions_are_exact_and_allow_a_single_documented_difference(self):
        actual = replace(self.snapshot, shadows=b'\x01' + bytes(391))
        exclusion = Exclusion(0xa000, 'Synthetic shadow exception', 'synthetic-case-2')
        self.assertIsNone(first_difference(self.snapshot, actual, (exclusion,)))
        with self.assertRaises(ValueError):
            first_difference(self.snapshot, actual, (exclusion, exclusion))

    def test_misaligned_or_missing_records_are_rejected(self):
        for actual in (replace(self.snapshot, tick=8),
                       replace(self.snapshot, phase='pre-game-irq'), None):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                first_difference(self.snapshot, actual)
        with self.assertRaises(ValueError):
            first_difference(None, self.snapshot)

    def test_invalid_snapshot_metadata_and_payloads_are_rejected(self):
        for changes in (dict(tick=-1), dict(tick=True), dict(phase='vblank'),
                        dict(video=bytes(4095)), dict(work=bytes(2049)),
                        dict(shadows=bytes(391)), dict(video=bytearray(4096)),
                        dict(shadows=None)):
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                replace(self.snapshot, **changes)

    def test_exclusions_require_real_addresses_and_specific_evidence(self):
        for address, reason, evidence in ((0x9000, 'gap', 'case'),
                                          (0xa188, 'outside', 'case'),
                                          (-1, 'negative', 'case'), (True, 'bool', 'case'),
                                          (0x8000, '', 'case'), (0x8000, 'reason', '  ')):
            with self.subTest(address=address), self.assertRaises(ValueError):
                Exclusion(address, reason, evidence)
        with self.assertRaises(ValueError):
            first_difference(self.snapshot, self.snapshot, (None,))


if __name__ == '__main__':
    unittest.main()
