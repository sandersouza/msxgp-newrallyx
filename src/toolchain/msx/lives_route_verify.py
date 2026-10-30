"""Keyboard-only special flag, death/restart, next flag, all lives and Home proof."""
import os
import statistics
import subprocess
from PIL import Image
from src.toolchain.graphics.roms import input_records,load_metadata,validate_roms
from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .rock_route_verify import route
from .player_verify import FRAME_BYTES,check_cache
from .screen5 import packed
from .death_verify import verify_images


def paths_for(board,records,rock):
    spawn=(15,50);special=next(i for i,f in enumerate(records) if f['kind']==2)
    def cell(i):
        a=records[i]['address']-0x9800
        return a%32,a//32
    def find(start,goal,collected):
        cells=bytearray(board)
        for i,c in enumerate(cells):
            if c==3:cells[i]=0x87
        for i in range(10):
            x,y=cell(i)
            if i not in collected and (x,y)!=goal:cells[y*32+x]=0x87
        cells[goal[1]*32+goal[0]]=0
        return route(cells,start,goal)
    first=find(spawn,cell(special),set())+find(cell(special),rock,{special})[1:]
    choices=[]
    for i,f in enumerate(records):
        if f['kind']!=1:continue
        try:choices.append((len(find(spawn,cell(i),{special})),i))
        except ValueError:pass
    normal=min(choices)[1]
    second=find(spawn,cell(normal),{special})+find(cell(normal),rock,{special,normal})[1:]
    third=find(spawn,rock,{special,normal})
    return [first,second,third],special,normal


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if info.get('incremental_stage')!=7:raise ValueError('Life keyboard route requires stage 07')
    out=destination(root,args.output);require_ignored(root,[out/'motion.bin']);out.mkdir(parents=True)
    source=root/'assets/arcade/native/rocks-v1';verify_manifest(source)
    board=(source/'work.bin').read_bytes()[:1792];records=read_json(bundle/'flags.json')['records']
    rock=read_json(bundle/'stage-one.json')['rock_fixture']['positions'][0]
    paths,special,normal=paths_for(board,records,(rock['cell_x'],rock['cell_y']))
    masks={(0,-1):32,(1,0):128,(0,1):64,(-1,0):16}
    routes=' '.join('{'+(' '.join('{'+f'{36+x*24} {36+y*24} {masks[x-a,y-b]}'+'}'
        for (a,b),(x,y) in zip(p,p[1:])))+'}' for p in paths)
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set speed 100','set throttle on','set vsync off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set minframeskip 0','set maxframeskip 0','set gamma 1','set brightness 0','set contrast 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','set blur 0','set noise 0','set scanline 0',
        'activate_input_layer -blocking life_route',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)};set routes {{{routes}}};set special {special};set normal {normal}',
        'set frames 0;set leg 0;set target 0;set phase navigate;set seen_flags 0;set deaths 0;set held 0;set warmup 0;set capture 0;set shots 0;set gpu_count 0;set reload 0',
        'foreach name {motion cache events times ticks reloads} {set ${name}_out [open [file join $out "$name.bin"] wb]}',
        'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
        'proc signed {v} {expr {$v>127?$v-256:$v}}',
        'proc keys {m} {keymatrixup 8 255;if {$m} {keymatrixdown 8 $m}}',
        'proc score {} {set s 0;foreach i {4 5 6 7 0 1 2 3} {set s [expr {$s*10+([debug read memory [expr {0xe0a0+$i}]]&15)}]};return $s}',
        'debug probe set_bp VDP.commandExecuting {[info exists ::begin] && [debug probe read VDP.commandExecuting]} {incr ::gpu_count}',
        'debug set_watchpoint write_mem 0xc5c1 {$wp_last_value==1 || $wp_last_value==0} {',
        ' if {$wp_last_value==1} {set ::reload 1;set ::reload_begin [machine_info time];keys 0} elseif {[info exists ::reload_begin]} {',
        '  puts $::reloads_out "$::frames [expr {([machine_info time]-$::reload_begin)*1000}]";unset ::reload_begin;set ::warmup 2',' }','}',
        f'debug set_bp {syms["Player_CountTick"]} {{[reg IM]==2}} {{',
        ' if {[debug read memory 0xc490]} {puts $::ticks_out "[debug read memory 0xc5c2] [debug read memory 0xc490] [debug read memory 0xc491] [debug read memory 0xe00f] [u16 0xe079] [debug read memory 0xe06d] [debug read memory 0xe06f]"}','}',
        'proc snapshot {} {',
        ' puts -nonewline $::motion_out [debug read_block memory 0xe000 4096];puts -nonewline $::motion_out [debug read_block memory 0xc400 96]',
        ' puts -nonewline $::motion_out [debug read_block memory 0xc0b0 4];puts -nonewline $::motion_out [debug read_block memory 0xc500 11]',
        ' puts -nonewline $::motion_out [debug read_block memory 0xc490 5];puts -nonewline $::motion_out [debug read_block memory 0xc5c0 3]',
        ' puts -nonewline $::cache_out [debug read_block VRAM 0 65536]','}',
        'proc step {} {',
        ' incr ::frames;set state [debug read memory 0xc490];set age [debug read memory 0xc491];set count [debug read memory 0xc50b]',
        ' set deaths [debug read memory 0xc5c2];set lives [debug read memory 0xe00f];set paused [debug read memory 0xc009]',
        ' puts $::events_out "$::frames $::phase $deaths $state $age $lives $count [debug read memory 0xe250] [debug read memory 0xe023] [expr {10*[debug read memory 0xe26b]+[debug read memory 0xe26a]}] [score] $paused $::gpu_count $::reload $::warmup"',
        ' snapshot',
        ' if {$::warmup} {incr ::warmup -1;if {$::warmup==0} {set ::capture 1}}',
        ' switch $::phase {',
        ' navigate {',
        '  if {$deaths>$::deaths} {',
        '   if {$lives!=3-$deaths} {error "Life did not decrement once"};set ::deaths $deaths;keys 0;set ::phase hold',
        '   if {$deaths==1} {keys 1;set ::phase death_pause;set ::held 0};return','  }',
        '  if {$count>$::seen_flags} {set ::seen_flags $count;keys 1;set ::held 0;set ::phase flag_pause;return}',
        '  set x [expr {36+24*[debug read memory 0xe070]+[signed [debug read memory 0xe06d]]}]',
        '  set y [expr {36+24*[debug read memory 0xe072]-[signed [debug read memory 0xe06f]]}]',
        '  set points [lindex $::routes $::leg];lassign [lindex $points $::target] tx ty mask',
        '  if {abs($tx-$x)<=6 && abs($ty-$y)<=6 && $::target<[llength $points]-1} {incr ::target;lassign [lindex $points $::target] tx ty mask}',
        '  keys $mask',' }',
        ' flag_pause {keys 0;if {$paused} {incr ::held};if {$::held==4} {',
        '  if {$count!=$::leg+1 || [score]!=200+100*$::leg} {error "Post-life flag points did not reset their ordinal"}',
        '  set ::capture 1;keys 1;set ::phase navigate',' }}',
        ' death_pause {keys 0;if {$paused} {incr ::held};if {$::held==4} {set ::capture 1};if {$::held==40} {set ::capture 1;keys 1;set ::phase hold}}',
        ' hold {',
        '  keys 0',
        '  if {$state==0} {',
        '   if {$lives!=3-$deaths || $count!=$deaths || [debug read memory 0xe250]!=0 || [debug read memory 0xe023]!=0 || [score]!=100+100*$deaths || [debug read memory 0xe26b]!=60 || [debug read memory 0xe26a]!=0} {error "Restart lost score/flags/fuel/ordinal"}',
        '   if {[debug read memory [expr {0xc501+$::special}]]!=0 || ($deaths==2 && [debug read memory [expr {0xc501+$::normal}]]!=0)} {error "Restart resurrected a collected flag"}',
        '   set ::leg $deaths;set ::target 0;set ::phase navigate',
        '  } elseif {[debug read memory 0xc5c0]==2} {',
        '   if {$deaths!=3 || $lives!=0} {error "Game over before three deaths"}',
        '   set ::phase game_over;set ::held 0;set ::stopped [debug read_block memory 0xe068 24];set ::stopped_fuel [debug read_block memory 0xe26a 2]',
        '  }',' }',
        ' game_over {',
        '  keys 128;incr ::held',
        '  if {[debug read_block memory 0xe068 24] ne $::stopped || [debug read_block memory 0xe26a 2] ne $::stopped_fuel || [debug read memory 0xe00f]!=0} {error "Game-over run resumed"}',
        '  if {$::held==4 || $::held==39} {set ::capture 1}',
        '  if {$::held==40} {keys 2;set ::phase home;set ::held 0}',' }',
        ' home {',
        '  keys 0;incr ::held',
        '  if {$lives!=3 || $count!=0 || $deaths!=0 || [score]!=0 || $state!=0} {error "Home did not reset the life fixture"}',
        '  if {$::held==3} {set ::capture 1}',
        '  if {$::held==5} {set ::done 1;foreach n {motion cache events times ticks reloads} {close [set ::${n}_out]};after frame {exit 0}}',' }',' }',
        ' if {$::frames>6000} {error "Life keyboard route timeout"}','}',
        'proc capture {n} {screenshot -raw -size auto [file join $::out "$n.png"]}',
        'proc footer {} {',
        ' set state [debug read memory 0xc490];set age [debug read memory 0xc491];set deaths [debug read memory 0xc5c2]',
        ' set key "$deaths-$state-$age"',
        ' if {$state==1 && $age in {1 60 95 119} && ![info exists ::seen($key)]} {set ::seen($key) 1;set ::capture 1}',
        ' if {$::capture && !$::reload && !$::warmup} {',
        '  set ::capture 0;set n [incr ::shots];set f [open [file join $::out "$n.state"] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
        '  set f [open [file join $::out "$n.vram"] wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f;after frame [list capture $n]',' }','}',
        'debug set_watchpoint write_mem 0xc000 {![info exists ::done] && ($wp_last_value==1 || $wp_last_value==2)} {',
        ' if {$wp_last_value==1} {set ::begin [machine_info time];set ::gpu_count 0;set ::reload 0} else {',
        '  puts $::times_out "main $::frames $::phase $::begin $::reload $::warmup"',
        '  if {[catch {step} problem]} {puts stderr $problem;exit 2}',' }','}',
        'debug set_watchpoint write_mem 0xc03c {![info exists ::done] && $wp_last_value in {2 4 6}} {',
        ' puts $::times_out "$wp_last_value $::frames $::phase [machine_info time] $::reload $::warmup"',
        ' if {$wp_last_value==6} {if {[catch {footer} problem]} {puts stderr $problem;exit 2}}','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Life route VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Life route timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    inputs=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    json_write(out/'verification-inputs.json',dict(roms=inputs,bios=bios))
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    return analyze(root,args,out,inputs,bios)


def analyze(root,args,out,inputs,bios):
    if (out/'manifest.json').exists():raise ValueError('Life proof is already sealed')
    bundle=args.rom.parent;info=read_json(bundle/'build.json')
    ticks=[list(map(int,r.split())) for r in (out/'ticks.bin').read_text().splitlines()]
    for death,limit in ((1,120),(2,120),(3,96)):
        rows=[r for r in ticks if r[0]==death]
        by_age={r[2]:r for r in rows}
        if set(by_age)!=set(range(limit+1)) or any(r[1]!=(1 if r[2]<limit else 2) or r[3]!=3-death or r[4:]!=rows[0][4:] for r in rows):raise ValueError(f'Life {death} hold/movement mismatch')
    events=[r.split() for r in (out/'events.bin').read_text().splitlines()]
    paused=[r for r in events if r[1]=='death_pause' and r[11]=='1']
    if len(paused)!=40 or len({(r[4],r[9]) for r in paused})!=1:raise ValueError('Death pause did not freeze life/fuel state')
    frames=check_cache_frames(root,bundle,out)
    images=verify_images(args,out)
    if images<12:raise ValueError('Insufficient life/restart images')
    stamps=[r.split() for r in (out/'times.bin').read_text().splitlines()];periods={}
    transitions={int(r[0]) for r in events if r[13]!='0' or r[14]!='0' or r[1]=='home'}
    for kind in ('main','2','4','6'):
        rows=[r for r in stamps if r[0]==kind]
        values=[]
        for a,b in zip(rows,rows[1:]):
            if any(int(r[1])<3 or r[2]=='home' or r[4]!='0' or r[5]!='0' for r in (a,b)):continue
            # A reload can suppress footer interrupts completely; its adjacent
            # footer samples then look normal. Bind the interval to the explicit
            # observed reload/warm-up events, including intervening frames.
            if any(n in transitions for n in range(int(a[1]),int(b[1])+1)):continue
            values.append((float(b[3])-float(a[3]))*1000)
        if not values or any(abs(v-info['timing']['frame_seconds']*1000)>.6 for v in values):raise ValueError(f'Life route refresh missed: {kind}, {max(values,default=0):.3f} ms')
        periods[kind]=dict(samples=len(values),min_ms=min(values),max_ms=max(values),median_ms=statistics.median(values))
    reloads=[float(r.split()[1]) for r in (out/'reloads.bin').read_text().splitlines()]
    if len(reloads)!=2:raise ValueError('Expected exactly two gameplay reloads')
    if inputs!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())) or bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Source/BIOS changed')
    verify_manifest(bundle)
    diagnostics=list(out.glob('*-diff.png'))+list(out.glob('*-expected.png'))
    if diagnostics:
        archive=out/'diagnostics/previous-oracle';archive.mkdir(parents=True)
        for p in diagnostics:p.rename(archive/p.name)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),keyboard_only=True,msx_game_state_writes=False,
        verifier_sha256={p:digest(root/p) for p in ('src/toolchain/msx/lives_route_verify.py','src/toolchain/msx/death_verify.py','src/toolchain/msx/player.py')},
        deaths=3,remaining_lives=[2,1,0],hold_ticks=[120,120,96],pause_refreshes=40,rgb_images=images,
        visible_cache_frames=frames,score_preserved=True,flags_preserved=True,ordinal_reset=True,
        reload_ms=reloads,periods=periods,gpu_commands_max=max(int(r[12]) for r in events if r[13]=='0' and r[1]!='home'),
        scope='Special flag before death, next normal flag after restart, same-round persistence, three deaths, pause, stopped zero-life run and Home; real RGB/cache including right edge; reload and two warm-up frames excluded explicitly'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Three keyboard deaths/restarts, {frames} cache states and {images} full RGB: {out}/report.json')
    return out


def check_cache_frames(root,bundle,out):
    from .stage_one import acquire,reconstruct
    width,height=1328,1904;world=(bundle/'stage-world.bin').read_bytes();padded=bytearray(width*height)
    for y in range(height):
        sy=y-256
        for x in range(width):
            sx=x-256;padded[y*width+x]=world[sy*816+sx] if 0<=sx<816 and 0<=sy<1392 else world[sy%24*816+sx%24]
    program,reference=acquire(root);cells,_,_=reconstruct(program,reference);cell=cells.index(0)
    tx=3+cell%32*3;ty=3+cell//32*3
    empty=bytes(world[(ty*8+y)*816+tx*8+x] for y in range(8) for x in range(8))
    records=read_json(bundle/'flags.json')['records'];tiles=(bundle/'death-pixels.bin').read_bytes()
    flags=read_json(bundle/'player.json')['flags'];sprites=(bundle/'player-pixels.bin').read_bytes();maps={}
    blitter=read_json(bundle/'build.json').get('player_blitter',False)
    smoke=bool((read_json(bundle/'build.json').get('smoke_component') or {}).get('runtime_enabled'))
    raw=(out/'motion.bin').read_bytes();size=FRAME_BYTES+19
    if len(raw)%size:raise ValueError('Incomplete life motion data')
    count=len(raw)//size
    smoke_display=(out/'smoke-display.bin').read_bytes() if smoke else None
    if smoke and len(smoke_display)!=count*2048:raise ValueError('Missing continuous smoke publication state')
    counted=bool((read_json(bundle/'build.json').get('smoke_component') or {}).get('publication_counts_address'))
    smoke_counts=(out/'smoke-counts.bin').read_bytes() if counted else None
    if counted and len(smoke_counts)!=count*32:raise ValueError('Missing continuous smoke publication counts')
    logical_rows=bool((read_json(bundle/'build.json').get('smoke_component') or {}).get('logical_row_presence_address'))
    native_rows=(out/'smoke-native-rows.bin').read_bytes() if logical_rows else None
    if logical_rows and len(native_rows)!=count*32:raise ValueError('Missing continuous native smoke row presence')
    presented=(out/'presentation.bin').read_bytes() if (out/'presentation.bin').exists() else None
    if presented is not None and (len(presented)!=count or any(s>2 for s in presented)):
        raise ValueError('Incomplete/invalid presentation-state trace')
    flag_display=(out/'flag-display.bin').read_bytes() if (out/'flag-display.bin').exists() else None
    if read_json(bundle/'build.json').get('flag_display_state_address') and (flag_display is None or len(flag_display)!=count*11):
        raise ValueError('Missing displayed flag-state trace')
    if flag_display is not None:
        from .flags import verify_display_snapshots
        verify_display_snapshots(b''.join(raw[i*size+FRAME_BYTES:i*size+FRAME_BYTES+11] for i in range(count)),
            flag_display,[int.from_bytes(raw[i*size+4160:i*size+4162],'little') for i in range(count)])
    with (out/'cache.bin').open('rb') as f:
        for i in range(count):
            r=raw[i*size:(i+1)*size];active=r[FRAME_BYTES:FRAME_BYTES+11];state,age,ax,ay,_=r[FRAME_BYTES+11:FRAME_BYTES+16]
            if flag_display is not None:active=flag_display[i*11:(i+1)*11]
            if presented is not None:state=presented[i]
            display=smoke_display[i*2048:(i+1)*2048] if smoke else None
            if counted:
                from .smoke import verify_publication_counts
                verify_publication_counts(display,smoke_counts[i*32:(i+1)*32])
            if logical_rows:
                from .smoke import verify_logical_rows
                verify_logical_rows(r[0x400:0x800],native_rows[i*32:(i+1)*32])
            key=(active,ax if state==1 else -1,ay if state==1 else -1,display)
            if key not in maps:
                image=bytearray(padded)
                for n,flag in enumerate(records,1):
                    if active[n]:continue
                    for y in range(24):
                        start=(flag['tile_y']*8+y+256)*width+flag['tile_x']*8+256
                        image[start:start+24]=empty[y%8*8:y%8*8+8]*3
                if smoke:
                    from .smoke import paint as smoke_paint
                    smoke_paint(image,width,256,display,(bundle/'smoke-pixels.bin').read_bytes())
                if state==1:
                    for n in range(9):
                        for y in range(8):
                            start=(ay*8+n//3*8+y+256)*width+ax*8+n%3*8+256
                            image[start:start+8]=tiles[n*64+y*8:n*64+y*8+8]
                maps[key]=packed(image)
            bitmap=bytearray(maps[key])
            wx=int.from_bytes(r[FRAME_BYTES-4:FRAME_BYTES-2],'little',signed=True);wy=int.from_bytes(r[FRAME_BYTES-2:FRAME_BYTES],'little',signed=True)
            if blitter and state==0:
                from .display import PLAYER_X
                car=sprites[flags.index(r[4105])*256:][:256]
                for y in range(16):
                    for x,color in enumerate(car[y*16:y*16+16]):
                        if not color:continue
                        px=wx+PLAYER_X-8+x;py=wy+97+y;at=(py+256)*(width//2)+(px+256)//2
                        bitmap[at]=bitmap[at]&15|color<<4 if px%2==0 else bitmap[at]&240|color
            if r[4120]:
                px=int.from_bytes(r[4101:4103],'little');py=int.from_bytes(r[4103:4105],'little');car=sprites[flags.index(r[4105])*256:][:256]
                for x,color in enumerate(car[240:]):
                    if not color:continue
                    at=(py+7+256)*(width//2)+(px-8+x+256)//2
                    bitmap[at]=bitmap[at]&15|color<<4 if (px-8+x)%2==0 else bitmap[at]&240|color
            check_cache(f.read(65536),bitmap,width,wx,wy,i)
        if f.read(1):raise ValueError('Extra life cache captures')
    return count
