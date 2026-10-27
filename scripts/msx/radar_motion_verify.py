"""Execute synthetic radar departure/queue cases with the actual full-game Z80."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .build import destination
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def cell_mask(point):
    x,y=point
    if x==255:return 0
    return sum(1<<cell for cell in range(12)
        if any(0<=px<48 and 0<=py<58 and cell%3*16<=px<cell%3*16+16 and
               cell//3*15+cell%3-2<=py<cell//3*15+cell%3+13
               for px in (x,x+1) for py in (y,y+1)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    out=destination(root,args.output);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym');cases=[];expected=[]
    points=[(x,y) for x in (0,1,2,14,15,16,17,30,31,32,33,46,47)
            for y in (0,1,2,11,12,13,14,15,16,27,28,29,30,31,42,43,44,45,56,57)]
    points.append((255,255))
    for old in points:
        targets=[old,(255,255)]
        targets+=([(2,2),(46,56)] if old[0]==255 else
                  [(old[0]+dx,old[1]+dy) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))
                   if 0<=old[0]+dx<48 and 0<=old[1]+dy<58])
        for new in targets:
            dirty,cleanup,ready,urgent=0x121,0x800,0xfff,2
            a,b=cell_mask(old),cell_mask(new)
            left=(a if a&b else a|b) if a!=b or (a|b).bit_count()>1 else 0
            cases.append(struct.pack('<4B4H',*old,*new,dirty,cleanup,ready,urgent))
            expected.append(struct.pack('<4H',dirty|a|b,cleanup|left,ready&~left,urgent&~left))
    departure_count=len(cases)
    last=bytes((255,255,4,4,15,14,16,15,31,29,32,30,45,55,2,2))
    for cell in range(12):
        for cleanup in (0,1<<cell,0xfff):
            bit=1<<cell;dirty,ready,urgent=0xfff,0x555,2
            cases.append(struct.pack('<4B4H',cell,0,0,0,dirty,cleanup,ready,urgent))
            expected.append(struct.pack('<4H',dirty&~bit,cleanup&~bit,ready|bit,urgent|(cleanup&bit))+
                            last+bytes((cell+20,)))
    (out/'cases.bin').write_bytes(b''.join(cases))
    setup=';'.join(f'debug write_block memory {syms[name]} [string range $c {4+i*2} {5+i*2}]'
                   for i,name in enumerate(('Radar_Dirty','Radar_Cleanup','Radar_Ready','Radar_Urgent')))
    results=';'.join(f'puts -nonewline $::actual [debug read_block memory {syms[name]} 2]'
                     for name in ('Radar_Dirty','Radar_Cleanup','Radar_Ready','Radar_Urgent'))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set cmdtiming real',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)}','set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set actual [open [file join $out actual.bin] wb];set index 0;set started 0',
        'proc issue {} {',
        f' if {{$::index=={len(cases)}}} {{close $::actual;exit 0;return}}',
        ' set c [string range $::cases [expr {$::index*12}] [expr {$::index*12+11}]]',
        ' binary scan $c cu* values',setup,
        f' debug write memory 0x7000 {syms["RADAR_CACHE_BANK"]}',
        f' if {{$::index<{departure_count}}} {{',
        f'  set target {syms["Full_RadarDeparture"]}',
        '  reg BC [expr {([lindex $values 0]<<8)|[lindex $values 1]}]',
        '  reg DE [expr {([lindex $values 2]<<8)|[lindex $values 3]}]',
        ' } else {',
        f'  set target {syms["Full_RadarCommit"]}',
        f'  debug write memory {syms["hud_cell"]} [lindex $values 0]',
        f'  debug write_block memory {syms["Radar_Last"]} [binary format c* {{{" ".join(map(str,last))}}}]',
        f'  debug write memory [expr {{{syms["Radar_WorkVisibility"]}+[lindex $values 0]}}] [expr {{20+[lindex $values 0]}}]',
        ' }',
        ' set p 0xd110;foreach byte [list 243 205 [expr {$target&255}] [expr {$target>>8}] 195 64 209] {debug write memory $p $byte;incr p}',
        ' reg IX 9029;reg IY 17767;reg SP 0xc7f0;reg PC 0xd110','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::vram [debug read_block VRAM 0 131072];set ::native [debug read_block memory 0xe000 4096];set ::mapping [debug read ioports 252];issue}}',
        'debug set_bp 0xd140 {$::started} {',
        ' if {[reg IX]!=9029 || [reg IY]!=17767 || [reg SP]!=0xc7f0} {error "Radar adapter changed stack/index registers"}',
        ' if {[debug read ioports 252]!=$::mapping} {error "Radar adapter leaked page0 mapping"}',
        ' if {[debug read_block VRAM 0 131072] ne $::vram || [debug read_block memory 0xe000 4096] ne $::native} {error "Radar adapter changed native state or VRAM"}',
        results,
        f' if {{$::index>={departure_count}}} {{',
        f'  set cell [debug read memory {syms["hud_cell"]}]',
        f'  puts -nonewline $::actual [debug read_block memory [expr {{{syms["Radar_StagedPoints"]}+$cell*16}}] 16]',
        f'  puts -nonewline $::actual [binary format c [debug read memory [expr {{{syms["Radar_StagedVisibility"]}+$cell}}]]]',
        ' }',' incr ::index;issue','}',
        'after time 120 {puts stderr "Radar motion component timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} error]} {puts stderr $error;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=120,
                       stdout=log,stderr=subprocess.STDOUT,
                       env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'actual.bin').read_bytes();wanted=b''.join(expected)
    if actual!=wanted:
        at=next((i for i,(a,b) in enumerate(zip(actual,wanted)) if a!=b),min(len(actual),len(wanted)))
        raise ValueError(f'Radar departure/commit differs at byte {at}')
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),departure_cases=departure_count,
        commit_cases=len(cases)-departure_count,native_and_vram_unchanged=True,stack_and_mapping_preserved=True))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} radar departure/commit cases pass: {out}/report.json')


if __name__=='__main__':main()
