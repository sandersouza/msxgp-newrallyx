import csv
import json
from pathlib import Path
import tempfile
import unittest

from scripts.msx.native_video_verify import verify_video_frames
from scripts.msx.native_verify import analyze_presentation_callers


class NativeVideoEvidenceTests(unittest.TestCase):
    def test_caller_costs_require_real_call_instructions_and_complete_totals(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            (output/'native.sym').write_text('Native_PrepareFrame: EQU 0x5000\n')
            (output/'native.rom').write_bytes(bytes((0xcd, 0, 0x50)))
            (output/'manifest.json').write_text('{}')
            (output/'presentation-context.json').write_text(json.dumps(dict(calls=3, steps=1)))
            path = output/'presentation-callers.tsv'
            header = 'caller\tcalls\tsteps\tskip_cycles\tstep_cycles\tmax_cycles\n'
            path.write_text(header+'16387\t3\t1\t100\t200\t200\n')
            self.assertTrue(analyze_presentation_callers(output, output)['complete'])
            for bad in ('16387\t4\t1\t100\t200\t200\n',
                        '16388\t3\t1\t100\t200\t200\n',
                        '16387\t3\t1\t0\t200\t200\n'):
                path.write_text(header+bad)
                with self.assertRaises(ValueError):
                    analyze_presentation_callers(output, output)

    def fixture(self, output):
        (output/'execution.json').write_text(json.dumps(dict(complete=True, ticks=7)))
        (output/'presentation-context.json').write_text(json.dumps(dict(
            complete=True, calls=9, steps=5, game_ram_bytes=6536,
            registers=['AF', 'BC', 'DE', 'HL', 'IX', 'IY', 'AF2', 'BC2', 'DE2', 'HL2', 'SP'])))
        fields = ['frame', 'tick', 'cycles', 'phase', 'time', 'hud_cycles',
                  'tile_cycles', 'restore_cycles', 'actor_cycles', 'input_tick', 'latency_cycles']
        with (output/'video.tsv').open('w') as stream:
            writer = csv.writer(stream, delimiter='\t')
            writer.writerow(fields)
            writer.writerow([1, 7, 1000, 1, 1.0, 100, 200, 300, 400, 6, 3000])
        with (output/'video-steps.tsv').open('w') as stream:
            writer = csv.writer(stream, delimiter='\t')
            writer.writerow(['input_tick', 'tick', 'stage', 'cycles', 'time'])
            for stage, cycles in enumerate([100, 200, 300, 400, 0]):
                writer.writerow([6, 7, stage, cycles, 0.99+stage*0.001])
        prefix = output/'video-frame-00001'
        host = bytearray(2176)
        host[0x10], host[0x16], host[0x18] = 1, 1, 0x3f
        for suffix, data in [('state', bytes(6536)), ('host', bytes(host)),
                             ('cache', bytes(4096)), ('dirty', bytes(128)),
                             ('vram', bytes(131072))]:
            prefix.with_name(prefix.name+f'-{suffix}.bin').write_bytes(data)

    def verify(self, output):
        return verify_video_frames(output, bytes(16384), bytes(16384),
                                   bytes(256), bytes(range(16)))

    def test_complete_scene_evidence_remains_distinct_from_raster_and_gameplay(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            self.fixture(output)
            result = self.verify(output)
            self.assertTrue(result['prepared_bitmaps_verified'])
            self.assertEqual(result['compared_pixels'], 40200)
            self.assertFalse(result['rendered_rgb_verified'])
            self.assertFalse(result['gameplay_verified'])
            self.assertEqual(result['max_step_cycles'], 400)

    def test_missing_frame_or_false_ready_page_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            self.fixture(output)
            vram = output/'video-frame-00001-vram.bin'
            vram.unlink()
            with self.assertRaisesRegex(ValueError, 'inventory'):
                self.verify(output)
            vram.write_bytes(bytes(131072))
            host = output/'video-frame-00001-host.bin'
            data = bytearray(host.read_bytes())
            data[0x18] = 0x1f  # Pending page disagrees with the completed draw page.
            host.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'ready'):
                self.verify(output)

    def test_register_context_and_pixel_corruption_are_separate_gates(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            self.fixture(output)
            vram = output/'video-frame-00001-vram.bin'
            data = bytearray(vram.read_bytes())
            data[32768+22*128+9//2] = 0x01
            vram.write_bytes(data)
            result = self.verify(output)
            self.assertFalse(result['prepared_bitmaps_verified'])
            self.assertEqual(result['different_pixels'], 1)
            context = output/'presentation-context.json'
            data = json.loads(context.read_text())
            data['game_ram_bytes'] = 6144
            context.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'context'):
                self.verify(output)


if __name__ == '__main__':
    unittest.main()
