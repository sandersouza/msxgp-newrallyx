"""Synthetic native-smoke cache equivalence probe; no contributor ROM needed."""

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

HERE = RUNTIME
ROOT = HERE.parents[1]
CASE_BYTES = 1066
RECORD_BYTES = 4130

BASELINE = '''GameSmoke_Baseline:
    ld ix,Game_SmokeList
    ld hl,0
    ld (Game_SmokeCount),hl
    ld hl,$e400
.next:
    ld a,(hl)
    sub $bd
    cp 9
    jr nc,.skip
    add a,GAME_SMOKE_TILE
    push hl
    push af
    call Smoke_DecodeAddress
    ld (ix+0),b
    ld (ix+1),c
    pop af
    ld (ix+2),a
    ld de,3
    add ix,de
    ld hl,(Game_SmokeCount)
    inc hl
    ld (Game_SmokeCount),hl
    pop hl
.skip:
    inc hl
    ld a,h
    cp $e8
    jr nz,.next
    ret
'''


def physical(x, y):
    return ((y-10) & 31)*32+((x-3) & 31)


def sparse(codes, left, top):
    """Full-scan contract: physical address order, retained native world tile."""
    result = bytearray()
    for index, code in enumerate(codes):
        if 0xbd <= code < 0xc6:
            x = (((index & 31)+3-left) & 31)+left
            y = (((index >> 5)+10-top) & 31)+top
            result.extend((x & 255, y & 255, code-0xbd+0xd0))
    return bytes(result)


def occupied(codes):
    return bytes(any(0xbd <= c < 0xc6 for c in codes[y*32:y*32+32])
                 for y in range(32))


def cases():
    rng = random.Random(98131)
    result = []
    def add(codes, rows, left=0, top=0, placements=1, hook=0,
            x=0, y=0, address=0xe400, label='mixed', after=None, touched=1):
        result.append(dict(codes=bytes(codes), rows=bytes(rows), left=left,
                           top=top, placements=placements, hook=hook,
                           x=x, y=y, address=address, label=label,
                           after=bytes(codes if after is None else after),
                           touched=touched))
    for index in range(1024):
        codes = bytearray(1024)
        codes[index] = 0xbd+index % 9
        y = ((index >> 5)+10+(index % 8)*32) & 255
        add(codes, bytes(32), rng.randrange(256), rng.randrange(256),
            hook=1, y=y, label='one-live-row')
        if index % 32 == 0:
            # The diagnostic placements word is not an emptiness invariant.
            add(codes, occupied(codes), rng.randrange(256), rng.randrange(256),
                placements=0, label='wrapped-placement-counter')
    for y in range(256):
        x = (y*19) & 255
        codes = bytearray(1024)
        for dy in range(3):
            for dx in range(3):
                codes[physical(x+dx, y+dy)] = 0xbd+dy*3+dx
        add(codes, bytes(32), (x-13) & 255, (y-17) & 255,
            hook=2, x=x, y=y, label='three-live-rows')
        # The clear notification runs before native code changes. Marking is
        # independent of code contents; this fixture supplies the cleared ring.
        add(bytes(1024), occupied(codes), (x-13) & 255, (y-17) & 255,
            hook=6, address=0xe400+physical(x, y), label='three-retired-rows')
        # Execute the actual flag brush and single-cell retirement adapters.
        after = bytearray(codes)
        for dy in (1, 2):
            for dx in (0, 1):
                after[physical(x+dx, y+dy)] = 0x81
        add(codes, occupied(codes), (x-13) & 255, (y-17) & 255,
            hook=5, x=x, y=y, label='flag-overlap', after=after)
        index = physical(x, y)
        after = bytearray(codes)
        after[index] = 0
        add(codes, occupied(codes), (x-13) & 255, (y-17) & 255,
            hook=7, x=x, y=y, address=0xe400+index,
            label='single-cell-retirement', after=after)
    for count in (0, 1, 3, 16, 32):
        for i in range(20):
            codes = bytearray(rng.choice((0, 0x81, 0xbc, 0xc6, 0xff))
                              for _ in range(1024))
            for row in rng.sample(range(32), count):
                for col in rng.sample(range(32), 1+i % 31):
                    codes[row*32+col] = rng.randrange(0xbd, 0xc6)
            add(codes, occupied(codes), rng.randrange(256), rng.randrange(256),
                label=f'{count}-occupied-rows')
    for code in range(9):
        # Maximum 32 records per row and repeated IXL wrap, without overflow
        # of the unchanged 1024-record sparse-list allocation.
        codes = bytes(0xbd+(i+code) % 9 for i in range(1024))
        add(codes, bytes([1])*32, 255, 255, label='32-full-rows')
    for i in range(32):
        add(bytes(1024), bytes(32), placements=0, label='never-placed', touched=0)
        add(bytes(1024), bytes([1])*32, hook=3, label='reset-metadata')
        codes = bytes(rng.randrange(256) for _ in range(1024))
        add(codes, bytes([1])*32, hook=4, label='clear-native-rings',
            after=bytes(1024))
    return result


def probe_source(cache_source=None):
    # Only authored adapter routines are copied; all native calls are excluded.
    from game_core import selected
    smoke = selected((ROOT/'src/screen5/smoke.inc').read_text())
    declarations = smoke[:smoke.index('Smoke_CachePressure:')]
    rings = smoke[smoke.index('Smoke_ClearRings:'):smoke.index('Smoke_PreTick:')]
    rings = rings.replace('Smoke_ClearRings:\n',
                          'Smoke_ClearRings:\n    call GameSmoke_ClearRows\n', 1)
    address = smoke[smoke.index('Smoke_Address:'):smoke.index('Smoke_Tick:')]
    notify = smoke[smoke.index('Smoke_ClearNotify:'):smoke.index('Smoke_RecoveredNotify:')]
    flags = smoke[smoke.index('Smoke_CollectedFlag:'):smoke.index('Smoke_ClearPublishedRow:')]
    return ''' OUTPUT "probe.rom"
Game_SmokeList EQU $0800
Game_SmokeCount EQU $c082
Game_WorldChanged EQU $c080
Game_SmokeChanged EQU $c051
GAME_SMOKE_TILE EQU $d0
Flag_X EQU $c510
Flag_Y EQU $c511
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 ; Map independent Page0 RAM using the active Page3 primary/subslot.
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
Smoke_EnqueueRow:
 jp GameSmoke_MarkRow
Smoke_Enqueue:
 jp GameSmoke_MarkCloud
Probe_NoHook:
 ret
'''+declarations+rings+address+notify+flags+BASELINE+f'''
 INCLUDE "{cache_source or HERE/'game-smoke-cache.inc'}"
Probe_End:
 ASSERT $ < $8000
 defs $8000-$,$ff
'''


def stats(values):
    ordered = sorted(values)
    return dict(calls=len(values), mean=statistics.mean(values),
                p99=ordered[(len(values)*99+99)//100-1], maximum=max(values))


def verify(bios, out=None, cache_source=None):
    sys.path.insert(0, str(ROOT))
    from src.toolchain.msx.emulator import reference_machine, tcl
    out = Path(out or ROOT/'outputs/fixed-hud/smoke-cache-synthetic').resolve()
    out.mkdir(parents=True, exist_ok=True)
    inputs = cases()
    packed = bytearray()
    for c in inputs:
        packed.extend(c['codes']+c['rows']+bytes((c['left'], c['top']))+
                      c['placements'].to_bytes(2, 'little')+
                      bytes((c['hook'], c['x'], c['y']))+
                      c['address'].to_bytes(2, 'little')+bytes((c['touched'],)))
    assert len(packed) == len(inputs)*CASE_BYTES
    (out/'cases.bin').write_bytes(packed)
    cache_source = Path(cache_source or HERE/'game-smoke-cache.inc').resolve()
    (out/'probe.asm').write_text(probe_source(cache_source))
    assembled = subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),
                                '--nologo', '--sym=probe.sym', 'probe.asm'],
                               cwd=out, capture_output=True, text=True)
    if assembled.returncode:
        raise AssertionError(assembled.stdout+assembled.stderr)
    syms = {n: int(v, 16) for n, v in re.findall(
        r'^([\w.]+): EQU 0x([0-9a-fA-F]+)', (out/'probe.sym').read_text(), re.M)}
    hooks = [syms[n] for n in ('Probe_NoHook', 'GameSmoke_MarkRow',
             'GameSmoke_MarkCloud', 'GameSmoke_ClearRows', 'Smoke_ClearRings',
             'Smoke_CollectedFlag', 'Smoke_ClearNotify', 'Smoke_RetireCode')]
    lines = ['set save_settings_on_exit false', 'set renderer none',
             'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'),
             'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(out/"probe.rom")} -romtype Normal', 'reset', f'set out {tcl(out)}',
             'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
             'set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]',
             'set index 0;set started 0', 'proc issue {} {',
             f' if {{$::index=={len(inputs)}}} {{close $::result;close $::timing;exit 0;return}}',
             f' set at [expr {{$::index*{CASE_BYTES}}}]',
             ' debug write_block memory 0xe400 [string range $::data $at [expr {$at+1023}]]',
             ' debug write_block memory 0x2800 [string range $::data [expr {$at+1024}] [expr {$at+1055}]]',
             ' debug write_block memory 0xc702 [string range $::data [expr {$at+1056}] [expr {$at+1057}]]',
             ' debug write_block memory 0xc711 [string range $::data [expr {$at+1058}] [expr {$at+1059}]]',
             ' debug write memory 0xc0af 165;debug write memory 0xc0b2 165;debug write memory 0x27ff 165;debug write memory 0x2820 165',
             ' debug write memory 0xc701 1;debug write memory 0xc080 0;debug write memory 0xc051 0',
             ' binary scan [string range $::data [expr {$at+1060}] [expr {$at+1065}]] cu* p',
             ' set ::hook [lindex $p 0];set x [lindex $p 1];set y [lindex $p 2];set h [expr {[lindex $p 3]+256*[lindex $p 4]}]',
             ' debug write memory 0xc0b0 [lindex $p 5]',
             ' debug write memory 0xc510 $x;debug write memory 0xc511 $y',
             ' debug write_block memory 0x0800 [string repeat "\x5a" 3072];debug write_block memory 0xc082 "\x34\x12"',
             f' set target [lindex [list {" ".join(map(str, hooks))}] $::hook]',
             f' set p 0xd100;foreach v [list 205 [expr {{$target&255}}] [expr {{$target>>8}}] 0 205 {syms["GameSmoke_BuildCache"]&255} {syms["GameSmoke_BuildCache"]>>8} 0 205 {syms["GameSmoke_Baseline"]&255} {syms["GameSmoke_Baseline"]>>8} 195 64 209] {{debug write memory $p $v;incr p}}',
             ' reg AF 0x7393;reg BC [expr {$x*256+$y}];reg DE 0x7a69;reg HL $h;reg IY 0x9a89;reg SP 0xf380;reg PC 0xd100',
             ' set ::registers [list [reg AF] [reg BC] [reg DE] [reg HL]];set ::hook_at [machine_info time]', '}',
             f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
             'debug set_bp 0xd103 {$::started} {',
             ' set ::hook_cycles [expr {round(([machine_info time]-$::hook_at)*3579545)}]',
             ' if {$::hook<=3 && $::registers ne [list [reg AF] [reg BC] [reg DE] [reg HL]]} {error "Hook clobbered original registers"}',
             ' if {[debug read_block memory 0x0800 3072] ne [string repeat "\x5a" 3072] || [debug read_block memory 0xc082 2] ne "\x34\x12"} {error "Hook dropped preceding sparse cache before restoration"}',
             ' if {$::hook in {3 4} && ([debug read memory 0xc080]!=1 || [debug read memory 0xc051]!=1)} {error "Ring reset failed to notify parent cache"}', '}',
             f'debug set_bp {syms["GameSmoke_BuildCache"]} {{$::started}} {{set ::candidate_at [machine_info time]}}',
             'debug set_bp 0xd107 {$::started} {',
             ' set ::candidate_cycles [expr {round(([machine_info time]-$::candidate_at)*3579545)}]',
             ' if {[reg IY]!=0x9a89} {error "Cache builder changed IY"}',
             ' foreach address {0x27ff 0x2820 0xc0af 0xc0b2} {if {[debug read memory $address]!=165} {error "Smoke cache scratch out of bounds"}}',
             ' set ::candidate_count [debug read_block memory 0xc082 2];binary scan $::candidate_count s count',
             ' set ::candidate_list [debug read_block memory 0x0800 [expr {$count*3}]]',
             ' puts -nonewline $::result $::candidate_count;puts -nonewline $::result [debug read_block memory 0x0800 3072]',
             ' puts -nonewline $::result [debug read_block memory 0x2800 32];puts -nonewline $::result [debug read_block memory 0xe400 1024]', '}',
             f'debug set_bp {syms["GameSmoke_Baseline"]} {{$::started}} {{set ::baseline_at [machine_info time]}}',
             'debug set_bp 0xd10b {$::started} {',
             ' set baseline_cycles [expr {round(([machine_info time]-$::baseline_at)*3579545)}]',
             ' if {$::candidate_count ne [debug read_block memory 0xc082 2] || $::candidate_list ne [debug read_block memory 0x0800 [string length $::candidate_list]]} {error "Sparse cache differs from full scan at $::index"}',
             ' puts $::timing "$::hook_cycles $::candidate_cycles $baseline_cycles"', '}',
             'debug set_bp 0xd140 {$::started} {incr ::index;issue}',
             'after time 300 {puts stderr "Smoke cache probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+
                                  '\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=120,
                       env=dict(os.environ, OPENMSX_HOME=str(out/'home'),
                                OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'actual.bin').read_bytes()
    if len(actual) != len(inputs)*RECORD_BYTES:
        raise AssertionError((len(actual), len(inputs)*RECORD_BYTES))
    for index, c in enumerate(inputs):
        record = actual[index*RECORD_BYTES:(index+1)*RECORD_BYTES]
        count = int.from_bytes(record[:2], 'little')
        expected = sparse(c['after'], c['left'], c['top'])
        if record[2:2+count*3] != expected:
            raise AssertionError(f'Sparse Python contract differs at case {index}')
        if record[3106:] != c['after']:
            raise AssertionError(f'Native ring differs at case {index}')
        if record[3074:3106] != occupied(c['after']):
            raise AssertionError(f'Candidate occupancy differs at case {index}')
    timings = [list(map(int, line.split())) for line in
               (out/'cycles.txt').read_text().splitlines()]
    report = dict(cases=len(inputs), cpu_hz=3579545,
                  machine='Panasonic_FS-A1WSX_NR128', video_hz_nominal=60,
                  calls_per_case=1, synchronization_waits=0,
                  rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(cache_source.read_bytes()).hexdigest(),
                  scope='Synthetic native code-ring bytes; inclusive emulated entry-to-return cycles include MSX memory waits. Excludes simulation, renderer, HUD, IRQ and synchronization. Hook CALL overhead is included in hook cycles; candidate/baseline entry-to-return excludes caller CALL.',
                  exact_comparison='Sparse count and ordered 3-byte records against assembled baseline and independent world-coordinate reference; native code bytes; retained candidate row occupancy; marker AF/BC/DE/HL and preceding sparse list preservation.',
                  limitations='No integrated cartridge, continuous scanout or physical hardware acceptance.',
                  workloads={})
    for label in sorted({c['label'] for c in inputs}):
        ids = [i for i, c in enumerate(inputs) if c['label'] == label]
        report['workloads'][label] = {name: stats([timings[i][column] for i in ids])
            for column, name in enumerate(('hook', 'candidate', 'baseline'))}
    (out/'cycle-ledger.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bios', type=Path, default=ROOT/'references/msxbios')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--cache-source', type=Path, help='Frozen authored cache source for paired comparisons')
    args = parser.parse_args()
    print(json.dumps(verify(args.bios, args.out, args.cache_source), indent=2))
