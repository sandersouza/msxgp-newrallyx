"""Synthetic Namco register traces; no original program, waveforms or music."""
import unittest

from src.toolchain.msx.audio_reference import decode_voices, summarize


class AudioReferenceTests(unittest.TestCase):
    def test_voice_register_layout_and_hardware_nibble_masks(self):
        registers = bytearray(32)
        registers[5] = 0xfd
        registers[10] = 0xfa
        registers[15] = 0xff
        for i in range(16, 32):
            registers[i] = i
        voices = decode_voices(registers)
        self.assertEqual([v.waveform for v in voices], [5, 2, 7])
        self.assertEqual([v.step for v in voices], [0x43210, 0x98760, 0xedcb0])
        self.assertEqual([v.volume for v in voices], [5, 10, 15])

    def test_frequency_uses_full_twenty_bit_phase_cycle(self):
        registers = bytearray(32)
        registers[19] = 1
        voice = decode_voices(registers)[0]
        self.assertEqual(voice.step, 4096)
        self.assertEqual(voice.frequency_hz, 375)

    def test_rejects_truncated_or_nonbyte_register_files(self):
        for registers in [bytes(31), bytes(33), [0] * 31 + [256], [0] * 31 + [-1]]:
            with self.assertRaises(ValueError):
                decode_voices(registers)

    def test_summary_keeps_write_order_and_reports_only_observed_coverage(self):
        registers = bytearray(32)
        first = [1, 0, 2, 0, 3, 0, 0, 0, 0, *registers]
        registers[17] = 1
        registers[21] = 8
        second = [2, 2, 2, 1, 3, 1, 128, 0, 0, *registers]
        writes = [(0, 0x1234, 0xa180, 255), (0, 0x1234, 0xa180, 254),
                  (1, 0x1234, 0xa180, 1), (1, 0x1234, 0xa180, 0),
                  (1, 0x2222, 0x89f4, 128)]
        report = summarize([first, second], writes)
        self.assertEqual(report['frames'], 2)
        self.assertEqual(report['maximum_active_voices'], 1)
        self.assertEqual(report['voices'][0]['audible_frames'], 1)
        self.assertEqual(report['voices'][1]['audible_frames'], 0)
        self.assertEqual(report['bang']['rising_edges'], 2)
        self.assertEqual(report['bang']['active_write_frames'], [0, 1])
        self.assertEqual(report['request_bits_written']['89f4'], [7])
        self.assertEqual(writes[0][-1], 255)  # Analysis must not normalize the raw trace.

    def test_capture_gaps_and_invalid_writes_cannot_be_qualified(self):
        row = [1, 0, 2, 0, 3, 0, 0, 0, 0, *bytes(32)]
        for rows, writes in [([row, row], []), ([row[:-1]], []),
                             ([row], [(0, 0, 0xa180, 256)]),
                             ([row], [(2, 0, 0xa180, 1)])]:
            with self.assertRaises(ValueError):
                summarize(rows, writes)

    def test_reset_ram_checks_do_not_become_gameplay_inventory(self):
        boot = [1, 240, 255, 0, 0, 0, 0, 0, 0, *bytes(32)]
        game = [2, 2, 2, 0, 3, 0, 0, 0, 0, *bytes(32)]
        report = summarize([boot, game], [(0, 0, 0x89f4, 255)], boot_frame=1)
        self.assertEqual(report['observed_modes'], [2])
        self.assertEqual(report['observed_internal_rounds'], [2])
        self.assertEqual(report['request_bits_written']['89f4'], [])


if __name__ == '__main__':
    unittest.main()
