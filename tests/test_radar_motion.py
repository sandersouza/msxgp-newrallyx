"""Synthetic actor identity and staggered-cell radar residue cases."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src.toolchain.msx.radar_motion import displayed_anchors,duplicated,analyze,unattributed_bits
from src.toolchain.msx.sprite_radar import bitmap,patterns


class RadarMotionTests(unittest.TestCase):
    def test_one_enemy_cannot_leave_distinct_markers_in_two_cells(self):
        syms=dict(Radar_PublishedPoints=0xdb40,Radar_StagedPoints=0xcd40,
                  Radar_PendingCell=0xcf18,Radar_Base=0xc800)
        state=bytearray(12288);state[0x1b40:0x1c00]=bytes([255])*192
        state[0xd40:0xe00]=bytes([255])*192;state[0xf18]=255
        points=[(4,4),(20,20)]
        for cell,point in [(0,points[0]),(4,points[1])]:
            state[0x1b40+cell*16+2:0x1b40+cell*16+4]=bytes(point)
        record=state+patterns(bitmap(points,border=False))
        self.assertFalse(unattributed_bits(record,syms))
        shown=displayed_anchors(record,syms)
        self.assertEqual(shown[0],set(points));self.assertTrue(duplicated(shown[0]))
        self.assertTrue(all(not p for p in shown[1:]))
        state[0xf18]=0  # Uploaded replacement has staged metadata pending commit.
        self.assertTrue(unattributed_bits(state+patterns(bitmap(points,border=False)),syms))
        shown=displayed_anchors(state+patterns(bitmap(points,border=False)),syms)
        self.assertEqual(shown[0],{points[1]});self.assertFalse(duplicated(shown[0]))

    def test_small_fragments_at_a_cell_boundary_are_one_marker(self):
        self.assertFalse(duplicated({(15,14),(16,15)}))
        self.assertTrue(duplicated({(14,14),(17,15)}))

    def test_persistent_residue_fails_even_if_each_cell_is_a_valid_old_snapshot(self):
        syms=dict(Radar_PublishedPoints=0xdb40,Radar_StagedPoints=0xcd40,
                  Radar_PendingCell=0xcf18,Radar_Base=0xc800)
        state=bytearray(12288);state[0x1b40:0x1c00]=bytes([255])*192
        state[0xd40:0xe00]=bytes([255])*192;state[0xf18]=255
        for cell,point in [(0,(4,4)),(4,(20,20))]:
            state[0x1b40+cell*16+2:0x1b40+cell*16+4]=bytes(point)
        stale=state+patterns(bitmap([(4,4),(20,20)],border=False))
        clean=bytearray(state);clean[0x1b42:0x1b44]=b'\xff\xff'
        clean+=patterns(bitmap([(20,20)],border=False))
        with TemporaryDirectory() as name:
            path=Path(name);(path/'effects-times.tsv').write_text('0\n0.1\n0.4\n')
            (path/'effects.bin').write_bytes(stale*3)
            self.assertFalse(analyze(path,syms)['passed'])
            (path/'effects-times.tsv').write_text('0\n0.1\n0.15\n')
            (path/'effects.bin').write_bytes(stale*2+clean)
            self.assertTrue(analyze(path,syms)['passed'])
            unowned=bytearray(stale);unowned[0x1b42:0x1b44]=b'\xff\xff'
            (path/'effects-times.tsv').write_text('0\n0.1\n0.4\n')
            (path/'effects.bin').write_bytes(unowned*3)
            result=analyze(path,syms)
            self.assertEqual(result['duplicate_actor_samples'],0)
            self.assertGreater(result['maximum_unknown_ink_ms'],200)
            self.assertFalse(result['passed'])
            broken=bytearray(clean);broken[12288+384]^=1
            (path/'effects.bin').write_bytes(broken*3)
            result=analyze(path,syms)
            self.assertGreater(result['shifted_pattern_mismatches'],0)
            self.assertFalse(result['passed'])
