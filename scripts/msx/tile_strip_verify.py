"""Run exact strip commands against full framebuffer canaries and queue edges."""
import os
import statistics
import subprocess
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('tile_strips'):raise ValueError('Tile-strip cartridge required')
    out=destination(root,args.output);require_ignored(root,[out/'cache.bin']);out.mkdir(parents=True)
    world=(bundle/'stage-world.bin').read_bytes();flags=read_json(bundle/'flags.json')['records']
    candidates={(axis,x,y,0) for axis in (1,2) for x in (0,1,3,27,30,31,32,63,64,99,101,102)
                for y in (0,1,3,27,30,31,32,63,64,129,171,173,174)}
    candidates.update((axis,x,y,mode) for axis in (1,2) for x,y in ((0,0),(33,33),(99,171)) for mode in range(1,8))
    for axis in (1,2):
        seen=set();tw,th=(24,8) if axis==1 else (8,24)
        for y in range(0,1392,th):
            for x in range(0,816,tw):
                pixels=b''.join(world[(y+r)*816+x:(y+r)*816+x+tw] for r in range(th))
                if pixels not in seen:candidates.add((axis,x//8,y//8,0));seen.add(pixels)
    cases=[]
    for axis,x,y,mode in sorted(candidates):
        owned=mode==1 or any(f['tile_x']<=x<f['tile_x']+3 and f['tile_y']<=y<f['tile_y']+3 for f in flags)
        along=x if axis==1 else y
        valid=(x<102 and y<174 and along%3==0 and along%32<=29
               and (x+2<102 if axis==1 else y+2<174) and not owned and mode not in (2,3,4,5,6))
        cases.append((axis,x,y,mode,int(owned),int(valid)))
    (out/'cases.bin').write_bytes(bytes(v for case in cases for v in case))
    syms=symbols(bundle/'raster-scroll.sym');call,wait=syms['Stage_TryStrip'],syms['stage_wait_command']
    code=[243,62,0,205,call&255,call>>8,245,205,wait&255,wait>>8,241,195,64,199]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set cache [open [file join $out cache.bin] wb];set costs [open [file join $out cycles.tsv] w];set index 0;set started 0',
        f'set columns {info["cache_columns"]}',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/6} {if {[debug read_block memory 0xe000 4096] ne $::native} {error "Strip changed native state"};close $::cache;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*6}] [expr {$::index*6+5}]] cu* c;lassign $c axis x y mode owner expected',
        ' set ::expected $expected;set ::axis $axis;set ::left [expr {$mode==3?1:7}]',
        ' set ::next [expr {($axis==1?$x:$y)+1+($mode==6)}]',
        ' set end [expr {($axis==1?$x:$y)+($mode==4?2:($mode==7?3:20))}]',
        ' set start [expr {($end-($axis==1?$::columns:32))&255}]',
        ' set cx [expr {$mode==5?($x+2-$::columns)&255:($mode==7 && $axis==1?$start:$x)}]',
        ' set cy [expr {$mode==5?($y-30)&255:($mode==7 && $axis==2?$start:$y)}]',
        ' set ::after [expr {$mode==7?$start:$::next+2}]',
        ' debug write_block VRAM 0 [string repeat [binary format c 170] 65536]',
        ' foreach {a v} [list 0xc702 $owner 0xc400 1 0xc009 1 0xc49a [expr {$mode==2}] 0xc0bc $x 0xc0bd $y 0xc0b7 $::left 0xc0b6 $::left 0xc0bb $::next 0xc0b9 $::next 0xcf1c $start 0xcf1d $end 0xcf1a $start 0xcf1b $end 0xcf26 $axis 0xc46f $cx 0xc470 $cy] {debug write memory $a $v}',
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc700','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::native [debug read_block memory 0xe000 4096]',
        ' debug write {VDP regs} 0 6;debug write {VDP regs} 1 66',
        *[f'debug write memory {0xc700+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc740 {$::started} {',
        ' set got_left [debug read memory [expr {$::axis==1?0xc0b7:0xc0b6}]];set got_next [debug read memory [expr {$::axis==1?0xc0bb:0xc0b9}]]',
        ' if {[reg SP]!=0xc7f0 || ([reg AF]&1)!=$::expected || $got_left!=$::left-2*$::expected || $got_next!=($::expected?$::after:$::next) || [debug read memory 0xc468]!=8 || [debug read memory 0xc46a]!=8 || [debug read memory 0xc463]!=2} {puts stderr "Strip state index=$::index SP=[reg SP] AF=[reg AF] left=$got_left/$::left next=$got_next/$::after expected=$::expected nx=[debug read memory 0xc468] ny=[debug read memory 0xc46a] syh=[debug read memory 0xc463]";exit 2}',
        ' puts -nonewline $::cache [debug read_block VRAM 0 65536];puts $::costs "$::index [expr {round(([machine_info time]-$::begin)*3579545)}]";incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Strip VRAM timing violation";exit 2}',
        'after time 90 {puts stderr "Strip proof timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=120,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    with (out/'cache.bin').open('rb') as data:
        for n,(axis,x,y,mode,owner,success) in enumerate(cases):
            expected=bytearray([170])*65536
            if success:
                tw,th=(24,8) if axis==1 else (8,24)
                for row in range(th):
                    for col in range(tw):
                        pixel=world[(y*8+row)*816+x*8+col]
                        px=(x*8+col)%512;py=(y*8+row)%256;at=px//256*32768+py*128+px%256//2
                        expected[at]=expected[at]&15|pixel<<4 if px%2==0 else expected[at]&240|pixel
            if data.read(65536)!=expected:raise ValueError(f'Strip pixels/canary mismatch at {n}: {cases[n]}')
    verify_manifest(bundle)
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    costs=[int(row.split()[1]) for row in (out/'cycles.tsv').read_text().splitlines()]
    successful=[cost for cost,case in zip(costs,cases) if case[-1]]
    if len(costs)!=len(cases):raise ValueError('Incomplete strip cost observations')
    json_write(out/'report.json',dict(cases=len(cases),isolated_irq_sources_disabled=True,
        successful_elapsed_cycles=dict(median=statistics.median(successful),maximum=max(successful)),successful_commands=sum(c[-1] for c in cases),rom_sha256=digest(args.rom),
        strict_vram_timing=True,native_unchanged=True,scope='Actual exact strips, framebuffer canaries, world/page/cache/queue/owner/death bounds; no rendered-game acceptance claim'))
    seal(out);print(f'{len(cases)} strip/canary cases: {out}/report.json')
    return out
