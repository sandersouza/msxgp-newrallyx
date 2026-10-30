"""Execute enemy presentation over facing, clipping, cache eviction and SAT phases."""
import os
import statistics
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols


def cases_for(flags):
    cases=[(flag,x,y,scroll,1,0,0) for flag in flags
           for x in (-8,-7,0,7,8,9,124,248,255,256)
           for y in (-5,-4,0,11,108,200,211,212) for scroll in (0,(217-y)&255)]
    cases += [(flags[0],124,108,0,registered,dead,contact)
              for registered in (0,1) for dead in (0,1) for contact in (0,1)]
    return cases


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('enemy_rendered') or not info.get('enemy_contact_applies_death'):
        raise ValueError('Presentation proof requires the complete one-enemy adapter')
    slot=info['sprites']['player_first_slot']+(0 if info.get('player_blitter') else 2)
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    flags=read_json(bundle/'player.json')['flags'];cases=cases_for(flags)
    data=b''.join(bytes([f])+x.to_bytes(2,'little',signed=True)+y.to_bytes(2,'little',signed=True)
                  +bytes((s,v,d,c)) for f,x,y,s,v,d,c in cases)
    (out/'cases.bin').write_bytes(data);syms=symbols(bundle/'raster-scroll.sym')
    code=[243,205,syms['Enemy_Prepare']&255,syms['Enemy_Prepare']>>8,
          205,syms['Enemy_Draw']&255,syms['Enemy_Draw']>>8,195,144,198]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set costs [open [file join $out cycles.tsv] w];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/9} {if {[debug read_block VRAM 0 65536] ne $::saved_scene} {error "Enemy presentation changed the maze cache"};close $::result;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*9}] [expr {$::index*9+8}]] cu* c;lassign $c flag xl xh yl yh scroll visible dead contact',
        ' set x [expr {$xl+256*$xh}];if {$x>32767} {incr x -65536};set y [expr {$yl+256*$yh}];if {$y>32767} {incr y -65536}',
        ' set wx [expr {384+$x-124}];set wy [expr {1236+$y-108}]',
        ' set cx [expr {($wx-36+12)/24}];set cy [expr {($wy-36+12)/24}]',
        ' foreach {at v} [list 0xc405 128 0xc406 1 0xc407 212 0xc408 4 0xc01c $scroll 0xe090 $cx 0xe092 $cy 0xe08d [expr {($wx-36-24*$cx)&255}] 0xe08f [expr {(-($wy-36-24*$cy))&255}] 0xe097 $flag 0xc490 $dead 0xc5d0 $contact] {debug write memory $at $v}',
        ' for {set a 0xe004} {$a<0xe00e} {incr a} {debug write memory $a 0}',
        ' if {$visible} {debug write memory 0xe00c 147;debug write memory 0xe00d 224}',
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc680','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved_scene [debug read_block VRAM 0 65536]',
        *[f'debug write memory {0xc680+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc690 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Enemy presentation stack imbalance"}',
        ' puts -nonewline $::result [debug read_block memory 0xc5d0 22]',
        f' puts -nonewline $::result [debug read_block VRAM {128512+slot*4} 9]',
        f' puts -nonewline $::result [debug read_block VRAM {128000+slot*16} 32]',
        f' foreach a {{{128514+slot*4} {128518+slot*4}}} {{set p [debug read VRAM $a];puts -nonewline $::result [debug read_block VRAM [expr {{129024+($p&252)*8}}] 32]}}',
        ' puts $::costs "$::index [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        ' incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Enemy presentation VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Enemy presentation timeout";exit 2}']
    # Use the linked scroll symbol, never a duplicated renderer RAM allocation.
    lines=[line.replace('0xc01c $scroll',f'{syms["scroll_y"]} $scroll') for line in lines]
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'msx.bin').read_bytes();size=127
    if len(raw)!=size*len(cases):raise ValueError('Incomplete enemy presentation evidence')
    pixels=(bundle/'player-pixels.bin').read_bytes();visible_count=0;biases=0;clips=0
    for n,(flag,x,y,scroll,registered,dead,contact) in enumerate(cases):
        r=raw[n*size:(n+1)*size];ram,sat,colors,masks=r[:22],r[22:31],r[31:63],r[63:]
        expected=bool(registered and not(dead and contact) and -7<=x<=255 and -4<=y<=211)
        if bool(ram[2])!=expected:raise ValueError(f'Enemy visibility mismatch in case {n}')
        if (int.from_bytes(ram[4:6],'little'),int.from_bytes(ram[6:8],'little'))!=(384+x-124,1236+y-108):
            raise ValueError(f'Enemy world coordinates changed in case {n}')
        if sat[8]!=216:raise ValueError('Enemy SAT terminator changed')
        if not expected:
            hidden=(scroll+211)&255;hidden+=int(hidden==216)
            if sat[0]!=hidden or sat[4]!=hidden:raise ValueError(f'Hidden enemy remained on screen: {n}')
            continue
        visible_count+=1;bias=int((scroll+y-1)&255==216);biases+=bias;clips+=int(x<8)
        if int.from_bytes(ram[10:12],'little',signed=True)!=y-bias:raise ValueError(f'Enemy presentation bias differs: {n}')
        ec=128 if x<0 else 0;ay=(scroll+y-1-bias)&255;ax=x+(32 if ec else 0)
        if sat[:2]!=bytes((ay,ax)) or sat[4:6]!=bytes((ay,ax)):raise ValueError(f'Enemy SAT position mismatch: {n}')
        if colors!=bytes([6|32|ec])*16+bytes([10|96|ec])*16:raise ValueError(f'Enemy OR/EC colors mismatch: {n}')
        car=pixels[flags.index(flag)*256:][:256]
        expected_masks=bytes(sum(int(car[py*16+px+bit] in plane and x+px+bit>=8 and py+y-bias!=11)<<(7-bit)
                                 for bit in range(8)) for plane in ((3,11),(9,11)) for px in (0,8) for py in range(16))
        if masks!=expected_masks:raise ValueError(f'Enemy source pixels/cache eviction mismatch: {n}')
    costs=[int(r.split()[1]) for r in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=len(cases):raise ValueError('Missing enemy presentation costs')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    report=dict(rom_sha256=digest(args.rom),cases=len(cases),visible=visible_count,
        forbidden_y_bias_cases=biases,left_clip_cases=clips,
        elapsed_cycles=dict(median=statistics.median(costs),maximum=max(costs)),
        occupied_slots=info['sprites']['total_slots'],free_slots=info['sprites']['free_slots'],strict_vram_timing=True,
        scope='Executed presentation component: exact source masks, cache eviction, OR colors, visibility, left clipping and declared SAT-Y bias; natural gameplay/full RGB validated separately')
    report['bios']=bios
    json_write(out/'report.json',report);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print({k:v for k,v in report.items() if k!='bios'})
