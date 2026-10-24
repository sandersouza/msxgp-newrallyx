#!/usr/bin/env python3
"""HUD-enabled dynamic-round scene probe with explicitly seeded transitions."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.stage_one import acquire,cells_from_rom,tile,bitmap,TILE_COLUMNS,TILE_ROWS
from scripts.msx.player import padded_world
from scripts.msx.player_verify import check_cache
from scripts.msx.screen5 import packed
from scripts.msx.raster_scroll import header
from scripts.scenes.bundle import load_assets,verify_manifest,digest
from scripts.scenes.storage import json_write,require_ignored,seal
from scripts.msx.full_memory import irq_image


def world(program,video,active,assets,palette):
    page=video[0x28f]&127
    cells=bytearray(cells_from_rom(program,page))
    def addresses(at,count):
        p=int.from_bytes(video[at:at+2],'little')-0xe000
        if not 0<=p<=4096-count*2:raise ValueError('Invalid dynamic object pointer')
        return [int.from_bytes(video[i:i+2],'little')-0x9800 for i in range(p,p+count*2,2)]
    for i,cell in enumerate(addresses(0x992,10),1):
        if active[i]:cells[cell]=1 if i<9 else 4 if i==9 else 2
    for cell in addresses(0x996,video[0x251]):cells[cell]=3
    pairs=[tile(program,cells,x-3,y-3,video[0x2b1],video[0x2d6])
           for y in range(TILE_ROWS) for x in range(TILE_COLUMNS)]
    return bitmap(pairs,assets,palette)


def check_header(state,vram,assets,palette):
    def value(at):
        packet=state[at:at+8]
        return int(''.join(str(packet[i]&15) for i in (4,5,6,7,0,1,2,3)))
    expected=packed(header(assets,palette,value(0x20a0),value(0x2060),
        player=state[0x7ec]+1,full_game=True,round_=(state[0x21b0]-1)&255))
    actual=vram[0x10000:0x10400]
    if actual!=expected:
        at=next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b)
        raise ValueError(f'Complete eight-digit/round header mismatch at byte {at}')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rounds',type=int,choices=range(1,255),default=4)
    p.add_argument('--headless',action='store_true')
    p.add_argument('--bios',type=Path,default=Path('references/msxbios'))
    p.add_argument('--machine',default='Panasonic_FS-A1WSX');p.add_argument('--openmsx',default='openmsx')
    args=p.parse_args(argv);root=Path(__file__).resolve().parents[1]
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    out=destination(root,args.output);require_ignored(root,[out/'1.state']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym')
    irq=irq_image(bundle,syms);irq_at=syms.get('Full_RadarIRQStart',0)-0xc000
    lines=['set save_settings_on_exit false','set sound_driver null',
        *(['set renderer none'] if args.headless else []),
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set throttle off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked true','set cmdtiming real','set limitsprites true',
        'set gamma 1','set brightness 0','set contrast 0','set blur 0','set noise 0','set scanline 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','activate_input_layer -blocking full_probe',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set started 0;set phase boot;set age 0;set count 0;set polls 0',
        f'debug set_bp {syms["startup_mode"]} {{!$::started}} {{set ::started 1}}',
        'proc step {} {',
        ' incr ::polls;incr ::age;if {$::polls>60000} {error "Full round probe timeout: $::phase"}',
        ' if {!$::started} {return}',
        ' set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]',
        ' switch $::phase {',
        ' boot {if {$state==1 && $ready} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}',
        ' coin {if {$::age==4} {keymatrixup 0 32;set ::phase release;set ::age 0}}',
        ' release {if {$::age==4} {keymatrixdown 0 2;set ::phase start;set ::age 0}}',
        ' start {if {$::age==4} {keymatrixup 0 2};if {$state==0} {keymatrixdown 4 32;set ::phase pause;set ::age 0}}',
        ' pause {if {$::age==4} {keymatrixup 4 32};if {[debug read memory 0xc009] && $::age>20} {set ::phase capture;set ::age 0}}',
        ' capture {if {$::age==20} {',
        '  incr ::count;set n $::count',
        '  if {[debug read memory 0xe1b0]!=$n+1} {error "Round progression did not preserve the original counter"}',
        '  set f [open [file join $::out "$n.state"] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
        '  set f [open [file join $::out "$n.vram"] wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f',
        *([] if args.headless else ['  screenshot -raw -size auto [file join $::out "$n.png"]']),
        f'  if {{$n=={args.rounds}}} {{exit 0}}',
        '  debug write memory 0xc724 3;set ::phase transition;set ::age 0',
        ' }}',
        ' transition {if {$state==0 && [debug read memory 0xe1b0]==$::count+2} {set ::phase capture;set ::age 0}}',
        ' }', '}',
        'proc poll {} {if {[catch {step} problem]} {puts stderr $problem;exit 2};after time 0.02 poll}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Full scene VRAM timing violation";exit 2}',
        'after time 1200 {puts stderr "Full scene wall timeout";exit 2}','after time 0.02 poll']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    program,_=acquire(root);assets=load_assets(root/'references/assets/nrallyx')
    palette=(bundle/'palette.bin').read_bytes()
    for n in range(1,args.rounds+1):
        state=(out/f'{n}.state').read_bytes();video=state[0x2000:0x3000]
        if irq and state[irq_at:irq_at+len(irq)]!=irq:raise ValueError('Round reload overwrote raster IRQ code')
        image=world(program,video,state[0x534:0x53f],assets,palette)
        data,width,_=padded_world(image)
        wx=int.from_bytes(state[0xb0:0xb2],'little');wy=int.from_bytes(state[0xb2:0xb4],'little')
        check_cache((out/f'{n}.vram').read_bytes(),packed(data),width,wx,wy,n)
        check_header(state,(out/f'{n}.vram').read_bytes(),assets,palette)
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),rounds=args.rounds,
        headless=args.headless,scope='Real credit/start, then explicitly seeded completion endpoints; original dynamic map and visible cache checked. Natural completion and full match remain separate.'))
    require_ignored(root,[x for x in out.rglob('*') if x.is_file()]);seal(out)
    print(f'{args.rounds} dynamic round scenes and cache states pass: {out}')


if __name__=='__main__':main()
