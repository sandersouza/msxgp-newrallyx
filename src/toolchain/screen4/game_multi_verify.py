"""Observe actual multi-enemy gameplay without editing native game state.

Supply an already built three/seven-enemy laboratory ROM and its symbols.
The scripted controls exercise the normal input path. RAM traces validate
motion, simultaneous visibility, smoke reactions, contacts and restarts when
those events occur. This instrumented run is not a performance/scanout proof.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.toolchain.msx.emulator import reference_machine, tcl
from src.toolchain.msx.hud_verify import symbols

STRIDE = 8192


def signed(value):
    return value-256 if value & 128 else value


def position(descriptor):
    return (36+24*descriptor[8]+signed(descriptor[5]),
            36+24*descriptor[10]+signed((-descriptor[7]) & 255))


def analyze(out, enemies):
    raw = (out/'states.bin').read_bytes()
    if not raw or len(raw) % STRIDE:
        raise ValueError('Incomplete population RAM samples')
    samples = [raw[at:at+STRIDE] for at in range(0, len(raw), STRIDE)]
    movements = [set() for _ in range(enemies)]
    visible_peak = 0
    whole_peak = 0
    smoke_spin_actors = set()
    contacts = []
    restarts = []
    previous_death = 0
    previous_lives = None
    max_smoke = 0
    max_flags = 0
    counts = set()
    sat_path = out/'sprites.bin'
    sat = sat_path.read_bytes() if sat_path.exists() else b''
    if sat and len(sat) != len(samples)*128:
        raise ValueError('Incomplete hardware sprite samples')
    scanline_peak = overflow_frames = overflow_rows = 0
    sentinel_cull_frames = sentinel_cull_mask = 0
    uncontested_visible_peak = uncontested_whole_peak = 0
    for frame, sample in enumerate(samples, 1):
        ram, native = sample[:4096], sample[4096:]
        counts.add(native[0x24e])
        death = ram[0x490]
        lives = native[0xf]
        if previous_lives is not None and previous_death == 1 and death == 0:
            restarts.append(dict(frame=frame, lives=lives, flags=ram[0x50b],
                                 enemies=native[0x24e]))
        previous_death, previous_lives = death, lives
        visible = whole = 0
        for actor in range(enemies):
            descriptor = native[0x88+actor*32:0xa0+actor*32]
            # Exclude parked/out-of-world descriptors from real actor evidence.
            if descriptor[8] < 32 and descriptor[10] < 56:
                movements[actor].add(position(descriptor))
            if descriptor[21] == 1 and descriptor[19] > 0:
                smoke_spin_actors.add(actor+1)
            x, y, animation, kind = struct.unpack_from('<hhBB', ram, 0x806+actor*6)
            if kind == 1 and x < 200 and x+16 > 8 and y < 212 and y+16 > 0:
                visible += 1
                whole += int(8 <= x <= 184 and 0 <= y <= 196)
        visible_peak = max(visible_peak, visible)
        whole_peak = max(whole_peak, whole)
        if ram[0x5d0] and death == 1:
            hit = int.from_bytes(ram[0x63c:0x63e], 'little')
            if (hit-0xe096) % 32 == 0 and 0 <= (hit-0xe096)//32 < enemies:
                event = dict(frame=frame, actor=1+(hit-0xe096)//32, lives=lives)
                if not contacts or contacts[-1]['actor'] != event['actor'] or contacts[-1]['lives'] != lives:
                    contacts.append(event)
        max_smoke = max(max_smoke, int.from_bytes(ram[0x711:0x713], 'little'))
        max_flags = max(max_flags, ram[0x50b])
        sentinel_cull_mask |= ram[0xd52]
        sentinel_cull_frames += bool(ram[0xd52])
        if sat:
            attributes = sat[(frame-1)*128:frame*128]
            assert 216 not in attributes[::4], 'Early mode-two sprite terminator'
            cy = int.from_bytes(ram[2:4], 'little')
            pressure = [sum(((y+cy-sy-1) & 255) < 16 for sy in attributes[::4])
                        for y in range(212)]
            scanline_peak = max(scanline_peak, max(pressure))
            rows = sum(candidates > 8 for candidates in pressure)
            overflow_frames += bool(rows)
            overflow_rows += rows
            if not rows and not ram[0xd52]:
                uncontested_visible_peak = max(uncontested_visible_peak, visible)
                uncontested_whole_peak = max(uncontested_whole_peak, whole)
    assert counts == {enemies}, f'Native population changed: {counts}'
    assert visible_peak >= 2, 'No simultaneous visible multi-enemy evidence'
    assert all(len(positions) > 1 for positions in movements), 'An active native enemy never moved'
    report = dict(scope='Instrumented real gameplay; normal keyboard controls only; no native state writes; no performance, continuous scanout or physical hardware claim',
                  samples=len(samples), enemies=enemies,
                  native_counts=sorted(counts),
                  maximum_simultaneously_visible_enemies=visible_peak,
                  maximum_wholly_visible_enemies=whole_peak,
                  distinct_world_positions_per_enemy=[len(positions) for positions in movements],
                  moved_enemies=sum(len(positions) > 1 for positions in movements),
                  smoke_placements_peak=max_smoke,
                  native_smoke_spin_actors=sorted(smoke_spin_actors),
                  enemy_contact_deaths=contacts,
                  restarts=restarts, maximum_flags_captured=max_flags,
                  final_lives=samples[-1][4096+0xf],
                  final_game_state=samples[-1][0x40],
                  hardware_sprite_limit_enabled=True,
                  hardware_sprite_samples=len(samples) if sat else 0,
                  maximum_scanline_sprite_candidates=scanline_peak if sat else None,
                  maximum_visible_enemies_without_scanline_or_sentinel_culling=uncontested_visible_peak if sat else None,
                  maximum_whole_enemies_without_scanline_or_sentinel_culling=uncontested_whole_peak if sat else None,
                  frames_with_hardware_scanline_overflow=overflow_frames if sat else None,
                  scanlines_with_hardware_overflow=overflow_rows if sat else None,
                  sentinel_whole_car_cull_frames=sentinel_cull_frames,
                  sentinel_whole_car_cull_actor_mask=sentinel_cull_mask,
                  limitations='Visibility counts use prepared complete native car records; actual scanline culling/VRAM fidelity is validated separately. Unobserved smoke/contact/restart events are not claimed as passing.')
    config = json.loads((out/'run.json').read_text())
    report.update(config)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def run(rom, sym, out, enemies, frames=480, scenario='natural', emulator='openmsx'):
    rom, sym, out = Path(rom).absolute(), Path(sym).absolute(), Path(out).absolute()
    out.relative_to(ROOT/'references')
    out.mkdir(parents=True, exist_ok=False)
    syms = symbols(sym)
    config = dict(rom=str(rom), rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
                  symbols_sha256=hashlib.sha256(sym.read_bytes()).hexdigest(),
                  scenario=scenario, requested_samples=frames,
                  machine='Panasonic_FS-A1WSX', nominal_cpu_hz=3579545)
    (out/'run.json').write_text(json.dumps(config, indent=2)+'\n')
    script = f'''set save_settings_on_exit false
set renderer none
set sound_driver null
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT, 'Panasonic_FS-A1WSX')}
set firmwareswitch off
set throttle off
set z80_freq 3579545
set z80_freq_locked true
set limitsprites true
if {{!$limitsprites}} {{error "Hardware sprite limit not enabled"}}
activate_input_layer -blocking native_population_verification
cart {tcl(rom)} -romtype ASCII16
reset
set n 0
set output [open {tcl(out/'states.bin')} wb]
set sprites [open {tcl(out/'sprites.bin')} wb]
set events [open {tcl(out/'events.tsv')} w]
puts $events "frame\tevent\tlives\tflags\tenemies"
proc event {{name}} {{
 puts $::events "$::n\t$name\t[debug read memory 0xe00f]\t[debug read memory 0xc50b]\t[debug read memory 0xe24e]"
}}
debug set_bp {syms['Game_Restart']} {{}} {{event restart}}
debug set_bp {syms['GameMulti_Init']} {{}} {{event population_init}}
debug set_bp {syms['loop']} {{}} {{
 incr ::n
 puts -nonewline $::output [debug read_block memory 0xc000 4096]
 puts -nonewline $::output [debug read_block memory 0xe000 4096]
 puts -nonewline $::sprites [debug read_block VRAM 0x1a00 128]
 keymatrixup 8 255
 set phase [expr {{(($::n-1)/80)%4}}]
 keymatrixdown 8 [lindex {{32 128 64 16}} $phase]
 if {{{tcl(scenario)} eq "smoke" && ($::n%160)>=10 && ($::n%160)<100}} {{keymatrixdown 8 1}}
 if {{$::n>={frames}}} {{close $::output;close $::sprites;close $::events;exit 0}}
}}
after time 120 {{puts stderr "Population gameplay timeout";exit 2}}
'''
    (out/'verify.tcl').write_text(script)
    with (out/'openmsx.log').open('w') as log:
        subprocess.run([emulator, '-script', str(out/'verify.tcl')], stdout=log,
            stderr=subprocess.STDOUT, check=True, timeout=180,
            env=dict(os.environ, OPENMSX_HOME=str(out/'home'),
                     OPENMSX_USER_DATA=str(out/'userdata')))
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == config['rom_sha256'], 'ROM changed during verification'
    return analyze(out, enemies)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--symbols', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--enemies', type=int, choices=(3, 7), required=True)
    parser.add_argument('--frames', type=int, default=480)
    parser.add_argument('--scenario', choices=('natural', 'smoke'), default='natural')
    parser.add_argument('--openmsx', default='openmsx')
    args = parser.parse_args()
    print(json.dumps(run(args.rom, args.symbols, args.output, args.enemies,
                         args.frames, args.scenario, args.openmsx), indent=2))
