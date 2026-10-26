#!/usr/bin/env python3
"""Measure fixed native-tick workloads, separating actual raster IRQ time.

Explicit actor fixtures isolate CPU scaling; these are not natural gameplay.
The complete HUD and real VDP limits remain enabled. Original data stays ignored.
"""
import argparse
import os
from pathlib import Path
import re
from statistics import median
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.enemy_navigation import original_maps
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--capture',type=Path,default=Path('references/build/issue12-stutter-route-v125'))
    p.add_argument('--iterations',type=int,default=100)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);verify_manifest(args.capture)
    if not read_json(bundle/'build.json')['hud_enabled']:raise ValueError('Tick benchmark requires HUD')
    if args.iterations<100:raise ValueError('Require at least 100 samples per group')
    fixture=next(path for path in sorted(args.capture.glob('*.state'),key=lambda p:int(p.stem))
        if (lambda d:d[0x21b0]==7 and d[0x490]==d[0x724]==d[0x5b0]==0)(path.read_bytes()))
    out=destination(root,args.output);require_ignored(root,[out/'fixture.bin']);out.mkdir(parents=True)
    seed=fixture.read_bytes();(out/'fixture.bin').write_bytes(seed);s=symbols(bundle/'raster-scroll.sym')
    page=seed[0x228f]&3
    navigation=original_maps((bundle/'native-program.bin').read_bytes())[page*2048:][:1792]
    (out/'navigation.bin').write_bytes(navigation)
    px,py=seed[0x2070],seed[0x2072]
    actor_cells=[]
    for corridor in (False,True):
        candidates=[(x,y) for y in range(56) for x in range(32)
            if 3<=abs(x-px)+abs(y-py)<=12 and navigation[y*32+x] and
            (navigation[y*32+x] in (5,10) if corridor else navigation[y*32+x].bit_count()>=3)]
        candidates.sort(key=lambda q:(abs(q[0]-px)+abs(q[1]-py),q))
        if len(candidates)<7:raise ValueError('Not enough declared actor fixture cells')
        for x,y in candidates[:7]:
            heading=next(d for d in range(4) if navigation[y*32+x]&(1<<d))
            actor_cells.extend((x,y,heading))
    (out/'actor-cells.bin').write_bytes(bytes(actor_cells))
    rom=args.rom.read_bytes();start=s['irq_return'];stop=s['register']
    reti=start+rom[start-0x4000:stop-0x4000].index(bytes.fromhex('ed4d'))
    entry=s['Player_Tick'];bank=s['PLAYER_BANK']
    phases=2 if s.get('Full_MSXEnemyMotionDivisor',1)==2 else 1
    code_ranges=[(s[a],s[b]-s[a]) for a,b in (
        ('Full_RadarIRQStart','Full_RadarIRQEnd'),
        ('Full_PresentStart','Full_PresentEnd')) if a in s and b in s]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set vsync off',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked true','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        f'set iterations {args.iterations};set phases {phases};set index 0;set started 0;set irq_total 0',
        'set f [open [file join $out fixture.bin] rb];set fixture [read $f];close $f',
        'set f [open [file join $out actor-cells.bin] rb];binary scan [read $f] cu* actor_cells;close $f',
        'set f [open [file join $out navigation.bin] rb];set tick_navigation [read $f];close $f',
        'set costs [open [file join $out costs.tsv] w];set profile [open [file join $out profile.tsv] w]',
        f'debug set_bp {s["interrupt"]} {{$::started}} {{set ::irq_begin [machine_info time]}}',
        f'debug set_bp {reti} {{$::started && [info exists ::irq_begin]}} {{set ::irq_total [expr {{$::irq_total+[machine_info time]-$::irq_begin}}];unset ::irq_begin}}',
        'proc issue {} {',
        ' if {$::index==28*$::iterations*$::phases} {close $::costs;close $::profile;exit 0;return}',
        ' set ::count [expr {($::index/$::iterations)%7+1}];set ::tick_case_mode [expr {($::index/(7*$::iterations))%4}];set ::tick_phase [expr {$::index/(28*$::iterations)}]',
        ' debug write_block memory 0xe000 [string range $::fixture 8192 12287]',
        ' foreach {start end} {1024 1279 1328 1503} {debug write_block memory [expr {0xc000+$start}] [string range $::fixture $start $end]}',
        # An older gameplay fixture contains data where this candidate now has
        # executable code. Restore current initialized code, never old opcodes.
        ' foreach {at bytes} $::tick_code {debug write_block memory $at $bytes}',
        ' foreach {at value} [list 0xc400 1 0xc490 0 0xc49a 0 0xc724 0 0xc5b0 0 0xc701 0 0xc7d0 0 0xc7ee 0 0xe24e $::count 0xe3f0 255] {debug write memory $at $value}',
        f' debug write memory {s["Full_LoopTicks"]} 0',
        f' debug write memory {s["player_native_ticks"]} $::tick_phase',
        *([f' debug write_block memory {s["Full_MSXDecision"]} [string repeat [binary format c 255] 14]'] if 'Full_MSXDecision' in s else []),
        ' set px [debug read memory 0xe070];set py [debug read memory 0xe072]',
        ' for {set i 0} {$i<7} {incr i} {',
        '  set at [expr {0xe088+$i*32}];set fine [expr {$::tick_case_mode==2?12:($::index%7)-3}]',
        '  lassign [lrange $::actor_cells [expr {($i+7*($::tick_case_mode==2))*3}] [expr {($i+7*($::tick_case_mode==2))*3+2}]] ax ay heading',
        '  set velocity [expr {$::tick_case_mode==0?0:($heading>=2?-656:656)}]',
        '  set fx [expr {$::tick_case_mode==2?(($heading&1)?($heading==3?-$fine:$fine):0):$fine}]',
        '  set fy [expr {$::tick_case_mode==2?(($heading&1)?0:($heading==2?-$fine:$fine)):$fine}]',
        '  foreach {offset value} [list 0 [expr {$::tick_case_mode==3?128:0}] 1 [expr {$velocity&255}] 2 [expr {$velocity>>8}] 3 [expr {$heading&1?255:0}] 4 0 5 $fx 6 0 7 $fy 8 $ax 10 $ay 11 0 12 80 13 0 14 80 19 [expr {$::tick_case_mode==3?130:0}] 21 [expr {$::tick_case_mode==3?1:0}]] {debug write memory [expr {$at+$offset}] [expr {$value&255}]}',
        ' }',
        ' for {set i 0} {$i<5} {incr i} {set a [expr {$i<$::count?0xe093+$i*32:0}];debug write memory [expr {0xe004+$i*2}] [expr {$a&255}];debug write memory [expr {0xe005+$i*2}] [expr {$a>>8}]}',
        f' debug write memory 0x7000 {bank}',
        f' set at 0xd140;foreach value {{243 205 {entry&255} {entry>>8} 195 80 209}} {{debug write memory $at $value;incr at}}',
        ' reg SP 0xf380;reg PC 0xd140;set ::begin [machine_info time];set ::irq_before $::irq_total','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{set ::started 1;set ::tick_code [list '+
        ' '.join(f'{at} [debug read_block memory {at} {size}]' for at,size in code_ranges)+
        f'];set ::terrain [debug read_block VRAM 0 65536];foreach device [debug list] {{if {{[debug desc $device] eq "memory mapper" && [debug size $device]>=131072}} {{set at [expr {{([debug read memory {s["Full_CacheSegment"]}]&([debug size $device]/16384-1))*16384+12288}}];debug write_block $device $at $::tick_navigation;break}}}};if {{[catch issue problem]}} {{puts stderr $problem;exit 2}}}}',
        'debug set_bp 0xd150 {$::started} {',
        ' if {[reg SP]!=0xf380 || [debug read_block VRAM 0 65536] ne $::terrain} {error "Native tick changed stack or terrain"}',
        ' set wall [expr {([machine_info time]-$::begin)*1000}];set irq [expr {($::irq_total-$::irq_before)*1000}]',
        ' puts $::costs "$::count $::tick_case_mode $::tick_phase $wall $irq";incr ::index;if {[catch issue problem]} {puts stderr $problem;exit 2}','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Tick benchmark VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Tick benchmark timeout";exit 2}']
    names={'Enemy_PreMove':'oam_cleanup','Enemy_AfterMove':'after_move','Fuel_Tick':'fuel',
           '$8069':'motion','$9052':'steering','$b600':'ai','$95bd':'visibility','$838a':'contact'}
    for row in (bundle/'raster-scroll.lst').read_text().splitlines():
        m=re.search(r'[+\s]([0-9A-F]{4}) (?:CD|C4|CC|D4|DC|E4|EC|F4|FC) [0-9A-F]{2} [0-9A-F]{2}\s+call (?:[a-z]+,)?([\w$]+)',row)
        if not m or m[2] not in names:continue
        address=int(m[1],16);name=names[m[2]]
        lines.extend([f'debug set_bp {address} {{$::started}} {{set ::profile_{name} [machine_info time];set ::irq_{name} $::irq_total}}',
            f'debug set_bp {address+3} {{$::started && [info exists ::profile_{name}]}} {{puts $::profile "{name} $::count $::tick_case_mode [expr {{([machine_info time]-$::profile_{name}-($::irq_total-$::irq_{name}))*1000}}]";unset ::profile_{name}}}'])
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=[list(map(float,line.split())) for line in (out/'costs.tsv').read_text().splitlines()]
    if len(rows)!=28*args.iterations*phases:raise ValueError('Incomplete native workload measurements')
    results=[]
    for mode in range(4):
        for count in range(1,8):
            values=sorted(wall-irq for n,m,phase,wall,irq in rows if (n,m)==(count,mode))
            results.append(dict(actors=count,mode=mode,median_cpu_ms=median(values),p95_cpu_ms=values[int(.95*len(values))-1]))
    verify_manifest(bundle);verify_manifest(args.capture)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),fixture_capture_manifest_sha256=digest(args.capture/'manifest.json'),fixture_file=fixture.name,results=results,
        samples_per_cadence_phase=args.iterations,cadence_phases=phases,
        modes=['zero initial velocity','moving intersection','moving between intersections','stunned'],
        scope='Fixed authored actor workloads from one declared gameplay seed; both enemy cadence phases sampled equally where applicable; current initialized executable RAM preserved; actual raster time subtracted; terrain/stack unchanged. Not natural gameplay.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'Native tick scaling measured: {out}/report.json')


if __name__=='__main__':main()
