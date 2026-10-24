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
    p.add_argument('--bios',type=Path,default=Path('references/msxbios'))
    p.add_argument('--machine',default='Panasonic_FS-A1WSX');p.add_argument('--openmsx',default='openmsx')
    args=p.parse_args(argv);root=Path(__file__).resolve().parents[1]
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
    if args.profile:
        lines.append('set profile_out [open [file join $out profile.tsv] w]')
        names={'keys','stage_position','HUD_PrepareEarlyCoordinates','Enemy_Prepare','Enemy_Draw','Full_EnemyFrame',
               'HUD_FinishCoordinates','Player_AdvanceEarly','HUD_PrepareFrame','HUD_DrawContent',
               'Player_Advance','Radar_WaitPublish','stage_stream'}
        for row in (bundle/'raster-scroll.lst').read_text().splitlines():
            match=re.search(r'\s([0-9A-F]{4}) CD [0-9A-F]{2} [0-9A-F]{2}\s+call (\w+)',row)
            if not match or match[2] not in names:continue
            address=int(match[1],16);name=match[2]
            if address>=0x4300:continue
            lines.extend([f'debug set_bp {address} {{$::phase eq "game"}} {{set ::profile_{name} [machine_info time]}}',
                f'debug set_bp {address+3} {{$::phase eq "game" && [info exists ::profile_{name}]}} {{puts $::profile_out "{name} $::frames [expr {{([machine_info time]-$::profile_{name})*3579545}}] [debug read memory 0xc5e8]"}}'])
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
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=240,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=[list(map(int,line.split())) for line in (out/'events.tsv').read_text().splitlines()]
    if not rows or max(r[1] for r in rows)<args.rounds+2:raise ValueError('Natural round completion evidence missing')
    headers=verify_header_reservations(out/'headers.tsv',313*228/3579545)
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),natural_completed_rounds=args.rounds,
        refreshes=len(rows),header_reservations=headers,maximum_smoke_placements=max(r[6] for r in rows),
        scope='Real keyboard credit/start, steering and smoke; no guest-state writes. Dynamic sprite/cache images require separate scene checks.'))
    require_ignored(root,[x for x in out.rglob('*') if x.is_file()]);seal(out)
    print(f'{args.rounds} naturally completed rounds: {out}/report.json')


if __name__=='__main__':main()
