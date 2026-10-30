"""Execute enemy adapters together, checking independent masks/cache ownership."""
import os
import statistics
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .enemy_presentation_verify import cases_for


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    count=info.get('enemy_count')
    if count not in (2,3) or not info.get('enemy_rendered'):
        raise ValueError('Population presentation proof requires two or three rendered enemies')
    planes=info.get('enemy_logic',{}).get('sprite_planes',2)
    first_slot=info['sprites']['player_first_slot']+2
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    flags=read_json(bundle/'player.json')['flags']
    cases=[(target,*case) for target in range(count) for case in cases_for(flags)]
    (out/'cases.bin').write_bytes(b''.join(bytes((target,f))+x.to_bytes(2,'little',signed=True)
        +y.to_bytes(2,'little',signed=True)+bytes((s,v,d,c)) for target,f,x,y,s,v,d,c in cases))
    syms=symbols(bundle/'raster-scroll.sym');code=[243]
    for name in ('Enemy_Prepare','Enemy_Radar','Enemy_Draw')+(('Flicker_Publish',) if info.get('sprite_flicker') else ()):
        code.extend((205,syms[name]&255,syms[name]>>8))
    code.extend((195,16,199))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false',
        'set cmdtiming real',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set costs [open [file join $out cycles.tsv] w];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/10} {if {[debug read_block VRAM 0 65536] ne $::saved_scene} {error "Population changed maze VRAM"};close $::result;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*10}] [expr {$::index*10+9}]] cu* c;lassign $c target flag xl xh yl yh scroll visible dead contact',
        ' set x [expr {$xl+256*$xh}];if {$x>32767} {incr x -65536};set y [expr {$yl+256*$yh}];if {$y>32767} {incr y -65536}',
        f' foreach {{at v}} [list 0xc405 128 0xc406 1 0xc407 212 0xc408 4 {syms["scroll_y"]} $scroll 0xc490 $dead 0xc5d0 $contact 0xc63c [expr {{150+32*$target}}] 0xc63d 224] {{debug write memory $at $v}}',
        ' for {set a 0xe004} {$a<0xe00e} {incr a} {debug write memory $a 0}',
        f' for {{set actor 0}} {{$actor<{count}}} {{incr actor}} {{',
        '  set ax [expr {$actor==$target?$x:124}];set ay [expr {$actor==$target?$y:108}];set af [expr {$actor==$target?$flag:[lindex {240 242 252 253} [expr {$::index%4}]]}]',
        '  set wx [expr {384+$ax-124}];set wy [expr {1236+$ay-108}];set cx [expr {($wx-36+12)/24}];set cy [expr {($wy-36+12)/24}];set base [expr {0xe088+32*$actor}]',
        '  foreach {offset v} [list 8 $cx 10 $cy 5 [expr {($wx-36-24*$cx)&255}] 7 [expr {(-($wy-36-24*$cy))&255}] 15 $af] {debug write memory [expr {$base+$offset}] $v}',
        '  if {$actor!=$target || $visible} {debug write memory [expr {0xe00c-2*$actor}] [expr {147+32*$actor}];debug write memory [expr {0xe00d-2*$actor}] 224}',' }',
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc700','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved_scene [debug read_block VRAM 0 65536]',
        *[f'debug write memory {0xc700+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc710 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Population stack imbalance"}',
        ' foreach {ram slot} {'+' '.join(f'{0xc5d0 if a==0 else 0xc640+(a-1)*0x30} {first_slot+a*planes}' for a in range(count))+'} {',
        *([f'  if {{[debug read memory 0xc7c0]}} {{set slot [expr {{$slot-{first_slot}+6}}]}}'] if info.get('sprite_flicker') else []),
        '  puts -nonewline $::result [debug read_block memory $ram 22]',
        f'  puts -nonewline $::result [debug read_block VRAM [expr {{128512+4*$slot}}] {4*planes}]',
        f'  puts -nonewline $::result [debug read_block VRAM [expr {{128000+16*$slot}}] {16*planes}]',
        f'  for {{set plane 0}} {{$plane<{planes}}} {{incr plane}} {{set p [debug read VRAM [expr {{128514+4*$slot+4*$plane}}]];puts -nonewline $::result [debug read_block VRAM [expr {{129024+($p&252)*8}}] 32]}}',' }',
        *([' puts -nonewline $::result [debug read_block VRAM 128608 4]',
           ' set p [debug read VRAM 128610];puts -nonewline $::result [debug read_block VRAM [expr {129024+($p&252)*8}] 32]',
           ' puts -nonewline $::result [debug read_block VRAM 128384 16]'] if count==3 else []),
        f' puts -nonewline $::result [binary format c [debug read VRAM {128512+4*info["sprites"]["total_slots"]}]]',
        ' puts $::costs "$::index [expr {round(([machine_info time]-$::begin)*3579545)}]";incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Population VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Population presentation timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'msx.bin').read_bytes();record=22+52*planes;size=record*count+1+(52 if count==3 else 0)
    if len(raw)!=len(cases)*size:raise ValueError('Incomplete population presentation evidence')
    pixels=(bundle/'player-pixels.bin').read_bytes();visible=0
    for n,(target,flag,x,y,scroll,registered,dead,contact) in enumerate(cases):
        r=raw[n*size:(n+1)*size]
        if r[-1]!=216:raise ValueError(f'Population SAT terminator changed: {n}')
        for actor in range(count):
            f,ax,ay,v=(flag,x,y,registered) if actor==target else ((240,242,252,253)[n%1928%4],124,108,1)
            ram,sat,colors,masks=[r[actor*record+a:actor*record+b] for a,b in
                ((0,22),(22,22+4*planes),(22+4*planes,22+20*planes),(22+20*planes,record))]
            expected=bool(v and not(dead and contact and actor==target) and -7<=ax<=255 and -4<=ay<=211)
            if bool(ram[2])!=expected:raise ValueError(f'Population visibility mismatch: case{n} actor{actor}')
            if (int.from_bytes(ram[4:6],'little'),int.from_bytes(ram[6:8],'little'))!=(384+ax-124,1236+ay-108):
                raise ValueError(f'Population coordinates changed: {n}/{actor}')
            if not expected:
                hidden=(scroll+211)&255;hidden+=int(hidden==216)
                if any(sat[p*4]!=hidden for p in range(planes)):raise ValueError(f'Hidden population actor visible: {n}/{actor}')
                continue
            visible+=1;bias=int((scroll+ay-1)&255==216);ec=128 if ax<0 else 0
            pos=bytes(((scroll+ay-1-bias)&255,(ax+(32 if ec else 0))&255))
            if any(sat[p*4:p*4+2]!=pos for p in range(planes)):raise ValueError(f'Population position mismatch: {n}/{actor}')
            expected_colors=bytes([6|32|ec])*16+(bytes([10|96|ec])*16 if planes==2 else b'')
            if colors!=expected_colors:raise ValueError(f'Population colors mismatch: {n}/{actor}')
            car=pixels[flags.index(f)*256:][:256]
            wanted=bytes(sum(int(car[py*16+px+bit] in plane and ax+px+bit>=8 and py+ay-bias!=11)<<(7-bit)
                             for bit in range(8)) for plane in (((3,9,11),) if planes==1 else ((3,11),(9,11))) for px in (0,8) for py in range(16))
            if masks!=wanted:raise ValueError(f'Population mask/cache collision: {n}/{actor}')
        if count==3:
            # The third dot is a separate lower-priority sprite. Its source
            # geometry is independent of the SAT packing and car victim caches.
            ax,ay=(x,y) if target==2 else (124,108)
            wx,wy=384+ax-124,1236+ay-108
            px=2+((wx//8)*8+4)*44//816;py=2+((wy//8)*8+4)*54//1392
            sy=(20+(py&248)+scroll-1)&255;shift=int(sy==216)
            dot=r[record*count:-1]
            expected_sat=bytes((sy-shift,204+(px&248),216+shift*4,0))
            from .sprite_radar import point_patterns
            expected_mask=point_patterns(px,py)[shift*32:(shift+1)*32]
            if dot!=expected_sat+expected_mask+bytes([info['sprites']['red']|32])*16:
                raise ValueError(f'Third enemy radar position/pattern/cache changed: {n}')
    costs=[int(r.split()[1]) for r in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=len(cases):raise ValueError('Missing population presentation costs')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(cases=len(cases),actors_checked=count*len(cases),visible=visible,
        rom_sha256=digest(args.rom),elapsed_cycles=dict(median=statistics.median(costs),maximum=max(costs)),
        maze_vram_unchanged=True,strict_vram_timing=True,occupied_slots=info['sprites']['total_slots'],
        scope=f'{count} simultaneous enemy adapters: exact independent masks, shared/victim cache ownership, clipping, hit-specific visibility and SAT phases; not a natural RGB/timing acceptance'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} executed {count}-enemy presentation vectors: {out}/report.json')
    return out
