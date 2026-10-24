"""Execute the actual cartridge blitter routines over arbitrary maze canaries."""
import os
import statistics
import subprocess

from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal
from .build import destination
from .emulator import reference_machine, tcl
from .hud_verify import symbols
from .screen5 import packed


def verify_radar_marker(root,args,out,info,syms):
    """Actual SAT/color writes, including the HL cursor contract used by fuel."""
    code=bytes([0xcd])+syms['BitmapRadar_Player'].to_bytes(2,'little')+bytes([0x76])
    (out/'marker-probe.bin').write_bytes(code)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set cmdtiming real','set z80_freq 3579545',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out marker-probe.bin] rb];set probe [read $f];close $f;set n -1;set started 0;set rows [open [file join $out markers.tsv] w]',
        'proc issue {} {incr ::n;if {$::n==1024} {close $::rows;exit 0;return};set cy [expr {$::n%256}];set blink [expr {($::n/256)%2*8}];set hidden [expr {$::n>=512}];set x [expr {$hidden?255:2+($cy*7)%45}];set y [expr {$hidden?255:2+($cy*11)%55}];',
        f'debug write memory {syms["scroll_y"]} $cy;debug write memory {syms["hud_player_x"]} $x;debug write memory {syms["hud_player_y"]} $y;debug write memory {syms["player_native_ticks"]} $blink;reg HL {syms["sat"]};reg SP 0xc7f0;reg PC 0xc780','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;debug write_block memory 0xc780 $::probe;set f [open [file join $::out marker-patterns.bin] wb];puts -nonewline $f [debug read_block VRAM 129952 64];close $f;issue}}',
        f'debug set_bp 0xc783 {{$::started}} {{if {{[reg SP]!=0xc7f0 || [reg HL]!={syms["sat"]+4}}} {{puts stderr "Marker register contract";exit 2}};binary scan [debug read_block memory {syms["sat"]} 4] cu* a;binary scan [debug read_block VRAM 128000 3] cu* c;puts $::rows "$::n $a $c";issue}}',
        'set VDP.too_fast_vram_access_callback {puts stderr "VRAM timing violation";exit 2}',
        'after time 30 {puts stderr "marker timeout";exit 2}']
    (out/'marker-session.tcl').write_text('\n'.join(lines))
    with (out/'marker-emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'marker-session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60,
            env=dict(os.environ,OPENMSX_HOME=str(out/'marker-home'),OPENMSX_USER_DATA=str(out/'marker-userdata')))
    rows=(out/'markers.tsv').read_text().splitlines()
    if len(rows)!=1024:raise ValueError('Incomplete radar marker matrix')
    for n,line in enumerate(rows):
        actual=list(map(int,line.split()));cy=n%256;hidden=n>=512
        x=255 if hidden else 2+(cy*7)%45;y=255 if hidden else 2+(cy*11)%55
        y=(cy+211 if hidden else cy+19+2+(y-2)*76//54)&255;phase=int(y==216)
        color=info['sprites']['black' if n//256%2 else 'white']|0x20
        expected=[n,y-phase,(x+204)&255,116+4*phase,0,color,color,color]
        if actual!=expected:raise ValueError(f'Radar marker mismatch {n}: {actual} != {expected}')
    patterns=bytes([192,192]+[0]*30+[0,192,192]+[0]*29)
    if (out/'marker-patterns.bin').read_bytes()!=patterns:raise ValueError('Resident radar marker mask differs from native 2x2 footprint')
    return len(rows)


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    player=info.get('player_blitter',False)
    radar=info.get('radar_blitter',False)
    if not (player or radar):raise ValueError('Bitmap renderer cartridge required')
    out=destination(root,args.output);require_ignored(root,[out/'frames.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym');flags=read_json(bundle/'player.json')['flags']
    cars=(bundle/'player-pixels.bin').read_bytes()
    scene=bytes(((i*37+(i//128)*17)^165)&255 for i in range(65536))
    (out/'scene.bin').write_bytes(scene)
    fast=info.get('player_fast_blitter',False)
    if fast:(out/'road.bin').write_bytes(bytes(65536))
    # Execute old draw, then the actual restore/save/new draw transaction.
    def calls(*names):return b''.join(bytes((0xcd,))+syms[n].to_bytes(2,'little') for n in names)
    before=calls(*(['Bitmap_Draw'] if player else []),*(['BitmapRadar_Draw'] if radar else []))
    after=calls(*(['BitmapRadar_Restore'] if radar else []),*(['Bitmap_Restore','Bitmap_Draw'] if player else []),*(['BitmapRadar_Draw'] if radar else []))
    code=before+bytes((0x76,))+after+bytes((0x76,))
    (out/'probe.bin').write_bytes(code)
    cases=[(frame,x,y) for frame in range(12) for x in (0,1,59,60,139,140,315,396,511) for y in (0,1,143,240,255)]
    (out/'cases.bin').write_bytes(b''.join(bytes((frame,))+x.to_bytes(2,'little')+bytes((y,)) for frame,x,y in cases))
    radar_flags=read_json(bundle/'radar.json')['scenes'][0]['flags'] if radar else []
    flag_bytes=[v for point in radar_flags for v in point]+[255]*(40-2*len(radar_flags))
    flag_variants=[flag_bytes,
        [v if i//2%2==0 else 255 for i,v in enumerate(flag_bytes)], [255]*40]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach name {probe scene cases} {set f [open [file join $out "$name.bin"] rb];set $name [read $f];close $f}',
        *(['set f [open [file join $out road.bin] rb];set road [read $f];close $f'] if fast else []),
        f'set flags {{{" ".join(map(str,flags))}}};set n -1;set started 0',
        *(['set radar_flags [list '+ ' '.join('[binary format c* {'+' '.join(map(str,variant))+'}]' for variant in flag_variants)+']'] if radar else []),
        'set frames [open [file join $out frames.bin] wb];set costs [open [file join $out costs.tsv] w]',
        *(['set paths [open [file join $out fast.bin] wb]'] if fast else []),
        'proc position {x y flag} {',
        ' debug write_block memory 0xc0b0 [binary format c* [list [expr {$x&255}] [expr {($x>>8)&255}] $y 0]];debug write memory 0xe077 $flag',
        *([' debug write memory 0xc409 $flag'] if info.get('incremental_stage',0)>=9 else []),
        ' debug write memory 0xc0c0 [expr {2+($x+132)*44/816}];debug write memory 0xc0c1 [expr {2+($y+105)*54/1392}]',
        ' debug write memory 0xc328 18;debug write memory 0xc329 42','}',
        'proc issue {} {',
        f' incr ::n;if {{$::n=={len(cases)*(2 if fast else 1)}}} {{close $::frames;close $::costs;'+('close $::paths;' if fast else '')+'exit 0;return}',
        f' set at [expr {{$::n%{len(cases)}*4}}];binary scan [string range $::cases $at [expr {{$at+3}}]] cu* c;lassign $c ::frame xl xh ::y;set ::x [expr {{$xl+256*$xh}}]',
        ' debug write_block VRAM 0 $::scene;debug write memory 0xc700 0;debug write memory 0xc743 0',
        *([f' if {{$::n>={len(cases)}}} {{debug write_block VRAM 0 $::road}}',
           f' debug write memory {syms["Blit_ForceSlow"]} [expr {{$::n<{len(cases)}}}]'] if fast else []),
        # Clear source markers left by the preceding case without changing its
        # valid saved-under state. Each new transaction starts from known data.
        *([f' debug write_block memory {syms["hud_flags"]} [binary format c* {{{" ".join(map(str,flag_bytes))}}}]'] if radar else []),
        ' position $::x $::y [lindex $::flags $::frame];reg SP 0xc7f0;reg PC 0xc780','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;debug write_block memory 0xc780 $::probe;issue}}',
        f'debug set_bp {0xc780+len(before)} {{$::started}} {{position [expr {{($::x+1)&511}}] [expr {{($::y+2)&255}}] [lindex $::flags [expr {{($::frame+1)%12}}]];'+
        (f'debug write_block memory {syms["hud_flags"]} [lindex $::radar_flags [expr {{($::frame+1)%3}}]];' if radar else '')+
        f'set ::begin [machine_info time];reg PC {0xc781+len(before)}}}',
        f'debug set_bp {0xc781+len(before)+len(after)} {{$::started}} {{if {{[reg SP]!=0xc7f0}} {{error "Bitmap stack imbalance"}};puts $::costs "$::n [expr {{1000*([machine_info time]-$::begin)}}]";puts -nonewline $::frames [debug read_block VRAM 0 65536];'+(f'puts -nonewline $::paths [debug read_block memory {syms["Blit_Fast"]} 1];' if fast else '')+'issue}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Bitmap VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Bitmap probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    def plot(image,x,y,color):
        rx,ry=x%512,y%256;at=(rx//256)*32768+ry*128+(rx%256)//2
        image[at]=(image[at]&15)|(color<<4) if rx%2==0 else (image[at]&240)|color
    blue=info['hud_style'].get('radar_background_index')
    all_cases=cases*(2 if fast else 1)
    paths=(out/'fast.bin').read_bytes() if fast else None
    if fast and len(paths)!=len(all_cases):raise ValueError('Incomplete fast-path trace')
    world=(bundle/'stage-world.bin').read_bytes() if fast else None
    with (out/'frames.bin').open('rb') as stream:
        for n,(frame,x,y) in enumerate(all_cases):
            expected=bytearray(65536) if fast and n>=len(cases) else bytearray(scene)
            x,y=(x+1)%512,(y+2)%256
            if fast:
                tx=(x+116)//8;ty=(y+97)//8
                safe=bool(n>=len(cases) and tx+2<102 and ty+2<174 and
                    all(world[(ty*8+row)*816+tx*8+col]==0 for row in range(24) for col in range(24)))
                if paths[n]!=safe:raise ValueError(f'Road certificate disagrees with independent pixels at {n}')
            car=cars[(frame+1)%12*256:][:256]
            if player:
                for py in range(16):
                    for px in range(16):
                        if car[py*16+px]:plot(expected,x+116+px,y+97+py,car[py*16+px])
            if radar:
                image=bytearray([blue])*(48*80)
                mode=(frame+1)%3
                for f,(px,py) in enumerate(radar_flags):
                    if mode==2 or mode==1 and f%2:continue
                    py=2+(py-2)*76//54
                    for row in range(2):image[(py+row)*48+px:(py+row)*48+px+2]=bytes([info['sprites']['white']])*2
                for px,py,color in ((18,42,info['sprites']['red']),):
                    py=2+(py-2)*76//54
                    for row in range(2):image[(py+row)*48+px:(py+row)*48+px+2]=bytes([color])*2
                for py in range(80):
                    for px in range(48):plot(expected,x+196+px,y+9+py,image[py*48+px])
            actual=stream.read(65536)
            if actual!=expected:
                diffs=[i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b]
                raise ValueError(f'Actual cartridge bitmap mismatch {n}, {frame,x,y}, first addresses {diffs[:12]}')
        if stream.read(1):raise ValueError('Extra bitmap frames')
    values=[float(row.split()[1]) for row in (out/'costs.tsv').read_text().splitlines()]
    if len(values)!=len(all_cases):raise ValueError('Incomplete bitmap costs')
    if fast and not sum(paths):raise ValueError('Fast-path matrix never exercised a certified road')
    marker_cases=verify_radar_marker(root,args,out,info,syms) if radar else 0
    json_write(out/'report.json',dict(cases=len(all_cases),radar=radar,rom_sha256=digest(args.rom),
        radar_flag_variants=3 if radar else 0,
        radar_marker_cases=marker_cases,
        fast_path_cases=sum(paths) if fast else 0,
        certified_new_footprint_elapsed_ms=(dict(median=statistics.median(values[n] for n,path in enumerate(paths) if path),
             maximum=max(values[n] for n,path in enumerate(paths) if path)) if fast else None),
        elapsed_ms=dict(median=statistics.median(values),maximum=max(values)),
        scope='Actual cartridge old restore/new save/draw routines; arbitrary complete 64KiB maze canary, all12 poses and both torus wraps. Component proof, not whole-game raster acceptance.'))
    verify_manifest(bundle);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(all_cases)} actual cartridge bitmap cases: {out}/report.json')
