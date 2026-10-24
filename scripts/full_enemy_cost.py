#!/usr/bin/env python3
"""Measure complete-car presentation scaling with controlled actor fixtures.

This isolates renderer cost; it does not replace natural gameplay/timing proofs.
The HUD and real VDP sprite/command limits remain enabled.
"""
import argparse
import os
from pathlib import Path
from statistics import median
import subprocess
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--iterations',type=int,default=200)
    p.add_argument('--profile',action='store_true')
    args=p.parse_args();root=Path(__file__).resolve().parents[1]
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    if args.iterations<100:raise ValueError('Use at least 100 samples per actor/motion group')
    if not read_json(bundle/'build.json')['hud_enabled']:raise ValueError('Renderer benchmark requires the complete HUD')
    out=destination(root,args.output);require_ignored(root,[out/'costs.tsv']);out.mkdir(parents=True)
    s=symbols(bundle/'raster-scroll.sym');entry=s['Full_EnemyFrame']
    code=bytes((243,205,entry&255,entry>>8,195,96,209))
    (out/'code.bin').write_bytes(code)
    flag=read_json(bundle/'player.json')['flags'][0]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        f'set iterations {args.iterations};set flag {flag};set started 0;set index 0',
        'set f [open [file join $out code.bin] rb];set code [read $f];close $f',
        'set costs [open [file join $out costs.tsv] w]']
    script=r'''
proc issue {} {
    if {$::index==14*$::iterations} {close $::costs;exit 0;return}
    set ::count [expr {($::index/$::iterations)%7+1}]
    set ::moving [expr {$::index/(7*$::iterations)}]
    set ::step [expr {$::moving?($::index%16):0}]
    foreach {at value} [list 0xc400 1 0xc472 1 0xc490 0 0xc5d0 0 0xe24e $::count \
        0xc405 128 0xc406 1 0xc407 212 0xc408 4 @SCROLL@ 0] {debug write memory $at $value}
    for {set i 0} {$i<7} {incr i} {
        set at [expr {0xe088+$i*32}]
        debug write memory [expr {$at+5}] 0
        debug write memory [expr {$at+7}] [expr {(-$::step)&255}]
        debug write memory [expr {$at+8}] [expr {12+$i}]
        debug write memory [expr {$at+10}] [expr {$i<$::count?50:100}]
        debug write memory [expr {$at+15}] $::flag
    }
    for {set i 0} {$i<5} {incr i} {
        set value [expr {$i<$::count?0xe093+$i*32:0}]
        debug write memory [expr {0xe004+$i*2}] [expr {$value&255}]
        debug write memory [expr {0xe005+$i*2}] [expr {$value>>8}]
    }
    set ::native [debug read_block memory 0xe000 4096]
    debug write_block memory 0xd150 $::code
    reg SP 0xf380;reg PC 0xd150
    set ::begin [machine_info time]
}
debug set_bp @MAIN@ {!$::started} {
    debug write memory 0xc7d0 0
    set ::started 1;set ::terrain [debug read_block VRAM 0 65536];issue
}
debug set_bp 0xd160 {$::started} {
    if {[reg SP]!=0xf380 || [debug read_block memory 0xe000 4096] ne $::native ||
        [debug read_block VRAM 0 65536] ne $::terrain} {puts stderr "Renderer fixture changed native state/terrain/stack";exit 2}
    puts $::costs "$::count $::moving [expr {round(([machine_info time]-$::begin)*3579545)}]"
    incr ::index;issue
}
set VDP.too_fast_vram_access_callback {puts stderr "Renderer benchmark VRAM timing violation";exit 2}
after time 180 {puts stderr "Renderer benchmark timeout";exit 2}
'''.replace('@MAIN@',str(s['main'])).replace('@SCROLL@',str(s['scroll_y']))
    if args.profile:
        lines.extend(['set profile [open [file join $out profile.tsv] w]',r'''
proc profile_enter {name} {
    set at [reg SP];set target [expr {[debug read memory $at]+256*[debug read memory [expr {$at+1}]]}]
    set ::profile_begin($name) [machine_info time]
    if {![info exists ::profile_return($name,$target)]} {
        set condition [format {[info exists ::profile_begin(%s)]} $name]
        set ::profile_return($name,$target) [debug set_bp $target $condition [list profile_exit $name]]
    }
}
proc profile_exit {name} {
    puts $::profile "$name $::count $::moving [expr {round(([machine_info time]-$::profile_begin($name))*3579545)}]"
    unset ::profile_begin($name)
}
'''])
        names=['Full_EnemySelect','Full_EnemyInactive','Full_EnemyLoad','Full_EnemySave',
            'FullEnemy_PrepareOne','FullEnemy_RadarOne','Sprite_Upload',
            'FullEnemy_DrawPrepared' if 'FullEnemy_DrawPrepared' in s else 'FullEnemy_DrawOne']
        for name in names:
            if name not in s:continue
            lines.append(f'debug set_bp {s[name]} {{$::started}} {{profile_enter {name}}}')
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=[list(map(int,line.split())) for line in (out/'costs.tsv').read_text().splitlines()]
    if len(rows)!=14*args.iterations:raise ValueError('Incomplete renderer cost samples')
    results=[]
    for moving in range(2):
        for count in range(1,8):
            values=sorted(cycles for actors,mode,cycles in rows if actors==count and mode==moving)
            results.append(dict(actors=count,moving=bool(moving),samples=len(values),
                minimum_cycles=min(values),median_cycles=median(values),p95_cycles=values[int(.95*len(values))]))
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cpu_hz=3579545,results=results,
        scope='Explicit one-to-seven actor renderer fixtures; up to five source virtual OAM entries, complete HUD and real sprite limits. Static/moving poses; no native state, terrain or stack changes. Costs include occasional real raster IRQs.'))
    require_ignored(root,[x for x in out.rglob('*') if x.is_file()]);seal(out)
    print(f'Controlled renderer scaling measured: {out}/report.json')


if __name__=='__main__':main()
