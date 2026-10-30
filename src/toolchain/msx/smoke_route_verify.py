"""Keyboard-only smoke creation, enemy stun, recovery, pause and bitmap checks."""
import os
import statistics
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl,scanout_recording_tcl
from .hud_verify import symbols
from .death_verify import verify_images
from .lives_route_verify import check_cache_frames
from .smoke_verify import RANGES


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not (info.get('smoke_component') or {}).get('runtime_enabled'):
        raise ValueError('Smoke keyboard route requires integrated stage10')
    out=destination(root,args.output);require_ignored(root,[out/'cache.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym')
    stress=bool(getattr(args,'smoke_stress',False))
    from .rock_route_verify import route
    board=bytearray((root/'assets/arcade/native/rocks-v1/work.bin').read_bytes()[:1792])
    rocks=read_json(bundle/'stage-one.json')['rock_fixture']['positions']
    rock=rocks[0];goal=(rock['cell_x'],rock['cell_y'])
    for i,c in enumerate(board):
        if c==3:board[i]=0x87
    board[goal[1]*32+goal[0]]=0
    path=route(board,(15,50),goal)
    masks={(0,-1):32,(1,0):128,(0,1):64,(-1,0):16}
    points=' '.join('{'+f'{36+x*24} {36+y*24} {masks[x-a,y-b]}'+'}' for (a,b),(x,y) in zip(path,path[1:]))
    streams='motion cache events ticks presentation smoke-display smoke-before smoke-after smoke-context times raster-times smoke-counts terrain-state smoke-native-rows components radar-queue flag-display held-refreshes'
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle on','set speed 100','set vsync off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set minframeskip 0','set maxframeskip 0','set gamma 1','set brightness 0','set contrast 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','set blur 0','set noise 0','set scanline 0',
        'activate_input_layer -blocking smoke_route',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)}',f'foreach name {{{streams}}} {{set files($name) [open [file join $out "$name.bin"] wb]}}',
        'set frames -1;set phase approach;set held 0;set warmup 3;set capture 0;set shots 0;set reload 0',
        f'set stress {int(stress)};set rock_route {{{points}}};set target 0;set stress_max 0;set stress_death 0',
        'set hudflags [binary format c* {0 1 1 1 1 1 1 1 1 1 1}]',
        'set header [string repeat [binary format c 0] 12]',
        'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
        'proc keys {m ctrl} {keymatrixup 8 255;keymatrixup 6 2;if {$m} {keymatrixdown 8 $m};if {$ctrl} {keymatrixdown 6 2}}',
        'proc input {n ctrl} {if {$n<80} {keys 0 $ctrl} else {keys [lindex {128 32 16 64} [expr {int(($n-80)/220)%4}]] $ctrl}}',
        'proc snapshot {} {',
        ' puts -nonewline $::files(motion) [debug read_block memory 0xe000 4096]',
        ' puts -nonewline $::files(motion) [debug read_block memory 0xc400 96]',
        ' puts -nonewline $::files(motion) [debug read_block memory 0xc0b0 4]',
        ' puts -nonewline $::files(motion) [debug read_block memory 0xc500 11]',
        ' puts -nonewline $::files(motion) [debug read_block memory 0xc490 5]',
        ' puts -nonewline $::files(motion) [debug read_block memory 0xc5c0 3]',
        ' puts -nonewline $::files(presentation) [debug read_block memory 0xc49a 1]',
        ' puts -nonewline $::files(flag-display) [debug read_block memory 0xc534 11]',
        ' puts -nonewline $::files(held-refreshes) [debug read_block memory 0xc71d 2]',
        ' puts -nonewline $::files(smoke-display) [debug read_block memory 0xd300 2048]',
        ' puts -nonewline $::files(smoke-counts) [debug read_block memory 0xdb00 32]',
        ' puts -nonewline $::files(terrain-state) [debug read_block memory 0xc000 256]',
        ' puts -nonewline $::files(smoke-native-rows) [debug read_block memory 0xdb20 32]',
        f' puts -nonewline $::files(radar-queue) [debug read_block memory {syms["Radar_Dirty"]} 2];puts -nonewline $::files(radar-queue) [debug read_block memory {syms["hud_flags_dirty"]} 2];puts -nonewline $::files(radar-queue) [debug read_block memory {syms["Radar_Ready"]} 2]',
        ' puts -nonewline $::files(cache) [debug read_block VRAM 0 65536]','}',
        'proc step {} {',
        ' incr ::frames;set paused [debug read memory 0xc009];set placed [u16 0xc711];set recovered [u16 0xc713]',
        ' if {[debug read memory 0xc70f]} {error "Smoke ring/queue overflow"}',
        ' puts $::files(events) "$::frames $::phase $paused $placed $recovered [debug read memory 0xc70e] [debug read memory 0xc490] [debug read memory 0xc5c2] $::warmup"',
        ' puts $::files(times) "$::frames $::phase $::begin $::warmup $::reload [machine_info time]"',
        ' if {!$::reload && !$::warmup} {snapshot}',
        ' if {$::warmup} {incr ::warmup -1}',
        ' if {$::frames%40==0} {set ::capture 1}',
        ' switch $::phase {',
        ' approach {',
        '  input $::frames 0',
        '  set dy [expr {[u16 0xc5d6]-[u16 0xc407]}];set dx [expr {[u16 0xc5d4]-[u16 0xc405]}];set flag [debug read memory 0xe077]',
        '  set behind [expr {($flag==240 && $dy>24 && $dy<96 && abs($dx)<12) || ($flag==242 && $dy< -24 && $dy> -96 && abs($dx)<12) || ($flag==252 && $dx< -24 && $dx> -96 && abs($dy)<12) || ($flag==253 && $dx>24 && $dx<96 && abs($dy)<12)}]',
        '  if {$behind && [debug read memory 0xe088]==0} {input $::frames 1;set ::phase firing;set ::held 0;set ::capture 1}',' }',
        ' firing {',
        '  incr ::held;input $::frames [expr {$::held<8}]',
        '  if {[debug read memory 0xe09d]} {keys 1 0;set ::phase pause;set ::held 0;set ::capture 1}',
        '  if {$::held>400} {error "Keyboard smoke did not stun the pursuing enemy"}',' }',
        ' pause {',
        '  keys 0 0',
        '  if {$paused} {',
        '   set frozen [list [u16 0xc440] [debug read_block memory 0xe068 96] [debug read_block memory 0xe26a 2] [debug read_block memory 0xe290 2] [debug read_block memory 0xc711 4]]',
        '   if {!$::held} {set ::frozen $frozen} elseif {$frozen ne $::frozen} {error "Paused smoke/enemy/fuel moved"}',
        '   incr ::held;if {$::held in {4 40}} {set ::capture 1}',
        '   if {$::held==40} {keys 1 0;set ::phase running;set ::held 0}','  }',' }',
        ' running {',
        '  incr ::held;keys [expr {$::held<140?128:16}] [expr {$::stress && $::held%24<8}]',
        '  if {$::held in {1 120 139 200 300}} {set ::capture 1}',
        '  if {$::held==320} {if {!$placed || !$recovered} {error "Missing natural smoke creation/recovery"};keys 2 0;set ::phase home;set ::held 0}',' }',
        ' home {',
        '  keys 0 0;incr ::held',
        '  if {$placed || $recovered || [debug read memory 0xc70e] || [debug read memory 0xc70f]} {error "Home retained smoke jobs/counters"}',
        '  if {[debug read_block memory 0xe400 1024] ne [string repeat [binary format c 0] 1024] || [debug read_block memory 0xd300 2048] ne [string repeat [binary format c 0] 2048]} {error "Home retained smoke code/pixels"}',
        '  if {$::held==5} {set ::capture 1}',
        f'  if {{$::held==8}} {{if {{$::stress && !$::stress_death}} {{set ::phase rock;set ::held 0}} else {{set ::done 1;foreach name {{{streams}}} {{close $::files($name)}};after frame {{record stop;exit 0}}}}}}',' }',
        ' rock {',
        '  incr ::held;set ::stress_max [expr {max($::stress_max,$placed)}]',
        '  if {[debug read memory 0xc490]} {',
        '   if {$placed<3 || [debug read memory 0xe00f]!=2} {error "Smoke stress did not reach rock death with clouds"}',
        '   set ::stress_death 1;set ::phase restart;keys 0 0;set ::capture 1',
        '  } else {',
        '   set x [u16 0xc405];set y [u16 0xc407];lassign [lindex $::rock_route $::target] tx ty mask',
        '   if {abs($tx-$x)<=6 && abs($ty-$y)<=6 && $::target<[llength $::rock_route]-1} {incr ::target;lassign [lindex $::rock_route $::target] tx ty mask}',
        '   keys $mask [expr {$::held%24<8}]','  }',' }',
        ' restart {',
        '  keys 0 0',
        '  if {![debug read memory 0xc490]} {',
        '   if {[debug read memory 0xe00f]!=2 || $placed || $recovered || [debug read memory 0xc70e] || [debug read memory 0xc70f]} {error "Life restart retained smoke work/state"}',
        '   if {[debug read_block memory 0xe400 1024] ne [string repeat [binary format c 0] 1024] || [debug read_block memory 0xd300 2048] ne [string repeat [binary format c 0] 2048]} {error "Life restart retained smoke code/pixels"}',
        '   set ::capture 1;set ::phase after_restart;set ::held 0','  }',' }',
        ' after_restart {keys 0 0;incr ::held;if {$::held==8} {keys 2 0;set ::phase home;set ::held 0}}',' }',
        ' set ::reload 0;if {$::frames>3000} {error "Smoke keyboard route timeout"}','}',
        f'debug set_bp {syms["show_scene"]} {{[info exists ::begin]}} {{set ::reload 1;set ::warmup 3}}',
        f'debug set_bp {syms["Player_Radar"]} {{[reg IM]==2}} {{set ::hudflags [debug read_block memory 0xc500 11]}}',
        'debug set_bp 0x8f64 {[reg IM]==2 && ![info exists ::done]} {puts -nonewline $::files(smoke-before) [debug read_block memory 0xe000 4096];puts -nonewline $::files(smoke-context) [debug read_block memory 0xc706 6];puts -nonewline $::files(smoke-context) [debug read_block memory 0xc500 11]}',
        f'debug set_bp {syms["Smoke_AfterNative"]} {{[reg IM]==2 && ![info exists ::done]}} {{',
        *[f' puts -nonewline $::files(smoke-after) [debug read_block memory {0xe000+a} {n}]' for a,n in RANGES],'}',
        f'debug set_bp {syms["Player_CountTick"]} {{[reg IM]==2 && ![info exists ::done]}} {{puts $::files(ticks) "[u16 0xc440] [debug read memory 0xe088] [debug read memory 0xe09d] [u16 0xc713] [u16 0xc711] [debug read memory 0xc490]"}}',
        'debug set_watchpoint write_mem 0xc000 {![info exists ::done] && $wp_last_value in {1 2}} {',
        ' if {$wp_last_value==1} {set ::begin [machine_info time]} elseif {[catch {step} problem]} {puts stderr $problem;exit 2}','}',
        'proc capture {n} {screenshot -raw -size auto [file join $::out "$n.png"]}',
        'debug set_watchpoint write_mem 0xc03c {![info exists ::done] && $wp_last_value==2} {set ::header [debug read_block memory 0xc30c 12]}',
        'debug set_watchpoint write_mem 0xc03c {[info exists ::begin] && ![info exists ::done] && $wp_last_value in {2 4 6}} {puts $::files(raster-times) "$wp_last_value $::frames $::phase [machine_info time] $::warmup $::reload"}',
        'debug set_watchpoint write_mem 0xc03c {![info exists ::done] && $wp_last_value==6} {',
        ' if {$::capture && !$::reload && !$::warmup} {set ::capture 0;set n [incr ::shots]',
        '  foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] hudflags $::hudflags header $::header] {set f [open [file join $::out "$n.$ext"] wb];puts -nonewline $f $data;close $f}',
        '  after frame [list after time 0.001 [list capture $n]]',' }','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Smoke route VRAM timing violation";exit 2}',
        'after time 120 {puts stderr "Smoke route timeout";exit 2}',scanout_recording_tcl(out,syms['startup_mode'])]
    for name,begin,end in (
        ('early','Player_AdvanceEarly','Smoke_Stream'),('clouds','Smoke_Stream','Flag_Stream'),
        ('prepare','HUD_PrepareFrame',next(k for k in syms if k.endswith('.split_wait'))),
        ('content','HUD_DrawContent','Player_Advance'),('late','Player_Advance','Flag_PublishHUD'),
        ('radar_wait','Radar_WaitPublish','stage_stream'),('terrain','stage_stream','Life_Frame'),
        ('smoke_pre','Smoke_PreTick',0x8069),('smoke_tick','Smoke_Tick',0x9052)):
        first=begin if isinstance(begin,int) else syms[begin];last=end if isinstance(end,int) else syms[end]
        lines.extend([
            f'debug set_bp {first} {{[reg IM]==2 && $::frames>=1170 && $::frames<=1340 && ![info exists ::cost_{name}]}} {{set ::cost_{name} [machine_info time]}}',
            f'debug set_bp {last} {{[info exists ::cost_{name}]}} {{puts $::files(components) "{name} $::frames [expr {{1000*([machine_info time]-$::cost_{name})}}]";unset ::cost_{name}}}'])
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    return analyze(root,args,out,bios)


def analyze(root,args,out,bios):
    from .smoke_replay import verify as verify_original
    original=verify_original(root,args.rom.parent,out)
    frames=check_cache_frames(root,args.rom.parent,out);images=verify_images(args,out)
    info=read_json(args.rom.parent/'build.json');backpressure=None
    if info.get('cache_backpressure'):
        from .smoke import held_refresh_metrics
        from .player_verify import FRAME_BYTES
        backpressure=held_refresh_metrics((out/'held-refreshes.bin').read_bytes(),(out/'motion.bin').read_bytes(),FRAME_BYTES+19)
    from .radar_cells import queue_metrics
    radar_queue=queue_metrics(out/'radar-queue.bin',frames,16,3)
    ticks=[list(map(int,r.split())) for r in (out/'ticks.bin').read_text().splitlines()]
    stun=[]
    for row in ticks:
        if row[2]:stun.append(row[1])
        elif stun:break
    if stun!=list(range(136,0,-1)):raise ValueError(f'Natural smoke stun differs from136 source ticks: {stun[:8]}, {len(stun)}')
    events=[r.split() for r in (out/'events.bin').read_text().splitlines()]
    if sum(r[1]=='pause' and r[2]=='1' for r in events)!=40:raise ValueError('Missing smoke pause observations')
    if getattr(args,'smoke_stress',False):
        if max(int(r[3]) for r in events)<6 or not any(r[1]=='after_restart' and r[7]=='1' for r in events):
            raise ValueError('Missing repeated smoke or smoke death/restart stress')
    rows=[r.split() for r in (out/'times.bin').read_text().splitlines()];values=[]
    for a,b in zip(rows,rows[1:]):
        if any(int(r[0])<3 or r[1]=='home' or r[3]!='0' or r[4]!='0' for r in (a,b)):continue
        values.append((float(b[2])-float(a[2]))*1000)
    if not values:raise ValueError('Missing smoke timing')
    info=read_json(args.rom.parent/'build.json');limit=info['timing']['frame_seconds']*1000
    periods=dict(samples=len(values),median_ms=statistics.median(values),p95_ms=sorted(values)[int(.95*(len(values)-1))],maximum_ms=max(values),missed_refreshes=sum(abs(v-limit)>.6 for v in values))
    raster={}
    for kind in ('2','4','6'):
        stamps=[r.split() for r in (out/'raster-times.bin').read_text().splitlines() if r.split()[0]==kind];v=[]
        for a,b in zip(stamps,stamps[1:]):
            if any(int(r[1])<3 or r[2]=='home' or r[4]!='0' or r[5]!='0' for r in (a,b)):continue
            v.append((float(b[3])-float(a[3]))*1000)
        if not v:raise ValueError('Missing smoke raster cadence')
        raster[kind]=dict(samples=len(v),median_ms=statistics.median(v),maximum_ms=max(v),missed_refreshes=sum(abs(a-limit)>.6 for a in v))
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed during smoke route')
    verify_manifest(args.rom.parent)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),keyboard_only=True,msx_game_state_writes=False,
        complete_visible_cache_frames=frames,full_rgb_images=images,stun_ticks=len(stun),pause_refreshes=40,
        original_live_calls=original,
        radar_queue=radar_queue,
        cache_backpressure=backpressure,
        repeated_firing_and_rock_restart=bool(getattr(args,'smoke_stress',False)),
        placements=max(int(r[3]) for r in events),recoveries=max(int(r[4]) for r in events),peak_dirty_clouds=max(int(r[5]) for r in events),
        periods=periods,raster_periods=raster,
        performance_accepted=not periods['missed_refreshes'] and not any(r['missed_refreshes'] for r in raster.values()),additional_sprite_slots=0,
        scope='Keyboard smoke/native stun/recovery, pause, movement/reversal, entire cache/RGB and Home; live-rule replay is separate'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Smoke route: {frames} cache states, {images} RGB: {out}/report.json')
    return out
