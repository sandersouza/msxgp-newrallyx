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


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('player_blitter'):raise ValueError('Bitmap renderer cartridge required')
    radar=info.get('radar_blitter',False)
    out=destination(root,args.output);require_ignored(root,[out/'frames.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym');flags=read_json(bundle/'player.json')['flags']
    cars=(bundle/'player-pixels.bin').read_bytes()
    scene=bytes(((i*37+(i//128)*17)^165)&255 for i in range(65536))
    (out/'scene.bin').write_bytes(scene)
    # Execute old draw, then the actual restore/save/new draw transaction.
    def calls(*names):return b''.join(bytes((0xcd,))+syms[n].to_bytes(2,'little') for n in names)
    before=calls('Bitmap_Draw',*(['BitmapRadar_Draw'] if radar else []))
    after=calls(*(['BitmapRadar_Restore'] if radar else []),'Bitmap_Restore','Bitmap_Draw',*(['BitmapRadar_Draw'] if radar else []))
    code=before+bytes((0x76,))+after+bytes((0x76,))
    (out/'probe.bin').write_bytes(code)
    cases=[(frame,x,y) for frame in range(12) for x in (0,1,59,60,139,140,315,396,511) for y in (0,1,143,240,255)]
    (out/'cases.bin').write_bytes(b''.join(bytes((frame,))+x.to_bytes(2,'little')+bytes((y,)) for frame,x,y in cases))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach name {probe scene cases} {set f [open [file join $out "$name.bin"] rb];set $name [read $f];close $f}',
        f'set flags {{{" ".join(map(str,flags))}}};set n -1;set started 0',
        'set frames [open [file join $out frames.bin] wb];set costs [open [file join $out costs.tsv] w]',
        'proc position {x y flag} {',
        ' debug write_block memory 0xc0b0 [binary format c* [list [expr {$x&255}] [expr {($x>>8)&255}] $y 0]];debug write memory 0xe077 $flag',
        ' debug write memory 0xc0c0 [expr {2+($x+132)*44/816}];debug write memory 0xc0c1 [expr {2+($y+105)*54/1392}]',
        ' debug write memory 0xc328 18;debug write memory 0xc329 42','}',
        'proc issue {} {',
        f' incr ::n;if {{$::n=={len(cases)}}} {{close $::frames;close $::costs;exit 0;return}}',
        ' binary scan [string range $::cases [expr {$::n*4}] [expr {$::n*4+3}]] cu* c;lassign $c ::frame xl xh ::y;set ::x [expr {$xl+256*$xh}]',
        ' debug write_block VRAM 0 $::scene;debug write memory 0xc700 0;debug write memory 0xc743 0',
        # Clear source markers left by the preceding case without changing its
        # valid saved-under state. Each new transaction starts from known data.
        ' position $::x $::y [lindex $::flags $::frame];reg SP 0xc7f0;reg PC 0xc780','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;debug write_block memory 0xc780 $::probe;issue}}',
        f'debug set_bp {0xc780+len(before)} {{$::started}} {{position [expr {{($::x+1)&511}}] [expr {{($::y+2)&255}}] [lindex $::flags [expr {{($::frame+1)%12}}]];set ::begin [machine_info time];reg PC {0xc781+len(before)}}}',
        f'debug set_bp {0xc781+len(before)+len(after)} {{$::started}} {{if {{[reg SP]!=0xc7f0}} {{error "Bitmap stack imbalance"}};puts $::costs "$::n [expr {{1000*([machine_info time]-$::begin)}}]";puts -nonewline $::frames [debug read_block VRAM 0 65536];issue}}',
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
    with (out/'frames.bin').open('rb') as stream:
        for n,(frame,x,y) in enumerate(cases):
            expected=bytearray(scene);x,y=(x+1)%512,(y+2)%256
            car=cars[(frame+1)%12*256:][:256]
            for py in range(16):
                for px in range(16):
                    if car[py*16+px]:plot(expected,x+116+px,y+97+py,car[py*16+px])
            if radar:
                image=bytearray([blue])*(48*80)
                for px,py in read_json(bundle/'radar.json')['scenes'][0]['flags']:
                    py=2+(py-2)*76//54
                    for row in range(2):image[(py+row)*48+px:(py+row)*48+px+2]=bytes([info['sprites']['white']])*2
                for px,py,color in ((18,42,info['sprites']['red']),(2+(x+132)*44//816,2+(y+105)*54//1392,info['sprites']['black'])):
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
    if len(values)!=len(cases):raise ValueError('Incomplete bitmap costs')
    json_write(out/'report.json',dict(cases=len(cases),radar=radar,rom_sha256=digest(args.rom),
        elapsed_ms=dict(median=statistics.median(values),maximum=max(values)),
        scope='Actual cartridge old restore/new save/draw routines; arbitrary complete 64KiB maze canary, all12 poses and both torus wraps. Component proof, not whole-game raster acceptance.'))
    verify_manifest(bundle);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} actual cartridge bitmap cases: {out}/report.json')
