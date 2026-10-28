#!/usr/bin/env python3
"""Execute bounded camera initialization and atomic car publication on the Z80."""
import argparse
import itertools
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.display import VIEWPORT_WIDTH, VIEWPORT_HALF
from scripts.msx.emulator import reference_machine, tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.stage_one import WIDTH, HEIGHT
from scripts.scenes.bundle import digest, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1]
    rom=args.rom.resolve();verify_manifest(rom.parent)
    s=symbols(rom.parent/'raster-scroll.sym')
    out=destination(root,args.output);require_ignored(root,[out/'result.tsv']);out.mkdir(parents=True)
    cases=list(itertools.product((24,36,123,124,125,300,691,692,693,780,792),
                                 (24,36,104,105,106,600,1295,1296,1297,1356,1368), (0,109,255)))
    def call(name):return [205,s[name]&255,s[name]>>8]
    code=[243,*call('Full_CacheEnter'),*call('Full_InitializeCamera')]
    checkpoint=0xd140+len(code)
    code += [*call('Full_CommitCamera'),58,s['irq_scroll_y']&255,s['irq_scroll_y']>>8,
             *call('Player_Draw.sat_value'),*call('Full_CacheLeave'),243,195,63,209]
    if len(code)>24:raise ValueError('Camera probe trampoline overlaps player projection state')
    fields=('world_x','world_y','player_x','player_y','Full_CameraCentreX','Full_CameraCentreY')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set throttle off',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',
        f'cart {tcl(rom)} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set started 0;set index 0',
        'set cases {'+' '.join('{'+ ' '.join(map(str,c))+'}' for c in cases)+'}',
        'set result [open [file join $out result.tsv] w]',
        'proc word {at value} {debug write memory $at [expr {$value&255}];debug write memory [expr {$at+1}] [expr {($value>>8)&255}]}',
        'proc u16 {at} {expr {[debug read memory $at]+256*[debug read memory [expr {$at+1}]]}}',
        'proc issue {} {',
        ' if {$::index==[llength $::cases]} {close $::result;exit 0;return}',
        ' lassign [lindex $::cases $::index] x y scroll',
        f' word {s["player_pending_x"]} $x;word {s["player_pending_y"]} $y',
        f' word {s["Full_PresentNextX"]} 4660;debug write memory {s["Full_PresentNextY"]} $scroll',
        f' debug write memory {s["Full_CacheHeld"]} 0',
        ' set ::native [debug read_block memory 0xe000 4096]',
        ' set at 0xd140;foreach value {'+' '.join(map(str,code))+'} {debug write memory $at $value;incr at}',
        ' reg SP 0xf380;reg IX 0x4567;reg IY 0x6789;reg PC 0xd140',
        '}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 2',
        ' set ::vram [debug read_block VRAM 0 131072];set ::primary [debug read ioports 168];set ::page [debug read ioports 252]',
        ' if {[catch issue problem]} {puts stderr $problem;exit 2}',
        '}',
        f'debug set_bp {checkpoint} {{$::started}} {{',
        f' set ::initial_pose [debug read_block memory {s["Full_PlayerActivePose"]} 2]',
        f' debug write memory {s["Full_PlayerPose"]} 11;debug write memory {s["Full_PlayerPose"]+1} 12',
        '}',
        'debug set_bp 0xd13f {$::started} {',
        ' set native [debug read_block memory 0xe000 4096]',
        ' set native [string replace $native 1014 1015 [string range $::native 1014 1015]]',
        ' if {[reg SP]!=0xf380 || [reg IX]!=0x4567 || [reg IY]!=0x6789 || $native ne $::native || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::page || [debug read_block VRAM 0 131072] ne $::vram} {puts stderr "Camera changed preserved native/VRAM/mapping state";exit 2}',
        f' if {{[debug read_block memory {s["Full_PlayerActivePose"]} 2] ne $::initial_pose}} {{puts stderr "Camera committed an unsealed car pose";exit 2}}',
        ' puts $::result "'+' '.join(f'[u16 {s[n]}]' for n in fields)+
        f' [binary encode hex [debug read_block memory {s["player_sat"]} 8]] [u16 {s["Full_PresentActiveX"]}] [debug read memory {s["irq_scroll_y"]}]"',
        ' incr ::index;if {[catch issue problem]} {puts stderr $problem;exit 2}',
        '}',
        'after time 60 {puts stderr "Camera bounds probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=90,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=(out/'result.tsv').read_text().splitlines()
    if len(rows)!=len(cases):raise ValueError('Incomplete bounded camera cases')
    for case,row in zip(cases,rows):
        x,y,scroll=case
        wx=max(0,min(WIDTH-VIEWPORT_WIDTH,x-VIEWPORT_HALF));wy=max(0,min(HEIGHT-201,y-105))
        sy=(scroll+y-wy+2)&255
        if sy==216:sy-=1
        expected=[str(v) for v in (wx,wy,x,y,wx+VIEWPORT_HALF,wy+105)]
        expected += [bytes((sy,x-wx,180,0,sy,x-wx,184,0)).hex(),'4660',str(scroll)]
        if row.split()!=expected:raise ValueError(f'Camera/projection mismatch: {case}: {row}, expected {expected}')
    json_write(out/'report.json',dict(rom_sha256=digest(rom),passed=True,cases=len(cases),
        scope='Seeded Z80 camera initialization at all edges and centre thresholds; sealed car projection and scroll commit despite a different candidate; native RAM except camera workspace, VRAM, stack, IX/IY and mapping preserved. Gameplay and collisions require route qualification.'))
    seal(out);print(f'{len(cases)} bounded camera/publication cases pass: {out}/report.json')


if __name__=='__main__':main()
