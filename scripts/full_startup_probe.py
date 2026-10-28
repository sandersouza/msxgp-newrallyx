#!/usr/bin/env python3
"""Verify normal startup pass-through and solid challenge cars through keys."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine, tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rom = args.rom.resolve()
    verify_manifest(rom.parent)
    syms=symbols(rom.parent/'raster-scroll.sym')
    out = destination(root, args.output)
    require_ignored(root, [out / 'report.json'])
    out.mkdir(parents=True)
    results = []
    for round_ in (1, 2, 3, 4, 5, 6, 7, 8):
        case = out / str(round_)
        case.mkdir()
        lines = ['set save_settings_on_exit false', 'set renderer none',
            'set sound_driver null', 'set throttle off', 'set cmdtiming real',
            'set limitsprites true',
            f'filepool add -path {tcl(root / "references/msxbios")} -types system_rom -position 1',
            reference_machine(root, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off',
            'activate_input_layer -blocking startup_probe',
            f'cart {tcl(rom)} -romtype ASCII16', 'reset',
            f'set out {tcl(case)};set target {round_ + 1};set solid {int(round_%4==3)};set phase boot;set age 0;set overlaps 0']
        script = r'''
proc signed {at} {set n [debug read memory $at];expr {$n<128?$n:$n-256}}
proc pose {at} {list [debug read memory [expr {$at+8}]] [debug read memory [expr {$at+10}]] [signed [expr {$at+5}]] [signed [expr {$at+7}]]}
proc approach {} {
    set ::selected -1
    for {set i 0} {$i<[debug read memory 0xe24e]} {incr i} {
        set at [expr {0xe088+32*$i}]
        if {[debug read memory [expr {$at+8}]]==15 && [debug read memory [expr {$at+10}]]==52} {set ::selected $at;break}
    }
    if {$::selected<0 || [debug read memory $::selected]<0x88} {error "No startup enemy in the initial downward lane"}
    set ::origin [pose $::selected];keymatrixdown 8 64;set ::phase drive;set ::age 0
}
proc step {} {
    incr ::age;set state [debug read memory 0xc7d0];set round [debug read memory 0xe1b0]
    switch $::phase {
        boot {if {$state==1 && [debug read memory 0xc7dd]} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}
        coin {if {$::age==4} {keymatrixup 0 32;set ::phase release;set ::age 0}}
        release {if {$::age==4} {keymatrixdown 0 2;set ::phase start;set ::age 0}}
        start {if {$::age==4} {keymatrixup 0 2};if {$state==0} {set ::phase next;set ::age 0}}
        next {if {$::age>=10} {
            if {$round==$::target} {approach} else {
                set ::wanted [expr {$round+1}];keymatrixdown 7 2;set ::phase skip
            }
        }}
        skip {if {$state==0 && $round==$::wanted} {keymatrixup 7 2;set ::phase next;set ::age 0}}
        drive {if {[debug read memory 0xc490]} {
            set pointer [expr {[debug read memory 0xc63c]+256*[debug read memory 0xc63d]}]
            if {!$::solid || $round!=$::target || [pose $::selected] ne $::origin || [debug read memory $::selected]<0x88 || ![debug read memory 0xc5d0] || $pointer!=$::selected+14} {error "Unexpected collision: round=$round enemy=[pose $::selected] origin=$::origin state=[debug read memory $::selected] contact=[debug read memory 0xc5d0] hit=$pointer"}
            set f [open [file join $::out result.txt] w]
            puts $f "solid [expr {($::selected-0xe088)/32}] [debug read memory $::selected] [pose $::selected]"
            close $f;exit 0
        } elseif {!$::solid} {
            lassign $::origin ex ey fx fy
            set dy [expr {24*([debug read memory 0xe072]-$ey)-[signed 0xe06f]+$fy}]
            if {[pose $::selected] ne $::origin || [debug read memory $::selected]<0x88} {error "Enemy activated before pass-through coverage"}
            if {$dy>14} {
                if {!$::overlaps || [debug read memory 0xc5d0]} {error "Missing actual overlap without collision"}
                set f [open [file join $::out result.txt] w]
                puts $f "pass-through $::overlaps $dy [pose $::selected]";close $f;exit 0
            }
        }}
    }
    after time 0.01 poll
}
proc poll {} {if {[catch step error]} {puts stderr $error;exit 2}}
set VDP.too_fast_vram_access_callback {puts stderr "Startup VDP timing violation";exit 2}
after time 120 {puts stderr "Startup collision timeout";exit 2}
after time 0.01 poll
'''
        script+=f'''\ndebug set_bp {syms['Enemy_AfterMoveDone']} {{[info exists ::selected] && $::phase eq "drive" && !$::solid}} {{
 lassign $::origin ex ey fx fy
 set dx [expr {{24*([debug read memory 0xe070]-$ex)+[signed 0xe06d]-$fx}}]
 set dy [expr {{24*([debug read memory 0xe072]-$ey)-[signed 0xe06f]+$fy}}]
 if {{abs($dx)<=10 && abs($dy)<=10}} {{
  incr ::overlaps
  if {{[debug read memory 0xc5d0]}} {{puts stderr "Normal startup contact was solid";exit 2}}
 }}
}}
'''
        (case / 'session.tcl').write_text('\n'.join(lines) + '\n' + script)
        with (case / 'emulator.log').open('w') as log:
            subprocess.run(['openmsx', '-script', str(case / 'session.tcl')],
                stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120,
                env=dict(os.environ, OPENMSX_HOME=str(case / 'home'),
                         OPENMSX_USER_DATA=str(case / 'userdata')))
        kind,*values=(case/'result.txt').read_text().split()
        expected='solid' if round_%4==3 else 'pass-through'
        if kind!=expected:raise ValueError('Unexpected startup contact result')
        results.append(dict(displayed_round=round_,behavior=kind,evidence=list(map(int,values))))
    json_write(out / 'report.json', dict(rom_sha256=digest(rom), cases=results,
        passed=True,normal_startup_pass_through=True,challenge_parked_contact=True,
        scope='Real credit/start/F5/down inputs on six normal and two challenge entries; no guest-state writes. Normal car remains parked while actual +/-10 overlap and complete crossing occur without contact; challenge collides before enemy motion. Separate from synthetic boundary contracts.'))
    require_ignored(root, [p for p in out.rglob('*') if p.is_file()])
    seal(out)
    print(f'Six normal pass-through and two challenge contact entries pass: {out}/report.json')


if __name__ == '__main__':
    main()
