#!/usr/bin/env python3
"""Execute all seven complete-car caches over facings and clipping boundaries."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.enemy_presentation_verify import cases_for
from scripts.msx.raster_scroll import sprite_pattern
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    flags=read_json(bundle/'player.json')['flags']
    cases=[(actor,*case) for actor in range(7) for case in cases_for(flags)]
    (out/'cases.bin').write_bytes(b''.join(bytes((actor,f))+x.to_bytes(2,'little',signed=True)+
        y.to_bytes(2,'little',signed=True)+bytes((scroll,registered,dead,contact))
        for actor,f,x,y,scroll,registered,dead,contact in cases))
    syms=symbols(bundle/'raster-scroll.sym')
    entry=syms['Full_EnemyFrame']
    code=bytes((243,205,entry&255,entry>>8,0,0,0,195,96,209))
    (out/'code.bin').write_bytes(code)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach n {cases code} {set f [open [file join $out "$n.bin"] rb];set data($n) [read $f];close $f}',
        'set index 0;set started 0;set sentinel 0;set result [open [file join $out result.bin] wb]']
    script=r'''
proc issue {} {
    if {$::index==[string length $::data(cases)]/10} {
        if {[debug read_block VRAM 0 65536] ne $::scene} {error "Enemy presentation changed terrain"}
        set f [open [file join $::out radar-mask.bin] wb]
        puts -nonewline $f [debug read_block VRAM @RADARMASK@ 64];close $f
        close $::result;exit 0;return
    }
    binary scan [string range $::data(cases) [expr {$::index*10}] [expr {$::index*10+9}]] cu* c
    lassign $c actor flag xl xh yl yh scroll registered dead contact
    set x [expr {$xl+256*$xh}];if {$x>32767} {incr x -65536}
    set y [expr {$yl+256*$yh}];if {$y>32767} {incr y -65536}
    set wx [expr {384+$x-124}];set wy [expr {1236+$y-108}]
    set cx [expr {($wx-36+12)/24}];set cy [expr {($wy-36+12)/24}]
    for {set i 0} {$i<7} {incr i} {debug write memory [expr {0xe092+$i*32}] 100}
    set p [expr {0xe088+$actor*32}];set ::slot [expr {18+$actor*2}]
    foreach {at v} [list 0xc400 1 0xc472 1 0xe24e 7 0xc405 128 0xc406 1 0xc407 212 0xc408 4 @SCROLL@ $scroll \
        [expr {$p+8}] $cx [expr {$p+10}] $cy [expr {$p+5}] [expr {($wx-36-24*$cx)&255}] \
        [expr {$p+7}] [expr {(-($wy-36-24*$cy))&255}] [expr {$p+15}] $flag 0xc490 $dead 0xc5d0 $contact \
        0xc63c [expr {($p+14)&255}] 0xc63d [expr {($p+14)>>8}]] {debug write memory $at $v}
    for {set a 0xe004} {$a<0xe00e} {incr a} {debug write memory $a 0}
    if {$registered} {debug write memory 0xe00c [expr {($p+11)&255}];debug write memory 0xe00d [expr {($p+11)>>8}]}
    debug write_block memory 0xd150 $::data(code)
    reg SP 0xf380;reg PC 0xd150
}
debug set_bp @MAIN@ {!$::started} {
    set ::started 1;set ::scene [debug read_block VRAM 0 65536]
    foreach {at value} {0xc400 1 0xc472 1 0xe24e 7 0xc405 128 0xc406 1 0xc407 212 0xc408 4 @SCROLL@ 0 0xc490 0 0xc5d0 0} {
        debug write memory $at $value
    }
    for {set i 0} {$i<7} {incr i} {debug write memory [expr {0xe092+$i*32}] 100}
    foreach i {0 2} {
        set p [expr {0xe088+$i*32}]
        foreach offset {5 7} value {12 0} {debug write memory [expr {$p+$offset}] $value}
        debug write memory [expr {$p+8}] 14;debug write memory [expr {$p+10}] 50
        debug write memory [expr {$p+15}] @FLAG@
    }
    for {set at 0xe004} {$at<0xe00e} {incr at} {debug write memory $at 0}
    foreach {at value} {0xe004 147 0xe005 224 0xe006 211 0xe007 224} {debug write memory $at $value}
    set ::sentinel 1;debug write_block memory 0xd150 $::data(code)
    reg SP 0xf380;reg PC 0xd150
}
debug set_bp 0xd160 {$::started} {
    if {$::sentinel==1} {
        debug write memory 0xe092 100
        set ::sentinel 2;reg PC 0xd150
    } elseif {$::sentinel==2} {
        for {set i 0} {$i<24} {incr i} {
            if {[debug read VRAM [expr {0x1f600+$i*4}]]==216} {error "A newly hidden car terminated SAT before a later visible car"}
        }
        if {![debug read memory 0xce60]} {error "SAT regression fixture lacks its later visible car"}
        set ::sentinel 0;issue
    } else {
    if {[reg SP]!=0xf380} {error "Enemy presentation damaged stack"}
    binary scan [string index $::data(cases) [expr {$::index*10}]] cu actor
    puts -nonewline $::result [debug read_block memory [expr {0xce20+$actor*32}] 32]
    set sat [expr {0x1f600+$::slot*4}]
    puts -nonewline $::result [debug read_block VRAM $sat 8]
    puts -nonewline $::result [debug read_block VRAM [expr {0x1f400+$::slot*16}] 32]
    foreach offset {2 6} {
        set pattern [debug read VRAM [expr {$sat+$offset}]]
        puts -nonewline $::result [debug read_block VRAM [expr {0x1f800+($pattern&252)*8}] 32]
    }
    for {set i 0} {$i<32} {incr i} {
        puts -nonewline $::result [binary format c [debug read VRAM [expr {0x1f600+$i*4}]]]
    }
    incr ::index;issue
    }
}
set VDP.too_fast_vram_access_callback {puts stderr "Full enemy VRAM timing violation";exit 2}
after time 600 {puts stderr "Full enemy presentation timeout";exit 2}
'''.replace('@MAIN@',str(syms['main'])).replace('@SCROLL@',str(syms['scroll_y'])).replace('@FLAG@',str(flags[0])).replace('@RADARMASK@',str(0x1f800+syms['RADAR_PLAYER_PATTERN']*8))
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'result.bin').read_bytes();size=168
    dot=bytes(int(x<2 and y<2) for y in range(16) for x in range(16))
    if (out/'radar-mask.bin').read_bytes()!=b''.join(sprite_pattern(dot,shift) for shift in (0,1)):
        raise ValueError('Complete-car caches overwrote the independent player radar masks')
    if len(raw)!=len(cases)*size:raise ValueError('Incomplete full enemy evidence')
    pixels=(bundle/'player-pixels.bin').read_bytes();visible=0
    for n,(actor,flag,x,y,scroll,registered,dead,contact) in enumerate(cases):
        data=raw[n*size:(n+1)*size];record,sat,colors,masks=data[:32],data[32:40],data[40:72],data[72:136]
        expected=bool(registered and not(dead and contact) and -7<=x<=255 and -4<=y<=211)
        if bool(record[0])!=expected:raise ValueError(f'Actor {actor} visibility mismatch in case {n}')
        if not expected:
            hidden=(scroll+211)&255;hidden+=int(hidden==216)
            if sat[0]!=hidden or sat[4]!=hidden:raise ValueError(f'Hidden actor remained visible: {n}')
            continue
        visible+=1;bias=int((scroll+y-1)&255==216)
        if 216 in data[136:136+18+actor*2+2]:
            raise ValueError(f'Early SAT terminator hides actor {actor}: {n}')
        ec=128 if x<0 else 0;ay=(scroll+y-1-bias)&255;ax=x+(32 if ec else 0)
        if sat[:2]!=bytes((ay,ax)) or sat[4:6]!=bytes((ay,ax)):raise ValueError(f'Actor SAT mismatch: {n}')
        if colors!=bytes([6|32|ec])*16+bytes([10|96|ec])*16:raise ValueError(f'Actor OR colors mismatch: {n}')
        car=pixels[flags.index(flag)*256:][:256]
        expected_masks=bytes(sum(int(car[py*16+px+bit] in plane and x+px+bit>=8 and py+y-bias!=11)<<(7-bit)
            for bit in range(8)) for plane in ((3,11),(9,11)) for px in (0,8) for py in range(16))
        if masks!=expected_masks:raise ValueError(f'Actor {actor} complete source masks differ: {n}')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),visible=visible,actors=7,
        scope='Explicit presentation fixtures: all original facings, source-pointer pages, cache eviction, clipping, OR colors, SAT positions/traversal and independent radar masks. Hardware culling remains enabled; scanout requires separate checks.'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} seven-car presentation cases pass: {out}/report.json')


if __name__=='__main__':main()
