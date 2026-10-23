"""Drive to every original flag and revisit one after cache eviction, using keys."""
import os
import statistics
import subprocess
from PIL import Image,ImageChops
from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest,read_json,verify_manifest,load_assets
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .rock_route_verify import route
from .flags_verify import original_oracle,analyze
from .player_verify import check_cache,FRAME_BYTES
from .raster_scroll import compose,header,bordered,palette_rgb
from .display import PLAYER_X,DISPLAY_SHIFT
from .screen5 import packed


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if info.get('incremental_stage') not in (4,5,6,7):raise ValueError('All-flag route requires stage 04 through 07')
    out=destination(root,args.output);require_ignored(root,[out/'contacts.tsv']);out.mkdir(parents=True)
    original_inputs=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    source=root/'references/stage-one/rocks-v1';verify_manifest(source)
    fixture=read_json(bundle/'stage-one.json')['rock_fixture']
    if digest(source/'manifest.json')!=fixture['manifest_sha256']:raise ValueError('Flag route rock fixture mismatch')
    board=bytearray((source/'work.bin').read_bytes()[:1792]);records=read_json(bundle/'flags.json')['records']
    # Rocks are genuine obstacles for route planning; collision logic remains active.
    for i,c in enumerate(board):
        if c==3:board[i]=0x87
    start=(15,50);nodes=[start]
    for f in records+[records[0]]:
        c=f['address']-0x9800;goal=(c%32,c//32)
        nodes.extend(route(board,nodes[-1],goal)[1:])
    masks={(0,-1):32,(1,0):128,(0,1):64,(-1,0):16}
    points=' '.join('{'+f'{36+x*24} {36+y*24} {masks[x-a,y-b]}'+'}'
                    for (a,b),(x,y) in zip(nodes,nodes[1:]))
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set speed 100','set throttle on','set vsync off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set pause_on_lost_focus false','set minframeskip 0','set maxframeskip 0',
        'set gamma 1','set brightness 0','set contrast 0','set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        'set blur 0','set noise 0','set scanline 0','activate_input_layer -blocking flag_route',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)};set points {{{points}}}',
        'set target 0;set phase navigate;set seen 0;set frames 0;set held 0;set gpu_count 0;set capture 0;set shots 0;set index 0',
        'set trace [open [file join $out contacts.tsv] w];set frames_out [open [file join $out motion.bin] wb];set cache [open [file join $out cache.bin] wb]',
        'set events [open [file join $out events.tsv] w];set times [open [file join $out times.tsv] w]',
        'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
        'proc signed {v} {expr {$v>127?$v-256:$v}}',
        'proc keys {mask} {keymatrixup 8 255;if {$mask} {keymatrixdown 8 $mask}}',
        'debug probe set_bp VDP.commandExecuting {[info exists ::begin] && [debug probe read VDP.commandExecuting]} {incr ::gpu_count}',
        f'debug set_bp {syms["Flag_Update"]} {{[reg IM]==2}} {{set ::component_begin [machine_info time]}}',
        f'debug set_bp {syms["Player_AfterFlag"]} {{[reg IM]==2 && $::phase!="restart" && $::phase!="reset"}} {{',
        ' binary scan [debug read_block memory 0xc500 14] cu* state',
        ' puts $::trace "$::index [lindex $state 11] [lindex $state 12] [lindex $state 13] [join [lrange $state 0 10]] [expr {round(([machine_info time]-$::component_begin)*3579545)}] [u16 0xe079] [debug read memory 0xe06d] [debug read memory 0xe06f]"',
        ' incr ::index','}',
        'proc step {} {',
        ' incr ::frames',
        ' if {[debug read memory 0xc490]!=0} {error "All-flag route hit a rock"}',
        ' set count [debug read memory 0xc50b];set paused [debug read memory 0xc009]',
        ' puts $::events "$::frames $::phase $count $paused $::gpu_count"',
        ' if {$::phase!="restart" && $::phase!="reset"} {',
        '  puts -nonewline $::frames_out [debug read_block memory 0xe000 4096];puts -nonewline $::frames_out [debug read_block memory 0xc400 96]',
        '  puts -nonewline $::frames_out [debug read_block memory 0xc0b0 4];puts -nonewline $::frames_out [debug read_block memory 0xc500 11]',
        '  puts -nonewline $::cache [debug read_block VRAM 0 65536]',
        ' }',
        ' switch $::phase {',
        ' navigate {',
        '  if {$count>$::seen} {set ::seen $count;keys 1;set ::phase pause;set ::held 0;return}',
        '  set x [expr {36+24*[debug read memory 0xe070]+[signed [debug read memory 0xe06d]]}]',
        '  set y [expr {36+24*[debug read memory 0xe072]-[signed [debug read memory 0xe06f]]}]',
        '  lassign [lindex $::points $::target] tx ty mask',
        '  if {abs($tx-$x)<=6 && abs($ty-$y)<=6} {',
        '   if {$::target==[llength $::points]-1} {if {$count!=10} {error "Route missed flags"};keys 1;set ::phase final;set ::held 0;return}',
        '   incr ::target;lassign [lindex $::points $::target] tx ty mask',
        '  }',
        '  keys $mask',
        ' }',
        ' pause {keys 0;if {$paused} {incr ::held};if {$::held==4} {set ::capture 1;keys 1;set ::phase navigate}}',
        ' final {keys 0;if {$paused} {incr ::held};if {$::held==4} {set ::capture 1;keys 2;set ::phase restart}}',
        ' restart {',
        '  if {$count!=0 || [debug read memory 0xc50e]!=0} {error "Home retained collection state"}',
        '  binary scan [debug read_block memory 0xc501 10] cu* active',
        '  foreach v $active {if {$v!=1} {error "Home did not restore flags"}}',
        '  keys 0;set ::phase reset;set ::held 0',
        ' }',
        ' reset {incr ::held;if {$::held==3} {set ::capture 1};if {$::held==5} {set ::done 1;close $::trace;close $::frames_out;close $::cache;close $::events;close $::times;after frame {exit 0}}}',
        ' }',
        ' if {$::frames>8500} {error "All-flag keyboard route timeout"}',
        '}',
        'proc screenshot_frame {n} {screenshot -raw -size auto [file join $::out "$n.png"]}',
        'proc footer {} {',
        ' if {$::capture} {',
        '  set ::capture 0;set n [incr ::shots]',
        '  set f [open [file join $::out "$n.state"] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
        '  after frame [list screenshot_frame $n]',
        ' }',
        '}',
        'debug set_watchpoint write_mem 0xc000 {![info exists ::done] && ($wp_last_value==1 || $wp_last_value==2)} {',
        ' if {$wp_last_value==1} {set ::begin [machine_info time];set ::gpu_count 0} else {',
        '  puts $::times "main $::frames $::phase $::begin [machine_info time]"',
        '  if {[catch {step} problem]} {puts stderr $problem;exit 2}',
        ' }','}',
        'debug set_watchpoint write_mem 0xc03c {![info exists ::done] && ($wp_last_value==2 || $wp_last_value==4 || $wp_last_value==6)} {',
        ' puts $::times "$wp_last_value $::frames $::phase [machine_info time]"',
        ' if {$wp_last_value==6} {if {[catch {footer} problem]} {puts stderr $problem;exit 2}}','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Flag route VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Flag keyboard route timeout";exit 2}']
    if info.get('incremental_stage',0)>=6:
        from .fuel_verify import route_capture
        lines.extend(route_capture(syms,out))
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    json_write(out/'verification-inputs.json',dict(roms=original_inputs,bios=bios))
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    return analyze_route(root,args,out,board,records,nodes,original_inputs,bios,source)


def analyze_route(root,args,out,board,records,nodes,original_inputs,bios,source):
    bundle=args.rom.parent;info=read_json(bundle/'build.json')
    rows=[list(map(int,r.split())) for r in (out/'contacts.tsv').read_text().splitlines()]
    cases=[(r[16],r[17],r[18],int(i==0)) for i,r in enumerate(rows)]
    version=original_oracle(root,out,cases,(bundle/'flag-records.bin').read_bytes())
    report=analyze(cases,records,(out/'original.bin').read_bytes(),[r[:16] for r in rows])
    if report['collection_events']!=10 or rows[-1][1]!=10:raise ValueError('Did not collect all ten flags exactly once')
    if info.get('incremental_stage',0)>=6:
        from .fuel_verify import verify_route
        report['exact_original_lucky_ticks']=verify_route(root,bundle,out)
    images,cache_frames=check_graphics(root,args,out,board,records)
    stamps=[r.split() for r in (out/'times.tsv').read_text().splitlines()];periods={}
    for kind in ('main','2','4','6'):
        samples=[r for r in stamps if r[0]==kind and int(r[1])>2 and r[2] not in ('restart','reset')]
        deltas=[(float(b[3])-float(a[3]))*1000 for a,b in zip(samples,samples[1:])]
        if not deltas or any(abs(d-info['timing']['frame_seconds']*1000)>.6 for d in deltas):
            raise ValueError(f'All-flag route refresh deadline missed: {kind}, {max(deltas,default=0):.3f} ms')
        periods[kind]=dict(min_ms=min(deltas),max_ms=max(deltas),median_ms=statistics.median(deltas))
    events=[r.split() for r in (out/'events.tsv').read_text().splitlines()]
    gpu=max(int(r[4]) for r in events[3:] if r[1] not in ('restart','reset'))
    if gpu>20:raise ValueError('All-flag route exceeded the graphics budget')
    if original_inputs!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):raise ValueError('Original ROMs changed')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle);verify_manifest(source)
    report.update(rom_sha256=digest(args.rom),keyboard_only=True,msx_game_state_writes=False,
        mame_version=version,route_cells=len(nodes),visible_cache_frames=cache_frames,rgb_images=images,
        periods=periods,gpu_commands_max=gpu,revisited_after_all_collected=True,home_reset_verified=True)
    json_write(out/'report.json',report);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'All ten flags/revisit/reset, {cache_frames} cache states and {images} full RGB images: {out}/report.json')
    return out


def check_graphics(root,args,out,board,records):
    bundle=args.rom.parent;info=read_json(bundle/'build.json');world=(bundle/'stage-world.bin').read_bytes()
    width,height=1328,1904;padded=bytearray(width*height)
    for y in range(height):
        sy=y-256
        for x in range(width):
            sx=x-256;padded[y*width+x]=world[sy*816+sx] if 0<=sx<816 and 0<=sy<1392 else world[(sy%24)*816+sx%24]
    cell=board.index(0);tx=3+cell%32*3;ty=3+cell//32*3
    empty=bytes(world[(ty*8+y)*816+tx*8+x] for y in range(8) for x in range(8))
    maps={}
    def changed(states):
        states=bytes(states)
        if states not in maps:
            result=bytearray(padded)
            for n,f in enumerate(records,1):
                if states[n]:continue
                for y in range(24):
                    start=(f['tile_y']*8+y+256)*width+f['tile_x']*8+256
                    result[start:start+24]=empty[y%8*8:y%8*8+8]*3
            maps[states]=(result,packed(result))
        return maps[states]
    flags=read_json(bundle/'player.json')['flags'];sprites=(bundle/'player-pixels.bin').read_bytes()
    raw=(out/'motion.bin').read_bytes();size=FRAME_BYTES+11
    if len(raw)%size:raise ValueError('Incomplete flag route cache trace')
    count=len(raw)//size
    scoring=info.get('incremental_stage',0)>=5
    bonus={}
    if info.get('incremental_stage',0)>=6:
        from .fuel_verify import RECORD
        from .score_verify import DIGITS
        initial=(out/'bonus-case.bin').read_bytes()[11:19]
        initial=int(''.join(str(initial[j]&15) for j in DIGITS))
        original=(out/'fuel-original/original.bin').read_bytes()
        for line in (out/'bonus-times.tsv').read_text().splitlines():
            frame,tick=map(int,line.split())
            r=original[tick*RECORD:(tick+1)*RECORD]
            bonus[frame]=int(''.join(str(r[21+j]&15) for j in DIGITS))-initial
    previous=bytes([0]+[1]*10);ordinal=score=special=0
    extra=0
    with (out/'cache.bin').open('rb') as cache:
        for i in range(count):
            r=raw[i*size:(i+1)*size];_,bitmap=changed(r[-11:]);bitmap=bytearray(bitmap)
            if scoring:
                active=r[-11:]
                for n,(old,new) in enumerate(zip(previous,active)):
                    if old and not new:
                        ordinal+=1
                        if records[n-1]['kind']==2:special^=1
                        score+=ordinal*100*(2 if special else 1)
                previous=active
                if i in bonus:extra=bonus[i]
                native_score=int(''.join(str(r[0xa0+j]&15) for j in (4,5,6,7,0,1,2,3)))
                if native_score!=score+extra:raise ValueError(f'Live flag scoring mismatch at {i}: {native_score} / {score}+{extra}')
            wx=int.from_bytes(r[FRAME_BYTES-4:FRAME_BYTES-2],'little',signed=True);wy=int.from_bytes(r[FRAME_BYTES-2:FRAME_BYTES],'little',signed=True)
            if r[4120]:
                px=int.from_bytes(r[4101:4103],'little');py=int.from_bytes(r[4103:4105],'little')
                car=sprites[flags.index(r[4105])*256:][:256]
                for x,color in enumerate(car[240:]):
                    if not color:continue
                    p=(py+7+256)*(width//2)+(px-8+x+256)//2
                    bitmap[p]=(bitmap[p]&15)|(color<<4) if (px-8+x)%2==0 else (bitmap[p]&240)|color
            check_cache(cache.read(65536),bitmap,width,wx,wy,i)
        if cache.read(1):raise ValueError('Extra flag route cache data')
    palette=(bundle/'palette.bin').read_bytes();colors=palette_rgb(palette);assets=load_assets(args.assets)
    enabled=info['hud_enabled'];images=0
    for p in out.glob('*.state'):
        ram=p.read_bytes();pixels,_=changed(ram[0x500:0x50b]);wx=int.from_bytes(ram[0xb0:0xb2],'little',signed=True);wy=int.from_bytes(ram[0xb2:0xb4],'little',signed=True)
        points=dict(read_json(bundle/'radar.json')['scenes'][0],player=[ram[0x93],ram[0x94]])
        hidden={f['hud_slot'] for n,f in enumerate(records,1) if not ram[0x500+n]}
        points['flags']=[v for n,v in enumerate(points['flags']) if n not in hidden]
        if scoring:
            native_score=int(''.join(str(ram[0x20a0+j]&15) for j in (6,7,0,1,2,3)))
            native_high=int(''.join(str(ram[0x2060+j]&15) for j in (6,7,0,1,2,3)))
            numeric=header(assets,palette,native_score,native_high)
        else:numeric=header(assets,palette)
        expected=compose(pixels,numeric if enabled else bytes([info['sprites']['black']])*(256*8),
            (bundle/'life.bin').read_bytes(),palette,wx+256,wy+256,2,points if enabled else None,ram[0x97],
            life_digits=(bundle/'life-digits.bin').read_bytes() if enabled else None,width=width,
            fuel_pixels=(ram[0x325] if info.get('incremental_stage',0)>=6 else 30) if enabled else None)
        car=sprites[flags.index(ram[0x409])*256:][:256]
        for y in range(16):
            for x in range(16):
                if car[y*16+x]:expected.putpixel((PLAYER_X+DISPLAY_SHIFT+x,108+y),colors[car[y*16+x]])
        expected=bordered(expected,palette)
        with Image.open(p.with_suffix('.png')) as image:actual=image.convert('RGB')
        diff=ImageChops.difference(actual,expected)
        if diff.getbbox():
            expected.save(p.with_name(p.stem+'-expected.png'));diff.save(p.with_name(p.stem+'-diff.png'))
            raise ValueError(f'Flag route RGB mismatch at {p.stem}: {diff.getbbox()}')
        images+=1
    if images!=12:raise ValueError(f'Incomplete all-flag/revisit/reset images: {images}')
    return images,count
