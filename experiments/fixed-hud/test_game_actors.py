"""Synthetic native-descriptor -> actor -> VRAM contracts and cycle ledger.

Uses synthetic descriptors, animation flags and car masks only. Optional old
source paths produce a differential cost ledger without rebuilding gameplay.

python experiments/fixed-hud/test_game_actors.py --bios references/msxbios
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys

from game_sprites import prepare_reference

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.msx.emulator import reference_machine, tcl


def signed8(value):
    return value - 256 if value & 128 else value


def reference_actors(case, flags):
    raw_count, death, cx, cy, old, descriptors = case
    count = min((raw_count + 1) & 255, 8)
    result = bytearray(old)
    for actor in range(8):
        target, source = actor * 6, actor * 32
        result[target + 5] = 255
        if actor >= count:
            continue
        x = descriptors[source + 8] * 24 + 28 + signed8(descriptors[source + 5]) - cx
        y = descriptors[source + 10] * 24 + 28 + signed8((-descriptors[source + 7]) & 255) - cy
        result[target:target + 4] = (x & 65535).to_bytes(2, 'little') + (y & 65535).to_bytes(2, 'little')
        animation = flags[descriptors[source + 15]]
        if animation >= 12:
            continue
        result[target + 4] = animation
        if actor or not death:
            result[target + 5] = int(actor != 0)
    return bytes(result)


def unpack_actors(records):
    return [(int.from_bytes(records[i:i+2], 'little', signed=True),
             int.from_bytes(records[i+2:i+4], 'little', signed=True),
             records[i+4], records[i+5]) for i in range(0, 48, 6)]


def cases_and_workloads():
    rng = random.Random(20261028)
    cases, workloads = [], {}
    def add(count=1, death=0, cx=0, cy=0, descriptors=None, old=None):
        cases.append((count, death, cx, cy,
                      bytes(rng.randrange(256) for _ in range(48)) if old is None else old,
                      bytes(rng.randrange(256) for _ in range(256)) if descriptors is None else descriptors))
    for count in range(256):
        add(count, count & 3, rng.randrange(65536), rng.randrange(65536))
    # Cover both signed offset extrema, NEG(-128), all camera scroll phases,
    # dead players, invalid flags, and modulo-65536 coordinate wrap.
    for cy in range(256):
        data = bytearray(256)
        for i in range(8):
            data[i*32+5] = (0, 1, 127, 128, 129, 254, 255, cy)[i]
            data[i*32+7] = (128, 127, 255, 0, 1, 129, 254, cy)[i]
            data[i*32+8] = (0, 255, 1, 128, 127, 64, 32, cy)[i]
            data[i*32+10] = (255, 0, 128, 1, 127, 64, 32, cy)[i]
            data[i*32+15] = (i*32+cy) & 255
        add(7, cy & 1, cy*257, cy, bytes(data))
    for _ in range(400):
        add(rng.choice((0, 1, 2, 7, 8, 254, 255)), rng.randrange(3),
            rng.randrange(65536), rng.randrange(65536))
    def interior(animation=0, enemy_visible=True):
        data = bytearray(256)
        for i in range(8):
            x = 40+i*20
            data[i*32+8], data[i*32+5] = divmod(x-28, 24)
            data[i*32+10] = 3
            data[i*32+15] = animation
        if not enemy_visible:
            data[32+8] = 30
        return bytes(data)
    for label, count, change, visible in (
            ('two-interior-warm', 1, False, True),
            ('two-interior-animation-change', 1, True, True),
            ('player-and-offscreen-enemy-warm', 1, False, False),
            ('eight-interior-warm', 7, False, True)):
        start = len(cases)
        for i in range(34):
            add(count, 0, 0, 0, interior(i % 12 if change else 0, visible), bytes(48))
        workloads[label] = (start+2, len(cases))
    return cases, workloads


def stats(values):
    ordered = sorted(values)
    return dict(calls=len(values), mean=statistics.mean(values),
                p99=ordered[int((len(values)-1)*.99)], maximum=max(values))


def probe(core, sprites, out, bios, cases, workloads, flags, templates):
    out.mkdir(parents=True, exist_ok=True)
    text = core.read_text()
    declarations = text[text.index('Game_State EQU'):text.index('Game_InitCore:')]
    axes = text[text.index('Player_AxisY:'):text.index('stage_div8:')]
    actors = text[text.index('Game_Actors:'):text.index('; Permanent Page0')]
    (out/'actors.inc').write_text(declarations+axes+actors+'\nGame_AnimationFlags:\n INCBIN "player-flags.bin"\n')
    (out/'game-sprites.inc').write_text(sprites.read_text())
    (out/'player-flags.bin').write_bytes(flags)
    (out/'game-sprite-templates.bin').write_bytes(templates)
    (out/'probe.asm').write_text(''' OUTPUT "probe.rom"
cx EQU $c000
cy EQU $c002
Death_State EQU $c600
GAME_NATIVE_BANK EQU 1
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 call GameSprites_Init
main:
 jp main
 INCLUDE "actors.inc"
 INCLUDE "game-sprites.inc"
 ASSERT $ < $8000
 defs $8000-$,$ff
''')
    assembled = subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', '--sym=probe.sym', 'probe.asm'],
                               cwd=out, capture_output=True, text=True)
    if assembled.returncode:
        raise RuntimeError(assembled.stdout+assembled.stderr)
    syms = {m[1]: int(m[2], 16) for m in re.finditer(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)', (out/'probe.sym').read_text())}
    packed = bytearray()
    expected = bytearray()
    for index, case in enumerate(cases):
        count, death, cx, cy, old, descriptors = case
        packed.extend(bytes((count, death))+cx.to_bytes(2, 'little')+cy.to_bytes(2, 'little')+old+descriptors)
        actors = reference_actors(case, flags)
        world = prepare_reference(templates, unpack_actors(actors), cy & 255, 1-(index & 1))
        expected.extend(actors+world['sat']+world['colors']+world['patterns']+bytes((sum(1 << i for i in world['culled']),)))
    (out/'cases.bin').write_bytes(packed)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(out/"probe.rom")} -romtype Normal', 'reset', f'set out {tcl(out)}',
             'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
             'set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w];set index 0;set started 0',
             'proc issue {} {',
             f' if {{$::index=={len(cases)}}} {{close $::result;close $::timing;exit 0;return}}',
             ' set at [expr {$::index*310}];binary scan [string range $::data $at [expr {$at+1}]] cu* values',
             ' debug write memory 0xe24e [lindex $values 0];debug write memory 0xc600 [lindex $values 1]',
             ' debug write_block memory 0xc000 [string range $::data [expr {$at+2}] [expr {$at+5}]]',
             ' debug write_block memory 0xc800 [string range $::data [expr {$at+6}] [expr {$at+53}]]',
             ' debug write_block memory 0xe068 [string range $::data [expr {$at+54}] [expr {$at+309}]]',
             f' debug write memory {syms["GS_Set"]} [expr {{$::index&1}}]',
             f' set p 0xd110;foreach v [list 243 205 {syms["Game_Actors"]&255} {syms["Game_Actors"]>>8} 0 205 {syms["GameSprites_Prepare"]&255} {syms["GameSprites_Prepare"]>>8} 0 205 {syms["GameSprites_Commit"]&255} {syms["GameSprites_Commit"]>>8} 195 64 209] {{debug write memory $p $v;incr p}}',
             ' reg SP 0xf380;reg PC 0xd110', '}',
             f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
             f'debug set_bp {syms["Game_Actors"]} {{$::started}} {{set ::actor_at [machine_info time]}}',
             'debug set_bp 0xd114 {$::started} {set ::actor_cycles [expr {round(([machine_info time]-$::actor_at)*3579545)}]}',
             f'debug set_bp {syms["GameSprites_Prepare"]} {{$::started}} {{set ::prepare_at [machine_info time]}}',
             'debug set_bp 0xd118 {$::started} {set ::prepare_cycles [expr {round(([machine_info time]-$::prepare_at)*3579545)}]}',
             f'debug set_bp {syms["GameSprites_Commit"]} {{$::started}} {{set ::commit_at [machine_info time]}}',
             'debug set_bp 0xd11c {$::started} {set ::commit_cycles [expr {round(([machine_info time]-$::commit_at)*3579545)}]}',
             'debug set_bp 0xd140 {$::started} {',
             ' puts $::timing "$::actor_cycles $::prepare_cycles $::commit_cycles"',
             ' set at [expr {$::index*310}]',
             ' if {[debug read_block memory 0xe068 256] ne [string range $::data [expr {$at+54}] [expr {$at+309}]]} {error "Native descriptors changed"}',
             ' if {[debug read_block memory 0xc000 4] ne [string range $::data [expr {$at+2}] [expr {$at+5}]]} {error "Camera changed"}',
             ' puts -nonewline $::result [debug read_block memory 0xc800 48]',
             ' puts -nonewline $::result [debug read_block memory 0xc980 72]',
             ' puts -nonewline $::result [debug read_block VRAM 0x18e0 288]',
             ' set target [expr {[debug read memory 0xcd40]*576+0x2800}]',
             ' puts -nonewline $::result [debug read_block VRAM $target 576]',
             f' puts -nonewline $::result [debug read_block memory {syms["GS_Culled"]} 1]',
             ' if {[debug read_block VRAM 0x1a38 72] ne [debug read_block memory 0xc980 72]} {error "SAT publication differs"}',
             ' incr ::index;issue', '}',
             'after time 60 {puts stderr "Actor probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, stdout=log, stderr=subprocess.STDOUT,
                       timeout=90, env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'actual.bin').read_bytes()
    if len(actual) != len(expected):
        raise AssertionError('Incomplete actor output')
    for index in range(len(cases)):
        a, e = actual[index*985:(index+1)*985], expected[index*985:(index+1)*985]
        relevant = list(range(48)) + [48+i*4 for i in range(18)] + [984]
        for group in range(18):
            if e[120+group*16] & 15:
                relevant.extend(range(48+group*4, 48+(group+1)*4))
                relevant.extend(range(120+group*16, 120+(group+1)*16))
                relevant.extend(range(408+group*32, 408+(group+1)*32))
        for offset in relevant:
            if a[offset] != e[offset]:
                raise AssertionError(f'case={index} offset={offset} actual={a[offset:offset+8].hex()} expected={e[offset:offset+8].hex()}')
    rows = [[int(v) for v in line.split()] for line in (out/'cycles.txt').read_text().splitlines()]
    ledger = dict(cpu_hz=3579545, machine='Panasonic_FS-A1WSX_NR128', video_hz_nominal=60, hardware_sprite_limits=True,
                  cases=len(cases), calls_per_case=1, synchronization_waits=0,
                  scope='Per-routine inclusive entry-to-return, emulated elapsed CPU cycles including wait states; synthetic descriptor/animation/template bytes; excludes renderer, HUD, simulation, IRQ and synchronization',
                  rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(),
                  core_source_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                  sprites_source_sha256=hashlib.sha256(sprites.read_bytes()).hexdigest(), workloads={})
    for label, (start, end) in workloads.items():
        ledger['workloads'][label] = {name: stats([row[column] for row in rows[start:end]])
            for column, name in enumerate(('Game_Actors', 'GameSprites_Prepare', 'GameSprites_Commit'))}
    (out/'cycle-ledger.json').write_text(json.dumps(ledger, indent=2)+'\n')
    return ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bios', required=True)
    parser.add_argument('--baseline-core', type=Path)
    parser.add_argument('--baseline-sprites', type=Path)
    args = parser.parse_args()
    rng = random.Random(77)
    flags = bytes(range(12))+bytes(rng.choice((*range(12), 12, 255)) for _ in range(244))
    templates = bytes(rng.randrange(256) for _ in range(768))
    cases, workloads = cases_and_workloads()
    out = ROOT/'outputs/fixed-hud/actor-bridge-synthetic'
    result = {'current': probe(HERE/'game-core.inc', HERE/'game-sprites.inc', out/'current', args.bios, cases, workloads, flags, templates)}
    if args.baseline_core and args.baseline_sprites:
        result['baseline'] = probe(args.baseline_core, args.baseline_sprites, out/'baseline', args.bios, cases, workloads, flags, templates)
    report_name='comparison.json' if 'baseline' in result else 'verification.json'
    (out/report_name).write_text(json.dumps(result, indent=2)+'\n')
    print(f'Actor and visible VRAM byte contracts passed {len(cases)} synthetic cases per version')
    print(json.dumps({version: data['workloads'] for version, data in result.items()}, indent=2))


if __name__ == '__main__':
    main()
