#!/usr/bin/env python3
"""Execute integrated PSG conversion and mute against original sound evidence."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audio_sequencer_probe import project, SAMPLE
from scripts.msx.audio_psg import period, volume_curve
from scripts.msx.audio_reference import decode_voices
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine, tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    rom = args.rom.resolve(); ref = args.reference.resolve()
    verify_manifest(rom.parent); verify_manifest(ref)
    s = symbols(rom.parent/'raster-scroll.sym')
    if not s.get('AUDIO_ENABLED'):
        raise ValueError('PSG probe requires an audio-enabled integration build')
    count = read_json(ref/'report.json')['sequencer_cases']
    raw = (ref/'sequencer.bin').read_bytes()
    if len(raw) != count*2*SAMPLE:
        raise ValueError('Incomplete original call evidence')
    seeds = b''.join(project(raw[i*2*SAMPLE:i*2*SAMPLE+SAMPLE]) for i in range(count))
    expected = bytearray(b''.join(project(raw[i*2*SAMPLE+SAMPLE:(i+1)*2*SAMPLE]) for i in range(count)))
    for line in (ref/'sequencer-stack.tsv').read_text().splitlines():
        case, at = map(int, line.split())
        offset = (case-1)*SAMPLE+at-0x8000
        expected[offset] = seeds[offset]
    out = destination(root, args.output)
    require_ignored(root, [out/'cases.bin']); out.mkdir(parents=True)
    (out/'cases.bin').write_bytes(seeds)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
        'set throttle off', 'set z80_freq 3579545', 'set z80_freq_locked false',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off',
        f'cart {tcl(rom)} -romtype ASCII16', 'reset', f'set out {tcl(out)}',
        f'set count {count};set index 0;set started 0;set active 0',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out result.bin] wb];set costs [open [file join $out costs.tsv] w]',
        'proc issue {} {',
        ' if {$::index==$::count*2} {if {[debug read_block VRAM 0 131072] ne $::vram} {error "Audio changed VRAM"};close $::result;close $::costs;exit 0;return}',
        ' set case [expr {$::index/2}];set mute [expr {$::index&1}]',
        ' set seed [string range $::cases [expr {$case*3104}] [expr {$case*3104+3103}]]',
        ' debug write_block memory 0xe000 [string range $seed 0 2559]',
        ' debug write_block $::mapper [expr {$::base+0x3800}] [string range $seed 2560 3071]',
        ' debug write_block $::mapper [expr {$::base+0x3a00}] [string range $seed 3072 3103]',
        ' debug write_block $::mapper [expr {$::base+0x3b00}] [string repeat [binary format c 0] 64]',
        ' debug write_block $::mapper [expr {$::base+0x3b20}] [string repeat [binary format c 255] 11]',
        f' debug write memory {s["Audio_Mute"]} $mute;debug write memory {s["Audio_Held"]} 0',
        f' debug write memory {s["Audio_Ticks"]} 1;debug write memory {s["Audio_Ticks"]+1} 0',
        ' debug write {PSG regs} 7 191',
        f' debug write memory 0x7000 {s["PLAYER_BANK"]}',
        ' debug write memory 0xf37e 95;debug write memory 0xf37f 209',
        f' reg SP 0xf37e;reg IX 0x4567;reg IY 0x6789;reg PC {s["Audio_ReferenceTick"]}',
        ' set ::active 1;set ::begin [machine_info time]',
        '}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 2',
        ' set ::primary [debug read ioports 168];set ::page [debug read ioports 252];set ::vram [debug read_block VRAM 0 131072];set ::native [debug read_block memory 0xea00 1536]',
        ' set ::io [debug read_block {PSG regs} 14 2]',
        ' foreach device [debug list] {if {[debug desc $device] eq "memory mapper" && [debug size $device]>=131072} {set ::mapper $device;set ::base [expr {(([debug read ioports 255]^2)&([debug size $device]/16384-1))*16384}];break}}',
        ' if {[catch issue problem]} {puts stderr $problem;exit 2}',
        '}',
        'debug set_bp 0xd15f {$::active} {',
        ' set ::active 0;puts $::costs [expr {([machine_info time]-$::begin)*1000}]',
        ' if {[reg SP]!=0xf380 || [reg IX]!=0x4567 || [reg IY]!=0x6789 || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::page || [debug read_block memory 0xea00 1536] ne $::native || [debug read_block {PSG regs} 14 2] ne $::io} {puts stderr "Audio changed stack, indices, mapping, game code or PSG I/O";exit 2}',
        ' puts -nonewline $::result [debug read_block memory 0xe000 2560]',
        ' puts -nonewline $::result [debug read_block $::mapper [expr {$::base+0x3800}] 512]',
        ' binary scan [debug read_block $::mapper [expr {$::base+0x3a00}] 32] cu* values;foreach value $values {puts -nonewline $::result [binary format c [expr {$value&15}]]}',
        ' puts -nonewline $::result [debug read_block {PSG regs} 0 11]',
        ' incr ::index;if {[catch issue problem]} {puts stderr $problem;exit 2}',
        '}',
        'after time 180 {puts stderr "PSG proof timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, timeout=240,
            stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'result.bin').read_bytes(); stride = SAMPLE+11
    if len(actual) != count*2*stride:
        raise ValueError('Incomplete integrated PSG execution')
    curve = volume_curve()
    for case in range(count):
        state = expected[case*SAMPLE:(case+1)*SAMPLE]
        psg = bytearray(11)
        for ch, voice in enumerate(decode_voices(state[3072:])):
            if voice.step & 15:
                raise ValueError('Sequencer emitted an unaligned phase step')
            value = period(voice.step >> 4) if voice.volume else 0
            psg[ch*2:ch*2+2] = value.to_bytes(2, 'little')
            psg[8+ch] = curve[voice.volume] if value else 0
        psg[7] = 0xb8
        if seeds[case*SAMPLE+0x9f4] & 128:
            psg[6] = 13; psg[7] ^= 0x24; psg[10] = 14
        for mute in range(2):
            offset = (case*2+mute)*stride
            if actual[offset:offset+SAMPLE] != state:
                at = next(i for i,(a,b) in enumerate(zip(actual[offset:offset+SAMPLE],state)) if a!=b)
                raise ValueError(f'Integrated sequencer differs: case {case+1}, mute {mute}, byte {at}')
            desired = psg.copy()
            if mute: desired[8:11] = bytes(3)
            if actual[offset+SAMPLE:offset+stride] != desired:
                raise ValueError(f'PSG differs: case {case+1}, mute {mute}: {actual[offset+SAMPLE:offset+stride].hex()} != {desired.hex()}')
    costs = [float(line) for line in (out/'costs.tsv').read_text().splitlines()]
    verify_manifest(rom.parent); verify_manifest(ref)
    json_write(out/'report.json', dict(rom_sha256=digest(rom), cases=count*2, passed=True,
        maximum_call_ms=max(costs), mean_call_ms=sum(costs)/len(costs),
        scope='Executed reference-kernel mapper/sequencer/PSG conversion, every captured original call with output on and muted. '
              'Exact native/state/WSG agreement, independently calculated PSG periods/volumes/noise and preserved MSX I/O directions; '
              'stack, indices, mapping, presentation/native smoke code, VRAM and PSG I/O latches preserved. '
              'Display/IRQs disabled at locked 3.58 MHz; production two-voice/noise scheduling, natural IRQ and loaded cadence are separate gates.'))
    require_ignored(root, [f for f in out.rglob('*') if f.is_file()]); seal(out)
    print(f'{count*2} integrated PSG/mute cases pass: {out}/report.json')


if __name__ == '__main__':
    main()
