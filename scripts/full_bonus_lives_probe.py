#!/usr/bin/env python3
"""Execute score crossings and require immediate native and HUD extra lives."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.score_verify import packet
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path.cwd();rom=args.rom.resolve();verify_manifest(rom.parent)
    s=symbols(rom.parent/'raster-scroll.sym');out=args.output.resolve()
    require_ignored(root,[out/'session.tcl']);out.mkdir(parents=True)
    cases=[(19900,1,0,4),(19900,2,0,4),(19900,2,2,3),
           (79900,1,2,4),(79900,2,2,4),(79900,2,10,3)]
    data=b''.join(bytes((ordinal,awards))+packet(value) for value,ordinal,awards,_ in cases)
    (out/'cases.bin').write_bytes(data)
    code=[243,62,s['PLAYER_BANK'],50,0,112,205,s['Score_Update']&255,s['Score_Update']>>8,195,63,209]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set throttle off',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',f'cart {tcl(rom)} -romtype ASCII16','reset',
        f'set out {tcl(out)};set nr_bonus_started 0;set nr_bonus_index 0',
        'set f [open [file join $out cases.bin] rb];set nr_bonus_cases [read $f];close $f',
        'set nr_bonus_results [open [file join $out result.tsv] w]',
        'proc nr_bonus_issue {} {',
        f' if {{$::nr_bonus_index=={len(cases)}}} {{close $::nr_bonus_results;exit 0;return}}',
        ' set at [expr {$::nr_bonus_index*10}];binary scan [string range $::nr_bonus_cases $at [expr {$at+9}]] cu* c;lassign $c ordinal awards',
        ' debug write_block memory 0xe000 $::nr_bonus_seed',
        ' debug write_block memory 0xe0a0 [string range $::nr_bonus_cases [expr {$at+2}] [expr {$at+9}]]',
        f' foreach {{at value}} [list 0xe020 1 0xe250 [expr {{$ordinal-1}}] 0xe271 [expr {{$ordinal-1}}] 0xe1b2 $awards 0xe00f 3 {s["Score_Seen"]} 0 {s["Flag_Count"]} $ordinal {s["Flag_Kind"]} 1 {s["lives"]} 2] {{debug write memory $at $value}}',
        ' set at 0xd100;foreach value {'+' '.join(map(str,code))+'} {debug write memory $at $value;incr at}',
        ' reg SP 0xf380;reg PC 0xd100',
        '}',
        f'debug set_bp {s["main"]} {{!$::nr_bonus_started}} {{set ::nr_bonus_started 1;debug write {{VDP regs}} 0 6;debug write {{VDP regs}} 1 2;set ::nr_bonus_seed [debug read_block memory 0xe000 4096];nr_bonus_issue}}',
        f'debug set_bp 0xd13f {{$::nr_bonus_started}} {{puts $::nr_bonus_results "[debug read memory 0xe00f] [debug read memory {s["lives"]}] [debug read memory 0xe1b2]";incr ::nr_bonus_index;nr_bonus_issue}}',
        'after time 90 {puts stderr "Bonus life probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=90,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=[list(map(int,l.split())) for l in (out/'result.tsv').read_text().splitlines()]
    for case,row in zip(cases,actual):
        expected=case[-1]
        if row[:2]!=[expected,expected-1]:raise ValueError(f'Extra life/HUD mismatch at {case}: native/HUD/award bits {row}')
    if len(actual)!=len(cases):raise ValueError('Incomplete bonus-life cases')
    json_write(out/'report.json',dict(rom_sha256=digest(rom),cases=len(cases),passed=True,
        scope='Seeded actual Z80 score awards at exact/crossed 20,000 and 80,000, duplicate suppression and immediate native/HUD life counts.'))
    seal(out);print(f'Bonus life thresholds and HUD pass: {out}/report.json')


if __name__=='__main__':main()
