import unittest

from scripts.msx.audio_score import encode, melody, pair_frames
from scripts.msx.audio_psg import period


class AudioScoreTests(unittest.TestCase):
    def test_pair_keeps_absolute_note_boundaries_and_stops_at_first_end(self):
        frames=pair_frames([(1024,3),(2048,5)],[(4096,8),(8192,20)])
        self.assertEqual(len(frames),4)
        self.assertEqual([int.from_bytes(row[:2],'little') for row in frames],
                         [period(1024),period(1024),period(2048),period(2048)])
        self.assertEqual({int.from_bytes(row[2:4],'little') for row in frames},{period(4096)})
        self.assertEqual(pair_frames([(0,2)],[(4096,2)])[0][4],0)

    def test_rle_splits_long_holds_without_wrapping_duration(self):
        first=bytes((1,0,2,0,10,11));second=bytes((3,0,4,0,12,13))
        result=encode([first]*256+[second]*2)
        packed_first=first[:4]+b'\xba';packed_second=second[:4]+b'\xdc'
        self.assertEqual(result,bytes((255,))+packed_first+bytes((1,))+packed_first+bytes((2,))+packed_second+b'\0')
        with self.assertRaises(ValueError): encode([])

    def test_synthetic_melody_uses_note_octave_and_duration_with_bounds(self):
        p=bytearray(16384)
        p[0x2b58:0x2b5a]=(0x2d00).to_bytes(2,'little')
        p[0x2afd+4:0x2aff+4]=(8192).to_bytes(2,'little')
        p[0x2d00:0x2d05]=bytes((0x32,6,0x02,4,255))
        self.assertEqual(melody(p,0),[(1024,6),(8192,4)])
        p[0x2d01]=0
        with self.assertRaises(ValueError): melody(p,0)
        p[0x2b58:0x2b5a]=b'\0\0'
        with self.assertRaises(ValueError): melody(p,0)
