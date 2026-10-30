"""Synthetic tests for the explicit laboratory native-enemy population."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = RUNTIME
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('game_multi', source_path('game_multi.py'))
multi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multi)
verify_spec = importlib.util.spec_from_file_location('game_multi_verify', source_path('game_multi_verify.py'))
verify = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verify)
EMULATOR = '--emulator' in sys.argv
if EMULATOR:
    sys.argv.remove('--emulator')


def synthetic_program():
    program = bytearray(16384)
    program[0xc9b:0xca3] = bytes.fromhex('dd36080fdd360a32')
    program[0xab5:0xabc] = bytes.fromhex('06051120000e0d')
    program[0xad0:0xad4] = bytes.fromhex('dd360a34')
    program[0x1d:0x21] = bytes.fromhex('dd36880f')
    return bytes(program)


class GameMultiTests(unittest.TestCase):
    def test_default_has_no_spawn_table_or_native_override(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            metadata = multi.prepare(ROOT, out, bytes(16384))
            self.assertEqual((out/'game-multi-spawns.bin').read_bytes(), b'')
            self.assertFalse(metadata['native_population_override'])
            self.assertEqual(json.loads((out/'game-multi.json').read_text()), metadata)

    def test_spawns_are_deterministic_visible_separated_roads(self):
        program = synthetic_program()
        plan = multi.spawn_plan(program)
        self.assertEqual(plan, multi.spawn_plan(program))
        cells = plan['extra_cells']
        self.assertEqual(len(set(cells)), 6)
        player = multi.world(plan['player_cell'])
        for cell in cells:
            at = multi.world(cell)
            self.assertGreater(multi.squared_distance(at, player), 48**2)
            sx, sy = [at[i]-8-plan['camera'][i] for i in range(2)]
            self.assertTrue(8 <= sx <= 184 and 0 <= sy <= 196)
        placed = [plan['original_enemy_cell'], *cells]
        for i, a in enumerate(placed):
            for b in placed[i+1:]:
                self.assertGreaterEqual(multi.squared_distance(a, b), 4)

    def test_wall_is_never_selected_and_modes_share_prefix(self):
        program = bytearray(synthetic_program())
        program[0x3000+48*4+12//8] |= 128 >> (12&7)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            three, seven = root/'three', root/'seven'
            metadata = multi.prepare(ROOT, three, program, 3)
            multi.prepare(ROOT, seven, program, 7)
            self.assertNotIn((12, 48), multi.spawn_plan(program)['extra_cells'])
            self.assertEqual((three/'game-multi-spawns.bin').read_bytes(),
                             (seven/'game-multi-spawns.bin').read_bytes()[:4])
            self.assertTrue(metadata['valid_roads'])
            self.assertEqual(metadata['descriptor_bytes'], 24)

    def test_invalid_population_and_changed_initializer_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                multi.prepare(ROOT, directory, synthetic_program(), 2)
        with self.assertRaises(ValueError):
            multi.spawn_plan(bytes(16384))

    def test_gameplay_analysis_requires_real_visible_moving_enemies(self):
        samples = []
        for frame in range(2):
            sample = bytearray(8192)
            sample[4096+0x24e] = 3
            sample[4096+0xf] = 3-frame
            sample[0x490] = 1-frame
            for actor in range(3):
                base = 4096+0x88+actor*32
                sample[base+8], sample[base+10], sample[base+5] = 12+actor*2, 48, frame
                sample[0x80a+actor*6], sample[0x80b+actor*6] = 0, 1
                sample[0x806+actor*6] = 24+actor*48
                sample[0x808+actor*6] = 49
            samples.append(sample)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out/'run.json').write_text('{}\n')
            (out/'states.bin').write_bytes(b''.join(samples))
            result = verify.analyze(out, 3)
            self.assertEqual(result['moved_enemies'], 3)
            self.assertEqual(result['maximum_simultaneously_visible_enemies'], 3)
            self.assertEqual(result['restarts'][0]['lives'], 2)
            # A changed count with parked descriptors cannot pass the oracle.
            samples[1][4096+0x88+32+10] = 100
            (out/'states.bin').write_bytes(b''.join(samples))
            with self.assertRaises(AssertionError):
                verify.analyze(out, 3)

    def test_default_assembles_to_one_ret_and_variants_use_live_bytes_only(self):
        assembler = ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
        if not assembler.exists():
            self.skipTest('Local sjasmplus unavailable')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            for count in multi.COUNTS:
                multi.prepare(ROOT, out, synthetic_program(), count)
                (out/'test.asm').write_text(f''' OUTPUT "multi.bin"
 ORG $4000
GAME_TEST_ENEMIES EQU {count}
 INCLUDE "{HERE}/game-multi.inc"
''')
                subprocess.run([str(assembler), '--nologo', 'test.asm'],
                               cwd=out, capture_output=True, check=True)
                raw = (out/'multi.bin').read_bytes()
                if count == 0:
                    self.assertEqual(raw, bytes((0xc9,)))
                else:
                    self.assertIn(bytes.fromhex('011800edb0'), raw)  # LD BC,24 / LDIR
                    self.assertNotIn(bytes.fromhex('012000edb0'), raw)
                    self.assertIn(bytes((0x3e, count, 0x32, 0x4e, 0xe2, 0xc9)), raw)

    def test_configured_core_really_calls_the_variant_hooks(self):
        from src.toolchain.msx.hud_verify import symbols
        core_spec = importlib.util.spec_from_file_location('game_core', source_path('game_core.py'))
        core = importlib.util.module_from_spec(core_spec)
        core_spec.loader.exec_module(core)
        assembler = ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
        if not assembler.exists():
            self.skipTest('Local sjasmplus unavailable')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            core.prepare(ROOT, out)
            for name, size in (('flag-records.bin', 60), ('player-flags.bin', 256)):
                (out/name).write_bytes(bytes(size))
            for count in (0, 3):
                multi.prepare(ROOT, out, synthetic_program(), count)
                source = f''' OUTPUT "core.bin"
 ORG $4000
 DEFINE GAMEPLAY_CONFIGURED
GAME_TEST_ENEMIES EQU {count}
GAME_RENDER_OPT EQU 0
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
 INCLUDE "{HERE}/game-multi.inc"
 INCLUDE "{HERE}/game-core.inc"
 INCLUDE "game-host.inc"
 ASSERT $ <= $8000
 DISP $b500
 INCLUDE "game-native-motion.inc"
 ASSERT $ <= $b600
 ENT
 DISP $b600
 INCLUDE "game-native-ai.inc"
 ASSERT $ <= $bf00
 ENT
'''
                (out/'core.asm').write_text(source)
                subprocess.run([str(assembler), '--nologo', '--sym=core.sym', 'core.asm'],
                               cwd=out, capture_output=True, check=True)
                syms = symbols(out/'core.sym')
                raw = (out/'core.bin').read_bytes()
                for begin, end, hook in (('Game_InitCars', 'Game_Frame', 'GameMulti_Init'),
                                         ('Game_LogicTick', 'Game_Restart', 'GameMulti_Parameters')):
                    code = raw[syms[begin]-0x4000:syms[end]-0x4000]
                    call = bytes((0xcd, syms[hook] & 255, syms[hook] >> 8))
                    self.assertEqual(code.count(call), int(bool(count)), hook)

    @unittest.skipUnless(EMULATOR, 'Pass --emulator to execute the assembled initializer')
    def test_executed_initializer_preserves_native_counters_and_first_enemy(self):
        from src.toolchain.msx.emulator import reference_machine, tcl
        from src.toolchain.msx.hud_verify import symbols
        base = ROOT/'references/experiments/fixed-hud'
        base.mkdir(parents=True, exist_ok=True)
        seed = bytes(range(0x30, 0x48))
        for count in multi.COUNTS:
            with self.subTest(count=count), tempfile.TemporaryDirectory(dir=base) as directory:
                out = Path(directory)
                multi.prepare(ROOT, out, synthetic_program(), count)
                (out/'seed.bin').write_bytes(seed)
                (out/'test.asm').write_text(f''' OUTPUT "multi.rom"
 ORG $4000
 db "AB"
 dw Boot,0,0,0,0,0,0
GAME_TEST_ENEMIES EQU {count}
Boot:
 di
 ld sp,$f380
 ld a,$a5
 ld hl,$e000
 ld de,$e001
 ld bc,$3ff
 ld (hl),a
 ldir
 ld hl,Seed
 ld de,$e088
 ld bc,24
 ldir
 call GameMulti_Init
 ; Model a native Parameters_Update count change, then reapply the override.
 ld a,1
 ld ($e24e),a
 call GameMulti_Parameters
Done:
 jp Done
 INCLUDE "{HERE}/game-multi.inc"
Seed:
 INCBIN "seed.bin"
 defs $8000-$,$ff
''')
                subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),
                    '--nologo', '--sym=multi.sym', 'test.asm'], cwd=out,
                    capture_output=True, check=True)
                script = f'''set save_settings_on_exit false
set renderer none
set sound_driver null
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT, 'Panasonic_FS-A1WSX')}
set firmwareswitch off
set throttle off
cart {tcl(out/'multi.rom')} -romtype ASCII16
reset
debug set_bp {symbols(out/'multi.sym')['Done']} {{}} {{
 set f [open {tcl(out/'ram.bin')} wb]
 puts -nonewline $f [debug read_block memory 0xe000 1024]
 close $f
 exit 0
}}
after time 10 {{puts stderr "Multi initializer timeout";exit 2}}
'''
                (out/'test.tcl').write_text(script)
                with (out/'openmsx.log').open('w') as log:
                    subprocess.run(['openmsx', '-script', str(out/'test.tcl')],
                        stdout=log, stderr=subprocess.STDOUT, timeout=30, check=True,
                        env=dict(os.environ, OPENMSX_HOME=str(out/'home'),
                                 OPENMSX_USER_DATA=str(out/'userdata')))
                expected = bytearray([0xa5])*1024
                expected[0x88:0xa0] = seed
                expected[0x24e] = count or 1
                if count:
                    payload = (out/'game-multi-spawns.bin').read_bytes()
                    for actor in range(count-1):
                        at = 0xa8+actor*32
                        expected[at:at+24] = seed
                        expected[at:at+8] = bytes(8)
                        expected[at+8] = payload[actor*2]
                        expected[at+10] = payload[actor*2+1]
                self.assertEqual((out/'ram.bin').read_bytes(), expected)


if __name__ == '__main__':
    unittest.main()
