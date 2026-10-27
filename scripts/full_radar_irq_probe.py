#!/usr/bin/env python3
"""Execute bounded radar publication independently of gameplay packets."""
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
    cases=[(0,c,cursor,mode,packet) for c,cursor,mode,packet in itertools.product(range(12),range(12),range(3),range(3))]
    cases.extend((1,c,7,2,0) for c in range(12))
    payloads=bytearray()
    for c in range(12):
        normal=bytes((c*17+i*7)&255 for i in range(32))
        shifted=b''.join(b'\0'+normal[at:at+15] for at in (0,16))
        payloads.extend(normal+shifted+bytes([0x26])*16)
    positions=bytes((i*13+9)&255 for i in range(192));visibility=bytes(i%4 for i in range(12))
    (out/'payloads.bin').write_bytes(payloads);(out/'positions.bin').write_bytes(positions)
    (out/'visibility.bin').write_bytes(visibility)
    entry=s['Full_PresentCommit'];begin=s['Full_RadarBegin']
    fields=[(s['Radar_PublishedPoints'],192),(s['Radar_BaseVisibility'],12),
            (s['Radar_Ready'],2),(s['Radar_Urgent'],2),(s['Radar_PublishCursor'],1),
            (s['hud_cell'],1),(s['Full_PresentLastTick'],2)]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set throttle off',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',
        'set z80_freq 3579545','set z80_freq_locked true',f'cart {tcl(rom)} -romtype ASCII16','reset',
        f'set out {tcl(out)};set started 0;set index 0',
        'set cases {'+' '.join('{'+ ' '.join(map(str,c))+'}' for c in cases)+'}',
        'foreach name {payloads positions visibility} {set f [open [file join $out "$name.bin"] rb];set data($name) [read $f];close $f}',
        'set result [open [file join $out result.bin] wb]',
        'proc word {at value} {debug write memory $at [expr {$value&255}];debug write memory [expr {$at+1}] [expr {$value>>8}]}',
        'proc issue {} {',
        ' if {$::index==[llength $::cases]} {close $::result;exit 0;return}',
        ' lassign [lindex $::cases $::index] op cell cursor mode packet;set ::op $op',
        ' set mask [expr {$mode==0?1<<$cell:4095}];set urgent [expr {$mode==2?1<<$cell:0}]',
        ' debug write_block VRAM 0x1f400 $::baseline',
        f' debug write_block memory {s["Radar_Payloads"]} $::data(payloads)',
        f' debug write_block memory {s["Radar_StagedPoints"]} $::data(positions)',
        f' debug write_block memory {s["Radar_StagedVisibility"]} $::data(visibility)',
        f' debug write_block memory {s["Radar_PublishedPoints"]} [string repeat [binary format c 255] 192]',
        f' debug write_block memory {s["Radar_BaseVisibility"]} [string repeat [binary format c 165] 12]',
        f' word {s["Radar_Ready"]} $mask;word {s["Radar_Urgent"]} $urgent',
        f' foreach {{at value}} [list {s["Radar_PublishCursor"]} $cursor {s["hud_cell"]} [expr {{$op?$cell:250}}] {s["Full_PresentReady"]} [expr {{$packet!=0}}] {s["Full_PresentClockValid"]} 0 {s["Full_PresentLastTick"]} 90 {s["Full_PresentLength"]} 1 {s["ticks"]} [expr {{$packet==2?1:0}}]] {{debug write memory $at $value}}',
        f' debug write_block $::mapper [expr {{$::base+{s["Full_PresentDirty"]}}}] [string repeat [binary format c 0] 7]',
        f' set entry [expr {{$op?{begin}:{entry}}}];set at 0xd150;foreach value [list 243 205 [expr {{$entry&255}}] [expr {{$entry>>8}}] 195 96 209] {{debug write memory $at $value;incr at}}',
        ' reg HL 0x1234;reg DE 0x2345;reg IX 0x4567;reg IY 0x6789;reg SP 0xf380;reg PC 0xd150','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 2',
        ' set ::native [debug read_block memory 0xe000 4096];set ::prefix [debug read_block VRAM 0 128000];set ::suffix [debug read_block VRAM 0x1fc00 1024]',
        ' set ::baseline [debug read_block VRAM 0x1f400 2048];set f [open [file join $::out baseline.bin] wb];puts -nonewline $f $::baseline;close $f',
        ' set ::primary [debug read ioports 168];set ::page [debug read ioports 252]',
        ' foreach device [debug list] {if {[debug desc $device] eq "memory mapper" && [debug size $device]>=131072} {',
        f'  set ::mapper $device;set ::base [expr {{([debug read memory {s["Full_CacheSegment"]}]&([debug size $device]/16384-1))*16384}}];break',
        ' }};if {[catch issue problem]} {puts stderr $problem;exit 2}','}',
        'debug set_bp 0xd160 {$::started} {',
        ' if {[reg SP]!=0xf380 || [reg IX]!=0x4567 || [reg IY]!=0x6789 || (!$::op && ([reg HL]!=0x1234 || [reg DE]!=0x2345)) || [debug read_block memory 0xe000 4096] ne $::native || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::page || [debug read_block VRAM 0 128000] ne $::prefix || [debug read_block VRAM 0x1fc00 1024] ne $::suffix} {puts stderr "Radar publication changed preserved state or VRAM canaries";exit 2}',
        ' puts -nonewline $::result [debug read_block VRAM 0x1f400 2048]',
        *[f' puts -nonewline $::result [debug read_block memory {at} {length}]' for at,length in fields],
        ' incr ::index;if {[catch issue problem]} {puts stderr $problem;exit 2}','}',
        'after time 180 {puts stderr "Radar IRQ probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'result.bin').read_bytes();size=2048+sum(n for _,n in fields);baseline=(out/'baseline.bin').read_bytes()
    if len(raw)!=len(cases)*size:raise ValueError('Incomplete radar IRQ evidence')
    for i,(op,c,cursor,mode,packet) in enumerate(cases):
        mask=(1<<c) if mode==0 else 4095;urgent=(1<<c) if mode==2 else 0
        vram=bytearray(baseline);points=bytearray([255])*192;shown=bytearray([165])*12
        if op:selected=c
        else:
            ready=mask&urgent or mask
            selected=next((cursor+offset)%12 for offset in range(12) if ready&(1<<((cursor+offset)%12)))
            source=payloads[selected*80:(selected+1)*80]
            for at,data in ((0x4a0+selected*32,source[:32]),(0x620+selected*32,source[32:64]),
                            (s['RADAR_MAP_SLOT']*16+selected*16,source[64:])):
                vram[at:at+len(data)]=data
            points[selected*16:(selected+1)*16]=positions[selected*16:(selected+1)*16]
            shown[selected]=visibility[selected];urgent&=~(1<<selected);cursor=(selected+1)%12
            if packet==2:vram[0x248]=216
        mask&=~(1<<selected)
        result=vram+points+shown+mask.to_bytes(2,'little')+urgent.to_bytes(2,'little')
        result+=bytes((cursor,c if op else 250,1 if packet==2 and not op else 90,int(packet==2 and not op)))
        if raw[i*size:(i+1)*size]!=result:raise ValueError(f'Radar IRQ byte/metadata mismatch: {cases[i]}')
    verify_manifest(rom.parent)
    json_write(out/'report.json',dict(rom_sha256=digest(rom),cases=len(cases),passed=True,
        scope='Executed one-cell publication: every cell/cursor, urgent/ordinary queues, no packet, even hold and odd commit; producer invalidation; complete VRAM and metadata canaries; native RAM, stack, indices and mapping preserved. Display/IRQs disabled at 3.58 MHz; gameplay independently qualifies physical VBlank timing.'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} radar IRQ publication cases pass: {out}/report.json')


if __name__=='__main__':main()
