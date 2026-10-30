"""Synthetic source-slicing and assembler contract tests for the game bridge."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import importlib.util
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

HERE = RUNTIME
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('game_core', source_path('game_core.py'))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class GameCoreTests(unittest.TestCase):
    def test_historical_flat_sources_require_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            view = base/'historical-view'
            flat = view/'src'
            flat.mkdir(parents=True)
            for source in (ROOT/'src/screen5').iterdir():
                if source.is_file() and source.suffix in ('.inc', '.asm'):
                    shutil.copyfile(source, flat/source.name)
            core.prepare(view, base/'historical-output', source_directory=flat)
            core.prepare(ROOT, base/'current-output')
            for name in ('game-host.inc', 'game-native-motion.inc', 'game-native-ai.inc'):
                self.assertEqual((base/'historical-output'/name).read_bytes(),
                                 (base/'current-output'/name).read_bytes())
            with self.assertRaises(FileNotFoundError):
                core.prepare(view, base/'unselected-flat-output')

    def test_conditional_selection(self):
        self.assertEqual(core.selected('IF HUD_ENABLED\nbad\nELSE\ngood\nENDIF\n'), 'good\n')
        self.assertEqual(core.selected('IF HUD_ENABLED\nIF UNKNOWN\nbad\nENDIF\nENDIF\ngood'), 'good\n')

    def test_native_patch_validates_each_boundary(self):
        program = bytearray(16384)
        for at, data in ((0xf3, 'dd6602'), (0xf3e, '571e09'), (0x1ddf, 'dd216880')):
            program[at:at+len(bytes.fromhex(data))] = bytes.fromhex(data)
        patched = core.patch_native(bytes(16384), program)
        self.assertEqual(patched[0xf3:0xf6], bytes((0xc3, 0, 0xb5)))
        self.assertEqual(patched[0x1ddf:0x1de3], bytes((0xc3, 9, 0xb6, 0)))
        program[0xf3] = 0
        with self.assertRaises(ValueError):
            core.patch_native(bytes(16384), program)

    def test_generated_bridge_assembles_without_legacy_video(self):
        assembler = ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
        if not assembler.exists():
            self.skipTest('local sjasmplus unavailable')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            core.prepare(ROOT, out)
            host = (out/'game-host.inc').read_text()
            self.assertNotIn('out ($99)', host)
            self.assertNotIn('out ($98)', host)
            self.assertNotIn('ld hl,Smoke_Display\n', host)
            for name, size in (('flag-records.bin', 60), ('player-flags.bin', 256)):
                (out/name).write_bytes(bytes(size))
            source = ''' OUTPUT "bridge.bin"
 ORG $4000
GAME_NATIVE_BANK EQU 5
PLAYER_DATA_BANK EQU 6
cx EQU $c000
cy EQU $c002
GameAudio_EVENT_START EQU 1
GameAudio_EVENT_FLAG EQU 2
GameAudio_EVENT_SMOKE EQU 3
GameAudio_EVENT_DEATH EQU 4
GameAudio_EVENT_CLEAR EQU 5
GameAudio_EVENT_BACKGROUND EQU 6
GameAudio_EVENT_SPECIAL_FLAG EQU 7
GameAudio_EVENT_GAMEOVER EQU 8
GameAudio_Init:
GameAudio_Tick:
GameAudio_Event:
 ret
'''+f' INCLUDE "{HERE}/game-core.inc"\n'+''' INCLUDE "game-host.inc"
 ASSERT $ <= $7000
 DISP $b500
 INCLUDE "game-native-motion.inc"
 ASSERT $ <= $b600
 ENT
 DISP $b600
 INCLUDE "game-native-ai.inc"
 ASSERT $ <= $bf00
 ENT
'''
            (out/'bridge.asm').write_text(source)
            subprocess.run([str(assembler), '--nologo', 'bridge.asm'], cwd=out,
                           capture_output=True, check=True)


if __name__ == '__main__':
    unittest.main()
