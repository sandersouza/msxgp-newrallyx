"""Keyboard-only first-round collection, paused completion and original bonus."""
from collections import deque
import os
import statistics
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl,scanout_recording_tcl
from .hud_verify import symbols
from .stage_one import acquire,reconstruct
from .fuel_verify import source_seed,original_oracle,compare
from .lives_route_verify import check_cache_frames
from .death_verify import verify_images
from .radar_cells import queue_metrics


def navigation(board,records):
    result=bytearray()
    for flag in records:
        a=flag['address']-0x9800;goal=(a%32,a//32)
        seen={goal};queue=deque([goal]);table=bytearray([255])*1792;table[a]=0
        while queue:
            x,y=queue.popleft()
            for dx,dy,mask in ((0,1,32),(-1,0,128),(0,-1,64),(1,0,16)):
                nx,ny=x+dx,y+dy
                if not 0<=nx<32 or not 0<=ny<56 or (nx,ny) in seen or board[ny*32+nx]&0xf8:continue
                seen.add((nx,ny));queue.append((nx,ny));table[ny*32+nx]=mask
        result.extend(table)
    return bytes(result)


def verify_header_reservations(path, frame_seconds):
    """A missed header comparator can show the old session page for one frame."""
    opened = None
    delays = []
    for row in (line.split() for line in path.read_text().splitlines()):
        stage, _, _, time, reload, warmup = row
        if int(reload) or int(warmup):
            opened = None
            continue
        if stage == '2':
            opened = float(time)
        elif stage == '4' and opened is not None:
            delay = float(time)-opened
            if not 0 < delay < frame_seconds*.75:
                raise ValueError('Header split missed its reserved refresh')
            delays.append(delay)
            opened = None
    if not delays:
        raise ValueError('Missing complete header split trace')
    return dict(refreshes=len(delays), maximum_ms=max(delays)*1000)


def verify_fuel_restoration(path, limit=2):
    rows=[line.split() for line in path.read_text().splitlines()]
    index=next((i for i in range(1,len(rows)) if rows[i-1][2]!='0' and rows[i][2]=='0'),None)
    if index is None or len(rows)-index<80:
        raise ValueError('Missing post-lucky fuel observation window')
    latency=next((j-index for j in range(index,len(rows))
                  if int(rows[j][6])==int(rows[j][5])==min(int(rows[j][3]),54)*30//54),None)
    if latency is None or latency>limit:
        raise ValueError('Restored native fuel did not reach the displayed gauge promptly')
    return dict(latency_refreshes=latency,limit_refreshes=limit,
                observed_post_bonus_refreshes=len(rows)-index,
                restored_whole_units=int(rows[index][3]))


def verify(root,args):
    lucky_only=getattr(args,'command','')=='verify-lucky-route'
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not (info.get('completion_component') or {}).get('runtime_enabled'):raise ValueError('Completion route requires stage11')
    out=destination(root,args.output);out.mkdir(parents=True);require_ignored(root,[out/'nav.bin'])
    program,reference=acquire(root);board,_,_=reconstruct(program,reference)
    records=read_json(bundle/'flags.json')['records'];(out/'nav.bin').write_bytes(navigation(board,records))
    syms=symbols(bundle/'raster-scroll.sym')
    streams='motion cache presentation smoke-display smoke-counts radar-queue events times raster-times bonus flag-display held-refreshes'
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle on','set speed 100','set vsync off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set minframeskip 0','set maxframeskip 0','set gamma 1','set brightness 0','set contrast 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','set blur 0','set noise 0','set scanline 0',
        'activate_input_layer -blocking completion_route',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)};foreach n {{{streams}}} {{set files($n) [open [file join $out "$n.bin"] wb]}}',
        'set f [open [file join $out nav.bin] rb];set nav [read $f];close $f',
        'set frames -1;set phase navigate;set warmup 3;set reload 0;set held 0;set shots 0;set capture 0;set seen 0;set deaths 0',
        'set tx 396;set ty 1236;set mask 0;set fire 0;set bonus_tick -1;set observing 0;set bonus_paused 0;set bonus_done 0',
        'set hudflags [binary format c* {0 1 1 1 1 1 1 1 1 1 1}]',
        'set header [string repeat [binary format c 0] 12]',
        'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
        'proc keys {mask ctrl} {keymatrixup 8 255;keymatrixup 6 2;if {$mask} {keymatrixdown 8 $mask};if {$ctrl} {keymatrixdown 6 2}}',
        'proc choose {x y} {',
        ' set g -1;for {set i 0} {$i<10} {incr i} {if {[debug read memory [expr {0xc501+$i}]]} {set g $i;break}}',
        ' if {$g<0} {set ::mask 0;return}',
        ' binary scan [string index $::nav [expr {$g*1792+$y*32+$x}]] cu m',
        ' if {$m==255 || !$m} {error "Completion navigation reached an invalid active flag cell"}',
        ' set ::mask $m;set ::tx [expr {36+24*($x+($m==128)-($m==16))}];set ::ty [expr {36+24*($y+($m==64)-($m==32))}]','}',
        'proc frozen {} {list [debug read_block memory 0xc720 5] [debug read_block memory 0xe068 24] [debug read_block memory 0xe24b 1] [debug read_block memory 0xe269 3] [debug read_block memory 0xe0a0 8]}',
        'proc snapshot {} {',
        ' foreach {a n} {0xe000 4096 0xc400 96 0xc0b0 4 0xc500 11 0xc490 5 0xc5c0 3} {puts -nonewline $::files(motion) [debug read_block memory $a $n]}',
        ' puts -nonewline $::files(cache) [debug read_block VRAM 0 65536];puts -nonewline $::files(presentation) [debug read_block memory 0xc49a 1]',
        ' puts -nonewline $::files(flag-display) [debug read_block memory 0xc534 11]',
        ' puts -nonewline $::files(held-refreshes) [debug read_block memory 0xc71d 2]',
        ' puts -nonewline $::files(smoke-display) [debug read_block memory 0xd300 2048];puts -nonewline $::files(smoke-counts) [debug read_block memory 0xdb00 32]',
        f' foreach a {{{syms["Radar_Dirty"]} {syms["hud_flags_dirty"]} {syms["Radar_Ready"]}}} {{puts -nonewline $::files(radar-queue) [debug read_block memory $a 2]}}','}',
        'proc bonus_record {} {',
        ' if {!$::observing} {return};incr ::bonus_tick;puts -nonewline $::files(bonus) [binary format ss 0 $::bonus_tick]',
        ' foreach a {0xe26a 0xe26b 0xe269 0xe020 0xe023 0xe292 0xe289 0xe28c 0xe28a} {puts -nonewline $::files(bonus) [binary format c [debug read memory $a]]}',
        ' foreach {a n} {0xe144 8 0xe0a0 8 0xe060 8} {puts -nonewline $::files(bonus) [debug read_block memory $a $n]}',
        ' foreach a {0xe00f 0xe1b2 0xe2d0 0xe027 0xe028 0xe9f4} {puts -nonewline $::files(bonus) [binary format c [debug read memory $a]]}',
        ' set done [expr {[debug read memory 0xc720]==2}];puts -nonewline $::files(bonus) [binary format c $done];if {$done} {set ::observing 0;set ::bonus_done 1}','}',
        'proc step {} {',
        ' incr ::frames;set count [debug read memory 0xc50b];set round [debug read memory 0xc724];set paused [debug read memory 0xc009];set death [debug read memory 0xc490]',
        ' puts $::files(events) "$::frames $::phase $count $round $paused $death [debug read memory 0xe00f] $::reload $::warmup"',
        ' puts $::files(times) "$::frames $::phase $::begin $::reload $::warmup"',
        ' if {!$::reload && !$::warmup} {snapshot};if {$::warmup} {incr ::warmup -1}',
        ' if {$::frames%160==0 || $count!=$::seen} {set ::capture 1};set ::seen $count',
        ' switch $::phase {',
        ' navigate {',
        '  if {$round} {keys 1 0;set ::phase settle_pause;set ::held 0;return}',
        '  if {$death} {keys 0 0;set ::phase life;set ::capture 1;return}',
        '  set x [u16 0xc405];set y [u16 0xc407]',
        '  if {abs($::tx-$x)<=6 && abs($::ty-$y)<=6} {choose [expr {int(($::tx-36)/24)}] [expr {int(($::ty-36)/24)}]}',
        '  set dx [expr {[u16 0xc5d4]-$x}];set dy [expr {[u16 0xc5d6]-$y}];set f [debug read memory 0xe077]',
        '  set behind [expr {($f==240 && $dy>24 && $dy<96 && abs($dx)<12) || ($f==242 && $dy< -24 && $dy> -96 && abs($dx)<12) || ($f==252 && $dx< -24 && $dx> -96 && abs($dy)<12) || ($f==253 && $dx>24 && $dx<96 && abs($dy)<12)}]',
        '  if {!$::fire && $behind && ![debug read memory 0xe09d]} {set ::fire 8};keys $::mask [expr {$::fire>0}];if {$::fire} {incr ::fire -1}',' }',
        ' life {keys 0 0;if {[debug read memory 0xc5c0]==2} {error "Completion route exhausted three lives"};if {!$death} {set ::tx 396;set ::ty 1236;set ::mask 0;set ::fire 0;set ::phase navigate;incr ::deaths;set ::capture 1}}',
        ' settle_pause - bonus_pause {',
        '  keys 0 0;if {$paused} {if {!$::held} {set ::frozen [frozen]} elseif {[frozen] ne $::frozen} {error "Completion advanced while paused"};incr ::held}',
        '  if {$::held==4} {set ::capture 1};if {$::held==40} {keys 1 0;set ::phase [expr {$::phase=="settle_pause"?"wait_bonus":"bonus"}];set ::capture 1}',' }',
        ' wait_bonus {keys 0 0;if {$round==2} {set ::phase bonus;set ::capture 1}}',
        ' bonus {',
        '  keys 0 0;if {!$::bonus_paused && $::bonus_tick>=3} {keys 1 0;set ::bonus_paused 1;set ::phase bonus_pause;set ::held 0}',
        '  if {$round==3} {if {!$::bonus_done || !$::bonus_paused || [u16 0xe26a] || $count!=10 || [debug read memory 0xe1b0]!=2} {error "Completion did not preserve the bounded original round/bonus"};set ::phase stopped;set ::held 0;set ::stopped [frozen];set ::capture 1}',' }',
        ' stopped {',
        '  keys 128 1;incr ::held;if {[frozen] ne $::stopped} {error "Completed segment still accepted movement/smoke"}',
        '  if {$::held==12} {keys 2 0;set ::phase home;set ::held 0}',' }',
        ' home {',
        '  keys 0 0;incr ::held;if {$round || $count || [debug read memory 0xe00f]!=3 || [debug read_block memory 0xc501 10] ne [string repeat [binary format c 1] 10]} {error "Home retained completion/life/flags"}',
        f'  if {{$::held==8}} {{set ::done 1;foreach n {{{streams}}} {{close $::files($n)}};after frame {{record stop;exit 0}}}}',' }',' }',
        ' set ::reload 0;if {$::frames>10000} {error "Completion keyboard navigation timeout"}','}',
        f'debug set_bp {syms["show_scene"]} {{[info exists ::begin]}} {{set ::reload 1;set ::warmup 3}}',
        f'debug set_bp {syms["Player_Radar"]} {{[reg IM]==2}} {{set ::hudflags [debug read_block memory 0xc500 11]}}',
        f'debug set_bp {syms["Completion_Begin"]} {{[reg IM]==2}} {{',
        ' set ::observing 1;set f [open [file join $::out bonus-native-seed.bin] wb];puts -nonewline $f [debug read_block memory 0xe000 4096];close $f',
        ' set f [open [file join $::out bonus-case.bin] wb];puts -nonewline $f [binary format c 2]',
        ' foreach a {0xe1b0 0xe26a 0xe26b 0xe271 0xe020 0xe269 0xe28b 0xe26e} {puts -nonewline $f [binary format c [debug read memory $a]]}',
        ' puts -nonewline $f [binary format s 0];puts -nonewline $f [debug read_block memory 0xe0a0 8];puts -nonewline $f [debug read_block memory 0xe060 8];puts -nonewline $f [debug read_block memory 0xe023 1];close $f','}',
        f'debug set_bp {syms["Player_CountTick"]} {{[reg IM]==2 && $::observing}} {{bonus_record}}',
        'debug set_watchpoint write_mem 0xc000 {![info exists ::done] && $wp_last_value in {1 2}} {if {$wp_last_value==1} {set ::begin [machine_info time]} elseif {[catch {step} p]} {puts stderr $p;exit 2}}',
        'debug set_watchpoint write_mem 0xc03c {[info exists ::begin] && ![info exists ::done] && $wp_last_value in {2 4 6}} {puts $::files(raster-times) "$wp_last_value $::frames $::phase [machine_info time] $::reload $::warmup"}',
        'debug set_watchpoint write_mem 0xc03c {![info exists ::done] && $wp_last_value==2} {set ::header [debug read_block memory 0xc30c 12]}',
        'proc screenshot_frame {n} {screenshot -raw -size auto [file join $::out "$n.png"]}',
        'debug set_watchpoint write_mem 0xc03c {![info exists ::done] && $wp_last_value==6 && $::capture && !$::reload && !$::warmup} {',
        ' set ::capture 0;set n [incr ::shots];foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] hudflags $::hudflags header $::header] {set f [open [file join $::out "$n.$ext"] wb];puts -nonewline $f $data;close $f};after frame [list after time 0.001 [list screenshot_frame $n]]','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Completion VRAM timing violation";exit 2}',
        'after time 240 {puts stderr "Completion route timeout";exit 2}',scanout_recording_tcl(out,syms['startup_mode'])]
    if getattr(args,'lucky_first',False) or lucky_only:
        order=sorted(range(10),key=lambda i:records[i]['kind']!=4)
        lines=[line.replace('for {set i 0} {$i<10} {incr i}',
            'foreach i {'+' '.join(map(str,order))+'}') for line in lines]
    if info.get('session'):
        lines=[line.replace('proc keys {mask ctrl} {keymatrixup 8 255;keymatrixup 6 2;',
            'proc keys {mask ctrl} {keymatrixup 4 32;keymatrixup 8 255;keymatrixup 6 2;if {$mask&1} {keymatrixdown 4 32;set mask [expr {$mask&254}]};') for line in lines]
        lines.extend([
            'file mkdir [file join $::out session-menus];set session_phase boot;set session_age 0',
            'proc menu_capture {n} {',
            ' set f [open [file join $::out session-menus "$n.state"] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
            ' after frame [list after frame [list after time 0.001 [list screenshot -raw -size auto [file join $::out session-menus "$n.png"]]]]','}',
            'proc session_controls {} {',
            ' if {[catch {session_step} p]} {puts stderr $p;exit 2};if {![info exists ::done]} {after time 0.02 session_controls}','}',
            'proc session_step {} {',
            ' set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd];incr ::session_age',
            ' switch $::session_phase {',
            ' boot {if {$state==1 && $ready==1} {menu_capture 1;keymatrixdown 0 32;set ::session_phase coin;set ::session_age 0}}',
            ' coin - clear_coin {if {$::session_age==4} {keymatrixup 0 255;set ::session_phase [expr {$::session_phase=="coin"?"release":"clear_release"}];set ::session_age 0}}',
            ' release - clear_release {if {$::session_age==3} {keymatrixdown 0 2;set ::session_phase [expr {$::session_phase=="release"?"start":"new_game"}];set ::session_age 0}}',
            ' start {if {$::session_age==4} {keymatrixup 0 255};if {!$state} {set ::session_phase playing}}',
            ' playing {if {$state==3 && $ready==1 && $::phase=="stopped"} {',
            '  if {[frozen] ne $::stopped} {error "Clear menu changed completed native game"};menu_capture 2;set ::session_phase clear_wait;set ::session_age 0',' }}',
            ' clear_wait {',
            '  if {[frozen] ne $::stopped} {error "Clear menu resumed native simulation"}',
            '  if {$::session_age==12} {keys 0 0;keymatrixdown 0 32;set ::phase session_restart;set ::session_phase clear_coin;set ::session_age 0}',' }',
            ' new_game {if {$::session_age==4} {keymatrixup 0 255};if {!$state} {',
            '  if {[debug read memory 0xc7d2] || [debug read memory 0xe00f]!=3 || [debug read memory 0xc50b]} {error "Clear credit/start did not restore fresh initial round"}',
            '  set ::phase home;set ::held 0;set ::session_phase done',' }}',' }','}',
            'after time 0.02 session_controls'])
    if lucky_only:
        lines=[line.replace('if {$::frames%160==0 || $count!=$::seen}',
                           'if {$::frames%160==0 || $count!=$::seen || [debug read memory 0xc5b0]}')
                    .replace(' switch $::phase {',
                      ' if {$count==1 && [debug read memory 0xc5b0]} {set ::saw_lucky 1}\n'
                      ' if {[info exists ::saw_lucky] && ![debug read memory 0xc5b0]} {'
                      'if {![info exists ::finished_age]} {set ::finished_age 0};incr ::finished_age;'
                      'set ::capture 1;keys 0 0;if {$::finished_age<96} {return};'
                      f'set ::done 1;foreach n {{{streams}}} {{close $::files($n)}};'
                      'close $::fuel_trace;after frame {after time 0.004 {record stop;exit 0}};return}\n switch $::phase {')
               if line==' switch $::phase {' or 'if {$::frames%160==0' in line else line for line in lines]
        from .fuel_verify import route_capture
        lines+=route_capture(syms,out)
        lines += ['set fuel_trace [open [file join $::out fuel.tsv] w]',
            'debug set_watchpoint write_mem 0xc000 {[info exists ::begin] && $wp_last_value==2 && ![info exists ::done]} {'
            'puts $::fuel_trace "$::frames [machine_info time] [debug read memory 0xc5b0] '
            '[debug read memory 0xe26b] [debug read memory 0xe26a] [debug read memory 0xc324] '
            '[debug read memory 0xc325] [debug read memory 0xc0a0]"}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    if lucky_only:
        from .fuel_verify import verify_route
        ticks=verify_route(root,bundle,out)
        restoration=verify_fuel_restoration(out/'fuel.tsv')
        headers=verify_header_reservations(out/'raster-times.bin',info['timing']['frame_seconds'])
        frames=check_cache_frames(root,bundle,out)
        images=verify_images(args,out)
        verify_manifest(bundle)
        if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
            raise ValueError('Lucky route changed BIOS files')
        json_write(out/'report.json',dict(rom_sha256=digest(args.rom),keyboard_only=True,
            msx_game_state_writes=False,lucky_collected_first=True,
            exact_original_lucky_ticks=ticks,fuel_restoration=restoration,
            header_reservations=headers,complete_visible_cache_frames=frames,full_rgb_images=images,
            scope='Real keyboard L pickup, complete original conversion and96 post-bonus refreshes; full cache, sampled RGB and every header split'))
        require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
        print(f'Lucky route: {ticks} original ticks,{frames} cache,{images} RGB,fuel latency{restoration["latency_refreshes"]}: {out}/report.json')
        return out
    oracle=out/'original-bonus';oracle.mkdir()
    (oracle/'cases.bin').write_bytes((out/'bonus-case.bin').read_bytes())
    (oracle/'source-seed.bin').write_bytes(source_seed(bundle,(out/'bonus-native-seed.bin').read_bytes()))
    original_oracle(root,oracle);ticks=compare([None],(oracle/'original.bin').read_bytes(),(out/'bonus.bin').read_bytes())
    frames=check_cache_frames(root,bundle,out);images=verify_images(args,out)
    backpressure=None
    if info.get('cache_backpressure'):
        from .smoke import held_refresh_metrics
        from .player_verify import FRAME_BYTES
        backpressure=held_refresh_metrics((out/'held-refreshes.bin').read_bytes(),(out/'motion.bin').read_bytes(),FRAME_BYTES+19)
    radar=queue_metrics(out/'radar-queue.bin',frames,16,3)
    menus=0
    header_reservations=None
    if info.get('session'):
        header_reservations=verify_header_reservations(out/'raster-times.bin',info['timing']['frame_seconds'])
        from .session_verify import verify_images as verify_menus
        menus=verify_menus(bundle,out/'session-menus')
        if menus!=2:raise ValueError('Missing actual title/first-round completion menu images')
    rows=[r.split() for r in (out/'times.bin').read_text().splitlines()];values=[]
    for a,b in zip(rows,rows[1:]):
        if any(int(r[0])<3 or r[1]=='home' or r[3]!='0' or r[4]!='0' for r in (a,b)):continue
        values.append((float(b[2])-float(a[2]))*1000)
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Completion BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),keyboard_only=True,msx_game_state_writes=False,
        original_completion_ticks=ticks,complete_visible_cache_frames=frames,full_rgb_images=images,radar_queue=radar,
        cache_backpressure=backpressure,
        full_session_menu_rgb_images=menus,
        header_reservations=header_reservations,
        main_periods=dict(median_ms=statistics.median(values),p95_ms=sorted(values)[int(.95*(len(values)-1))],maximum_ms=max(values)),
        lucky_flag_collected_first=bool(getattr(args,'lucky_first',False)),
        performance_accepted=False,scope='Initial normal round, all flags, source remaining-fuel bonus, two40-refresh pauses and fresh game; real credit/start and clear menu' if info.get('session') else 'Initial normal round, all flags, source remaining-fuel bonus, two40-refresh pauses, stopped segment and Home; credit/start/game-over UI pending'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Completion: {ticks} exact original bonus ticks, {frames} cache states, {images} RGB: {out}/report.json')
    return out
