"""Keyboard-only enemy contact, explosion, pause and same-round restart proof."""
import os
import statistics
import subprocess

from src.toolchain.graphics.roms import input_records,load_metadata,validate_roms
from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl,scanout_recording_tcl
from .hud_verify import symbols
from .death_verify import verify_images
from .lives_route_verify import check_cache_frames


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    population=info.get('enemy_count',1);slots=info['sprites']['total_slots']
    sat_address='[expr {128512-2048*[debug read memory 0xc7c1]}]' if info.get('outline_flicker') else '128512'
    fuel_slot=next(iter(info['sprites']['life_reuses_fuel_slots']),0)
    if not info.get('enemy_contact_applies_death'):raise ValueError('Enemy route needs complete stage 08')
    out=destination(root,args.output);require_ignored(root,[out/'motion.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle on','set speed 100','set vsync off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set minframeskip 0','set maxframeskip 0','set gamma 1','set brightness 0','set contrast 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','set blur 0','set noise 0','set scanline 0',
        'activate_input_layer -blocking enemy_route',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set frames -1;set phase navigate;set held 0;set reload 0;set warmup 0;set shots 0;set capture 0;set gpu_count 0;set contact_index 0',
        'set hudflags [binary format c* {0 1 1 1 1 1 1 1 1 1 1}]',
        'foreach name {motion cache events times ticks reloads contacts occupancy presentation radar_queue} {set ${name}_out [open [file join $out "$name.bin"] wb]}',
        'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
        'proc keys {m} {keymatrixup 8 255;if {$m} {keymatrixdown 8 $m}}',
        'proc input {n} {if {$n<80} {keys 0} else {keys [lindex {128 32 16 64} [expr {int(($n-80)/220)%4}]]}}',
        'proc snapshot {} {',
        ' puts -nonewline $::motion_out [debug read_block memory 0xe000 4096];puts -nonewline $::motion_out [debug read_block memory 0xc400 96]',
        ' puts -nonewline $::motion_out [debug read_block memory 0xc0b0 4];puts -nonewline $::motion_out [debug read_block memory 0xc500 11]',
        ' puts -nonewline $::motion_out [debug read_block memory 0xc490 5];puts -nonewline $::motion_out [debug read_block memory 0xc5c0 3]',
        f' puts -nonewline $::presentation_out [debug read_block memory {info.get("death",{}).get("display_state_address",0xc490)} 1]',
        *([' puts -nonewline $::smoke_display_out [debug read_block memory 0xd300 2048]'] if (info.get('smoke_component') or {}).get('runtime_enabled') else []),
        *([' puts -nonewline $::smoke_counts_out [debug read_block memory 0xdb00 32]'] if (info.get('smoke_component') or {}).get('publication_counts_address') else []),
        *([' puts -nonewline $::smoke_rows_out [debug read_block memory 0xdb20 32]'] if (info.get('smoke_component') or {}).get('logical_row_presence_address') else []),
        *([f' puts -nonewline $::flag_display_out [debug read_block memory {info["flag_display_state_address"]} 11]'] if info.get('flag_display_state_address') else []),
        *([f' puts -nonewline $::radar_queue_out [debug read_block memory {info["hud_style"]["radar_dirty_state_address"]} 2];puts -nonewline $::radar_queue_out [debug read_block memory {syms["hud_flags_dirty"]} 2]'] if info.get('hud_style',{}).get('radar_dirty_state_address') else []),
        *([f' puts -nonewline $::radar_queue_out [debug read_block memory {info["hud_style"]["radar_ready_state_address"]} 2]'] if info.get('hud_style',{}).get('radar_ready_state_address') else []),
        ' puts -nonewline $::cache_out [debug read_block VRAM 0 65536]','}',
        'proc occupancy {} {',
        f' binary scan [debug read_block VRAM {sat_address} {slots*4}] cu* attrs',
        ' binary scan [debug read_block memory 0xc290 12] cu* footer;set sy [debug read memory 0xc01c];array set counts {};set peak 0',
        f' for {{set slot 0}} {{$slot<{slots}}} {{incr slot}} {{',
        '  foreach band {0 1} {',
        f'   set ay [lindex $attrs [expr {{$slot*4}}]];if {{$band && $slot>={fuel_slot} && $slot<={fuel_slot+2} && {int(info["hud_enabled"])}}} {{set ay [lindex $footer [expr {{($slot-{fuel_slot})*4}}]]}}',
        f'   if {{$ay==216}} {{error "Enemy SAT truncated before slot {slots}"}}',
        '   for {set row 0} {$row<16} {incr row} {set y [expr {($ay+1-$sy+$row)&255}];if {$y<11 || $y>=212 || ($band && $y<176) || (!$band && $y>=176)} {continue};if {![info exists counts($y)]} {set counts($y) 0};incr counts($y);if {$counts($y)>$peak} {set peak $counts($y)}}','  }',' }',
        f' if {{$peak>8 && {int(not bool(info.get("sprite_flicker") or info.get("allow_sprite_overflow")))}}} {{',
        '  set f [open [file join $::out sprite-budget-failure.txt] w];puts $f "frame $::frames scroll $sy peak $peak";puts $f "SAT $attrs";puts $f "footer $footer";foreach y [lsort -integer [array names counts]] {if {$counts($y)>8} {puts $f "row $y count $counts($y)"}};close $f',
        '  set f [open [file join $::out sprite-budget-failure.state] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
        '  error "Enemy sprite-line budget exceeded: $peak"',' };puts $::occupancy_out "$::frames $peak"','}',
        'debug probe set_bp VDP.commandExecuting {[info exists ::begin] && [debug probe read VDP.commandExecuting]} {incr ::gpu_count}',
        f'debug set_bp {syms["Player_Radar"]} {{[reg IM]==2}} {{set ::hudflags [debug read_block memory 0xc500 11]}}',
        f'debug set_bp {syms["show_scene"]} {{[info exists ::begin]}} {{set ::reload 1;set ::reload_begin [machine_info time];set ::warmup 3}}',
        'debug set_bp 0x838a {[reg IM]==2} {',
        ' set px [debug read memory 0xe074];set py [debug read memory 0xe076];set ex [debug read memory 0xe094];set ey [debug read memory 0xe096]',
        ' set dx [expr {(($ex-$px+128)&255)-128}];set dy [expr {(($ey-$py+128)&255)-128}];set registered 0',
        ' for {set a 0xe004} {$a<0xe00e} {incr a 2} {if {[u16 $a]==0xe093} {set registered 1}}',
        ' set ::expected_contact [expr {$registered && !([debug read memory 0xe093]&1) && abs($dx)<11 && abs($dy)<11}]',
        ' set ::contact_input "$dx $dy $registered [debug read memory 0xe093]"','}',
        f'debug set_bp {syms["Enemy_AfterMoveDone"]} {{[reg IM]==2}} {{',
        ' set actual [debug read memory 0xc5d0]',
        ' if {$actual!=$::expected_contact} {puts stderr "Live enemy contact differs from source boundary";exit 2}',
        ' puts $::contacts_out "$::contact_index $::contact_input $actual";incr ::contact_index','}',
        f'debug set_bp {syms["Player_CountTick"]} {{[reg IM]==2}} {{puts $::ticks_out "[u16 0xc440] [debug read memory 0xc490] [debug read memory 0xc491] [debug read memory 0xc5d0] [debug read memory 0xc480] [debug read memory 0xe00f]"}}',
        'proc step {} {',
        ' incr ::frames;set state [debug read memory 0xc490];set age [debug read memory 0xc491];set deaths [debug read memory 0xc5c2];set paused [debug read memory 0xc009]',
        ' puts $::events_out "$::frames $::phase $state $age $deaths $paused $::reload $::warmup $::gpu_count"',
        ' snapshot;occupancy',
        ' if {$::reload} {puts $::reloads_out "$::frames [expr {1000*([machine_info time]-$::reload_begin)}]"}',
        ' if {$::warmup} {incr ::warmup -1}',
        ' if {$::frames%60==0} {set ::capture 1}',
        ' switch $::phase {',
        ' navigate {',
        '  if {$deaths} {',
        '   if {$deaths!=1 || ![debug read memory 0xc5d0] || [debug read memory 0xc480] || [debug read memory 0xe00f]!=2} {error "Expected one enemy death, no rock contact"}',
        '   set ::retained [debug read_block memory 0xc500 11];set ::score [debug read_block memory 0xe0a0 8];keys 1;set ::phase pause;set ::held 0;set ::capture 1',
        '  } else {input [expr {$::frames+1}]}',' }',
        ' pause {',
        '  keys 0',
        '  if {$paused} {',
        '   set value [list $age [u16 0xc440] [debug read_block memory 0xe068 64]]',
        '   if {$::held==0} {set ::frozen $value} elseif {$value ne $::frozen} {error "Paused enemy/death moved"}',
        '   incr ::held;if {$::held==4 || $::held==40} {set ::capture 1}',
        '   if {$::held==40} {keys 1;set ::phase hold}','  }',' }',
        ' hold {',
        '  keys 0',
        '  if {$state==0} {',
        '   if {$deaths!=1 || [debug read memory 0xe00f]!=2 || [debug read memory 0xc5d0] || [debug read memory 0xe24e]!=1 || [debug read_block memory 0xc500 11] ne $::retained || [debug read_block memory 0xe0a0 8] ne $::score} {error "Enemy restart lost retained state"}',
        '   set ::phase restarted;set ::held 0;set ::capture 1','  }',' }',
        ' restarted {keys 0;incr ::held;if {$::held==6 || $::held==19} {set ::capture 1};if {$::held==20} {keys 2;set ::phase home;set ::held 0}}',
        ' home {',
        '  keys 0;incr ::held',
        '  if {$state || $deaths || [debug read memory 0xe00f]!=3 || [debug read memory 0xc50b]} {error "Home did not reset enemy fixture"}',
        '  if {$::held==3} {set ::capture 1}',
        '  if {$::held==6} {set ::done 1;foreach n {motion cache events times ticks reloads contacts occupancy presentation radar_queue} {close [set ::${n}_out]};after frame {exit 0}}',' }',' }',
        ' if {$::frames>1800} {error "Enemy keyboard route timeout"}','}',
        'proc capture {n} {screenshot -raw -size auto [file join $::out "$n.png"]}',
        'proc footer {} {',
        ' set state [debug read memory 0xc490];set age [debug read memory 0xc491]',
        ' set key "$state-$age";if {$state==1 && $age in {1 60 119} && ![info exists ::seen($key)]} {set ::seen($key) 1;set ::capture 1}',
        ' if {$::capture && !$::reload && !$::warmup} {',
        '  set ::capture 0;set n [incr ::shots]',
        '  foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] hudflags $::hudflags] {set f [open [file join $::out "$n.$ext"] wb];puts -nonewline $f $data;close $f}',
        '  after frame [list after time 0.001 [list capture $n]]',' }','}',
        'debug set_watchpoint write_mem 0xc000 {![info exists ::done] && $wp_last_value in {1 2}} {',
        ' if {$wp_last_value==1} {set ::begin [machine_info time];set ::gpu_count 0;set ::reload 0} else {',
        '  puts $::times_out "main $::frames $::phase $::begin $::reload $::warmup"',
        '  if {[catch {step} problem]} {puts stderr $problem;exit 2}',' }','}',
        'debug set_watchpoint write_mem 0xc03c {![info exists ::done] && $wp_last_value in {2 4 6}} {',
        ' puts $::times_out "$wp_last_value $::frames $::phase [machine_info time] $::reload $::warmup"',
        ' if {$wp_last_value==6} {if {[catch {footer} problem]} {puts stderr $problem;exit 2}}','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Enemy route VRAM timing violation";exit 2}',
        'after time 90 {puts stderr "Enemy route timeout";exit 2}']
    lines.insert(0,f'set component_out [open {tcl(out/"components.tsv")} w]')
    if (info.get('smoke_component') or {}).get('publication_counts_address'):
        lines.insert(0,f'set smoke_counts_out [open {tcl(out/"smoke-counts.bin")} wb]')
    if (info.get('smoke_component') or {}).get('logical_row_presence_address'):
        lines.insert(0,f'set smoke_rows_out [open {tcl(out/"smoke-native-rows.bin")} wb]')
        lines=[line.replace('record stop;exit 0','close $::smoke_rows_out;record stop;exit 0') for line in lines]
    if (info.get('smoke_component') or {}).get('runtime_enabled'):
        lines.insert(0,f'set smoke_display_out [open {tcl(out/"smoke-display.bin")} wb]')
        lines=[line.replace('record stop;exit 0','close $::smoke_display_out;record stop;exit 0') for line in lines]
    if info.get('flag_display_state_address'):
        lines.insert(0,f'set flag_display_out [open {tcl(out/"flag-display.bin")} wb]')
        lines=[line.replace('record stop;exit 0','close $::flag_display_out;record stop;exit 0') for line in lines]
    pairs=[('ram_prepare','main.position','Enemy_AfterPrepare'),
           ('actors','Player_Draw','HUD_PrepareFrame'),
           ('early','Player_AdvanceEarly',next(name for name in syms if name.endswith('.split_wait'))),
           ('late','Player_Advance','Flag_PublishHUD'),
           ('hud_content','HUD_DrawContent','Player_Advance'),
           ('stream','stage_stream','Life_Frame')]
    if info.get('hud_enabled') and info.get('hud_style',{}).get('radar_cells_only'):
        pairs.append(('radar','Radar_PrepareTail' if info.get('radar_work_phase') else 'Radar_Prepare','Life_Frame' if info.get('radar_work_phase') else 'update_fuel'))
    for name,begin,end in pairs:
        lines.extend([
            f'debug set_bp {syms[begin]} {{[info exists ::begin] && [reg IM]==2}} {{set ::profile_{name} [machine_info time]}}',
            f'debug set_bp {syms[end]} {{[info exists ::profile_{name}] && [reg IM]==2}} {{puts $::component_out "{name} $::frames [expr {{round(([machine_info time]-$::profile_{name})*3579545)}}]";unset ::profile_{name}}}'])
    if population>1:
        lines=[line.replace('debug set_bp 0x838a {[reg IM]==2}',
                            'debug set_bp 0x838a {[reg IM]==2 && [reg IY]==57348}') for line in lines]
        start=lines.index(' set px [debug read memory 0xe074];set py [debug read memory 0xe076];set ex [debug read memory 0xe094];set ey [debug read memory 0xe096]')
        end=lines.index(' set ::contact_input "$dx $dy $registered [debug read memory 0xe093]"',start)+1
        lines[start:end]=[
            ' set px [debug read memory 0xe074];set py [debug read memory 0xe076];set ::expected_contact 0;set ptr 0;set dx 0;set dy 0;set flag 0',
            ' for {set slot 0xe004} {$slot<0xe00e} {incr slot 2} {',
            '  set ptr [u16 $slot];if {!$ptr} {continue};set flag [debug read memory $ptr]',
            '  set dx [expr {(([debug read memory [expr {$ptr+1}]]-$px+128)&255)-128}];set dy [expr {(([debug read memory [expr {$ptr+3}]]-$py+128)&255)-128}]',
            '  if {!($flag&1) && abs($dx)<11 && abs($dy)<11} {set ::expected_contact 1;break}',' }',
            ' set ::contact_input "$dx $dy $ptr $flag"']
        lines=[line.replace('[debug read memory 0xe24e]!=1',f'[debug read memory 0xe24e]!={population}') for line in lines]
    lines=[line.replace('after frame {exit 0}','after frame {record stop;exit 0}') for line in lines]
    if info.get('flag_display_state_address'):
        lines=[line.replace('record stop;exit 0','close $::flag_display_out;record stop;exit 0') for line in lines]
    lines.append(scanout_recording_tcl(out,syms['startup_mode']))
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    inputs=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    json_write(out/'verification-inputs.json',dict(roms=inputs,bios=bios))
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    if not (out/'scanout.avi').is_file():raise ValueError('Complete-frame video recording missing')
    return analyze(root,args,out,inputs,bios)


def analyze(root,args,out,inputs,bios):
    info=read_json(args.rom.parent/'build.json')
    slots=info['sprites']['total_slots']
    ticks=[list(map(int,r.split())) for r in (out/'ticks.bin').read_text().splitlines()]
    dead=[r for r in ticks if r[1]]
    if not dead or dead[0][2]!=0 or [r[2] for r in dead[1:]]!=list(range(1,121)):
        raise ValueError('Enemy death did not retain the exact original 120-tick hold')
    if any(r[3]!=1 or r[4]!=0 or r[5]!=2 for r in dead):raise ValueError('Enemy death source/life changed during hold')
    contacts=[list(map(int,r.split())) for r in (out/'contacts.bin').read_text().splitlines()]
    if sum(r[-1] for r in contacts)!=1:raise ValueError('Expected exactly one live enemy contact event')
    images=verify_images(args,out);frames=check_cache_frames(root,args.rom.parent,out)
    radar_queue=None
    if info.get('hud_style',{}).get('radar_dirty_state_address'):
        from .radar_cells import queue_metrics
        radar_queue=queue_metrics(out/'radar_queue.bin',frames,info['hud_style']['radar_pending_refresh_limit'],3 if info['hud_style'].get('radar_ready_state_address') else 2)
    events=[r.split() for r in (out/'events.bin').read_text().splitlines()]
    occupancy=[list(map(int,r.split())) for r in (out/'occupancy.bin').read_text().splitlines()]
    allowed_candidates=slots if info.get('sprite_flicker') or info.get('allow_sprite_overflow') else 8
    if len(occupancy)!=frames or [r[0] for r in occupancy]!=list(range(frames)) or any(not 0<=r[1]<=allowed_candidates for r in occupancy):
        raise ValueError('Missing continuous sprite-line occupancy evidence')
    if sum(r[1]=='pause' and r[5]=='1' for r in events)!=40:raise ValueError('Enemy pause proof incomplete')
    transitions={int(r[0]) for r in events if r[6]!='0' or r[7]!='0' or r[1]=='home'}
    stamps=[r.split() for r in (out/'times.bin').read_text().splitlines()];periods={}
    for kind in ('main','2','4','6'):
        rows=[r for r in stamps if r[0]==kind];values=[]
        for a,b in zip(rows,rows[1:]):
            if any(int(r[1])<3 or r[2]=='home' or r[4]!='0' or r[5]!='0' for r in (a,b)):continue
            if any(n in transitions for n in range(int(a[1]),int(b[1])+1)):continue
            values.append((float(b[3])-float(a[3]))*1000)
        if not values or any(abs(v-info['timing']['frame_seconds']*1000)>.6 for v in values):raise ValueError(f'Enemy route refresh missed: {kind}, {max(values,default=0):.3f} ms')
        periods[kind]=dict(samples=len(values),min_ms=min(values),max_ms=max(values),median_ms=statistics.median(values))
    if inputs!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())) or bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Source/BIOS changed')
    verify_manifest(args.rom.parent)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),keyboard_only=True,msx_game_state_writes=False,
        complete_frame_recording=(out/'scanout.avi').is_file(),
        contact_comparisons=len(contacts),deaths=1,hold_ticks=120,pause_refreshes=40,rgb_images=images,visible_cache_frames=frames,
        radar_queue=radar_queue,
        sprite_occupancy_frames=frames,sprite_line_peak=max(r[1] for r in occupancy),sprite_overflow_frames=sum(r[1]>8 for r in occupancy),hardware_sprite_limit_enabled=True,occupied_slots=info['sprites']['total_slots'],free_slots=info['sprites']['free_slots'],
        reload_ms=[float(r.split()[1]) for r in (out/'reloads.bin').read_text().splitlines()],periods=periods,
        scope='Natural original enemy pursuit, strict source contact, '+('next-refresh explosion presentation' if info.get('death',{}).get('presentation_latency_refreshes') else 'same-frame explosion')+', pause/frozen enemy, exact native hold, same-round restart and Home; full RGB/cache and unchanged timing gate'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Enemy keyboard contact/restart, {frames} cache states, {images} RGB: {out}/report.json')
    return out
