#!/usr/bin/env python3
"""Require exact viewport forecasts to finish without unfilled margin jobs."""
import argparse
import itertools
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];rom=args.rom.resolve()
    verify_manifest(rom.parent);s=symbols(rom.parent/'raster-scroll.sym')
    out=destination(root,args.output);require_ignored(root,[out/'owners.bin']);out.mkdir(parents=True)
    cases=list(itertools.product((-8,0,1,30,31,32,63,64),(-6,0,1,30,31,32,63,90),range(4),(0,7),(0,1,2),(0,1)))
    owners=bytearray();expected=[]
    for x,y,direction,fine,missing,stale in cases:
        vertical=direction<2;sign=-1 if direction in (0,2) else 1
        edges=([y-4+i for i in range(4)] if sign<0 else [y+26+i for i in range(4)]) if vertical else (
            [x-3+i for i in range(3)] if sign<0 else [x+32+i for i in range(3)])
        cells=([(xx,yy) for yy in edges for xx in range(x,x+32)] if vertical else
               [(xx,yy) for xx in edges for yy in range(y,y+26)])
        image=bytearray([128])*4096
        for xx,yy in cells:
            at=(yy%32)*128+(xx%64)*2;image[at:at+2]=bytes((xx&255,yy&255))
        edge=edges[0] if sign<0 else edges[-1]
        if missing:
            missing_edges=([edges[-1],edges[0]] if sign<0 else [edges[0],edges[-1]]) if missing==2 else [edge]
            edge=missing_edges[0]
            for lost in missing_edges:
                xx,yy=(x,lost) if vertical else (lost,y)
                image[(yy%32)*128+(xx%64)*2]=128
        owners.extend(image)
        expected.append((32 if vertical and missing else 0,26 if not vertical and missing else 0,int(bool(missing)),edge&255 if missing else -1))
    (out/'owners.bin').write_bytes(owners)
    entry=s['Full_StageQueue']
    fields=[(s['world_x'],2),(s['world_y'],2),(s['Full_DirX'],1),(s['Full_DirY'],1)]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set throttle off',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',
        f'cart {tcl(rom)} -romtype ASCII16','reset',f'set out {tcl(out)};set started 0;set index 0',
        'set cases {'+' '.join('{'+ ' '.join(map(str,c))+'}' for c in cases)+'}',
        'set f [open [file join $out owners.bin] rb];set owners [read $f];close $f',
        'set result [open [file join $out result.tsv] w]',
        'proc word {at value} {debug write memory $at [expr {$value&255}];debug write memory [expr {$at+1}] [expr {($value>>8)&255}]}',
        'proc issue {} {',
        ' if {$::index==[llength $::cases]} {close $::result;exit 0;return}',
        ' lassign [lindex $::cases $::index] x y direction fine missing stale',
        ' set vertical [expr {$direction<2}];set sign [expr {$direction==0 || $direction==2?-1:1}]',
        ' debug write_block $::mapper $::owner_at [string range $::owners [expr {$::index*4096}] [expr {$::index*4096+4095}]]',
        f' word {s["world_x"]} [expr {{$x*8+$fine}}];word {s["world_y"]} [expr {{$y*8+$fine}}]',
        f' foreach {{at value}} [list {s["previous_x"]} [expr {{($x-($stale && !$vertical?$sign:0))&255}}] {s["previous_y"]} [expr {{($y-($stale && $vertical?$sign:0))&255}}] {s["row_left"]} [expr {{$stale && !$vertical}}] {s["column_left"]} [expr {{$stale && $vertical}}] {s["row_x"]} [expr {{($x+35)&255}}] {s["row_y"]} [expr {{($y+30)&255}}] {s["column_x"]} [expr {{($x+35)&255}}] {s["column_y"]} [expr {{($y+30)&255}}] {s["Full_QueueDirty"]} 1 {s["Full_CameraBlocked"]} 0 {s["Session_PositionIRQ"]} 1 {s["Full_DirX"]} [expr {{$vertical?0:($sign&255)}}] {s["Full_DirY"]} [expr {{$vertical?($sign&255):0}}] 0xe06b [expr {{$vertical?0:255}}] 0xe06a [expr {{($vertical?-$sign:$sign)<0?255:0}}]] {{debug write memory $at $value}}',
        ' set ::native [debug read_block memory 0xe000 4096]',
        f' set at 0xd150;foreach value {{243 205 {entry&255} {entry>>8} 195 96 209}} {{debug write memory $at $value;incr at}}',
        ' reg IY 0x6789;reg SP 0xf380;reg PC 0xd150','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 2',
        ' set ::vram [debug read_block VRAM 0 131072];set ::primary [debug read ioports 168];set ::page [debug read ioports 252]',
        ' foreach device [debug list] {if {[debug desc $device] eq "memory mapper" && [debug size $device]>=131072} {',
        f'  set ::mapper $device;set ::owner_at [expr {{([debug read memory {s["Full_CacheSegment"]}]&([debug size $device]/16384-1))*16384+8192}}];break',
        ' }};if {[catch issue problem]} {puts stderr $problem;exit 2}','}',
        'debug set_bp 0xd160 {$::started} {',
        ' lassign [lindex $::cases $::index] x y direction fine missing stale;set vertical [expr {$direction<2}]',
        ' if {[reg SP]!=0xf380 || [reg IY]!=0x6789 || [debug read_block memory 0xe000 4096] ne $::native || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::page || [debug read_block VRAM 0 131072] ne $::vram} {puts stderr "Forecast changed preserved state";exit 2}',
        f' puts $::result "[debug read memory {s["row_left"]}] [debug read memory {s["column_left"]}] [debug read memory {s["Full_QueueDirty"]}] [expr {{$missing?($vertical?[debug read memory {s["row_y"]}]:[debug read memory {s["column_x"]}]):-1}}]"',
        ' incr ::index;if {[catch issue problem]} {puts stderr $problem;exit 2}','}',
        'after time 180 {puts stderr "Forecast probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=[tuple(map(int,l.split())) for l in (out/'result.tsv').read_text().splitlines()]
    if actual!=expected:
        i=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),min(len(actual),len(expected)))
        raise ValueError(f'Viewport forecast did not converge: {cases[i]}, got {actual[i]}, expected {expected[i]}')
    verify_manifest(rom.parent)
    json_write(out/'report.json',dict(rom_sha256=digest(rom),cases=len(cases),passed=True,
        scope='Exact 32-tile rows and 26-tile columns complete without nonexistent margin debt; removing a forecast tile creates work. Four directions, negative/world/physical seams, both fine offsets; VRAM/native RAM, stack, index and mapping preserved.'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} cache forecast convergence cases pass: {out}/report.json')


if __name__=='__main__':main()
