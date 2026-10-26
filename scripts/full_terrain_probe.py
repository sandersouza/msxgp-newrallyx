#!/usr/bin/env python3
"""Execute terrain ownership and contiguous cell fragments across buffer seams."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);s=symbols(bundle/'raster-scroll.sym')
    out=destination(root,args.output);require_ignored(root,[out/'result.bin']);out.mkdir(parents=True)
    cases=[];expected=bytearray()
    for y in (0,1,31,255):
        for x in range(256):
            for fault in range(65):
                tags=bytearray([128,0]*64)
                for n in range(32):
                    at=((x+n)&63)*2;tags[at:at+2]=bytes(((x+n)&255,y))
                if fault:
                    n=(fault-1)//2;at=((x+n)&63)*2+(fault-1)%2;tags[at]^=1
                cases.append(bytes((x,y))+tags)
                expected.append(int(bool(fault) or any((x+n)&255==128 for n in range(32))))
    (out/'cases.bin').write_bytes(b''.join(cases))
    fragments=[]
    if 'Full_CellClipSpan' in s:
        for start in range(256):
            for offset in range(3):
                # Independent partition: all original cell tiles in the same
                # physical 32-tile band as the requested tile.
                tiles=[start+n for n in range(3) if (start+n)//32==(start+offset)//32]
                fragments.append((start,(start+offset)&255))
                expected.extend((tiles[0]&255,len(tiles)*8))
    (out/'fragments.bin').write_bytes(bytes(v for pair in fragments for v in pair))
    entry=s['Full_CheckRow'];enter=s['Full_CacheEnter']
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set index 0;set started 0;set result [open [file join $out result.bin] wb]',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set f [open [file join $out fragments.bin] rb];binary scan [read $f] cu* fragments;close $f',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/130+[llength $::fragments]/2} {',
        '  if {[debug read_block memory 0xe000 4096] ne $::native || [debug read_block VRAM 0 131072] ne $::vram} {error "Row check changed native state or VRAM"}',
        '  close $::result;exit 0;return',' }',
        ' if {$::index>=[string length $::cases]/130} {',
        '  set at [expr {($::index-[string length $::cases]/130)*2}];reg AF [expr {[lindex $::fragments $at]*256}];reg BC [expr {[lindex $::fragments [expr {$at+1}]]*256}];reg IX 0x6789;reg IY 0x789a;reg SP 0xc7f0;reg PC 0xd170;return',' }',
        ' set base [expr {$::index*130}];binary scan [string range $::cases $base [expr {$base+1}]] cu* xy',
        ' lassign $xy x y;debug write_block memory [expr {0x2000+($y&31)*128}] [string range $::cases [expr {$base+2}] [expr {$base+129}]]',
        ' reg DE [expr {$y*256+$x}];reg IX 0x6789;reg IY 0x789a',
        ' reg SP 0xc7f0;reg PC 0xd150','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        'set ::started 1;set ::native [debug read_block memory 0xe000 4096];set ::vram [debug read_block VRAM 0 131072]',
        f'set at 0xd140;foreach value {{243 205 {enter&255} {enter>>8} 195 96 209}} {{debug write memory $at $value;incr at}}',
        f'set at 0xd150;foreach value {{243 205 {entry&255} {entry>>8} 195 96 209}} {{debug write memory $at $value;incr at}}',
        *([f'set at 0xd170;foreach value {{243 205 {s["Full_CellClipSpan"]&255} {s["Full_CellClipSpan"]>>8} 195 96 209}} {{debug write memory $at $value;incr at}}'] if fragments else []),
        'reg SP 0xc7f0;reg PC 0xd140','}',
        'debug set_bp 0xd160 {$::started} {',
        ' if {![info exists ::entered]} {set ::entered 1;issue} else {',
        '  if {[reg SP]!=0xc7f0 || [reg IX]!=0x6789 || [reg IY]!=0x789a} {error "Row check changed stack/index registers"}',
        '  if {$::index>=[string length $::cases]/130} {puts -nonewline $::result [binary format cc [reg A] [reg C]]} else {puts -nonewline $::result [binary format c [expr {[reg F]&1}]]};incr ::index;issue',' }','}',
        'after time 180 {puts stderr "Row proof timeout";exit 2}']
    # The first return enters the harness; subsequent returns are row results.
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,
                OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    if (out/'result.bin').read_bytes()!=expected:raise ValueError('Terrain ownership or cell fragment differs from its independent oracle')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),cell_fragment_cases=len(fragments),
        native_ram_unchanged=True,vram_unchanged=True,stack_and_index_registers_unchanged=True,
        scope='Every global X, both physical row halves, Y wrap, all 32 X/Y corruption positions and the invalid X sentinel. Cell fragments contain every contiguous original tile on the requested side of each physical seam.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'{len(cases)} terrain row and {len(fragments)} cell fragment cases pass: {out}/report.json')


if __name__=='__main__':main()
