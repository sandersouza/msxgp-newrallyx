"""Keyboard-only rock death, pause, bitmap/RGB, logical hold and reset proof."""
import os
import statistics
import subprocess
from PIL import Image,ImageChops

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest,load_assets
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .rock_route_verify import route
from .raster_scroll import compose,header,bordered


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    info=read_json(bundle/'build.json')
    if info.get('incremental_stage') not in (3,4,5,6):raise ValueError('Death proof requires stage 03 through 06')
    out=destination(root,args.output);require_ignored(root,[out/'ticks.tsv']);out.mkdir(parents=True)
    fixture=read_json(bundle/'stage-one.json')['rock_fixture']
    cache=root/'assets/arcade/native/rocks-v1';verify_manifest(cache)
    if digest(cache/'manifest.json')!=fixture['manifest_sha256']:raise ValueError('Rock fixture mismatch')
    death_cache=root/'assets/arcade/native/death-v1';verify_manifest(death_cache)
    if digest(death_cache/'manifest.json')!=info['death']['manifest_sha256']:raise ValueError('Death fixture mismatch')
    rock=fixture['positions'][0]
    path=route((cache/'work.bin').read_bytes()[:1792],(15,50),(rock['cell_x'],rock['cell_y']))
    masks={(0,-1):32,(1,0):128,(0,1):64,(-1,0):16}
    points=' '.join('{'+f'{36+x*24} {36+y*24} {masks[x-a,y-b]}'+'}'
                    for (a,b),(x,y) in zip(path,path[1:]))
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set speed 100','set throttle on','set vsync off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set pause_on_lost_focus false','set minframeskip 0','set maxframeskip 0',
        'set gamma 1','set brightness 0','set contrast 0','set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        'set blur 0','set noise 0','set scanline 0','activate_input_layer -blocking death_verify',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)};set points {{{points}}}',
        'set target 0;set phase navigate;set frames 0;set held 0;set gpu_count 0;set shot_count 0',
        'set ticks [open [file join $out ticks.tsv] w];set events [open [file join $out events.tsv] w];set times [open [file join $out times.tsv] w]',
        'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
        'proc signed {v} {expr {$v>127?$v-256:$v}}',
        'proc keys {mask} {keymatrixup 8 255;if {$mask} {keymatrixdown 8 $mask}}',
        'debug probe set_bp VDP.commandExecuting {[info exists ::begin] && [debug probe read VDP.commandExecuting]} {incr ::gpu_count}',
        *[f'debug set_bp {syms[name]} {{[reg IM]==2}} {{set ::component_begin [machine_info time]}}' for name in ('Death_Begin','Death_Tick')],
        f'debug set_bp {syms["Player_CountTick"]} {{[reg IM]==2}} {{',
        ' set s [debug read memory 0xc490];set age [debug read memory 0xc491]',
        ' puts $::ticks "[u16 0xc440] $s $age [u16 0xe079] [debug read memory 0xe06d] [debug read memory 0xe06f] [debug read memory 0xc492] [debug read memory 0xc493] [expr {round(([machine_info time]-$::component_begin)*3579545)}]"',
        '}',
        'proc step {} {',
        ' incr ::frames',
        ' set s [debug read memory 0xc490];set age [debug read memory 0xc491];set paused [debug read memory 0xc009]',
        ' puts $::events "$::frames $::phase $s $age $paused [u16 0xc440] $::gpu_count"',
        ' switch $::phase {',
        ' navigate {',
        '  if {$s==1} {keys 1;set ::phase pause;return}',
        '  set x [expr {36+24*[debug read memory 0xe070]+[signed [debug read memory 0xe06d]]}]',
        '  set y [expr {36+24*[debug read memory 0xe072]-[signed [debug read memory 0xe06f]]}]',
        '  lassign [lindex $::points $::target] tx ty mask',
        '  if {abs($tx-$x)<=6 && abs($ty-$y)<=6 && $::target<[llength $::points]-1} {incr ::target;lassign [lindex $::points $::target] tx ty mask}',
        '  keys $mask',
        ' }',
        ' pause {keys 0;if {$paused} {incr ::held};if {$::held==40} {keys 1;set ::phase hold}}',
        ' hold {keys 0;if {$s==2} {set ::phase complete;set ::held 0}}',
        ' complete {keys 0;incr ::held;if {$::held==4} {keys 2;set ::phase restart}}',
        ' restart {',
        '  if {$s!=0 || $age!=0 || [debug read memory 0xc494]!=0 || [u16 0xc482]!=0} {error "Home retained death state"}',
        '  keys 0;set ::phase reset;set ::held 0',
        ' }',
        ' reset {incr ::held;if {$::held==4} {close $::ticks;close $::events;close $::times;after frame {exit 0}}}',
        ' }',
        ' if {$::frames>1600} {error "Keyboard death route timeout"}',
        '}',
        'proc capture {name} {screenshot -raw -size auto [file join $::out "$name.png"]}',
        'proc footer {} {',
        ' set s [debug read memory 0xc490];set age [debug read memory 0xc491]',
        ' set key "$::phase-$s-$age"',
        ' if {($s && ($age<4 || $age==60 || $age==119 || $age==120)) || $::phase=="reset"} {',
        '  if {![info exists ::seen($key)]} {',
        '   set ::seen($key) 1;set n [incr ::shot_count]',
        '   set f [open [file join $::out "$n.state"] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
        '   set f [open [file join $::out "$n.vram"] wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f',
        '   after frame [list capture $n]',
        '  }',
        ' }',
        '}',
        'debug set_watchpoint write_mem 0xc000 {$wp_last_value==1 || $wp_last_value==2} {',
        ' if {$wp_last_value==1} {set ::begin [machine_info time];set ::gpu_count 0} else {',
        '  puts $::times "main $::frames $::phase $::begin [machine_info time]"',
        '  if {[catch {step} problem]} {puts stderr $problem;exit 2}',
        ' }',
        '}',
        'debug set_watchpoint write_mem 0xc03c {$wp_last_value==2 || $wp_last_value==4 || $wp_last_value==6} {',
        ' puts $::times "$wp_last_value $::frames $::phase [machine_info time]"',
        ' if {$wp_last_value==6} {if {[catch {footer} problem]} {puts stderr $problem;exit 2}}',
        '}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Death route VRAM timing violation";exit 2}',
        'after time 60 {puts stderr "Death route timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')),
            stdout=log,stderr=subprocess.STDOUT)
    rows=[list(map(int,r.split())) for r in (out/'ticks.tsv').read_text().splitlines()]
    dead=[]
    for row in rows:
        if row[1]:dead.append(row)
        elif dead:break
    if len(dead)<121 or [r[2] for r in dead[:121]]!=list(range(121)):
        raise ValueError('Death hold did not run for exactly 120 logical ticks')
    if any(r[1]!=(1 if r[2]<120 else 2) or r[3:8]!=dead[0][3:8] for r in dead):
        raise ValueError('Death sequence changed movement/anchor or completion state')
    events=[r.split() for r in (out/'events.tsv').read_text().splitlines()]
    paused=[r for r in events if r[4]=='1']
    if len(paused)!=40 or len({(r[3],r[5]) for r in paused})!=1:
        raise ValueError('Pause did not freeze death and logical ticks for 40 refreshes')
    periods={};target=info['timing']['frame_seconds']*1000
    stamps=[r.split() for r in (out/'times.tsv').read_text().splitlines()]
    for kind in ('main','2','4','6'):
        samples=[r for r in stamps if r[0]==kind and int(r[1])>2 and r[2] not in ('restart','reset')]
        deltas=[(float(b[3])-float(a[3]))*1000 for a,b in zip(samples,samples[1:])]
        if not deltas or any(abs(d-target)>.6 for d in deltas):
            raise ValueError(f'Death route refresh deadline missed: {kind}, {max(deltas,default=0):.3f} ms')
        periods[kind]=dict(min_ms=min(deltas),max_ms=max(deltas),median_ms=statistics.median(deltas))
    images=verify_images(args,out)
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle);verify_manifest(cache);verify_manifest(death_cache)
    costs=[r[8] for r in rows]
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),keyboard_only=True,msx_game_state_writes=False,
        logical_ticks=len(rows),hold_ticks=120,pause_refreshes=40,rgb_images=images,
        periods=periods,gpu_commands_max=max(int(r[6]) for r in events[3:] if r[1] not in ('restart','reset')),
        component_elapsed_cycles=dict(median=statistics.median(costs),maximum=max(costs)),
        measured_cost_scope='Death adapter elapsed cycles include interrupts; GPU commands counted; GPU durations unmeasured',
        scope='Keyboard contact, exact bitmap pixels/full RGB, movement lock, logical hold, pause and Home reset; no lives/restart gameplay yet'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Death hold, pause/reset and {images} exact full RGB images: {out}/report.json')
    return out


def verify_images(args,out,*,mismatches=None):
    """Compare every full image; optional diagnostics collect rather than accept errors."""
    bundle=args.rom.parent;info=read_json(bundle/'build.json');palette=(bundle/'palette.bin').read_bytes()
    world=(bundle/'stage-world.bin').read_bytes();tiles=(bundle/'death-pixels.bin').read_bytes()
    assets=load_assets(args.assets);black=info['sprites']['black'];enabled=info['hud_enabled'];images=0
    records=read_json(bundle/'flags.json')['records'] if info.get('incremental_stage',0)>=4 else []
    if records:
        from .stage_one import acquire,reconstruct
        from pathlib import Path
        program,reference=acquire(Path(__file__).resolve().parents[3]);cells,_,_=reconstruct(program,reference)
        cell=cells.index(0);tx=3+cell%32*3;ty=3+cell//32*3
        empty=bytes(world[(ty*8+y)*816+tx*8+x] for y in range(8) for x in range(8))
    from .player import padded_world
    padded,width,_=padded_world(world)
    for path in out.glob('*.state'):
        ram=path.read_bytes();state=ram[info.get('death',{}).get('display_state_address',0xc490)-0xc000]
        wx=int.from_bytes(ram[0xb0:0xb2],'little',signed=True);wy=int.from_bytes(ram[0xb2:0xb4],'little',signed=True)
        pixels=bytearray(padded)
        flag_at=(info.get('flag_display_state_address') or 0xc500)-0xc000
        for n,f in enumerate(records,1):
            if ram[flag_at+n]:continue
            for y in range(24):
                start=(f['tile_y']*8+y+256)*width+f['tile_x']*8+256
                pixels[start:start+24]=empty[y%8*8:y%8*8+8]*3
        if (info.get('smoke_component') or {}).get('runtime_enabled'):
            if info['smoke_component'].get('logical_row_presence_address'):
                from .smoke import verify_logical_rows
                verify_logical_rows(ram[0x2400:0x2800],ram[0x1b20:0x1b40])
            from .smoke import paint as smoke_paint
            at=info['smoke_component'].get('publication_counts_address')
            if at:
                from .smoke import verify_publication_counts
                verify_publication_counts(ram[0x1300:0x1b00],ram[at-0xc000:at-0xc000+32])
            smoke_paint(pixels,width,256,ram[0x1300:0x1b00],(bundle/'smoke-pixels.bin').read_bytes())
        if state==1:
            ax,ay=ram[0x492]*8,ram[0x493]*8
            for n in range(9):
                for y in range(8):
                    start=(ay+n//3*8+y+256)*width+ax+n%3*8+256
                    pixels[start:start+8]=tiles[n*64+y*8:n*64+y*8+8]
        points=dict(read_json(bundle/'radar.json')['scenes'][0],player=[ram[0x93],ram[0x94]])
        style=info.get('hud_style',{})
        points['border']=style.get('radar_border',True)
        points['square']=style.get('radar_square',False)
        points['cells_only']=style.get('radar_cells_only',False)
        if points['cells_only']:
            from .radar_cells import published_cells
            points['published_cells']=published_cells(ram,read_json(bundle/'radar.json')['scenes'][0]['flags'],style)
            if style.get('radar_player_sprite'):
                points['separate_player']=list(ram[0xf38:0xf3a])
                points['separate_player_visible']=bool(ram[0xf3a])
                points['separate_player_color']=ram[0xf3b]
        shown=path.with_suffix('.hudflags').read_bytes() if path.with_suffix('.hudflags').exists() else ram[0x500:0x50b]
        hidden={f['hud_slot'] for n,f in enumerate(records,1) if not shown[n]}
        points['flags']=[p for n,p in enumerate(points['flags']) if n not in hidden]
        actors=[];merged=bool(info.get('enemy_logic',{}).get('paired_radar') and ram[0x660])
        if info.get('enemy_rendered'):
            points['enemy']=[ram[0x95],ram[0x96]]
            if info.get('enemy_logic',{}).get('paired_radar'):
                points['enemy']=list(ram[0x666:0x668])
                if merged:points['extra_enemies']=[ram[0x638:0x63a]]
            from .enemy_population import actor_images
            flags=read_json(bundle/'player.json')['flags'];sprites=(bundle/'player-pixels.bin').read_bytes()
            actors=actor_images(ram,sprites,flags,info['enemy_count'],info.get('enemy_logic',{}).get('sprite_planes',2))
        if points['cells_only']:
            points['player']=list(ram[0xf00:0xf02]);points['enemy']=list(ram[0xf02:0xf04])
            points['extra_enemies']=[ram[0xf04:0xf06]] if info.get('enemy_count',0)>1 else []
        if info.get('player_blitter') and state==0:
            from .display import PLAYER_X
            flags=read_json(bundle/'player.json')['flags'];sprites=(bundle/'player-pixels.bin').read_bytes()
            actors.insert(0,(sprites[flags.index(ram[0x409])*256:][:256],PLAYER_X,108))
        if info.get('incremental_stage',0)>=5:
            score=int(''.join(str(ram[0x20a0+j]&15) for j in (6,7,0,1,2,3)))
            high=int(''.join(str(ram[0x2060+j]&15) for j in (6,7,0,1,2,3)))
            numeric=header(assets,palette,score,high)
            if info.get('enemy_rendered'):
                # The hidden header page can change after its scanlines have
                # passed. Use the digits observed at that frame's header split.
                digits=path.with_suffix('.header').read_bytes() if path.with_suffix('.header').exists() else ram[0x30c:0x318]
                if len(digits)!=12 or any(d>9 for d in digits):
                    raise ValueError(f'Invalid displayed header digits at {path.stem}')
                numeric=header(assets,palette,int(''.join(map(str,digits[:6]))),int(''.join(map(str,digits[6:]))),background=style.get('header_background'))
        else:numeric=header(assets,palette)
        expected=compose(pixels,numeric if enabled else bytes([black])*(256*8),
            (bundle/'life.bin').read_bytes(),palette,wx+256,wy+256,ram[0xa5] if info.get('incremental_stage',0)>=7 else 2,points if enabled else None,ram[0x97],
            life_digits=(bundle/'life-digits.bin').read_bytes() if enabled else None,width=width,
            fuel_pixels=(ram[0x325] if info.get('incremental_stage',0)>=6 else 30) if enabled else None,actors=actors,
            actor_top=info.get('enemy_logic',{}).get('sprite_body_top',11) if info.get('enemy_rendered') else 11,
            radar_back_points=([ram[0x690:0x692]] if info.get('enemy_count',0)==3 and enabled else
                [ram[0x638:0x63a]] if info.get('enemy_count',0)>1 and enabled and not merged and not points['cells_only'] else ()),
            life_outline=style.get('life_outline',True),
            fuel_color=ram[style['fuel_color_state_address']-0xc000]&15 if style.get('fuel_color_state_address') else None)
        overflow=set()
        if info.get('sprite_flicker') or info.get('allow_sprite_overflow'):
            background=compose(pixels,numeric if enabled else bytes([black])*(256*8),
                (bundle/'life.bin').read_bytes(),palette,wx+256,wy+256,width=width)
            from .sprite_flicker import paint,overflow_rows
            fuel_slot=info['sprites']['life_reuses_fuel_slots'][0]
            vram=path.with_suffix('.vram').read_bytes()
            hardware=paint(background,ram,vram,info,palette,
                (bundle/'sprite-colors.bin').read_bytes()[fuel_slot*16:(fuel_slot+3)*16])
            if info.get('sprite_flicker'):expected=hardware
            else:
                overflow=overflow_rows(ram,vram,info)
                for y in overflow:expected.paste(hardware.crop((0,y,256,y+1)),(0,y))
        if state==0 and not info.get('sprite_flicker') and not info.get('player_blitter'):
            from .raster_scroll import palette_rgb
            from .display import PLAYER_X,DISPLAY_SHIFT
            flags=read_json(bundle/'player.json')['flags'];sprites=(bundle/'player-pixels.bin').read_bytes()
            car=sprites[flags.index(ram[0x409])*256:][:256];colors=palette_rgb(palette)
            car_bias=info['sprites'].get('player_forbidden_y_bias',0) if (ram[0x1c]+107)&255==216 else 0
            for y in range(16):
                if 108+y+car_bias in overflow:continue
                for x in range(16):
                    if car[y*16+x]:expected.putpixel((PLAYER_X+DISPLAY_SHIFT+x,108+y+car_bias),colors[car[y*16+x]])
        expected=bordered(expected,palette)
        with Image.open(path.with_suffix('.png')) as image:actual=image.convert('RGB')
        diff=ImageChops.difference(actual,expected)
        if diff.getbbox():
            expected.save(path.with_name(path.stem+'-expected.png'));diff.save(path.with_name(path.stem+'-diff.png'))
            if mismatches is None:
                raise ValueError(f'Death RGB mismatch at {path.stem}, state {state}: {diff.getbbox()}')
            from .display import DISPLAY_SHIFT
            from . import sprite_radar
            outside=diff.copy()
            x=32+DISPLAY_SHIFT+sprite_radar.X;y=14+sprite_radar.Y
            outside.paste((0,0,0),(x,y,x+sprite_radar.WIDTH,y+sprite_radar.HEIGHT))
            mismatches.append(dict(image=path.stem,state=state,bbox=diff.getbbox(),
                outside_radar_bbox=outside.getbbox(),pixels=sum(any(p) for p in diff.getdata())))
        vram=path.with_suffix('.vram').read_bytes();stop=next((i for i in range(32) if vram[0x1f600+i*4]==216),32)
        if stop!=(info['sprites']['total_slots'] if info.get('enemy_rendered') else 17 if state else 19):raise ValueError('Death did not hide/restore only player slots')
        images+=1
    if images<5:raise ValueError('Missing death sequence RGB captures')
    return images
