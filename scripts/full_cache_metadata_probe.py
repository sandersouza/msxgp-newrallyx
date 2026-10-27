#!/usr/bin/env python3
"""Check terrain ownership and overwritten smoke tags against array oracles."""
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
    out=destination(root,args.output);require_ignored(root,[out/'result.bin']);out.mkdir(parents=True)
    cases=[(x,y,w,h,mode) for x,y,w,h,mode in itertools.product(
        (0,29,30,31,32,61,62,63,64,99),(0,29,30,31,32,63,64,171),(1,2,3,6,9,15,24,30),(1,2,3),range(3))
        if x%32+w<=32 and y%32+h<=32]
    seeds=[bytes((1+(x+3*y)%9 if mode==1 or mode==2 and (5*x+7*y)%11<3 else 0)
                 for y in range(32) for x in range(64)) for mode in range(3)]
    (out/'seeds.bin').write_bytes(b''.join(seed+bytes(sum(bool(v) for v in seed[y*64:(y+1)*64])
        for y in range(32)) for seed in seeds))
    entry=s['Full_CacheCommand'];command=s['stage_command']
    code=bytes((243,205,entry&255,entry>>8,195,96,209))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set throttle off',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',
        'set z80_freq 3579545','set z80_freq_locked false',f'cart {tcl(rom)} -romtype ASCII16','reset',
        f'set out {tcl(out)};set started 0;set index 0',
        'set cases {'+' '.join('{'+ ' '.join(map(str,c))+'}' for c in cases)+'}',
        'set f [open [file join $out seeds.bin] rb];set seeds [read $f];close $f',
        'set result [open [file join $out result.bin] wb]',
        'proc issue {} {',
        ' if {$::index==[llength $::cases]} {close $::result;exit 0;return}',
        ' lassign [lindex $::cases $::index] x y w h mode',
        f' debug write_block memory {s["Smoke_Display"]} [string range $::seeds [expr {{$mode*2080}}] [expr {{$mode*2080+2047}}]]',
        f' debug write_block memory {s["Smoke_DisplayRows"]} [string range $::seeds [expr {{$mode*2080+2048}}] [expr {{$mode*2080+2079}}]]',
        ' debug write_block $::mapper $::owner_at [string repeat [binary format c 128] 4096]',
        f' foreach {{at value}} [list {s["tile_x"]} $x {s["tile_y"]} $y {command+8} [expr {{$w*8}}] {command+9} 0 {command+10} [expr {{$h*8}}] {command+11} 0] {{debug write memory $at $value}}',
        f' debug write_block memory 0xd150 [binary format H* {code.hex()}]',
        ' reg IX 0x4567;reg IY 0x6789;reg SP 0xf380;reg PC 0xd150','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 66',
        ' set ::native [debug read_block memory 0xe000 4096];set ::vram [debug read_block VRAM 0 131072]',
        ' set ::primary [debug read ioports 168];set ::page [debug read ioports 252]',
        ' foreach device [debug list] {if {[debug desc $device] eq "memory mapper" && [debug size $device]>=131072} {',
        f'  set ::mapper $device;set ::owner_at [expr {{([debug read memory {s["Full_CacheSegment"]}]&([debug size $device]/16384-1))*16384+8192}}];break',
        ' }};if {[catch issue problem]} {puts stderr $problem;exit 2}','}',
        'debug set_bp 0xd160 {$::started} {',
        ' if {[reg SP]!=0xf380 || [reg IX]!=0x4567 || [reg IY]!=0x6789 || [debug read_block memory 0xe000 4096] ne $::native || [debug read_block VRAM 0 131072] ne $::vram || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::page} {puts stderr "Cache metadata changed preserved state";exit 2}',
        f' puts -nonewline $::result [debug read_block memory {s["Smoke_Display"]} 2080]',
        ' puts -nonewline $::result [debug read_block $::mapper $::owner_at 4096]',
        ' incr ::index;if {[catch issue problem]} {puts stderr $problem;exit 2}','}',
        'after time 180 {puts stderr "Cache metadata probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'result.bin').read_bytes();size=2080+4096
    if len(raw)!=len(cases)*size:raise ValueError('Incomplete metadata evidence')
    for n,(x,y,w,h,mode) in enumerate(cases):
        smoke=bytearray(seeds[mode]);owners=bytearray([128])*4096
        for dy in range(h):
            for dx in range(w):
                smoke[((y+dy)%32)*64+(x+dx)%64]=0
                at=((y+dy)%32)*128+((x+dx)%64)*2
                owners[at:at+2]=bytes((x+dx,y+dy))
        counts=bytes(sum(bool(v) for v in smoke[row*64:(row+1)*64]) for row in range(32))
        if raw[n*size:(n+1)*size]!=smoke+counts+owners:
            raise ValueError(f'Terrain ownership/smoke metadata mismatch: {cases[n]}')
    verify_manifest(rom.parent)
    json_write(out/'report.json',dict(rom_sha256=digest(rom),cases=len(cases),passed=True,
        scope='Executed metadata writer: empty/full/sparse smoke rows, physical seams and independent full-array canaries. Native RAM, VRAM, stack, index registers and mapper preserved. This component does not issue VDP copies.'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} cache ownership/smoke metadata cases pass: {out}/report.json')


if __name__=='__main__':main()
