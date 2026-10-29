import unittest

from scripts.msx.audio_score import encode, melody, pair_frames, voice_frames, dictionary_encode, effect_frames
from scripts.msx.audio_psg import period


class AudioScoreTests(unittest.TestCase):
    def test_three_parts_play_together_and_share_the_earliest_ending(self):
        frames=voice_frames(([(1024,8)],[(2048,6)],[(4096,4)]),volumes=(12,10,11))
        self.assertEqual(len(frames),2)
        self.assertEqual(len(frames[0]),9)
        self.assertEqual([int.from_bytes(frames[0][i:i+2],'little') for i in (0,2,4)],
                         [period(1024),period(2048),period(4096)])
        self.assertEqual(frames[0][6:],bytes((12,10,11)))

    def test_dictionary_packets_preserve_all_three_tones_and_volumes(self):
        frame=bytes((1,0,2,0,3,0,12,10,11))
        tones={(0,0):0}
        self.assertEqual(dictionary_encode([frame]*2,tones),bytes((2,1,2,3,0)))
        self.assertEqual(list(tones),[(0,0),(1,12),(2,10),(3,11)])

    def test_credit_is_a_melodic_contour_while_smoke_uses_noise(self):
        p=bytearray(16384)
        p[0x2b58:0x2b5a]=(0x2d00).to_bytes(2,'little')
        p[0x2afd+2:0x2aff+2]=(1024).to_bytes(2,'little')
        p[0x2afd+4:0x2aff+4]=(2048).to_bytes(2,'little')
        p[0x2d00:0x2d05]=bytes((1,4,2,4,255))
        frames=effect_frames(p,5)
        self.assertEqual([int.from_bytes(f[:2],'little') for f in frames],[period(1024)]*2+[period(2048)]*2)
        self.assertTrue(all(f[3:]==bytes((0,32)) for f in frames))
        self.assertTrue(all(f[3]>0 and f[4]==4 for f in effect_frames(p,2)))

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

    def test_omitted_voice_still_ends_the_original_music_group(self):
        first=[(1024,4),(2048,8)]
        second=[(4096,4),(8192,4)]
        omitted=[(16384,4)]
        frames=pair_frames(first,second,omitted)
        self.assertEqual(len(frames),2)
        self.assertEqual({int.from_bytes(row[:2],'little') for row in frames},{period(1024)})
        self.assertEqual({int.from_bytes(row[2:4],'little') for row in frames},{period(4096)})
        self.assertEqual(len(pair_frames(first,second,[(0,20)])),4)

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
