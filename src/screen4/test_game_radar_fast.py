"""Exact synthetic baseline/candidate actor-radar RAM and elapsed-cycle probe.

python src/screen4/test_game_radar_fast.py --bios references/msxbios
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

from radar_variants import name_program
from test_game_radar import phases
from game_radar_source_cache import uniform_source_colors

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ROW_Y = bytes(70+y*106//56 for y in range(56))
SEED = bytes((i*17+53) & 255 for i in range(576))
RESULT_BYTES = 1+1024+576
CASE_BYTES = 260


def fixtures():
    result = []
    rng = random.Random(0x20261028)
    for phase, payload, groups in phases():
        n = payload[:224]
        size = (len(payload)-224)//16
        p = payload[224:224+size*8].ljust(512, b'\xa5')
        c = payload[224+size*8:].ljust(512, b'\x5a')
        names = bytearray([96])*1024
        for i, value in enumerate(n):
            row, col = divmod(i, 7)
            if row*32+26+col < 1024:
                names[row*32+26+col] = value+96
        result.append(dict(phase=phase, payload=payload, groups=groups,
                           names=bytes(names), patterns=p, colors=c,
                           program=name_program(groups)))
    cases = []
    for phase in range(64):
        for count in (0, 1, 3, 7, 8, 255):
            for kind in ('spread', 'overlap', 'same-tile', 'parked', 'bounds'):
                for mask in (0, 0x155, 0x2aa, 1023):
                    data = bytearray(256)
                    for i in range(8):
                        if kind == 'spread':
                            x, y = (i*5+phase) % 32, (i*9+phase) % 56
                        elif kind == 'overlap':
                            x, y = phase % 32, phase % 56
                        elif kind == 'same-tile':
                            x, y = i % 4+8, i//4+10
                        elif kind == 'parked':
                            x, y = (255, 31, 32, 8, 0, 64, 15, 7)[i], (60, 55, 0, 56, 255, 5, 30, 8)[i]
                        else:
                            x, y = (0, 31, 32, 255, 1, 30, 7, 8)[i], (0, 55, 56, 255, 1, 54, 7, 8)[i]
                        data[i*32+8], data[i*32+10] = x, y
                    cases.append(dict(phase=phase, count=count, mask=mask,
                                      descriptors=bytes(data), label=f'{count}-enemies-{kind}'))
        # Every valid native X and Y occurs at every phase. The paired axes
        # deliberately include character crossings and shared actor cells.
        for y in range(56):
            data = bytearray(256)
            for i in range(8):
                data[i*32+8] = (y+i*7) % 32
                data[i*32+10] = (y+i*13) % 56
            cases.append(dict(phase=phase, count=7, mask=rng.randrange(1024),
                              descriptors=bytes(data), label='coordinate-matrix'))
    return result, cases


def reference(case, fixture):
    names = bytearray(fixture['names'])
    patterns, colors, addresses = bytearray(SEED[:256]), bytearray(SEED[256:512]), bytearray(SEED[512:])
    for group in fixture['groups']:
        selected = sum(((case['mask'] >> slot) & 1) << bit for bit, slot in enumerate(group['slots']))
        row, col = divmod(group['entry'], 7)
        names[row*32+26+col] = group['ids'][selected]
    count = 0
    for actor in range(min(case['count'], 7)+1):
        x, y = case['descriptors'][actor*32+8], case['descriptors'][actor*32+10]
        if x >= 32 or y >= 56:
            continue
        x, y = x+8+case['phase'] % 8, ROW_Y[y]+case['phase']//8
        at = (y//8)*32+26+x//8
        tile = names[at]
        if 64 <= tile < 96:
            index = tile-64
        else:
            index = count
            count += 1
            addresses[index*2:index*2+2] = (0xd400+at).to_bytes(2, 'little')
            names[at] = 64+index
            source = (tile-96)*8
            patterns[index*8:index*8+8] = fixture['patterns'][source:source+8]
            colors[index*8:index*8+8] = fixture['colors'][source:source+8]
        at = index*8+y % 8
        if colors[at] != 0xc1:
            patterns[at] = 0
        colors[at] = 0xc1
        patterns[at] |= 128 >> (x % 8)
    return bytes((count,))+names+patterns+colors+addresses


def probe_source(uniform=False):
    main = (HERE/'game-main.inc').read_text()
    declarations = main[main.index('Game_WorldGeneration EQU'):main.index('Game_Prepare:')]
    baseline = main[main.index('Game_Radar:'):main.index('Game_RadarUpload:')]
    for old in ('Game_RadarCellY', 'Game_RadarErase', 'Game_RadarDot', 'Game_RadarPoint', 'Game_Radar'):
        baseline = re.sub(r'\b'+old+r'\b', old.replace('Game_', 'Baseline_'), baseline)
    return (' DEFINE GAME_RADAR_UNIFORM_SOURCE\n' if uniform else '')+''' OUTPUT "probe.rom"
fx EQU $c004
fy EQU $c005
dotx EQU $c012
doty EQU $c013
names EQU $d400
GAME_RADAR_COLOR EQU $c1
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 in a,($a8)
 rlca
 rlca
 and 3
 ld c,a
 ld b,0
 ld hl,$fcc1
 add hl,bc
 bit 7,(hl)
 jr z,.primary
 ld a,($ffff)
 cpl
 ld b,a
 rlca
 rlca
 and 3
 ld d,a
 ld a,b
 and $fc
 or d
 ld ($ffff),a
.primary:
 in a,($a8)
 and $fc
 or c
 out ($a8),a
 ld a,4
 out ($fc),a
main:
 jp main
'''+declarations+baseline+f'''
 INCLUDE "game-radar-fast.inc"
Game_RadarCellRows:
 INCBIN "rows.bin"
 ASSERT $ < $8000
 defs $8000-$,$ff
'''


def stats(values):
    ordered = sorted(values)
    return dict(calls=len(values), mean=statistics.mean(values),
                p99=ordered[(len(values)*99+99)//100-1], maximum=max(values))


def verify(bios, out=None, uniform=False):
    sys.path.insert(0, str(ROOT))
    from scripts.msx.emulator import reference_machine, tcl
    out = Path(out or ROOT/'outputs/fixed-hud/radar-fast-synthetic').resolve()
    out.mkdir(parents=True, exist_ok=True)
    fixtures_data, cases = fixtures()
    candidate_source = (HERE/'game-radar-fast.inc').read_bytes()
    (out/'game-radar-fast.inc').write_bytes(candidate_source)
    (out/'rows.bin').write_bytes(ROW_Y)
    (out/'seed.bin').write_bytes(SEED)
    fixture_bytes = bytearray()
    for fixture in fixtures_data:
        data = uniform_source_colors(fixture['patterns'], fixture['colors'], (len(fixture['payload'])-224)//16)
        fixture_bytes.extend(fixture['names']+fixture['patterns']+fixture['colors']+fixture['program'].ljust(512, b'\0')+data)
    assert len(fixture_bytes) == 64*2624
    (out/'fixtures.bin').write_bytes(fixture_bytes)
    packed, expected = bytearray(), bytearray()
    for case in cases:
        packed.extend(bytes((case['phase'], case['count']))+case['mask'].to_bytes(2, 'little')+case['descriptors'])
        expected.extend(reference(case, fixtures_data[case['phase']]))
    assert len(packed) == len(cases)*CASE_BYTES
    (out/'cases.bin').write_bytes(packed)
    (out/'probe.asm').write_text(probe_source(uniform))
    assembled = subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', '--sym=probe.sym', 'probe.asm'], cwd=out, capture_output=True, text=True)
    if assembled.returncode:
        raise AssertionError(assembled.stdout+assembled.stderr)
    syms = {n: int(v, 16) for n, v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)', (out/'probe.sym').read_text())}
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(out/"probe.rom")} -romtype Normal', 'reset', f'set out {tcl(out)}',
             'foreach n {cases fixtures seed} {set f [open [file join $out $n.bin] rb];set ::$n [read $f];close $f}',
             'set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]',
             'set index 0;set started 0;set stage 0;set last_phase -1',
             'proc issue {} {',
             f' if {{$::index=={len(cases)}}} {{close $::result;close $::timing;exit 0;return}}',
             f' set at [expr {{$::index*{CASE_BYTES}}}];binary scan [string range $::cases $at [expr {{$at+3}}]] cu* values',
             ' set phase [lindex $values 0];set count [lindex $values 1];set mask [expr {[lindex $values 2]+256*[lindex $values 3]}]',
             ' set f [expr {$phase*2624}]',
             ' debug write_block memory 0xd400 [string range $::fixtures $f [expr {$f+1023}]]',
             ' if {$phase!=$::last_phase} {',
             '  debug write_block memory 0x8100 [string range $::fixtures [expr {$f+1024}] [expr {$f+1535}]]',
             '  debug write_block memory 0x8500 [string range $::fixtures [expr {$f+1536}] [expr {$f+2047}]]',
             '  debug write_block memory 0xa700 [string range $::fixtures [expr {$f+2048}] [expr {$f+2559}]]',
             '  debug write_block memory 0xa940 [string range $::fixtures [expr {$f+2560}] [expr {$f+2623}]]',
             '  set ::last_phase $phase', ' }',
             ' debug write_block memory 0x2400 [string range $::seed 0 511]',
             ' debug write_block memory 0x2300 [string range $::seed 512 575]',
             ' debug write_block memory 0xe068 [string range $::cases [expr {$at+4}] [expr {$at+259}]]',
             ' debug write memory 0xe24e $count;debug write memory 0xc004 [expr {$phase&7}];debug write memory 0xc005 [expr {$phase>>3}]',
             ' for {set i 0} {$i<10} {incr i} {debug write memory [expr {0xc501+$i}] [expr {($mask>>$i)&1}]}',
             f' set routine [expr {{$::stage?{syms["GameRadarFast_Draw"]}:{syms["Baseline_Radar"]}}}]',
             ' set p 0xd110;foreach v [list 205 [expr {$routine&255}] [expr {$routine>>8}] 195 64 209] {debug write memory $p $v;incr p}',
             ' reg SP 0xf380;reg PC 0xd110', '}',
             f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
             f'debug set_bp {syms["Baseline_Radar"]} {{$::started}} {{set ::at_time [machine_info time]}}',
             f'debug set_bp {syms["GameRadarFast_Draw"]} {{$::started}} {{set ::at_time [machine_info time]}}',
             'debug set_bp 0xd113 {$::started} {set ::cycles [expr {round(([machine_info time]-$::at_time)*3579545)}]}',
             'debug set_bp 0xd140 {$::started} {',
             ' set cycles $::cycles',
             ' set actual [debug read_block memory 0xc087 1];append actual [debug read_block memory 0xd400 1024] [debug read_block memory 0x2400 512] [debug read_block memory 0x2300 64]',
             ' if {!$::stage} {set ::old $actual;set ::old_cycles $cycles;set ::stage 1;issue} else {',
             '  if {$actual ne $::old} {set f [open [file join $::out mismatch-old.bin] wb];puts -nonewline $f $::old;close $f;set f [open [file join $::out mismatch-new.bin] wb];puts -nonewline $f $actual;close $f;puts stderr "Radar RAM mismatch case $::index";exit 3}',
             '  puts -nonewline $::result $actual;puts $::timing "$::old_cycles $cycles"',
             '  incr ::index;set ::stage 0;issue', ' }', '}',
             'after time 600 {puts stderr "Radar fast probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, stdout=log, stderr=subprocess.STDOUT,
                       timeout=660, env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'actual.bin').read_bytes()
    if actual != expected:
        for at, (a, e) in enumerate(zip(actual, expected)):
            if a != e:
                raise AssertionError(f'Reference mismatch case={at//RESULT_BYTES}, offset={at%RESULT_BYTES}: {a:02x}!={e:02x}')
        raise AssertionError('Incomplete radar output')
    rows = [[int(v) for v in line.split()] for line in (out/'cycles.txt').read_text().splitlines()]
    labels = sorted(set(case['label'] for case in cases))
    report = dict(complete=True, cases=len(cases), phases=64, cpu_hz=3579545,
                  machine='Panasonic_FS-A1WSX_NR128', video_hz_nominal=60,
                  hardware_sprite_limits=True, calls_per_case=1, synchronization_waits=0,
                  scope='Inclusive radar entry-to-return elapsed emulated CPU cycles including wait states; synthetic HUD/flag/actor bytes; all 1601 output RAM bytes compared to both original Z80 path and independent reference; no renderer, upload, IRQ, gameplay or scanout claim',
                  rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(),
                  candidate_sha256=hashlib.sha256(candidate_source).hexdigest(),
                  uniform_source_optimization=uniform,
                  candidate_bytes=syms['GameRadarFast_Masks']+8-syms['GameRadarFast_Draw'], workloads={})
    for label in labels:
        selected = [row for row, case in zip(rows, cases) if case['label'] == label]
        report['workloads'][label] = {name: stats([row[i] for row in selected]) for i, name in enumerate(('baseline', 'candidate'))}
    (out/'cycle-ledger.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Exact radar RAM contracts passed {len(cases)} synthetic cases, 64 phases')
    print(json.dumps({key: value for key, value in report['workloads'].items() if key.startswith('3-enemies')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bios', required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--uniform-source', action='store_true')
    args = parser.parse_args()
    verify(args.bios, args.out, args.uniform_source)
