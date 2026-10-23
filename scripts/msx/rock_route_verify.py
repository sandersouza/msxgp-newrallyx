"""Real keyboard route: enter, pause on, leave and re-enter a rock, then restart."""
from collections import deque
import os
import subprocess

from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .rock_collision_verify import analyze,original_oracle


def route(cells,start,goal):
    pending=deque([start]);previous={start:None}
    while pending:
        x,y=pending.popleft()
        if (x,y)==goal:
            result=[];node=goal
            while node is not None:result.append(node);node=previous[node]
            return result[::-1]
        for dx,dy in ((0,-1),(1,0),(0,1),(-1,0)):
            n=(x+dx,y+dy)
            if 0<=n[0]<32 and 0<=n[1]<56 and cells[n[1]*32+n[0]]&0xf8==0 and n not in previous:
                previous[n]=(x,y);pending.append(n)
    raise ValueError('Original rock cell is unreachable from the driving spawn')


def verify(root,args):
    verify_manifest(args.rom.parent)
    info=read_json(args.rom.parent/'build.json')
    if info.get('incremental_stage')!=2:raise ValueError('Keyboard rock route requires stage 02')
    out=destination(root,args.output);require_ignored(root,[out/'contacts.tsv']);out.mkdir(parents=True)
    source=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    fixture=read_json(args.rom.parent/'stage-one.json')['rock_fixture']
    cache=root/'references/stage-one/rocks-v1'
    verify_manifest(cache)
    if digest(cache/'manifest.json')!=fixture['manifest_sha256']:
        raise ValueError('Keyboard route does not match the bound original rock fixture')
    board=(cache/'work.bin').read_bytes()[:1792]
    rock=fixture['positions'][0];path=route(board,(15,50),(rock['cell_x'],rock['cell_y']))
    masks={(0,-1):32,(1,0):128,(0,1):64,(-1,0):16}
    points=' '.join('{'+f'{36+x*24} {36+y*24} {masks[(x-a,y-b)]}'+'}'
                    for (a,b),(x,y) in zip(path,path[1:]))
    forward=masks[(path[-1][0]-path[-2][0],path[-1][1]-path[-2][1])]
    reverse={32:64,64:32,128:16,16:128}[forward]
    syms=symbols(args.rom.parent/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set speed 100','set throttle on','set vsync off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set pause_on_lost_focus false','set minframeskip 0','set maxframeskip 0',
        'activate_input_layer -blocking rock_route',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)};set points {{{points}}};set forward {forward};set reverse {reverse}',
        'set target 0;set phase navigate;set held 0;set frames 0;set contact_index 0',
        'set trace [open [file join $out contacts.tsv] w];set events [open [file join $out events.tsv] w]',
        'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
        'proc signed {v} {expr {$v>127?$v-256:$v}}',
        'proc keys {mask} {keymatrixup 8 255;if {$mask!=0} {keymatrixdown 8 $mask}}',
        f'debug set_bp {syms["Rock_Update"]} {{[reg IM]==2}} {{set ::begin [machine_info time]}}',
        f'debug set_bp {syms["Player_AfterRock"]} {{[reg IM]==2}} {{',
        ' puts $::trace "$::contact_index [debug read memory 0xc480] [u16 0xc482] [u16 0xc486] [u16 0xc484] [expr {round(([machine_info time]-$::begin)*3579545)}] [expr {[u16 0xc440]+1}] [u16 0xe079] [debug read memory 0xe06d] [debug read memory 0xe06f]"',
        ' incr ::contact_index', '}',
        'proc step {} {',
        ' incr ::frames',
        ' set count [u16 0xc482];set contact [debug read memory 0xc480];set paused [debug read memory 0xc009]',
        ' puts $::events "$::frames $::phase $count $contact $paused"',
        ' switch $::phase {',
        ' navigate {',
        '  if {$count==1} {if {$contact!=1} {error "Unexpected rock reached"};keys 1;set ::phase pause1;set ::held 0;return}',
        '  set x [expr {36+24*[debug read memory 0xe070]+[signed [debug read memory 0xe06d]]}]',
        '  set y [expr {36+24*[debug read memory 0xe072]-[signed [debug read memory 0xe06f]]}]',
        '  lassign [lindex $::points $::target] tx ty mask',
        '  if {abs($tx-$x)<=6 && abs($ty-$y)<=6 && $::target<[llength $::points]-1} {incr ::target;lassign [lindex $::points $::target] tx ty mask}',
        '  keys $mask',
        ' }',
        ' pause1 {',
        '  if {$count!=1} {error "Contact repeated while paused"}',
        '  keys 0',
        '  if {$paused} {incr ::held}',
        '  if {$::held==60} {keys [expr {1|$::reverse}];set ::phase leave}',
        ' }',
        ' leave {keys $::reverse;if {$contact==0} {keys $::forward;set ::phase reenter}}',
        ' reenter {keys $::forward;if {$count==2} {keys 1;set ::phase pause2;set ::held 0}}',
        ' pause2 {',
        '  if {$count!=2} {error "Re-entry repeated while paused"}',
        '  keys 0;if {$paused} {incr ::held}',
        '  if {$::held==60} {keys 2;set ::phase restart}',
        ' }',
        ' restart {',
        '  keys 0;if {$count!=0 || $contact!=0 || [u16 0xc484]!=0} {error "Restart did not clear rock events"}',
        '  if {[u16 0xc440]!=0 || !$paused} {error "Paused restart state changed"}',
        '  keys 1;set ::phase resumed',
        ' }',
        ' resumed {',
        '  keys 0;if {$count!=0 || $contact!=0 || [u16 0xc440]==0} {error "First restarted tick has stale rock state"}',
        '  close $::trace;close $::events;exit 0',
        ' }',
        ' }',
        ' if {$::frames>1800} {error "Keyboard route failed to reach/re-enter the rock"}',
        '}',
        'debug set_watchpoint write_mem 0xc000 {$wp_last_value==2 && [reg IM]==2} {if {[catch {step} problem]} {puts stderr $problem;exit 2}}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Rock route VRAM timing violation";exit 2}',
        'after time 60 {puts stderr "Keyboard rock route timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')),
            stdout=log,stderr=subprocess.STDOUT)
    records=[list(map(int,r.split())) for r in (out/'contacts.tsv').read_text().splitlines()]
    if not records or any(len(r)!=10 for r in records):raise ValueError('Incomplete live rock contact trace')
    cases=[(r[7],r[8],r[9]) for r in records]
    resets={i for i,r in enumerate(records) if i and r[6]<=records[i-1][6]}
    rock_data=(args.rom.parent/'rock-cells.bin').read_bytes()
    rocks=[int.from_bytes(rock_data[i:i+2],'little') for i in (0,2)]
    version=original_oracle(root,out,cases,rock_data)
    report=analyze(cases,rocks,(out/'original.bin').read_bytes(),[r[:6] for r in records],resets=resets)
    phases=[r.split()[1] for r in (out/'events.tsv').read_text().splitlines()]
    if any(p not in phases for p in ('pause1','leave','reenter','pause2','restart')) or len(resets)!=1:
        raise ValueError('Incomplete physical keyboard contact/restart scenario')
    verify_manifest(args.rom.parent)
    if source!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):
        raise ValueError('Source ROMs changed during keyboard route')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('BIOS changed during keyboard route')
    report.update(rom_sha256=digest(args.rom),keyboard_only=True,source_state_writes=False,
        route_cells=len(path),restart_count=len(resets),mame_version=version,
        scope='Real keyboard entry/pause/departure/re-entry/restart; every live logical contact compared with original Z80; elapsed call times include interrupts; RGB not captured')
    json_write(out/'report.json',report);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Keyboard rock entry/re-entry/restart and {len(cases)} original contacts: {out}/report.json')
    return out
