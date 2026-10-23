"""Execute exact solid fills with synthetic queue and framebuffer canaries."""
import os
import subprocess
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    info=read_json(bundle/'build.json');syms=symbols(bundle/'raster-scroll.sym')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    if 'Stage_SolidTile' not in syms:raise ValueError('Solid-run experiment is not linked')
    out=destination(root,args.output);require_ignored(root,[out/'cache.bin']);out.mkdir(parents=True)
    cases=[]
    maximum_run=info.get('cache_solid_run_tiles',4)
    for color in range(16):
        for x in (0,1,30,31,32,63,64,100):
            for y in (0,31):
                for mode in range(10 if info.get('tile_strips') else 9):
                    # Seven queued tiles: homogeneous; next flag; death; queue wrap.
                    length=min(8,32-x%32,102-x)
                    if mode in (1,2,3):length=1
                    if mode==4:length=min(2,32-x%32,102-x)
                    if mode in (5,6):length=1
                    if mode==7:length=min(32,32-x%32,102-x)
                    if mode==8:length=min(2,32-x%32,102-x)
                    length=min(length,maximum_run)
                    cases.append((color,x,y,mode,length,1))
        for x in (0,31):
            for y in (0,1,30,31,32,63,64,172):
                for mode in range(10 if info.get('tile_strips') else 9):
                    length=min(8,32-y%32,174-y) if mode in (0,9) else 1
                    if mode==4:length=min(2,32-y%32,174-y)
                    if mode==7:length=min(32,32-y%32,174-y)
                    if mode==8:length=min(2,32-y%32,174-y)
                    length=min(length,maximum_run)
                    cases.append((color,x,y,mode,length,2))
    (out/'cases.bin').write_bytes(bytes(v for case in cases for v in case))
    call,wait=syms['Stage_SolidTile'],syms['stage_wait_command']
    code=[0xf3,0x21,0,0xe0,0x3e,0,0xcd,call&255,call>>8,0xcd,wait&255,wait>>8,0x76]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set cache [open [file join $out cache.bin] wb];set index 0;set started 0',
        f'set cache_columns {info["cache_columns"]}',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/6} {close $::cache;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*6}] [expr {$::index*6+5}]] cu* c;lassign $c color x y mode length axis;set ::axis $axis',
        ' debug write_block VRAM 0 [string repeat [binary format c 170] 65536]',
        ' set tag [expr {($color<<4)|2}];debug write_block memory 0xe000 [string repeat [binary format cc $tag 0] 4096]',
        ' if {$mode==9} {debug write memory [expr {$axis==1?0xe002:0xe100}] [expr {$tag|4}]}',
        ' if {$mode==1} {debug write memory [expr {$axis==1?0xe002:0xe100}] 1}',
        ' if {$mode==5} {debug write memory [expr {$axis==1?0xe002:0xe100}] [expr {$tag^16}]}',
        ' set ::queued [expr {$mode==6?0:($mode==7?31:7)}]',
        ' foreach {a v} [list 0xc400 1 0xc009 1 0xc49a [expr {$mode==2}] 0xc0bc $x 0xc0bd $y 0xc0b7 $::queued 0xc0b6 $::queued 0xc0bb [expr {$mode==3?$x+9:$x+1}] 0xc0b9 [expr {$mode==3?$y+9:$y+1}] 0xcf1a 0 0xcf1b [expr {$mode==4?$y+2:200}] 0xcf1c 0 0xcf1d [expr {$mode==4?$x+2:120}] 0xcf26 $axis 0xc46f [expr {$mode==8?($x+2-$::cache_columns)&255:$x}] 0xc470 [expr {$mode==8?($y-30)&255:$y}] 0xc605 $tag] {debug write memory $a $v}',
        ' reg SP 0xc7f0;reg PC 0xc600','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;',
        *[f'debug write memory {0xc600+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc60c {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read memory [expr {$::axis==1?0xc0b7:0xc0b6}]]!=$::queued+1-$length || [debug read memory 0xc468]!=8 || [debug read memory 0xc469]!=0 || [debug read memory 0xc46a]!=8 || [debug read memory 0xc46b]!=0 || [debug read memory 0xc46e]!=208} {error "Solid run queue/stack/command state invalid"}',
        ' puts -nonewline $::cache [debug read_block VRAM 0 65536];incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Solid fill VRAM timing violation";exit 2}',
        'after time 90 {puts stderr "Solid fill timeout";exit 2}']
    # Case variables must survive until the return breakpoint.
    lines=[line.replace(';set ::axis $axis',';set ::axis $axis;set ::length $length') for line in lines]
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=120,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    with (out/'cache.bin').open('rb') as data:
        for n,(color,x,y,mode,length,axis) in enumerate(cases):
            expected=bytearray([170])*65536
            width,height=(length*4,8) if axis==1 else (4,length*8)
            for row in range(height):
                at=(x//32%2)*32768+((y*8+row)%256)*128+(x%32)*4
                expected[at:at+width]=bytes([color*17])*width
            if data.read(65536)!=expected:raise ValueError(f'Solid fill/canary mismatch at {n}: {cases[n]}')
        if data.read(1):raise ValueError('Extra solid fill captures')
    verify_manifest(bundle)
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('BIOS changed during solid-run proof')
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),strict_vram_timing=True,
        maximum_run_tiles=maximum_run,bios_sha256=bios,
        scope='Actual solid-run assembly: sixteen colors, both axes, page/world/cache/queue edges, flag owner, changed color and death; exact framebuffer and surrounding canary'))
    seal(out);print(f'{len(cases)} solid fill/canary cases: {out}/report.json')
    return out
