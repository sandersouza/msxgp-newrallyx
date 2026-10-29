"""Execute contributor-native gameplay and PSG independently of SCREEN4 effects.

Run: .venv/bin/python src/screen4/game_core_probe.py
All generated native bytes, ROMs and observations stay under references/.
This uses explicit elapsed ticks, with interrupts disabled: it does not validate
VRAM, presented graphics, perceptual audio, or physical gameplay cadence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.msx.emulator import reference_machine, tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.inputs import load_huds, background_zero
from scripts.scenes.storage import require_ignored
import game_build
import game_sprites


def build(out):
    palette, huds, _ = load_huds(ROOT/'references/scenes/rom-input/normal',
                                ROOT/'references/scenes/rom-input/overlap')
    palette, _ = background_zero(palette, huds)
    contract = game_sprites.palette_contract(palette)
    (out/'palette.bin').write_bytes(contract['palette'])
    # These unused tile identifiers are declarations only: this ROM contains no
    # renderer or replacement effect artwork, and does not validate effects.
    (out/'prepare.json').write_text(json.dumps(dict(
        effects=dict(empty=[0], death=[0], smoke=[0]),
        palette_translation=list(contract['translation'])))+'\n')
    banks = bytearray(game_build.append_resources(ROOT, out, bytearray(), legacy_render=True))
    lab = (Path(__file__).with_name('lab.asm')).read_text()
    cartridge_slot = lab[lab.index('    call $0138'):lab.index('    ld a,4\n    call $005f')]
    main = (Path(__file__).with_name('game-main.inc')).read_text()
    page0 = main[main.index('    ; Select the primary'):main.index('    ld a,GAME_RESOURCE_BANK')]
    source = ''' OUTPUT "resident.bin"
 INCLUDE "game-config.inc"
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
cx EQU $c000
cy EQU $c002
boot:
 di
 ld sp,$f380
'''+cartridge_slot+page0+''' ld a,GAME_RESOURCE_BANK
 ld ($7000),a
 ld hl,$8000
 ld de,$3000
 ld bc,2048
 ldir
 ld a,PLAYER_DATA_BANK
 ld ($7000),a
 ld hl,$a000
 ld de,$e000
 ld bc,4096
 ldir
 ld a,$5a
 ld ($dc53),a
 ld ($de00),a
 ld ($f000),a
 call Game_InitCore
ProbeTick:
 ld a,1
 call Game_Frame
 call Game_Actors
ProbeTickDone:
 jp ProbeTick
'''+f' INCLUDE "{Path(__file__).with_name("game-core.inc")}"\n'+''' INCLUDE "game-host.inc"
 INCLUDE "game-audio-data.inc"
'''+f' INCLUDE "{Path(__file__).with_name("game-audio.inc")}"\n'+''' ASSERT $ <= $8000
 defs $8000-$,$ff
 OUTPUT "native.bin"
 ORG $8000
 INCBIN "game-native-raw.bin",0,$3500
 INCLUDE "game-native-motion.inc"
 ASSERT $ <= $b600
 defs $b600-$,$ff
 INCLUDE "game-native-ai.inc"
 ASSERT $ <= $bf00
 defs $bf00-$,$ff
 INCBIN "game-native-raw.bin",$3f00,$100
'''
    (out/'probe.asm').write_text(source)
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo',
                    '--sym=probe.sym', 'probe.asm'], cwd=out, check=True)
    banks[:16384] = (out/'native.bin').read_bytes()
    (out/'probe.rom').write_bytes((out/'resident.bin').read_bytes()+banks)
    return symbols(out/'probe.sym')


def execute(out, syms, emulator):
    lines = ['set save_settings_on_exit false', 'set renderer none',
             'set sound_driver null',
             f'filepool add -path {tcl(ROOT/"references/msxbios")} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'),
             'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked true',
             f'cart {tcl(out/"probe.rom")} -romtype ASCII16', 'reset',
             f'set output [open {tcl(out/"states.bin")} wb]', 'set sample_count 0',
             f'debug set_bp {syms["ProbeTickDone"]} {{}} {{',
             ' puts -nonewline $::output [debug read_block memory 0xc000 4096]',
             ' puts -nonewline $::output [debug read_block memory 0xe000 4096]',
             ' puts -nonewline $::output [debug read_block {PSG regs} 0 16]',
             ' incr ::sample_count',
             ' if {$::sample_count==40} {keymatrixdown 8 128}',
             ' if {$::sample_count==120} {keymatrixup 8 255;keymatrixdown 8 32}',
             ' if {$::sample_count==160} {keymatrixdown 8 1}',
             ' if {$::sample_count==164} {keymatrixup 8 1}',
             ' if {$::sample_count==240} {keymatrixup 8 255;keymatrixdown 8 16}',
             ' if {$::sample_count==400} {keymatrixup 8 255}',
             ''' if {$::sample_count==850} {
  foreach {address value} {0xc50b 10 0xc540 10 0xe271 10 0xc5b0 0 0xc490 0 0xc50e 0 0xc050 0 0xe020 1 0xe26a 0 0xe26b 1 0xe269 0} {
   debug write memory $address $value
  }
 }''',
             ' foreach address {0xdc53 0xde00 0xf000} {if {[debug read memory $address]!=90} {error "RAM canary changed at $address"}}',
             ' if {$::sample_count>=1200} {close $::output;exit 0}', '}',
             'after time 60 {puts stderr "CORE TIMEOUT";exit 2}']
    (out/'probe.tcl').write_text('\n'.join(lines)+'\n')
    env = dict(os.environ, OPENMSX_HOME=str(out/'home'),
               OPENMSX_USER_DATA=str(out/'userdata'))
    with (out/'emulator.log').open('w') as log:
        subprocess.run([emulator, '-script', str(out/'probe.tcl')], env=env,
                       stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)


def verify(out):
    raw = (out/'states.bin').read_bytes()
    stride = 8192+16
    assert len(raw) == 1200*stride, 'Incomplete core execution'
    states = [raw[i:i+stride] for i in range(0, len(raw), stride)]
    first_death = next(i for i, s in enumerate(states) if s[0x490] == 1)
    restart = next(i for i in range(first_death+1, len(states)) if states[i][0x490] == 0)
    complete = next(i for i, s in enumerate(states) if s[0x40] == 2)
    assert restart-first_death == 120
    assert states[restart][0x100f] == states[0][0x100f]-1 == 2
    assert states[restart][0x50b] == states[849][0x50b] == 1
    assert states[restart][0x126b] == 60
    assert max(s[0x711] for s in states[:850]) > 0
    assert all(int.from_bytes(s[0x440:0x442], 'little') == i+1
               for i, s in enumerate(states[:complete+1]))
    assert len({s[4096:8192] for s in states[complete:]}) == 1
    intro = (out/'game-audio-intro-frames.bin').read_bytes()
    assert len(intro) == 120*6
    for i in range(120):
        psg = states[(i+1)*2-1][8192:]
        assert psg[:4]+psg[8:10] == intro[i*6:(i+1)*6]
    psg = states[241][8192:]
    assert psg[:4]+psg[8:10] == (out/'game-audio-normal-frames.bin').read_bytes()[:6]
    assert len({s[8192+14:8192+16] for s in states}) == 1
    assert max(s[8192+10] for s in states) > 2
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(scope='Contributor-native core at explicit elapsed ticks; no IRQ/VRAM/presentation/physical-cadence or PCM-listening validation.',
                  calls=1200, natural_flag_count=1, death_call=first_death+1,
                  restart_call=restart+1, death_hold_ticks=120, remaining_lives=2,
                  flags_preserved_on_restart=True, fuel_refilled=60,
                  synthetic_clear_setup_after_call=850, completion_call=complete+1,
                  completed_native_state_frozen=True, canaries_held=True,
                  intro_packets_matched=120, background_started_call=242,
                  psg_io_14_15_preserved=True, noise_effect_output=True,
                  rom_sha256=digest(out/'probe.rom'),
                  sources_sha256={name: digest(Path(__file__).with_name(name))
                                  for name in ('game_core_probe.py', 'game-core.inc',
                                               'game_core.py', 'game-audio.inc', 'game_audio.py')})
    (out/'execution-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT/'references/experiments/fixed-hud/core-execution-repro')
    parser.add_argument('--openmsx', default='openmsx')
    args = parser.parse_args()
    # Keep this checkout's lexical references path when it is a shared symlink.
    output = args.output.absolute()
    output.relative_to(ROOT/'references')
    # Shared reference subdirectories may point into the contributor checkout.
    canonical = output.resolve()
    owner = next(parent for parent in canonical.parents if (parent/'.git').exists())
    require_ignored(owner, [canonical/'probe.rom'])
    output.mkdir(parents=True, exist_ok=True)
    syms = build(output)
    execute(output, syms, args.openmsx)
    print(json.dumps(verify(output), indent=2))
