"""Synthetic queue/oracle guards; execute game_dirty_probe.py for Z80/VRAM."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import unittest

from game_dirty_probe import cases, fixture, oracle_phase, queued, source, visible


class DirtyNamesTests(unittest.TestCase):
    def test_duplicate_marks_preserve_fifo_groups_and_128_group_capacity(self):
        bits, queue, count = queued((9, 0, 9, 15, 0))
        self.assertEqual(count, 2)
        self.assertEqual(bits[:2], bytes((1, 0x82)))
        self.assertEqual(queue[:2], bytes((1, 0)))
        bits, queue, count = queued(list(range(1024))*2)
        self.assertEqual((bits, queue, count), (bytes([255])*128, bytes(range(128)), 128))

    def test_sparse_ownership_excludes_left_edge_hud_and_hidden_rows(self):
        self.assertTrue(visible(31*32, 31, 31))  # relative column1,row0
        self.assertFalse(visible(31*32+31, 31, 31))  # special left edge
        self.assertFalse(visible(31*32+23, 31, 31))  # HUD begins at relative24
        self.assertFalse(visible(27*32, 31, 31))  # relative row28
        self.assertTrue(visible(26*32, 31, 31))  # relative row27

    def test_coverage_threshold_and_seen_are_selected_per_back_table(self):
        for back in (0, 1):
            case = dict(marks=(168,), col=0, row=0, back=back)
            world, old, names = fixture(case, 0)
            seen = bytearray((0, 0, 0, 0))
            seen[2*(1-back)] = 255  # unseen other plane does not cover this one
            _, _, plan, _, writes = oracle_phase(case, world, old, names, seen, back, {21: 1})
            self.assertEqual(plan[-1], 0)
            self.assertEqual(writes, 1)
            seen[2*back] = 255
            _, _, plan, ring_writes, writes = oracle_phase(case, world, old, names, seen, back, {21: 1})
            self.assertEqual((plan[-1], ring_writes, writes), (255, 1276, 0))
            _, _, plan, _, writes = oracle_phase(case, world, old, names, bytes(4), back,
                                                {g: 1 for g in range(24)})
            self.assertEqual((plan[-1], writes), (255, 0))

    def test_empty_unseen_plane_needs_no_dirty_coverage_flag_or_writes(self):
        case = dict(marks=(), col=7, row=31, back=0)
        world, old, names = fixture(case, 0)
        _, seen, plan, ring_writes, writes = oracle_phase(
            case, world, old, names, bytes((255, 0, 7, 31)), 0, {})
        self.assertEqual((plan[-1], ring_writes, writes), (0, 1276, 0))
        self.assertEqual(seen[:2], bytes((7, 31)))

    def test_duplicate_fixture_always_starts_with_stale_ids(self):
        case = dict(marks=(168, 168), col=0, row=0, back=0)
        world, old, _ = fixture(case, 0)
        self.assertNotEqual(world[168], old[168])

    def test_probe_uses_real_assembly_and_complete_matrix(self):
        text = source()
        self.assertIn('GameDirty_Bits EQU $d000', text)
        self.assertIn('GameDirty_Queues EQU $d100', text)
        self.assertIn('GameDirty_Plan:', text)
        self.assertIn('Ring_UploadNames:', text)
        matrix = cases()
        self.assertEqual({c['marks'][0] for c in matrix if c['label'] == 'single'},
                         set(range(1024)))
        self.assertEqual(sum(c['label'] == 'all-byte-masks' for c in matrix), 255)
        self.assertIn('128-groups', {c['label'] for c in matrix})
        self.assertIn('24-groups', {c['label'] for c in matrix})
        self.assertIn('23-groups', {c['label'] for c in matrix})


if __name__ == '__main__':
    unittest.main()
