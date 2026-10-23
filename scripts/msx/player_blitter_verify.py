"""Measure real VDP save/restore/transparent player copies with wrap canaries.

This is an isolated component experiment. It does not replace player sprites in
the playable ROM or claim that its raster integration has passed.
"""
import os
import statistics
import subprocess

from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .screen5 import packed


def packets(x,y,width,linear_x,linear_y,*,save=False,command=0xd0,height=16):
    result=[];yo=0
    while yo<height:
        h=min(height-yo,256-(y+yo)%256);xo=0
        while xo<width:
            w=min(width-xo,256-(x+xo)%256)
            rx=(x+xo)%256;ry=(y+yo)%256+((x+xo)%512//256)*256
            lx,ly=linear_x+xo,linear_y+yo
            coords=(rx,ry,lx,ly) if save else (lx,ly,rx,ry)
            result.append(b''.join(v.to_bytes(2,'little') for v in (*coords,w,h))+bytes((0,0,command)))
            xo+=w
        yo+=h
    return result


PROBE='''    OUTPUT "probe.bin"
    ORG $c600
    di
    ld a,$42
    out ($99),a
    ld a,$81
    out ($99),a
sprite_mode:
    ld a,$0a
    out ($99),a
    ld a,$88
    out ($99),a
    ld hl,$c800
before_count:
    ld d,1
    call blit_submit
    ld a,1
    ld ($c6f0),a
after_count:
    ld d,1
    call blit_submit
    ld a,2
    ld ($c6f0),a
    jp probe_stop
blit_submit:
    ld a,32
    out ($99),a
    ld a,$91
    out ($99),a
    ld bc,$0f9b
    otir
blit_submitted:
    ld a,2
    out ($99),a
    ld a,$8f
    out ($99),a
.wait:
    in a,($99)
    and 1
    jr nz,.wait
    dec d
    jr nz,blit_submit
    ret
probe_stop:
    halt
'''


def verify(root,args,*,radar=False):
    bundle=args.rom.parent;verify_manifest(bundle)
    out=destination(root,args.output);require_ignored(root,[out/'scene.bin']);out.mkdir(parents=True)
    cars=(bundle/'player-pixels.bin').read_bytes()
    width,height,frames,source_y,backup_x,backup_y=16,16,12,576,208,608
    if radar:
        from .raster_scroll import index_for
        palette=(bundle/'palette.bin').read_bytes()
        blue=index_for(palette,(0,0,151));white=index_for(palette,(222,222,222))
        red=index_for(palette,(255,0,0));black=index_for(palette,(0,0,0))
        width,height,frames,source_y,backup_x,backup_y=48,80,2,640,0,768
        images=[]
        for phase in range(frames):
            image=bytearray([blue])*(width*height)
            for x,y,color in [(4+i*4,4+i*6,white) for i in range(10)]+[(22+phase,39+phase,black),(18-phase,52,red)]:
                for row in range(2):image[(y+row)*width+x:(y+row)*width+x+2]=bytes([color])*2
            images.append(bytes(image))
        cars=b''.join(images)
    scene=bytes(((i*37+(i//128)*17)^165)&255 for i in range(65536))
    (out/'scene.bin').write_bytes(scene)
    atlas=bytes(v for y in range(height) for frame in range(frames) for v in packed(cars[frame*width*height+y*width:frame*width*height+y*width+width]))
    (out/'atlas.bin').write_bytes(atlas)
    cases=[(mode,frame,x,y) for mode in (0x0a,0x2a) for frame in range(frames)
           for x in (0,1,247,248,255,256,503,504,511) for y in (0,1,240,248,255)]
    stream=bytearray()
    for mode,frame,x,y in cases:
        nx,ny=(x+1)%512,(y+2)%256
        old_x=x&~1;old_width=width+2*(x&1);new_x=nx&~1;new_width=width+2*(nx&1)
        def rect(x,y,w,lx,ly,**kw):return packets(x,y,w,lx,ly,height=height,**kw)
        before=rect(old_x,y,old_width,backup_x,backup_y,save=True)+rect(x,y,width,frame*width,source_y,command=0x90 if radar else 0x98)
        after=rect(old_x,y,old_width,backup_x,backup_y)+rect(new_x,ny,new_width,backup_x,backup_y,save=True)+rect(nx,ny,width,(frame+1)%frames*width,source_y,command=0x90 if radar else 0x98)
        stream.extend(bytes((mode,len(before),len(after)))+b''.join(before+after))
    (out/'packets.bin').write_bytes(stream);(out/'probe.asm').write_text(PROBE)
    result=subprocess.run([str(args.assembler.resolve()),'--nologo','--sym=probe.sym','probe.asm'],cwd=out,capture_output=True,text=True,check=True)
    (out/'assembly.log').write_text(result.stdout+result.stderr)
    syms=symbols(out/'probe.sym');cart=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach n {packets scene probe atlas} {set f [open [file join $out "$n.bin"] rb];set $n [read $f];close $f}',
        'set index 0;set position 0;set started 0;set measured 0;set command 0',
        'set frames [open [file join $out frames.bin] wb];set costs [open [file join $out costs.tsv] w];set gpu [open [file join $out gpu.tsv] w];set cpu [open [file join $out cpu.tsv] w]',
        'proc issue {} {',
        ' if {$::position==[string length $::packets]} {set f [open [file join $::out remaining.bin] wb];puts -nonewline $f [debug read_block VRAM 65536 65536];close $f;close $::frames;close $::costs;close $::gpu;close $::cpu;exit 0;return}',
        ' binary scan [string range $::packets $::position [expr {$::position+2}]] cu* h;lassign $h mode before after;incr ::position 3;set bytes [expr {15*($before+$after)}]',
        ' debug write_block VRAM 0 $::scene;debug write_block memory 0xc800 [string range $::packets $::position [expr {$::position+$bytes-1}]];incr ::position $bytes',
        f' debug write memory {syms["sprite_mode"]+1} $mode;debug write memory {syms["before_count"]+1} $before;debug write memory {syms["after_count"]+1} $after',
        ' set ::measured 0;set ::command 0;reg SP 0xc7f0;reg PC 0xc600','}',
        f'debug set_bp {cart["main"]} {{!$::started}} {{set ::started 1;debug write_block memory 0xc600 $::probe',
        f' for {{set y 0}} {{$y<{height}}} {{incr y}} {{debug write_block VRAM [expr {{{source_y}*128+$y*128}}] [string range $::atlas [expr {{$y*{width*frames//2}}}] [expr {{$y*{width*frames//2}+{width*frames//2-1}}}]]}}',
        ' set f [open [file join $::out remaining-before.bin] wb];puts -nonewline $f [debug read_block VRAM 65536 65536];close $f;issue','}',
        'debug set_watchpoint write_mem 0xc6f0 {$::started} {if {$wp_last_value==1} {set ::measured 1;set ::begin [machine_info time]} else {set ::measured 0;puts $::costs "$::index [expr {round(([machine_info time]-$::begin)*3579545)}]"}}',
        f'debug set_bp {syms["blit_submit"]} {{$::started && $::measured}} {{set ::submit [machine_info time]}}',
        f'debug set_bp {syms["blit_submitted"]} {{$::started && $::measured}} {{puts $::cpu "$::index [expr {{round(([machine_info time]-$::submit)*3579545)}}]"}}',
        'debug probe set_bp VDP.commandExecuting {$::started && $::measured} {if {[debug probe read VDP.commandExecuting]} {set ::gpu_begin [machine_info time]} elseif {[info exists ::gpu_begin]} {puts $::gpu "$::index [expr {1000*([machine_info time]-$::gpu_begin)}]";unset ::gpu_begin}}',
        f'debug set_bp {syms["probe_stop"]} {{$::started}} {{if {{[reg SP]!=0xc7f0}} {{error "Blitter probe stack imbalance"}};puts -nonewline $::frames [debug read_block VRAM 0 65536];incr ::index;issue}}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Blitter probe VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Blitter probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    with (out/'frames.bin').open('rb') as f:
        for n,(mode,frame,x,y) in enumerate(cases):
            expected=bytearray(scene);nx,ny=(x+1)%512,(y+2)%256;car=cars[(frame+1)%frames*width*height:][:width*height]
            for py in range(height):
                for px in range(width):
                    color=car[py*width+px]
                    if not color and not radar:continue
                    rx,ry=(nx+px)%512,(ny+py)%256;at=(rx//256)*32768+ry*128+(rx%256)//2
                    expected[at]=(expected[at]&15)|(color<<4) if rx%2==0 else (expected[at]&240)|color
            if f.read(65536)!=expected:raise ValueError(f'Blitter transparent copy/restore/wrap mismatch: {n}, {mode,frame,x,y}')
        if f.read(1):raise ValueError('Extra blitter captures')
    before=(out/'remaining-before.bin').read_bytes();after=(out/'remaining.bin').read_bytes()
    allowed={y*128+x//2-65536 for y in range(backup_y,backup_y+height) for x in range(backup_x,backup_x+width+2)}
    if any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(before,after))):raise ValueError('Blitter corrupted unrelated high VRAM')
    rows=[tuple(map(int,r.split())) for r in (out/'costs.tsv').read_text().splitlines()]
    cpu=[tuple(map(int,r.split())) for r in (out/'cpu.tsv').read_text().splitlines()]
    gpu=[tuple(map(float,r.split())) for r in (out/'gpu.tsv').read_text().splitlines()]
    if len(rows)!=len(cases) or [r[0] for r in rows]!=list(range(len(cases))) or not cpu or not gpu:raise ValueError('Incomplete blitter timings')
    groups={}
    for mode,label in ((0x0a,'sprites_enabled'),(0x2a,'sprites_disabled')):
        ids={n for n,c in enumerate(cases) if c[0]==mode};values=[v/3579.545 for n,v in rows if n in ids]
        submissions=[v for n,v in cpu if n in ids];commands=[v for n,v in gpu if int(n) in ids]
        groups[label]=dict(cases=len(values),complete_ms=dict(median=statistics.median(values),maximum=max(values)),
            cpu_packet_cycles=dict(median=statistics.median(submissions),maximum=max(submissions)),
            gpu_command_ms=dict(median=statistics.median(commands),maximum=max(commands)))
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),groups=groups,
        transparent_command='LMMM IMP 0x90' if radar else 'LMMM TIMP 0x98',background_commands='HMMM 0xd0',world_canary_bytes=65536,
        dimensions=[width,height],
        scope='Isolated standard-clock real-VDP save/restore/draw with even aligned odd-X backups and both ring wraps; elapsed waits include busy polling; not a playable raster integration or measured whole-game FPS'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact {"radar" if radar else "player"} blitter/save-under/wrap cases: {out}/report.json')
    return out
