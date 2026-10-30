"""Exact synthetic horizontal-mask optimization probe; no canonical build.

python src/toolchain/screen4/test_game_sprite_mask_fast.py --bios references/msxbios
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
import random
import re
import statistics
import subprocess
import sys

from game_sprites import prepare_reference
from test_game_sprites import actors_at, synthetic_templates

ROOT = Path(__file__).resolve().parents[3]
HERE = RUNTIME
RAM_PARTS = ((0xc980, 360), (0xcb00, 576), (0xc840, 130), (0xcd40, 19), (0xcd60, 11))
VRAM_PARTS = ((0x2800, 1152), (0x1a38, 72), (0x18e0, 288))
RESULT_BYTES = sum(n for _, n in RAM_PARTS+VRAM_PARTS)


def cases_and_workloads():
    # Keep the established 1163-case matrix as an exact prefix.
    cases, workloads = [], {}
    for cy in range(256):
        cases.append((cy, cy & 1, actors_at(100, 100, cy % 12, cy & 1)))
    for x in (-300, -16, -8, -7, -1, 0, 7, 8, 184, 185, 199, 200, 255, 300):
        for y in (-300, -16, -15, -1, 0, 196, 197, 211, 212, 255, 300):
            cases.append((117, len(cases) & 1, actors_at(x, y, len(cases) % 12, len(cases) & 1)))
    for cy in range(256):
        cases.append((cy, cy & 1, [(8+i*21, 100, i % 12, i & 1) for i in range(8)]))
    rng = random.Random(411)
    for _ in range(300):
        cases.append((rng.randrange(256), rng.randrange(2),
                      [(rng.randrange(-20, 220), rng.randrange(-20, 230), rng.randrange(14), rng.choice((0, 1, 255))) for _ in range(8)]))
    def add(label, sequence):
        start = len(cases)
        cases.extend(sequence)
        workloads[label] = (start+2, len(cases))
    interior = [(20+i*20, 100, i % 12, i & 1) for i in range(8)]
    add('eight-interior-unchanged-warm', [(0, i & 1, interior) for i in range(32)])
    add('eight-interior-animation-change', [(0, i & 1, [(x, y, (a+i) % 12, k) for x, y, a, k in interior]) for i in range(32)])
    add('eight-interior-scroll-only', [(i, i & 1, interior) for i in range(101)])
    add('eight-right-clipped-animation-change', [(0, i & 1, [(199, 100, (a+i) % 12, k) for x, y, a, k in interior]) for i in range(32)])
    assert len(cases) == 1163
    workloads['original-1163-cases'] = (0, 1163)
    for label, x in (('left', -7), ('right', 199)):
        add(f'one-{label}-clipped-animation-change', [(0, i & 1, actors_at(x, 100, i % 12, i & 1)) for i in range(34)])
        add(f'four-cars-one-{label}-clipped-animation-change', [(0, i & 1,
             [(x, 100, i % 12, 0)]+[(40+j*35, 100, (j+i) % 12, 1) for j in range(3)]+[(0, 0, 0, 255)]*4) for i in range(34)])
    # All 30 horizontal clipping positions and the two adjacent interior bounds,
    # all 12 animations, all 256 scroll values. Animation changes force the copy
    # path every case; cy=117 also exercises the unchanged sentinel fallback.
    start = len(cases)
    positions = list(range(-7, 8))+[8, 184]+list(range(185, 200))
    assert len(positions) == 32
    for batch in range(4):
        for cy in range(256):
            for animation in range(12):
                actors = [(x, 100, (animation+i) % 12, i & 1)
                          for i, x in enumerate(positions[batch*8:(batch+1)*8])]
                cases.append((cy, len(cases) & 1, actors))
    workloads['all-horizontal-clips-animations-scrolls'] = (start, len(cases))
    return cases, workloads


def stats(values):
    ordered = sorted(values)
    return dict(calls=len(values), mean=statistics.mean(values),
                p99=ordered[(len(values)*99+99)//100-1], maximum=max(values))


def candidate_source(original):
    needle = '    cp $ff\n    jr nz,.slow\n    push ix\n'
    assert original.count(needle) == 1
    return original.replace(needle, '    cp $ff\n    jp nz,GS_MaskedCopyFast\n    push ix\n')+f'\n INCLUDE "{HERE/"game-sprite-mask-fast.inc"}"\n'


def probe(version, source, out, bios, packed, templates, cases, workloads):
    sys.path.insert(0, str(ROOT))
    from src.toolchain.msx.emulator import reference_machine, tcl
    out.mkdir(parents=True, exist_ok=True)
    (out/'game-sprites.inc').write_text(source)
    (out/'game-sprite-templates.bin').write_bytes(templates)
    (out/'cases.bin').write_bytes(packed)
    seed = bytes((i*29+71) & 255 for i in range(360+576+1152+72+288))
    (out/'seed.bin').write_bytes(seed)
    (out/'probe.asm').write_text(''' OUTPUT "probe.rom"
cy EQU $c002
 MACRO reg number,value
 ld a,value
 out ($99),a
 ld a,$80+number
 out ($99),a
 ENDM
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 reg 0,4
 reg 1,$42
 reg 8,$28
 reg 9,$80
 call GameSprites_Init
main:
 jp main
 INCLUDE "game-sprites.inc"
Probe_End:
 ASSERT $ < $8000
 defs $8000-$,$ff
''')
    assembled = subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', '--sym=probe.sym', 'probe.asm'], cwd=out, capture_output=True, text=True)
    if assembled.returncode:
        raise AssertionError(assembled.stdout+assembled.stderr)
    syms = {n: int(v, 16) for n, v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)', (out/'probe.sym').read_text())}
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(out/"probe.rom")} -romtype Normal', 'reset', f'set out {tcl(out)}',
             'foreach n {cases seed} {set f [open [file join $out $n.bin] rb];set ::$n [read $f];close $f}',
             'set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]',
             'set index 0;set started 0;set fast 0',
             'set VDP.too_fast_vram_access_callback {if {$::started} {incr ::fast}}',
             'proc issue {} {',
             f' if {{$::index=={len(cases)}}} {{close $::result;close $::timing;set f [open [file join $::out strict.txt] w];puts $f $::fast;close $f;exit 0;return}}',
             ' set at [expr {$::index*50}];binary scan [string range $::cases $at [expr {$at+1}]] cu* c',
             ' debug write memory 0xc002 [lindex $c 0]',
             f' debug write memory {syms["GS_Set"]} [lindex $c 1]',
             ' debug write_block memory 0xc800 [string range $::cases [expr {$at+2}] [expr {$at+49}]]',
             f' set p 0xd110;foreach v [list 243 205 {syms["GameSprites_Prepare"]&255} {syms["GameSprites_Prepare"]>>8} 205 {syms["GameSprites_Commit"]&255} {syms["GameSprites_Commit"]>>8} 195 64 209] {{debug write memory $p $v;incr p}}',
             ' reg SP 0xf380;reg PC 0xd110', '}',
             f'debug set_bp {syms["main"]} {{!$::started}} {{',
             ' debug write_block memory 0xc980 [string range $::seed 0 359]',
             ' debug write_block memory 0xcb00 [string range $::seed 360 935]',
             ' debug write_block VRAM 0x2800 [string range $::seed 936 2087]',
             ' debug write_block VRAM 0x1a38 [string range $::seed 2088 2159]',
             ' debug write_block VRAM 0x18e0 [string range $::seed 2160 2447]',
             ' set ::started 1;issue', '}',
             f'debug set_bp {syms["GameSprites_Prepare"]} {{$::started}} {{set ::begin [machine_info time]}}',
             'debug set_bp 0xd114 {$::started} {set ::prepare_cycles [expr {round(([machine_info time]-$::begin)*3579545)}]}',
             f'debug set_bp {syms["GameSprites_Commit"]} {{$::started}} {{set ::begin [machine_info time]}}',
             'debug set_bp 0xd117 {$::started} {set ::commit_cycles [expr {round(([machine_info time]-$::begin)*3579545)}]}',
             'debug set_bp 0xd140 {$::started} {',
             ' puts $::timing "$::prepare_cycles $::commit_cycles"']
    lines.extend(f' puts -nonewline $::result [debug read_block memory {at} {length}]' for at, length in RAM_PARTS)
    lines.extend(f' puts -nonewline $::result [debug read_block VRAM {at} {length}]' for at, length in VRAM_PARTS)
    lines.extend([' incr ::index;issue', '}', 'after time 600 {puts stderr "Sprite-mask probe timeout";exit 2}'])
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, stdout=log, stderr=subprocess.STDOUT,
                       timeout=660, env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'actual.bin').read_bytes()
    if len(actual) != len(cases)*RESULT_BYTES:
        raise AssertionError(f'Incomplete {version} output')
    # The first 937-byte subset is checked against the established independent
    # sprite model; untouched invisible bytes retain their exact prior history.
    for index, (cy, target, actors) in enumerate(cases):
        model = prepare_reference(templates, actors, cy, target)
        record = actual[index*RESULT_BYTES:(index+1)*RESULT_BYTES]
        sat, colors = record[:72], record[72:360]
        vram_at = sum(n for _, n in RAM_PARTS)+target*576
        patterns = record[vram_at:vram_at+576]
        if sat[::4] != model['sat'][::4] or record[360+576+130+18] != sum(1 << i for i in model['culled']):
            raise AssertionError(f'{version} hidden/sentinel contract case {index}')
        for group in range(18):
            if model['colors'][group*16] & 15:
                for actual_bytes, expected_bytes in ((sat[group*4:(group+1)*4], model['sat'][group*4:(group+1)*4]),
                                                    (colors[group*16:(group+1)*16], model['colors'][group*16:(group+1)*16]),
                                                    (patterns[group*32:(group+1)*32], model['patterns'][group*32:(group+1)*32])):
                    if actual_bytes != expected_bytes:
                        raise AssertionError(f'{version} reference mismatch case {index} group {group}')
    rows = [[int(v) for v in line.split()] for line in (out/'cycles.txt').read_text().splitlines()]
    report = dict(rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(), source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                  resident_bytes=syms['Probe_End']-0x4000, strict_vram_callbacks=int((out/'strict.txt').read_text()), workloads={})
    for label, (start, end) in workloads.items():
        report['workloads'][label] = {name: stats([row[i] for row in rows[start:end]]) for i, name in enumerate(('prepare', 'commit'))}
    return report


def verify(bios):
    cases, workloads = cases_and_workloads()
    templates = synthetic_templates()
    packed = bytearray()
    for cy, target, actors in cases:
        packed.extend((cy, 1-target))
        for x, y, animation, kind in actors:
            packed.extend(x.to_bytes(2, 'little', signed=True)+y.to_bytes(2, 'little', signed=True)+bytes((animation, kind)))
    out = ROOT/'outputs/fixed-hud/sprite-mask-fast-synthetic'
    original = (HERE/'game-sprites.inc').read_text()
    guarded=('    IFDEF GAMEPLAY_CONFIGURED\n    IF GAME_RENDER_OPT\n'
             '    jp nz,GS_MaskedCopyFast\n    ELSE\n    jr nz,.slow\n'
             '    ENDIF\n    ELSE\n    jr nz,.slow\n    ENDIF\n')
    original=original.replace(guarded,'    jr nz,.slow\n')
    original = original.replace('    cp $ff\n    jp nz,GS_MaskedCopyFast\n    push ix\n', '    cp $ff\n    jr nz,.slow\n    push ix\n')
    original = re.sub(r'(?m)^\s*INCLUDE [\"\'](?:[^\"\']*/)?game-sprite-mask-fast\.inc[\"\']\s*$', '', original)
    results = {name: probe(name, source, out/name, bios, packed, templates, cases, workloads)
               for name, source in (('baseline', original), ('candidate', candidate_source(original)))}
    a, b = (out/'baseline/actual.bin').read_bytes(), (out/'candidate/actual.bin').read_bytes()
    if a != b:
        at = next(i for i, (old, new) in enumerate(zip(a, b)) if old != new)
        raise AssertionError(f'Exact sprite RAM/VRAM mismatch case {at//RESULT_BYTES} offset {at%RESULT_BYTES}: {a[at]:02x}!={b[at]:02x}')
    report = dict(complete=True, cases=len(cases), original_cases=1163, cpu_hz=3579545, video_hz_nominal=60,
                  machine='Panasonic_FS-A1WSX_NR128', hardware_sprite_limits=True,
                  results=results, candidate_sha256=hashlib.sha256((HERE/'game-sprite-mask-fast.inc').read_bytes()).hexdigest(),
                  added_resident_bytes=results['candidate']['resident_bytes']-results['baseline']['resident_bytes'],
                  exact_bytes_per_case=RESULT_BYTES,
                  scope='Synthetic templates/actors. Inclusive entry-to-immediate-return elapsed CPU cycles including memory/IO waits. Display-on SCREEN4 60Hz strict callback. Full SAT/color/pattern RAM, caches/visible state and both pattern VRAM sets/SAT/color VRAM compared. Private row/plane/pattern-id/tail/ink scratch and clobbered registers are excluded. No integrated gameplay/presentation/hardware claim.')
    (out/'cycle-ledger.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Exact sprite mask contracts passed {len(cases)} synthetic cases')
    print(json.dumps({version: {k: v for k, v in result['workloads'].items() if 'clipped-animation-change' in k}
                      for version, result in results.items()}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bios', required=True)
    args = parser.parse_args()
    verify(args.bios)
