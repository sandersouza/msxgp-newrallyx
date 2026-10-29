"""Compare compiled terrain-overlay workers on identical synthetic RAM inputs.

Contributor cartridges are read only and stay in ignored references. No game
assets are embedded here. Compare the complete name ring, boundary IDs, both
dirty queues and native RAM guards, including modulo wrap and clipped squares.
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

ROOT = Path(__file__).resolve().parents[2]


def verify(before, after, out):
    sys.path.insert(0, str(ROOT))
    from scripts.msx.emulator import reference_machine, tcl
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(603871)
    cases = []
    # Every physical alignment and both edges; include partially visible and
    # entirely rejected squares, boundary columns24/25 and all cached rows.
    offsets = (-3, -2, -1, 0, 1, 23, 24, 25, 27, 28, 30, 31, 32)
    for i in range(256):
        for dx, dy in ((rng.choice(offsets), rng.choice(offsets)), (24, i % 32),
                       (i % 32, 0), (i % 32, 31)):
            col, row = i, (i*17) & 255
            cases.append((col, row, (col+dx) & 255, (row+dy) & 255,
                          (28, 29, 38)[i % 3], i % 4))
    # Saturating IDs are also defined by the authored baseline; test all256.
    cases += [(17, 29, 41, 42, value, 0) for value in range(256)]
    evidence = []
    for label, bundle in (('before', Path(before).resolve()), ('after', Path(after).resolve())):
        folder = out/label
        folder.mkdir(exist_ok=True)
        syms = {n: int(v, 16) for n, v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)', (bundle/'lab.sym').read_text())}
        # Copy the immutable measured binary because the canonical build can
        # legitimately be rebuilt while the evidence is retained.
        rom = (bundle/'fixed-hud.rom').read_bytes()
        (folder/'measured.rom').write_bytes(rom)
        data = bytes(v for c in cases for v in c)
        (folder/'cases.bin').write_bytes(data)
        lines = ['set save_settings_on_exit false', 'set renderer none',
                 'set sound_driver null',
                 f'filepool add -path {tcl(ROOT/"references/msxbios")} -types system_rom -position 1',
                 reference_machine(ROOT, 'Panasonic_FS-A1WSX'),
                 'set firmwareswitch off', 'set throttle off', 'set limitsprites true',
                 'set z80_freq 3579545', 'set z80_freq_locked false',
                 f'cart {tcl(folder/"measured.rom")} -romtype ASCII16', 'reset',
                 f'set out {tcl(folder)}',
                 'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
                 'set actual [open [file join $out actual.bin] wb]',
                 'set timing [open [file join $out cycles.txt] w]',
                 'set index 0;set started 0',
                 'proc issue {} {',
                 f' if {{$::index=={len(cases)}}} {{close $::actual;close $::timing;exit 0;return}}',
                 ' set at [expr {$::index*6}];binary scan [string range $::data $at [expr {$at+5}]] cu* p',
                 ' lassign $p col row x y id mode',
                 ' set ring {};for {set i 0} {$i<1024} {incr i} {lappend ring [expr {$mode==1?$id:($mode==2?($id+$i)%256:($i*73+19)%256)}]}',
                 ' debug write_block memory 0xd800 [binary format c* $ring]',
                 ' debug write_block memory 0xc920 [string repeat "\xa5" 84]',
                 ' debug write_block memory 0x2600 [string repeat "\x00" 256]',
                 ' debug write_block memory 0x2700 [string repeat "\x5a" 256]',
                 ' debug write_block memory 0xc096 "\x00\x00"',
                 ' debug write_block memory 0xc084 "\xaa\xbb\xcc"',
                 f' debug write memory {syms["mapcol"]} $col;debug write memory {syms["maprow"]} $row',
                 ' set ::native [debug read_block memory 0xe000 4096]',
                 f' debug write memory 0xd100 243;debug write memory 0xd101 205;debug write memory 0xd102 {syms["Game_PatchSquare"]&255};debug write memory 0xd103 {syms["Game_PatchSquare"]>>8}',
                 ' reg AF [expr {$id*256+147}];reg BC [expr {$x*256+$y}];reg DE 0x7a69;reg HL 0x1234;reg IX 0xabcd;reg IY 0x9a89;reg SP 0xf380;reg PC 0xd100',
                 '}',
                 f'debug set_bp {syms["Game_Prepare"]} {{!$::started}} {{set ::started 1;issue}}',
                 f'debug set_bp {syms["Game_PatchSquare"]} {{$::started}} {{set ::begin [machine_info time]}}',
                 'debug set_bp 0xd104 {$::started} {',
                 ' if {[reg IX]!=0xabcd || [reg IY]!=0x9a89 || $::native ne [debug read_block memory 0xe000 4096]} {error "Overlay corrupted native state or IX/IY"}',
                 ' puts $::timing [expr {round(([machine_info time]-$::begin)*3579545)}]',
                 ' foreach {at length} {0xd800 1024 0xc920 84 0x2600 256 0x2700 256 0xc096 2 0xc084 3} {puts -nonewline $::actual [debug read_block memory $at $length]}',
                 ' puts -nonewline $::actual [binary format s [reg BC]]',
                 ' incr ::index;issue', '}',
                 'after time 300 {puts stderr "Overlay probe timeout";exit 2}']
        (folder/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
        with (folder/'emulator.log').open('w') as log:
            subprocess.run(['openmsx', '-script', str(folder/'session.tcl')], check=True,
                           stdout=log, stderr=subprocess.STDOUT, timeout=150,
                           env=dict(os.environ, OPENMSX_HOME=str(folder/'home'),
                                    OPENMSX_USER_DATA=str(folder/'userdata')))
        cycles = [int(v) for v in (folder/'cycles.txt').read_text().split()]
        assert len(cycles) == len(cases)
        evidence.append(dict(rom_sha256=hashlib.sha256(rom).hexdigest(), cycles=cycles,
                             actual=(folder/'actual.bin').read_bytes()))
    assert len(evidence[0]['actual']) == len(cases)*1627
    assert evidence[0]['actual'] == evidence[1]['actual'], 'Compiled overlay output differs'
    kept = [i for i, c in enumerate(cases) if (c[2]-c[0]+2) % 256 < 34 and (c[3]-c[1]+2) % 256 < 34]
    result = dict(complete=True, cases=len(cases), exact_bytes=len(evidence[0]['actual']),
                  cpu_hz=3579545, machine='Panasonic_FS-A1WSX_NR128',
                  before_sha256=evidence[0]['rom_sha256'], after_sha256=evidence[1]['rom_sha256'],
                  accepted_squares=len(kept),
                  mean_accepted_cycles={name: statistics.mean(evidence[n]['cycles'][i] for i in kept)
                                        for n, name in enumerate(('before', 'after'))},
                  scope='Identical synthetic inputs to compiled Game_PatchSquare. Complete RAM name ring,84 boundary IDs, both dirty bitplanes/queues, lengths, patch scratch and BC match. Native4KiB RAM, IX/IY protected. Isolated entry-to-return timing with interrupts disabled; no VRAM or scanout claim.')
    (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    verify(a.before, a.after, a.out)
