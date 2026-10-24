#!/usr/bin/env python3
"""Drive full-game rounds through real credit/start, steering and smoke inputs."""
import argparse
import os
import re
from pathlib import Path
import subprocess
import sys

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.stage_one import acquire,cells_from_rom
from scripts.msx.completion_route_verify import verify_header_reservations
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rounds',type=int,choices=range(1,255),default=2)
    p.add_argument('--avoid-enemies',action='store_true',help='Route around current enemy cells using host-side BFS')
    p.add_argument('--profile',action='store_true',help='Observe main-loop call durations without guest writes')
    p.add_argument('--trace-di',action='store_true',help='Observe interrupt-masked intervals without guest writes')
    p.add_argument('--radar-trace',action='store_true',help='Compare live radar SAT against latched R23 before each visible band')
    p.add_argument('--require-stable-radar',action='store_true')
    p.add_argument('--bios',type=Path,default=Path('references/msxbios'))
    p.add_argument('--machine',default='Panasonic_FS-A1WSX');p.add_argument('--openmsx',default='openmsx')
    args=p.parse_args(argv);root=Path(__file__).resolve().parents[1]
    if args.require_stable_radar and not args.radar_trace:raise ValueError('Stable radar gate requires --radar-trace')
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    out=destination(root,args.output);require_ignored(root,[out/'board-0.bin']);out.mkdir(parents=True)
    program,_=acquire(root)
    for i in range(4):(out/f'board-{i}.bin').write_bytes(cells_from_rom(program,0x30+i))
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set throttle off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'activate_input_layer -blocking full_route',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)};set rounds {args.rounds};set avoid_enemies {int(args.avoid_enemies)}',
        'for {set i 0} {$i<4} {incr i} {set f [open [file join $out "board-$i.bin"] rb];set boards($i) [read $f];close $f}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Full route VRAM timing violation";exit 2}',
        'after time 900 {puts stderr "Full route emulated timeout";exit 2}']
    script=(root/'scripts/msx/full-route-probe.tcl').read_text().replace('@SHOW_SCENE@',str(syms['show_scene']))
    if 'Full_RadarIRQStart' in syms:
        lines.extend([
            f'debug set_watchpoint write_mem {{{syms["Full_RadarIRQStart"]} {syms["Full_RadarIRQEnd"]-1}}} {{[info exists ::phase] && $::phase eq "game"}} {{',
            'puts stderr "Raster IRQ RAM overwritten: $::wp_last_address value=$::wp_last_value PC=[reg PC] frame=$::frames";exit 2',
            '}',
        ])
    if args.radar_trace:
        (out/'radar-table.bin').write_bytes((bundle/f'bank-{syms["RADAR_SAT_BANK"]}.bin').read_bytes())
        lines.extend([
            'set f [open [file join $out radar-table.bin] rb];set radar_table [read $f];close $f',
            'set radar_samples 0;set radar_mismatches 0;set radar_out [open [file join $out radar.tsv] w]',
            'proc radar_sample {band} {',
            ' if {$::phase ne "game" || [debug read memory 0xc7d0]!=0 || [debug read memory 0xc5c1]} {return}',
            ' incr ::radar_samples;set scroll [debug read {VDP regs} 23]',
            f' set offset [expr {{$scroll*64+4+$band*12}}];set address [expr {{0x1f604+$band*12}}]',
            ' set actual [debug read_block VRAM $address 12]',
            ' set expected [string range $::radar_table $offset [expr {$offset+11}]]',
            ' if {$actual ne $expected} {incr ::radar_mismatches;puts $::radar_out "$::frames $band $scroll [binary encode hex $actual] [binary encode hex $expected]"}',
            '}',
            f'set radar_x {syms["RADAR_X"]};set radar_y {syms["RADAR_Y"]};set radar_pattern {syms["RADAR_PLAYER_PATTERN"]}',
            r'''proc radar_dot_sample {} {
 if {$::phase ne "game" || [debug read memory 0xc7d0]!=0 || [debug read memory 0xc5c1]} {return}
 incr ::radar_samples;set scroll [debug read {VDP regs} 23]
 binary scan $::radar_point cu* point;lassign $point x y
 if {$x==255} {set y 192}
 set sy [expr {($scroll+$::radar_y-1+$y)&255}];set pattern $::radar_pattern
 if {$sy==216} {incr sy -1;incr pattern 4}
 set expected [binary format c* [list $sy [expr {($x+$::radar_x)&255}] $pattern 0]]
 set actual [debug read_block VRAM 0x1f600 4]
 if {$actual ne $expected} {incr ::radar_mismatches;puts $::radar_out "$::frames -1 $scroll [binary encode hex $actual] [binary encode hex $expected]"}
}''',
            (f'debug set_bp {syms["Full_RadarIRQ"]} {{$::phase eq "game" && !$::skip_headers}} {{' if 'Full_RadarIRQ' in syms else
             'debug set_watchpoint write_mem 0xc03c {$wp_last_value==4 && $::phase eq "game" && !$::skip_headers} {'),
            *([f'set ::radar_point [debug read_block memory {syms["Radar_PlayerPoint"]} 2]',
                f'after time {(syms["RADAR_Y"]+2-3-9)*228/3579545:.10f} radar_dot_sample'] if 'Full_RadarIRQ.point' in syms else []),
            *[f' after time {(syms["RADAR_Y"]+band*15-3-9)*228/3579545:.10f} {{radar_sample {band}}}' for band in range(4)],
            '}',
        ])
    if args.profile:
        lines.append('set profile_out [open [file join $out profile.tsv] w]')
        names={'keys','stage_position','HUD_PrepareEarlyCoordinates','Enemy_Prepare','Enemy_Draw','Full_EnemyFrame',
               'HUD_FinishCoordinates','Player_AdvanceEarly','HUD_PrepareFrame','HUD_DrawContent',
               'Player_Advance','Radar_WaitPublish','stage_stream','Enemy_PreMove','Enemy_AfterMove',
               'Full_NativeAI','FullEnemy_PrepareOne','FullEnemy_DrawOne','Smoke_Tick','Fuel_Tick'}
        for row in (bundle/'raster-scroll.lst').read_text().splitlines():
            match=re.search(r'[+\s]([0-9A-F]{4}) CD [0-9A-F]{2} [0-9A-F]{2}\s+call (\w+)',row)
            if not match or match[2] not in names:continue
            address=int(match[1],16);name=match[2]
            lines.extend([f'debug set_bp {address} {{$::phase eq "game"}} {{set ::profile_{name} [machine_info time]}}',
                f'debug set_bp {address+3} {{$::phase eq "game" && [info exists ::profile_{name}]}} {{puts $::profile_out "{name} $::frames [expr {{([machine_info time]-$::profile_{name})*3579545}}] [debug read memory 0xe1b0]"}}'])
    if args.trace_di:
        lines.extend(['set di_out [open [file join $out di.tsv] w]',
            'proc di_begin {} {set ::di_begin [machine_info time];set ::di_pc [reg PC]}',
            'proc di_end {} {if {[info exists ::di_begin]} {set cycles [expr {([machine_info time]-$::di_begin)*3579545}];if {$cycles>500} {puts $::di_out "$::frames $::di_pc [reg PC] $cycles"};unset ::di_begin}}'])
        seen=set()
        for row in (bundle/'raster-scroll.lst').read_text().splitlines():
            match=re.search(r'[+\s]([0-9A-F]{4}) (F3|FB)\s+(di|ei)\b',row)
            if not match:continue
            address=int(match[1],16)
            if address in seen or 0x8000<=address<0xc000:continue
            seen.add(address)
            condition='$::phase eq "game" && ![debug read memory 0xc5c1] && [debug read memory 0xc7d0]==0'
            if match[3]=='di':condition+=' && ([reg IFF]&1)'
            lines.append(f'debug set_bp {address} {{{condition}}} {{di_{"begin" if match[3]=="di" else "end"}}}')
    if args.radar_trace:
        script=script.replace('exit 0','set f [open [file join $::out radar-counts.txt] w];puts $f "$::radar_samples $::radar_mismatches";close $f;exit 0')
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=240,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=[list(map(int,line.split())) for line in (out/'events.tsv').read_text().splitlines()]
    if not rows or max(r[1] for r in rows)<args.rounds+2:raise ValueError('Natural round completion evidence missing')
    headers=verify_header_reservations(out/'headers.tsv',313*228/3579545)
    radar=None
    if args.radar_trace:
        samples,mismatches=map(int,(out/'radar-counts.txt').read_text().split())
        radar=dict(samples=samples,mismatches=mismatches,player_dot='Full_RadarIRQ.point' in syms,
            scope='Live SAT before each band fetch against actual latched R23; dot uses its IRQ point snapshot')
        if args.require_stable_radar and (mismatches or not samples):raise ValueError('Fixed radar missed its scanline-coherence gate')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),natural_completed_rounds=args.rounds,
        refreshes=len(rows),header_reservations=headers,radar_coherence=radar,maximum_smoke_placements=max(r[6] for r in rows),
        scope='Real keyboard credit/start, steering and smoke; no guest-state writes. Dynamic sprite/cache images require separate scene checks.'))
    require_ignored(root,[x for x in out.rglob('*') if x.is_file()]);seal(out)
    print(f'{args.rounds} naturally completed rounds: {out}/report.json')


if __name__=='__main__':main()
