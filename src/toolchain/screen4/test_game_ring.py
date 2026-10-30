"""Compare both assembled name-ring implementations using synthetic IDs only.

The emulator probe checks the cache, boundary/pointer records and both name
tables, and records inclusive routine cycles with MSX memory/IO wait states.
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

HERE = RUNTIME
ROOT = HERE.parents[1]
RECORD_BYTES = 3274
CASE_BYTES = 119


def cases():
    result = []
    for row in (0, 7, 31, 127, 128, 224, 255):
        for col in range(128):
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (1, 1), (-2, 0), (0, 2)):
                result.append((col, row, (col-dx)&255, (row-dy)&255,
                               len(result)&1, (col-dx)&255, (row-dy)&255))
    for row in (0, 7, 31, 127, 128, 224, 255):
        for col in range(128):
            result.append((col, row, 255, 255, len(result)&1, 255, 255))
    return result


def source(include, fast_refresh=False):
    lab = (HERE/'lab.asm').read_text()
    definitions = lab[lab.index('cx EQU '):lab.index('    ORG $4000')]
    definitions = definitions.replace('names EQU $c400', 'names EQU $d400')
    mapping = lab[lab.index('    call $0138'):lab.index('    reg 1,$02')]
    io = lab[lab.index('address:\n'):lab.index('palette:\n')]
    return (' OUTPUT "probe.rom"\n MACRO reg number,value\n ld a,value\n'
            ' out ($99),a\n ld a,$80+number\n out ($99),a\n ENDM\n'+
            definitions+(' DEFINE GAME_RING_REFRESH 1\n' if fast_refresh else '')+
            ' ORG $4000\n db "AB"\n dw boot,0,0,0,0,0,0\n'
            'boot:\n di\n ld sp,$f380\n'+mapping+
            ' reg 1,$02\n reg 0,4\n reg 8,$2a\n reg 9,$82\n'
            'main:\n jp main\n'+f' INCLUDE "{include}"\n'+io+
            'RingProbe_End:\n ASSERT $<$8000\n defs $8000-$,$ff\n')


def stats(values):
    ordered = sorted(values)
    return dict(calls=len(values), mean=statistics.mean(values),
                p95=ordered[int((len(ordered)-1)*.95)], maximum=max(values))


def verify(bios, fast_refresh=False):
    sys.path.insert(0, str(ROOT))
    from src.toolchain.msx.emulator import reference_machine, tcl
    out = ROOT/('outputs/fixed-hud/ring-refresh-synthetic' if fast_refresh else 'outputs/fixed-hud/ring-synthetic')
    out.mkdir(parents=True, exist_ok=True)
    inputs = cases()
    rng = random.Random(9917)
    seed = bytes(rng.randrange(256) for _ in range(1024+1024+112+84))
    terrain = bytes(((x*37+y*19)^((x+y)>>3))&255
                    for y in range(256) for x in range(128))
    (out/'seed.bin').write_bytes(seed)
    packed = bytearray()
    for c in inputs:
        packed.extend(c)
        for y in range(28):
            row = ((c[1]+y)&31)*32+0x2000
            packed.extend((row+(c[0]&31)).to_bytes(2, 'little'))
            packed.extend((row+((c[0]+24)&31)).to_bytes(2, 'little'))
    (out/'cases.bin').write_bytes(packed)
    results = {}
    baseline_include = 'game-ring.inc' if fast_refresh else 'ring.inc'
    for name, include in (('baseline', baseline_include), ('candidate', 'game-ring.inc')):
        target = out/name
        target.mkdir(exist_ok=True)
        fast = fast_refresh and name == 'candidate'
        (target/'probe.asm').write_text(source(HERE/include, fast))
        assembled = subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),
                                    '--nologo', '--sym=probe.sym', 'probe.asm'],
                                   cwd=target, capture_output=True, text=True)
        if assembled.returncode:
            raise AssertionError(assembled.stdout+assembled.stderr)
        rom = target/'probe.rom'
        resident = rom.read_bytes()
        rom.write_bytes(resident+bytes(16384)+terrain)
        if fast:
            from game_ring_refresh import compile_worker, OFFSET
            worker = compile_worker(ROOT, target)
            rom.write_bytes(rom.read_bytes()+bytes(OFFSET)+worker+bytes(16384-OFFSET-len(worker)))
        syms = {n: int(v, 16) for n, v in re.findall(
            r'^([\w.]+): EQU 0x([0-9a-fA-F]+)', (target/'probe.sym').read_text(), re.M)}
        lines = ['set save_settings_on_exit false', 'set renderer none',
                 'set sound_driver null',
                 f'filepool add -path {tcl(bios)} -types system_rom -position 1',
                 reference_machine(ROOT, 'Panasonic_FS-A1WSX'),
                 'set firmwareswitch off', 'set throttle off',
                 'set z80_freq 3579545', 'set z80_freq_locked false',
                 'set limitsprites true', f'cart {tcl(rom)} -romtype ASCII16',
                 'reset', f'set out {tcl(out)}', f'set target {tcl(target)}',
                 'set f [open [file join $out seed.bin] rb];set seed [read $f];close $f',
                 'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
                 'set result [open [file join $target actual.bin] wb]',
                 'set timing [open [file join $target cycles.txt] w]',
                 'set index 0;set started 0', 'proc issue {} {',
                 f' if {{$::index=={len(inputs)}}} {{close $::result;close $::timing;exit 0;return}}',
                 f' set at [expr {{$::index*{CASE_BYTES}}}]',
                 ' binary scan [string range $::data $at [expr {$at+6}]] cu* c',
                 ' debug write_block memory 0xc000 [string repeat "\0" 64]',
                 ' debug write_block memory 0xd800 [string range $::seed 0 1023]',
                 ' debug write_block memory 0xd400 [string range $::seed 1024 2047]',
                 ' debug write_block memory 0xce00 [string range $::data [expr {$at+7}] [expr {$at+118}]]',
                 ' debug write_block memory 0xc920 [string range $::seed 2160 2243]',
                 ' debug write_block VRAM 0x2000 [string repeat "\x5a" 2048]',
                 ' foreach address {0xc009 0xc008 0xc00e 0xc00f 0xc006 0xc018 0xc019} value $c {debug write memory $address $value}',
                 ' debug write_block memory 0xc01a [debug read_block memory 0xc018 2]',
                 # DI/CALL Prepare/CALL Upload/DI/JP finish; VDP IRQ is disabled.
                 f' set p 0xd100;foreach v [list 243 205 {syms["Ring_Prepare"]&255} {syms["Ring_Prepare"]>>8} 205 {syms["Ring_UploadNames"]&255} {syms["Ring_UploadNames"]>>8} 243 195 64 209] {{debug write memory $p $v;incr p}}',
                 ' reg SP 0xf380;reg PC 0xd100;set ::begin [machine_info time]', '}',
                 f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
                 f'debug set_bp {syms["Ring_UploadNames"]} {{$::started}} {{set ::upload_begin [machine_info time]}}',
                 'debug set_bp 0xd140 {$::started} {',
                 ' puts $::timing [list [expr {round(($::upload_begin-$::begin)*3579545)}] [expr {round(([machine_info time]-$::upload_begin)*3579545)}]]',
                 ' foreach {address length} {0xd800 1024 0xce00 112 0xc920 84 0xc00e 2 0xc018 4} {puts -nonewline $::result [debug read_block memory $address $length]}',
                 ' puts -nonewline $::result [debug read_block VRAM 0x2000 2048]',
                 ' incr ::index;issue', '}',
                 'after time 600 {puts stderr "Ring probe timeout";exit 2}']
        script = target/'session.tcl'
        script.write_text('if {[catch {\n'+'\n'.join(lines)+
                          '\n} problem]} {puts stderr $problem;exit 2}\n')
        with (target/'emulator.log').open('w') as log:
            subprocess.run(['openmsx', '-script', str(script)], stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=120,
                           env=dict(os.environ, OPENMSX_HOME=str(target/'home'),
                                    OPENMSX_USER_DATA=str(target/'userdata')))
        actual = (target/'actual.bin').read_bytes()
        if len(actual) != len(inputs)*RECORD_BYTES:
            raise AssertionError((name, len(actual), len(inputs)*RECORD_BYTES))
        timing = [tuple(map(int, line.split())) for line in
                  (target/'cycles.txt').read_text().splitlines()]
        results[name] = dict(rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
                             resident_used=syms['RingProbe_End']-0x4000,
                             prepare=stats([a for a, b in timing]),
                             upload=stats([b for a, b in timing]),
                             timing=timing)
    baseline = (out/'baseline/actual.bin').read_bytes()
    candidate = (out/'candidate/actual.bin').read_bytes()
    if baseline != candidate:
        at = next(i for i, (a, b) in enumerate(zip(baseline, candidate)) if a != b)
        raise AssertionError(dict(case=at//RECORD_BYTES, input=inputs[at//RECORD_BYTES],
                                  offset=at%RECORD_BYTES, baseline=baseline[at], candidate=candidate[at]))
    groups = {
        'stationary': [i for i, c in enumerate(inputs)
                       if c[0:2] == c[2:4] and c[3] != 255],
        'one-tile-scroll': [i for i, c in enumerate(inputs) if
                            (c[0]-c[2])&255 in (0, 1, 255) and
                            (c[1]-c[3])&255 in (0, 1, 255) and c[3] != 255 and
                            c[0:2] != c[2:4]],
        'horizontal-one-tile': [i for i, c in enumerate(inputs) if
                                (c[0]-c[2])&255 in (1, 255) and
                                c[1] == c[3] and c[3] != 255],
        'vertical-one-tile': [i for i, c in enumerate(inputs) if
                              (c[1]-c[3])&255 in (1, 255) and
                              c[0] == c[2] and c[3] != 255],
        'full-initial': list(range(len(inputs)-896, len(inputs))),
    }
    for result in results.values():
        timing = result.pop('timing')
        result['workloads'] = {label: dict(prepare=stats([timing[i][0] for i in ids]),
                                         upload=stats([timing[i][1] for i in ids]))
                               for label, ids in groups.items()}
    report = dict(cases=len(inputs), cpu_hz=3579545,
                  machine='Panasonic_FS-A1WSX_NR128', video_hz_nominal=60,
                  scope='Synthetic bytes; DI/CALL Prepare then CALL Upload/DI/JP wrapper. Inclusive elapsed emulator cycles include memory/IO waits; excludes IRQ, synchronization, native logic and other rendering.',
                  exact_comparison='1024 cached IDs,112 pointer bytes,84 boundary IDs,old camera,both seen records,2048 VRAM name bytes per case',
                  limitations='No continuous scanout or physical-hardware validation; full-stage acceptance belongs to the integrated cartridge.',
                  results=results)
    (out/'cycle-ledger.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bios', type=Path, default=ROOT/'references/msxbios')
    parser.add_argument('--fast-refresh', action='store_true')
    args = parser.parse_args()
    verify(args.bios.resolve(), args.fast_refresh)
