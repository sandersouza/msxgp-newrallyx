"""Compare exact-ROM retirement calls against the generated inline Z80 body.

All resulting native/host/Page0 bytes, main registers, VRAM and cycle deltas are
checked. Synthetic code rings and callable-boundary probes are not gameplay.
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
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.toolchain.msx.emulator import reference_machine, tcl
from game_smoke_fast import inline_body, transform


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    syms = {n: int(v, 16) for n, v in re.findall(
        r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)', (bundle/'lab.sym').read_text(), re.M)}
    out = Path(tempfile.mkdtemp(prefix='smoke-retire-proof-', dir=bundle))
    smoke = (bundle.parent/'stage-one-3-enemies/baseline-ca9e6ae6/game-host.inc')
    if not smoke.exists():
        smoke = ROOT/'references/experiments/stage-one-3-enemies/baseline-ca9e6ae6/game-host.inc'
    text = smoke.read_text()
    changed = transform(text)
    original_helper = text[text.index('Smoke_RetireCode:'):text.index('Smoke_DirtyTile:')]
    assert original_helper in changed, 'Retained helper changed'
    assert changed.count('    IF GAME_RENDER_OPT\n') >= 2
    functions = []
    for mode in ('row', 'column'):
        if mode == 'row':
            advance = '''    ld a,l
    inc a
    and 31
    or e
    ld l,a
    inc b
    dec d
    jr nz,.loop
    ret
'''
        else:
            advance = '''    ld a,l
    add a,32
    ld l,a
    jr nc,.next
    inc h
    ld a,h
    and 3
    or $e4
    ld h,a
.next:
    inc c
    dec d
    jr nz,.loop
    ret
'''
        for variant in ('old', 'new'):
            if variant == 'old':
                body = f'    call ${syms["Smoke_RetireCode"]:04x}\n'
            else:
                start = changed.index('.clear_' + mode + ':\n') + len('.clear_' + mode + ':\n')
                next_step = '    ld a,l\n    ' + ('inc a\n' if mode == 'row' else 'add a,32\n')
                body = changed[start:changed.index(next_step, start)]
            functions.append(f'{variant}_{mode}:\n    di\n.loop:\n' + body + advance)
    def assemble(definitions):
        source = (' OUTPUT "harness.bin"\n ORG $d100\n' + definitions +
                  f'Smoke_RetireCode EQU ${syms["Smoke_RetireCode"]:04x}\n' +
                  f'Smoke_DirtyTile EQU ${syms["Smoke_DirtyTile"]:04x}\n' + ''.join(functions))
        (out/'harness.asm').write_text(source)
        subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo',
                        '--sym=harness.sym', 'harness.asm'], cwd=out, check=True,
                       capture_output=True, text=True)
        hs = {n: int(v, 16) for n, v in re.findall(
            r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)', (out/'harness.sym').read_text(), re.M)}
        return hs, (out/'harness.bin').read_bytes()
    for definitions in ('', '    DEFINE GAMEPLAY_CONFIGURED 1\nGAME_RENDER_OPT EQU 0\n'):
        config_syms, binary = assemble(definitions)
        boundaries = [config_syms[name]-0xd100 for name in
                      ('old_row', 'new_row', 'old_column', 'new_column')] + [len(binary)]
        pieces = [binary[a:b] for a,b in zip(boundaries,boundaries[1:])]
        assert pieces[0] == pieces[1] and pieces[2] == pieces[3], 'Legacy/unconfigured retirement changed'
    hs, _ = assemble('    DEFINE GAMEPLAY_CONFIGURED 1\nGAME_RENDER_OPT EQU 1\n')
    rng = random.Random(0x534d4f4b45)
    cases, fixtures = [], bytearray()
    def add(mode, start, label, ring):
        row = (start*7+len(cases)) & 31
        col = start
        at = 0xe400+row*32+col
        b = (start*11+len(cases)) & 255
        c = (row+10) & 255
        e = (at & 0xe0) if mode == 0 else (start*13+len(cases)) & 255
        flags = (start*17+len(cases)) & 255
        a = (len(cases)*31) & 255
        fixtures.extend(struct.pack('<BHBBBBB', mode, at, b, c, e, flags, a))
        fixtures.extend(bytes(ring))
        cases.append(dict(mode=('row' if mode == 0 else 'column'), start=start,
                          physical_row=row, label=label))
    for mode in range(2):
        for start in range(32):
            add(mode, start, 'empty', [0]*1024)
            add(mode, start, 'cleared-road', [0x81]*1024)
            add(mode, start, 'dense', [0xbd+i%9 for i in range(1024)])
            add(mode, start, 'mostly-empty', [0xbd+i%9 if i%97 == 0 else 0 for i in range(1024)])
            add(mode, start, 'mixed-random', [rng.randrange(256) for _ in range(1024)])
            add(mode, start, 'dense-random', [rng.randrange(0xbd,0xc6) for _ in range(1024)])
        for value in range(256):
            add(mode, value%32, f'uniform-{value:02x}', [value]*1024)
    (out/'fixtures.bin').write_bytes(fixtures)
    (out/'fixtures.json').write_text(json.dumps(cases, indent=2)+'\n')
    script = f'''
set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq 3579545
set z80_freq_locked true
set limitsprites true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(bundle/'fixed-hud.rom')} -romtype ASCII16
reset
set out {tcl(out)}
set started 0
set index 0
set variant 0
set entries {{{hs['old_row']} {hs['new_row']} {hs['old_column']} {hs['new_column']}}}
proc issue {{}} {{
    if {{$::index=={len(cases)}}} {{close $::fixture_file;close $::costs;exit 0;return}}
    if {{!$::variant}} {{
        set ::fixture [read $::fixture_file 1032]
        if {{[string length $::fixture]!=1032}} {{error "Truncated fixture"}}
    }}
    binary scan [string range $::fixture 0 7] cu* fields
    lassign $fields mode low high b c e flags a
    debug write_block memory 0 $::seed_page0
    debug write_block memory 0xc000 $::seed_host
    debug write_block memory 0xe000 $::seed_native
    debug write_block memory 0xe400 [string range $::fixture 8 end]
    debug write memory 0xc080 251
    debug write memory 0xc051 254
    debug write memory 0xc0b0 0
    debug write memory 0xf380 240
    debug write memory 0xf381 208
    reg AF [expr {{$a*256+$flags}}]
    reg BC [expr {{$b*256+$c}}]
    reg DE [expr {{32*256+$e}}]
    reg HL [expr {{$high*256+$low}}]
    reg IX 4660
    reg IY 22136
    reg SP 62336
    set ::begin [machine_info time]
    reg PC [lindex $::entries [expr {{$mode*2+$::variant}}]]
}}
debug set_bp {syms['Game_Prepare']} {{!$::started}} {{
    set ::started 1
    set f [open [file join $::out harness.bin] rb]
    debug write_block memory 0xd100 [read $f]
    close $f
    set ::seed_page0 [debug read_block memory 0 16384]
    set ::seed_host [debug read_block memory 0xc000 4096]
    set ::seed_native [debug read_block memory 0xe000 4096]
    set ::seed_vram [debug read_block VRAM 0 65536]
    set ::fixture_file [open [file join $::out fixtures.bin] rb]
    set ::costs [open [file join $::out costs.tsv] w]
    issue
}}
debug set_bp 0xd0f0 {{$::started}} {{
    if {{[catch {{
        set duration [expr {{([machine_info time]-$::begin)*3579545}}]
        set registers [list [reg AF] [reg BC] [reg DE] [reg HL] [reg IX] [reg IY] [reg SP]]
        set result [list [debug read_block memory 0 16384] [debug read_block memory 0xc000 4096] [debug read_block memory 0xe000 4096] $registers]
        if {{[debug read_block VRAM 0 65536] ne $::seed_vram}} {{error "Retirement changed VRAM"}}
        if {{!$::variant}} {{
            set ::baseline $result
            set ::baseline_cycles $duration
            set ::variant 1
        }} else {{
            if {{$::baseline ne $result}} {{error "Retirement state mismatch case $::index registers $registers baseline [lindex $::baseline end]"}}
            puts $::costs "$::index\\t$::baseline_cycles\\t$duration\\t[expr {{$::baseline_cycles-$duration}}]"
            incr ::index
            set ::variant 0
        }}
        issue
    }} problem]}} {{puts stderr $problem;exit 2}}
}}
after time 600 {{puts stderr "SMOKE RETIREMENT PROOF TIMEOUT";exit 2}}
'''
    (out/'session.tcl').write_text(script)
    env = dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata'))
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    rows = [list(map(float, line.split())) for line in (out/'costs.tsv').read_text().splitlines()]
    assert len(rows) == len(cases)
    assert all(abs(row[3]-928) < .01 for row in rows), sorted(set(row[3] for row in rows))
    report = dict(cases=len(cases), result='Exact inline retirement equivalence',
                  rom_sha256=hashlib.sha256((bundle/'fixed-hud.rom').read_bytes()).hexdigest(),
                  cycles_saved_per_32_cells=statistics.mean(row[3] for row in rows),
                  cycles_saved_per_cell=29,
                  original_paths='Unconfigured and GAME_RENDER_OPT=0 assembled byte-identically to the original CALL loops; optimized probes execute the actual guarded transform output.',
                  comparison='AF/BC/DE/HL/IX/IY/SP; full Page0, C000..CFFF host RAM, E000..EFFF native RAM; VRAM unchanged. World/smoke generation bytes start near wrap and candidate-row notifications are compared exactly.',
                  coverage='Both row/column loops; all32 physical starting offsets; all256 code values; empty, cleared-road81, mostly empty, denseBD..C5, mixed random and dense random rings; all native code bytes including81 are zeroed identically.',
                  cpu_hz=3579545, machine='Panasonic_FS-A1WSX_NR128',
                  limits='Isolated synthetic callable-boundary proof with IRQ disabled; no gameplay or physical hardware timing claim.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
