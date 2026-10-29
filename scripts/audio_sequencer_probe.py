#!/usr/bin/env python3
"""Execute relocated sound calls against unmodified arcade entry/exit evidence."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.audio_native import build, map_address
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine, tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.stage_one import acquire
from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


SAMPLE = 3072 + 32


def project(raw):
    game = bytearray(raw[:2560])
    value = int.from_bytes(game[0x98a:0x98c], 'little')
    game[0x98a:0x98c] = map_address(value).to_bytes(2, 'little')
    state = bytearray(raw[2560:3072])
    for at in (0x19a, 0x19c, 0x19e):
        state[at:at+2] = map_address(int.from_bytes(state[at:at+2], 'little')).to_bytes(2, 'little')
    return bytes(game + state + raw[3072:])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    rom = args.rom.resolve()
    verify_manifest(rom.parent)
    verify_manifest(args.reference)
    ref = read_json(args.reference/'report.json')
    count = ref['sequencer_cases']
    raw = (args.reference/'sequencer.bin').read_bytes()
    if len(raw) != count * SAMPLE * 2:
        raise ValueError('Incomplete original sound-call snapshots')
    out = destination(root, args.output)
    require_ignored(root, [out/'audio-overlay.bin', out/'cases.bin'])
    out.mkdir(parents=True)
    program, _ = acquire(root)
    image, changes = build(program, out)
    seeds = b''.join(project(raw[i*2*SAMPLE:i*2*SAMPLE+SAMPLE]) for i in range(count))
    expected = bytearray(b''.join(project(raw[i*2*SAMPLE+SAMPLE:(i+1)*2*SAMPLE]) for i in range(count)))
    # The arcade stack lives inside its video/game RAM. Its checked call-stack
    # writes are not logical state; our isolated caller uses the host stack.
    original_stack = set()
    for row in (args.reference/'sequencer-stack.tsv').read_text().splitlines():
        case, address = map(int, row.split())
        at = (case-1)*SAMPLE + address-0x8000
        expected[at] = seeds[at]
        original_stack.add((case, address))
    (out/'cases.bin').write_bytes(seeds)
    s = symbols(rom.parent/'raster-scroll.sym')
    enter, leave = s['Full_CacheEnter'], s['Full_CacheLeave']
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
        'set throttle off', 'set z80_freq 3579545', 'set z80_freq_locked true',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off',
        f'cart {tcl(rom)} -romtype ASCII16', 'reset', f'set out {tcl(out)}',
        f'set count {count};set index 0;set started 0;set active 0',
        'foreach name {cases audio-overlay} {set f [open [file join $out "$name.bin"] rb];set data($name) [read $f];close $f}',
        'set result [open [file join $out result.bin] wb];set hardware [open [file join $out hardware.tsv] w];set costs [open [file join $out costs.tsv] w]',
        'proc issue {} {',
        ' if {$::index==$::count} {if {[debug read_block VRAM 0 131072] ne $::vram} {error "Sound changed VRAM"};close $::result;close $::hardware;close $::costs;exit 0;return}',
        ' set seed [string range $::data(cases) [expr {$::index*3104}] [expr {$::index*3104+3103}]]',
        ' debug write_block memory 0xe000 [string range $seed 0 2559]',
        ' debug write_block $::mapper [expr {$::base+0x3800}] [string range $seed 2560 3071]',
        ' debug write_block $::mapper [expr {$::base+0x3a00}] [string range $seed 3072 3103]',
        ' debug write_block $::mapper [expr {$::base+0x3a20}] [binary format cc 0 0]',
        ' reg SP 0xf380;reg IX 0x4567;reg IY 0x6789;reg PC 0xd150;set ::active 1;set ::begin [machine_info time]',
        '}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 2',
        ' set ::primary [debug read ioports 168];set ::page [debug read ioports 252];set ::vram [debug read_block VRAM 0 131072];set ::native [debug read_block memory 0xea00 1536]',
        f' set ::cache [debug read memory {s["Full_CacheSegment"]}];set ::audio [expr {{[debug read ioports 255]^2}}]',
        ' foreach device [debug list] {if {[debug desc $device] eq "memory mapper" && [debug size $device]>=131072} {set ::mapper $device;set ::audio [expr {$::audio&([debug size $device]/16384-1)}];set ::base [expr {$::audio*16384}];break}}',
        ' if {$::audio==$::cache || $::audio==[debug read ioports 255]} {error "Audio segment overlaps renderer/main RAM"}',
        ' debug write_block $::mapper $::base $::data(audio-overlay)',
        f' debug write memory {s["Full_CacheHeld"]} 0',
        f' set at 0xd150;foreach value [list 243 205 {enter&255} {enter>>8} 62 $::audio 211 252 205 128 37 62 $::cache 211 252 205 {leave&255} {leave>>8} 195 176 209] {{debug write memory $at $value;incr at}}',
        ' if {[catch issue problem]} {puts stderr $problem;exit 2}',
        '}',
        'debug set_watchpoint write_mem {14848 14881} {$::active} {',
        ' set address [expr {$::wp_last_address<14880?0xa100+$::wp_last_address-14848:($::wp_last_address==14880?0xa180:0xa182)}]',
        ' puts $::hardware "[expr {$::index+1}] $address $::wp_last_value"',
        '}',
        'debug set_bp 0xd1b0 {$::active} {',
        ' set ::active 0;puts $::costs [expr {([machine_info time]-$::begin)*1000}]',
        ' if {[reg SP]!=0xf380 || [reg IX]!=0x4567 || [reg IY]!=0x6789 || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::page || [debug read_block memory 0xea00 1536] ne $::native} {puts stderr "Sound changed preserved state, code or mapping";exit 2}',
        ' if {[debug read_block $::mapper $::base 14336] ne [string range $::data(audio-overlay) 0 14335] || [debug read_block $::mapper [expr {$::base+0x3a22}] 1502] ne [string range $::data(audio-overlay) 14882 16383]} {puts stderr "Sound overwrote overlay code/data canaries";exit 2}',
        ' puts -nonewline $::result [debug read_block memory 0xe000 2560]',
        ' puts -nonewline $::result [debug read_block $::mapper [expr {$::base+0x3800}] 512]',
        ' binary scan [debug read_block $::mapper [expr {$::base+0x3a00}] 32] cu* values;foreach value $values {puts -nonewline $::result [binary format c [expr {$value&15}]]}',
        ' incr ::index;if {[catch issue problem]} {puts stderr $problem;exit 2}',
        '}',
        'after time 180 {puts stderr "Sound sequencer execution timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, timeout=240,
                       stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'result.bin').read_bytes()
    if actual != expected:
        at = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), min(len(actual), len(expected)))
        raise ValueError(f'Sound state differs: call {at//SAMPLE+1}, byte {at%SAMPLE}')
    actual_writes = (out/'hardware.tsv').read_text().splitlines()
    expected_writes = (args.reference/'sequencer-writes.tsv').read_text().splitlines()
    if actual_writes != expected_writes:
        at = next((i for i, (a, b) in enumerate(zip(actual_writes, expected_writes)) if a != b), min(len(actual_writes), len(expected_writes)))
        raise ValueError(f'Ordered sound hardware writes differ at event {at}')
    costs = [float(line) for line in (out/'costs.tsv').read_text().splitlines()]
    verify_manifest(rom.parent); verify_manifest(args.reference)
    json_write(out/'report.json', dict(rom_sha256=digest(rom), reference_manifest_sha256=digest(args.reference/'manifest.json'),
        cases=count, ordered_hardware_writes=len(actual_writes), original_stack_bytes=len(original_stack), address_changes=changes,
        maximum_call_ms=max(costs), mean_call_ms=sum(costs)/len(costs), passed=True,
        scope='Executed original sound calls at locked 3.58 MHz, display/IRQs disabled. '
              'Projected original game/command/state and every raw ordered WSG/BANG write agree; '
              'VRAM, presentation/native smoke code, overlay canaries, stack/indices and mapping preserved. '
              'Wrapper timing includes mapper entry/exit; this is not loaded gameplay or audible PSG qualification.'))
    require_ignored(root, [f for f in out.rglob('*') if f.is_file()]); seal(out)
    print(f'{count} relocated sound calls and {len(actual_writes)} ordered writes pass: {out}/report.json')


if __name__ == '__main__':
    main()
