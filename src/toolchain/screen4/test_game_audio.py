"""Synthetic compiler/placement checks; no original melody fixtures."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('game_audio', source_path('game_audio.py'))
audio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audio)
ROOT = Path(__file__).resolve().parents[3]


def synthetic_program():
    program = bytearray(0x3000)
    program[0x2afd:0x2aff] = (2048).to_bytes(2, 'little')
    program[0x2b54:0x2b58] = bytes((1, 2, 3, 255))
    for identifier in range(24):
        program[0x2b58+identifier*2:0x2b5a+identifier*2] = (0x2c00).to_bytes(2, 'little')
    program[0x2c00:0x2c03] = bytes((0, 12, 255))
    return program


class GameAudioTests(unittest.TestCase):
    def test_score_bank_is_bounded_and_symbols_are_mapped(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            bank, metadata = audio.build(synthetic_program(), out)
            self.assertEqual(len(bank), 16384)
            for name, entry in metadata.items():
                self.assertEqual(bank[entry['address']+entry['bytes']-1], 0)
                self.assertIn(f'GameAudio_{name.title()}Score EQU ${0x8000+entry["address"]:04x}',
                              (out/'game-audio-data.inc').read_text())
            self.assertEqual(metadata['intro']['frames'], 6)
            self.assertEqual(metadata['normal']['frames'], 18)

    def test_omitted_voice_still_terminates_group(self):
        first = [(2048, 10)]
        self.assertEqual(len(audio.pair_frames(first, first, [(2048, 3)])), 2)

    def test_malformed_input_rejected(self):
        with self.assertRaises(ValueError):
            audio.melody(bytearray(0x3000), 0)
        with self.assertRaises(ValueError):
            audio.encode([])
        with self.assertRaises(ValueError):
            audio.encode([bytes((0, 0, 0, 0, 16, 0))])

    def test_resident_assembler_and_private_ram_contract(self):
        assembler = ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
        if not assembler.exists():
            self.skipTest('local sjasmplus not installed')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            audio.build(synthetic_program(), out)
            source = ('    OUTPUT "probe.bin"\n    ORG $4000\nGAME_AUDIO_BANK EQU 3\n'
                      '    INCLUDE "game-audio-data.inc"\n'
                      f'    INCLUDE "{source_path("game-audio.inc")}"\n'
                      '    ASSERT $ <= $8000\n'
                      '    ASSERT GameAudio_PlayDesired >= $dc00\n'
                      '    ASSERT GameAudio_StateEnd <= $de00\n')
            (out/'probe.asm').write_text(source)
            subprocess.run([str(assembler), '--nologo', 'probe.asm'], cwd=out,
                           check=True, capture_output=True)
            self.assertLess(len((out/'probe.bin').read_bytes()), 1200)


if __name__ == '__main__':
    unittest.main()
