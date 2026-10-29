"""Exact SCREEN4 display-on packet transfer and inclusive elapsed-cycle probe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def verify(bios, out):
    sys.path.insert(0, str(ROOT))
    from scripts.msx.emulator import reference_machine, tcl
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    helper = (HERE/'game-packet-fast.inc').read_bytes()
    (out/'game-packet-fast.inc').write_bytes(helper)
    source = ''' OUTPUT "probe.rom"
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
     call $0138
     rrca
     rrca
     and 3
     ld c,a
     ld b,0
     ld hl,$fcc1
     add hl,bc
     ld a,(hl)
     and $80
     or c
     ld c,a
     ld de,4
     add hl,de
     ld a,(hl)
     and $0c
     or c
     ld h,$80
     call $0024
     ld a,4
     call $005f
     di
     reg 0,4
     reg 1,$42
     reg 8,$28
     reg 9,$80
main:
     jp main
Baseline_Transfer:
     nop
     otir
     ret
     INCLUDE "game-packet-fast.inc"
     ASSERT $ < $8000
     defs $8000-$,$ff
'''
    (out/'probe.asm').write_text(source)
    assembled = subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', '--sym=probe.sym', 'probe.asm'], cwd=out, capture_output=True, text=True)
    assert assembled.returncode == 0, assembled.stdout+assembled.stderr
    syms = {n: int(v, 16) for n, v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)', (out/'probe.sym').read_text())}
    cases = [(back, length, 0) for back in range(2) for length in range(1, 256)]
    # Actual VDP interrupts are enabled for chained, mixed-size packets.
    cases += [(back, 725, 1) for back in range(2)]
    seed = bytes((i*73+19) & 255 for i in range(1024))
    (out/'seed.bin').write_bytes(seed)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(out/"probe.rom")} -romtype Normal', 'reset', f'set out {tcl(out)}',
             'set f [open [file join $out seed.bin] rb];set seed [read $f];close $f',
             'set timing [open [file join $out cycles.txt] w]',
             'set index 0;set stage 0;set started 0;set fast 0;set irq_count 0',
             'set poison [binary format c* [lrepeat 131072 238]]',
             'set VDP.too_fast_vram_access_callback {if {$::started} {incr ::fast}}',
             'set cases {'+' '.join('{'+f'{back} {length} {irq}'+'}' for back, length, irq in cases)+'}',
             'proc issue {} {',
             f' if {{$::index=={len(cases)}}} {{close $::timing;set f [open [file join $::out strict.txt] w];puts $f $::fast;close $f;set f [open [file join $::out irq-count.txt] w];puts $f $::irq_count;close $f;exit 0;return}}',
             ' lassign [lindex $::cases $::index] back length irq',
             ' debug write {VDP regs} 1 [expr {$irq?98:66}]',
             ' debug write_block VRAM 0 $::poison;debug write_block memory 0xe000 $::seed',
             # Both pattern/color destinations, 14-bit page crossing and
             # two inactive VRAM tables occur among all lengths.
             ' set target [expr {($length&1)?0x3ff0:0x4200}];set page [expr {($target>>14)+$back*2}]',
             f' set routine [expr {{$::stage?{syms["GamePacketFast_Transfer"]}:{syms["Baseline_Transfer"]}}}]',
             ' set code [list 243 62 $page 211 153 62 142 211 153 62 [expr {$target&255}] 211 153 62 [expr {(($target>>8)&63)|64}] 211 153 33 0 224]',
             ' if {$irq} {lappend code 17 254 202 251;foreach n {2 7 16 31 32 63 64 127 128 255} {lappend code 1 152 $n 205 [expr {$routine&255}] [expr {$routine>>8}]}} else {lappend code 1 152 $length 17 254 202 251 205 [expr {$routine&255}] [expr {$routine>>8}] 0}',
             ' lappend code 195 112 209',
             ' set p 0xd110;foreach v $code {debug write memory $p $v;incr p}',
             ' set p 0xd170;foreach v {0 243 195 128 209} {debug write memory $p $v;incr p}',
             ' reg SP 0xf380;reg PC 0xd110', '}',
             f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
             f'debug set_bp {syms["Baseline_Transfer"]} {{$::started}} {{set ::begin [machine_info time]}}',
             f'debug set_bp {syms["GamePacketFast_Transfer"]} {{$::started}} {{set ::begin [machine_info time]}}',
             'debug set_bp 56 {$::started} {incr ::irq_count}',
             'debug set_bp 0xd12e {$::started} {set ::cycles [expr {round(([machine_info time]-$::begin)*3579545)}]}',
             'debug set_bp 0xd170 {$::started} {if {!([reg IFF]&1)} {puts stderr "Interrupt state changed case=$::index";exit 3}}',
             'debug set_bp 0xd180 {$::started} {',
             ' lassign [lindex $::cases $::index] back length irq',
             ' set bc [reg BC];set hl [reg HL];set de [reg DE]',
             ' if {$bc!=152 || $hl!=0xe000+$length || $de!=0xcafe} {puts stderr "Register contract case=$::index BC=$bc HL=$hl DE=$de";exit 3}',
             ' set actual [debug read_block VRAM 0 131072]',
             ' set target [expr {($length&1)?0x3ff0:0x4200}];set at [expr {$target+$back*32768}]',
             ' set expected $::poison;set expected [string replace $expected $at [expr {$at+$length-1}] [string range $::seed 0 [expr {$length-1}]]]',
             ' if {$actual ne $expected} {puts stderr "Exact VRAM mismatch case=$::index stage=$::stage length=$length";exit 3}',
             ' if {!$::stage} {set ::old_cycles $::cycles;set ::stage 1;issue} else {puts $::timing "$back $length $::old_cycles $::cycles";if {$irq && !$::irq_count} {puts stderr "VDP IRQ never exercised";exit 3};incr ::index;set ::stage 0;issue}', '}',
             'after time 120 {puts stderr "Packet fast probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, stdout=log, stderr=subprocess.STDOUT,
                       timeout=150, env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    callbacks = int((out/'strict.txt').read_text())
    assert callbacks == 0, f'Strict VRAM callbacks: {callbacks}'
    irq_count = int((out/'irq-count.txt').read_text())
    assert irq_count > 0, 'No VDP interrupt exercised'
    rows = [[int(v) for v in line.split()] for line in (out/'cycles.txt').read_text().splitlines()]
    assert len(rows) == len(cases)
    report = dict(complete=True, cases=len(cases), lengths='1..255', back_buffers=2,
                  strict_vram_callbacks=callbacks, cpu_hz=3579545, video_hz_nominal=60,
                  vdp_interrupts_exercised=irq_count,
                  machine='Panasonic_FS-A1WSX_NR128', hardware_sprite_limits=True,
                  helper_bytes=syms['GamePacketFast_End']-syms['GamePacketFast_Transfer'],
                  helper_sha256=hashlib.sha256(helper).hexdigest(), rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(),
                  cycles={str(n): dict(baseline=sum(r[2] for r in rows if r[1]==n)/2-5,
                                      candidate=sum(r[3] for r in rows if r[1]==n)/2) for n in range(1, 256)},
                  scope='Inclusive transfer entry-to-return elapsed cycles including wait states. SCREEN4 display on, CPU interrupts enabled, VDP interrupt generation disabled for isolated timing and enabled for mixed-size chained packet cases. Every case compares all128KiB VRAM, final BC/HL/DE and preserved IFF, both R14 table sets and14-bit destination rollover. No mapper changes or integrated gameplay claim.')
    (out/'native-result.json').write_text(json.dumps(report, indent=2)+'\n')
    # This fails against the original OTIR worker, proving the intended saving.
    for length in (64, 128, 255):
        row = report['cycles'][str(length)]
        assert row['candidate']+29 < row['baseline'], f'No net inline replacement saving at length{length}: {row}'
    print(json.dumps({key: value for key, value in report.items() if key != 'cycles'}, indent=2))
    print({n: report['cycles'][str(n)] for n in (1, 8, 16, 32, 64, 128, 255)})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bios', required=True)
    parser.add_argument('--out', type=Path, default=ROOT/'outputs/fixed-hud/packet-fast-synthetic')
    args = parser.parse_args()
    verify(args.bios, args.out)
