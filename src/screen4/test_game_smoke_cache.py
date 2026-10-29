"""Source boundary guards for the independently assembled smoke-cache probe."""
from pathlib import Path
import tempfile
import unittest

import game_core
from game_smoke_cache import BASELINE, cases, physical, sparse


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class SmokeCacheTests(unittest.TestCase):
    def test_reference_preserves_physical_order_and_world_wrap(self):
        codes = bytearray(1024)
        codes[physical(255, 255)] = 0xc5
        codes[physical(0, 0)] = 0xbd
        expected = bytearray()
        for index in sorted((physical(255, 255), physical(0, 0))):
            expected.extend((255, 255, 0xd8) if codes[index] == 0xc5
                            else (0, 0, 0xd0))
        self.assertEqual(sparse(codes, 240, 240), bytes(expected))

    def test_probe_baseline_remains_the_original_full_scan(self):
        main = (HERE/'game-main.inc').read_text()
        original = main[main.index('Game_CacheSmoke:'):
                        main.index('Game_DirtyTileUpload:')]
        self.assertEqual(BASELINE.replace('GameSmoke_Baseline:', 'Game_CacheSmoke:').strip(),
                         original.strip())

    def test_generated_hooks_mark_rows_without_dropping_old_sparse_list(self):
        with tempfile.TemporaryDirectory() as directory:
            game_core.prepare(ROOT, directory)
            host = (Path(directory)/'game-host.inc').read_text()
        reset = host[host.index('Smoke_ClearRings:'):host.index('Smoke_PreTick:')]
        self.assertLess(reset.index('call GameSmoke_ClearRows'),
                        reset.index('ld hl,$e400'))
        row = host[host.index('Smoke_EnqueueRow:'):host.index('Smoke_Enqueue:')]
        cloud = host[host.index('Smoke_Enqueue:'):host.index('Smoke_CodeAtBC:')]
        self.assertIn('call GameSmoke_MarkRow', row)
        self.assertNotIn('call GameSmoke_MarkCloud', row)
        self.assertIn('call GameSmoke_MarkCloud', cloud)
        helper = (HERE/'game-smoke-cache.inc').read_text()
        markers = helper[:helper.index('GameSmoke_BuildCache:')]
        self.assertNotIn('(Game_SmokeCount)', markers)
        self.assertNotIn('ld ix,Game_SmokeList', markers)

    def test_native_mutation_paths_reach_the_marked_hooks(self):
        smoke = game_core.selected((ROOT/'src/screen5/smoke.inc').read_text())
        placement = smoke[smoke.index('Smoke_AfterNative:'):
                          smoke.index('Smoke_PreparePlacement:')]
        retirement = smoke[smoke.index('Smoke_RetireCode:'):
                           smoke.index('Smoke_DecodeAddress:')]
        clearing = smoke[smoke.index('Smoke_ClearNotify:'):
                         smoke.index('Smoke_RecoveredNotify:')]
        flag = smoke[smoke.index('Smoke_CollectedFlag:'):
                     smoke.index('Smoke_ClearPublishedRow:')]
        self.assertIn('jp Smoke_Enqueue', placement)
        self.assertIn('jp Smoke_EnqueueRow', retirement)
        self.assertIn('call Smoke_Enqueue', clearing)
        self.assertIn('call Smoke_Enqueue', flag)
        recovery = smoke[smoke.index('Smoke_RecoveredNotify:'):
                         smoke.index('Smoke_CollectedFlag:')]
        self.assertNotIn('Smoke_Address', recovery)
        self.assertNotIn('ld (hl),', recovery)

    def test_matrix_covers_every_physical_cell_and_diagnostic_counter_wrap(self):
        inputs = cases()
        singles = [c for c in inputs if c['label'] == 'one-live-row']
        self.assertEqual(len(singles), 1024)
        self.assertEqual({next(i for i, v in enumerate(c['codes']) if v)
                          for c in singles}, set(range(1024)))
        self.assertEqual({v for c in singles for v in c['codes'] if v},
                         set(range(0xbd, 0xc6)))
        self.assertEqual(sum(c['label'] == 'wrapped-placement-counter'
                             for c in inputs), 32)


if __name__ == '__main__':
    unittest.main()
