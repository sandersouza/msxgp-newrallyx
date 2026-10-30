"""Execute paired/separate red radar dots through the real host HUD routines."""
import os
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .sprite_radar import X,Y


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('enemy_logic',{}).get('paired_radar') or not info['hud_enabled']:
        raise ValueError('Pair proof requires the HUD-on paired-radar build')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    cases=[]
    for anchor in (2,7,15):
        for dx in range(16):
            for dy in range(16):
                for diagonal in range(2):
                    a,b=((anchor,anchor+dy),(anchor+dx,anchor)) if diagonal else ((anchor,anchor),(anchor+dx,anchor+dy))
                    for scroll in (0,(217-Y-anchor)&255):cases.append((*a,*b,scroll))
    cases.extend((255,255,15,15,s) for s in (0,217))
    cases.extend((15,15,255,255,s) for s in (0,217))
    (out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    syms=symbols(bundle/'raster-scroll.sym');code=[243]
    for name in ('Enemy_PairRadar','update_radar','update_lives','Player_Draw','Enemy_Draw'):
        code.extend((205,syms[name]&255,syms[name]>>8))
    code.extend((195,176,198))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/5} {if {[debug read_block VRAM 0 65536] ne $::maze} {error "Radar pair changed maze VRAM"};close $::result;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*5}] [expr {$::index*5+4}]] cu* c;lassign $c x y ex ey scroll',
        f' foreach {{at v}} [list {syms["hud_enemy_x"]} $x {syms["hud_enemy_y"]} $y 0xc638 $ex 0xc639 $ey {syms["scroll_y"]} $scroll] {{debug write memory $at $v}}',
        ' reg SP 0xc7f0;reg PC 0xc680','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::maze [debug read_block VRAM 0 65536]',
        *[f'debug write memory {0xc680+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc6b0 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Radar pair stack imbalance"}',
        ' puts -nonewline $::result [binary format c [debug read memory 0xc660]]',
        ' foreach slot {13 21} {',
        '  puts -nonewline $::result [debug read_block VRAM [expr {128512+4*$slot}] 4]',
        '  set p [debug read VRAM [expr {128514+4*$slot}]];puts -nonewline $::result [debug read_block VRAM [expr {129024+($p&252)*8}] 32]',' }',
        ' incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Radar pair VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Radar pair timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'msx.bin').read_bytes();size=73;merged=0
    if len(raw)!=size*len(cases):raise ValueError('Incomplete radar pair captures')
    for n,(x,y,ex,ey,scroll) in enumerate(cases):
        r=raw[n*size:(n+1)*size];wanted={(X+px+dx,Y+py+dy) for px,py in ((x,y),(ex,ey)) if px!=255 for dx in (0,1) for dy in (0,1)}
        expected_merged=x!=255 and ex!=255 and abs(x-ex)<=14 and abs(y-ey)<=13
        if bool(r[0])!=expected_merged:raise ValueError(f'Radar pair mode mismatch: {n}')
        merged+=bool(r[0]);actual=set()
        for part in (r[1:37],r[37:73]):
            ay,ax,p,_=part[:4];mask=part[4:]
            for sy in range(16):
                py=(ay+1-scroll+sy)&255
                if not 11<=py<212:continue
                for sx in range(16):
                    if mask[(sx//8)*16+sy]&(128>>(sx%8)):actual.add((ax+sx,py))
        if actual!=wanted:raise ValueError(f'Radar pair pixel mismatch: {n}, {cases[n]}, missing{sorted(wanted-actual)[:5]}, extra{sorted(actual-wanted)[:5]}')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(cases=len(cases),merged=merged,separate=len(cases)-merged,
        rom_sha256=digest(args.rom),strict_vram_timing=True,maze_vram_unchanged=True,
        scope='Executed two-red-dot packing, exact2x2 footprints, diagonal/delta boundaries, byte crossings, hidden points, sentinel phases and merged/separate transitions; full priority/RGB checked by natural route'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact paired/separate radar vectors: {out}/report.json')
    return out
