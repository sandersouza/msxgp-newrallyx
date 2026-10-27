"""Clock comparisons must include stalls and expose lost odd refreshes."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.msx.axis_timing import analyze


class AxisTimingTests(unittest.TestCase):
    def test_score_loss_is_distinct_from_native_and_display_clocks(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            motion = []
            audio = []
            display = []
            for n in range(121):
                axis = 0 if n < 61 else 255
                # Coordinates intentionally stop; time must remain in the sample.
                motion.append(f'{n/60} 2 0 0 0 0 0 0 {axis} 0 512 0 {n} 0 0 0 0 0')
                if n % 3 == 0:
                    audio.append(f'{n/60} 0 1 0')
                if n % 2 == 0:
                    display.append(f'{n/60} 2 commit 0 0 0 0 0')
            (root/'motion').write_text('\n'.join(motion))
            (root/'audio').write_text('\n'.join(audio))
            (root/'display').write_text('\n'.join(display))
            axes = analyze(root/'motion', root/'audio', root/'display')['axes']
            self.assertEqual(set(axes), {'horizontal', 'vertical'})
            for values in axes.values():
                self.assertAlmostEqual(values['native_hz'], 60)
                self.assertAlmostEqual(values['score_hz'], 20)
                self.assertAlmostEqual(values['presentation_hz'], 30)
                self.assertEqual(values['segments'], 1)
