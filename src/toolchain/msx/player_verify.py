"""Compare keyboard-controlled MSX movement with the original Z80 in MAME."""
import os
from pathlib import Path
import subprocess
import statistics
from PIL import Image,ImageChops
from .build import destination
from .emulator import tcl, reference_machine,scanout_recording_tcl
from .player import coordinates
from .raster_scroll import compose,header,bordered
from .display import VIEWPORT_WIDTH, PLAYER_X, DISPLAY_SHIFT, HORIZONTAL_ADJUST, TOTAL_SPRITES
from .screen5 import packed
from src.toolchain.scenes.bundle import digest,read_json,verify_manifest,load_assets
from src.toolchain.scenes.storage import json_write,require_ignored

FRAME_BYTES=4096+96+4


def verify(root,args):
    headless=getattr(args,'headless',False)
    output=destination(root,args.output);verify_manifest(args.rom.parent)
    info=read_json(args.rom.parent/'build.json')
    slots=info.get('sprites',{}).get('total_slots',TOTAL_SPRITES+(2 if info.get('enemy_rendered') else 0))
    collections=info.get('incremental_stage',0)>=4
    require_ignored(root,[output/'commands.bin',output/'native.bin'])
    output.mkdir(parents=True)
    lines=['set save_settings_on_exit false',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set speed 100',f'set throttle {"off" if headless else "on"}',
        'set z80_freq 3579545','set cmdtiming real','set limitsprites true','set disablesprites false','set vsync off',
        'set pause_on_lost_focus false','set minframeskip 0','set maxframeskip 0',
        'set gamma 1','set brightness 0','set contrast 0','set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        'set blur 0','set noise 0','set scanline 0','activate_input_layer -blocking player_verify',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(output)}',
        'set step -1; set lastshot -1; set frames 1600',
        'set motion [open [file join $out motion.bin] wb]; set cache [open [file join $out cache.bin] wb]',
        'set times [open [file join $out times.tsv] w]',
        'set slots [open [file join $out slots.tsv] w]',
        'set gpu [open [file join $out gpu.tsv] w]; set gpu_count 0',
        'debug probe set_bp VDP.commandExecuting {[info exists ::begin] && [debug probe read VDP.commandExecuting]} {incr ::gpu_count}',
        'proc snapshot {file} {puts -nonewline $file [debug read_block memory 0xe000 4096]; puts -nonewline $file [debug read_block memory 0xc400 96]; puts -nonewline $file [debug read_block memory 0xc0b0 4]}',
        'proc input {n} {keymatrixup 8 255; if {$n==160 || $n==200} {keymatrixdown 8 1; return}; if {$n==1000} {keymatrixdown 8 2; return}; if {$n<80 || $n>=1400} {return}; set m [lindex {128 32 16 64} [expr {int(($n-80)/220)%4}]]; keymatrixdown 8 $m}',
        'proc mark {} {',
        ' if {[info exists ::done]} {return}',
        ' if {$::wp_last_value==1} {set ::begin [machine_info time]; set ::gpu_count 0; return}',
        ' if {$::wp_last_value!=2} {return}',
        ' if {![debug read memory 0xc400]} {puts stderr "Default ROM did not start in driving mode"; exit 2}',
        ' incr ::step',
        f' if {{[debug read {{VDP regs}} 18]!={HORIZONTAL_ADJUST}}} {{puts stderr "Display adjustment changed";exit 2}}',
        ' set stop 32; for {set i 0} {$i<32} {incr i} {if {[debug read VRAM [expr {128512+$i*4}]]==216} {set stop $i;break}}',
        f' if {{$stop!={slots}' + ('' if info.get('player_blitter') else f' || [debug read VRAM {128512+info["sprites"]["player_first_slot"]*4+1}]!={PLAYER_X} || [debug read VRAM {128512+(info["sprites"]["player_first_slot"]+1)*4+1}]!={PLAYER_X}') + '} {puts stderr "Invalid compact SAT allocation";exit 2}',
        ' puts $::slots "$::step $stop"',
        ' puts $::gpu "$::step $::gpu_count"',
        ' snapshot $::motion; puts -nonewline $::cache [debug read_block VRAM 0 65536]',
        ' puts $::times "main $::step [machine_info time] [expr {[machine_info time]-$::begin}]"',
        ' input [expr {$::step+1}]',
        ' if {$::step==$::frames-1} {set ::done 1}',
        '}',
        'proc capture {n} {screenshot -raw -size auto [file join $::out "$n.png"]; set f [open [file join $::out "$n.state"] wb]; puts -nonewline $f $::shot($n); close $f; unset ::shot($n)}',
        'proc raster {} {',
        ' set v $::wp_last_value',
        ' if {$v!=2 && $v!=4 && $v!=6} {return}',
        ' if {$::step>=0} {puts $::times "$v $::step [machine_info time]"}',
        ' if {$v!=6 || $::step<0 || $::lastshot==$::step} {return}',
        ' set flag [debug read memory 0xe077]',
        # Freeze presentation state at the footer; capture only once the renderer
        # finishes that frame. VBlank precedes the renderer's frame-end event.
        ' if {$::step%60==0 || ![info exists ::seen($flag)] || ([debug read memory 0xc418] && ![info exists ::patchseen])} {set ::seen($flag) 1; if {[debug read memory 0xc418]} {set ::patchseen 1}; set ::lastshot $::step; set ::shot($::step) [debug read_block memory 0xc000 12288]; after frame [list after time 0.001 [list capture $::step]]}',
        ' if {[info exists ::done]} {after time 0.004 {close $::motion;close $::cache;close $::times;close $::slots;close $::gpu;exit}}',
        '}',
        'debug set_watchpoint write_mem 0xc000 {$wp_last_value==1 || $wp_last_value==2} mark',
        'debug set_watchpoint write_mem 0xc03c {$wp_last_value==2 || $wp_last_value==4 || $wp_last_value==6} raster',
        'set VDP.too_fast_vram_access_callback {puts stderr "VRAM timing violation"; exit 2}',
        'after time 75 {puts stderr "Player verification timeout";exit 2}']
    if collections:
        from .hud_verify import symbols
        syms=symbols(args.rom.parent/'raster-scroll.sym')
        lines.insert(0,'set hudflags [binary format c* {0 1 1 1 1 1 1 1 1 1 1}]')
        lines.extend([
            f'debug set_bp {syms["Player_Radar"]} {{[reg IM]==2}} {{set ::hudflags [debug read_block memory 0xc500 11]}}',
            f'debug set_bp {syms["Flag_Update"]} {{[reg IM]==2}} {{set ::flag_begin [machine_info time]}}',
            f'debug set_bp {syms["Player_AfterFlag"]} {{[reg IM]==2}} {{puts $::components "update $::step [expr {{round(([machine_info time]-$::flag_begin)*3579545)}}]"}}',
            f'debug set_bp {syms["HUD_DrawContent"]} {{[reg IM]==2}} {{set ::hud_begin [machine_info time]}}',
            f'debug set_bp {syms["Player_Advance"]} {{[reg IM]==2}} {{if {{[info exists ::hud_begin]}} {{puts $::components "hud $::step [expr {{round(([machine_info time]-$::hud_begin)*3579545)}}]";unset ::hud_begin}}}}',
            f'debug set_bp {syms["Flag_Stream"]} {{[reg IM]==2}} {{set ::stream_begin [machine_info time]}}',
            f'debug set_bp {syms.get("stage_stream_driving.after_flags",syms["stage_stream_driving.next"])} {{[reg IM]==2}} {{if {{[info exists ::stream_begin]}} {{puts $::components "dirty $::step [expr {{round(([machine_info time]-$::stream_begin)*3579545)}}]";unset ::stream_begin}}}}'])
        if info.get('incremental_stage',0)>=5:
            lines.extend([
                f'debug set_bp {syms["Score_Update"]} {{[reg IM]==2}} {{set ::score_begin [machine_info time]}}',
                f'debug set_bp {syms.get("Score_AfterUpdate",syms.get("Player_AfterScore"))} {{[reg IM]==2}} {{puts $::components "score $::step [expr {{round(([machine_info time]-$::score_begin)*3579545)}}]"}}'])
        if info.get('incremental_stage',0)>=6:
            for name,begin,end in (('fuel','Fuel_Tick','Player_AfterFuel'),('fuel_hud','update_fuel','update_fuel_sat')):
                lines.extend([
                    f'debug set_bp {syms[begin]} {{[reg IM]==2}} {{set ::{name}_begin [machine_info time]}}',
                    f'debug set_bp {syms[end]} {{[reg IM]==2 && [info exists ::{name}_begin]}} {{puts $::components "{name} $::step [expr {{round(([machine_info time]-$::{name}_begin)*3579545)}}]";unset ::{name}_begin}}'])
        if info.get('enemy_count',0):
            for name,begin,end in (('enemy_cleanup','Enemy_PreMove','Player_AfterEnemyCleanup'),('enemy_ai','Enemy_AfterMove','Enemy_AfterMoveDone'),('tile','stage_copy_tile','stage_copy_done')):
                lines.extend([
                    f'debug set_bp {syms[begin]} {{[reg IM]==2}} {{set ::{name}_begin [machine_info time]}}',
                    f'debug set_bp {syms[end]} {{[reg IM]==2}} {{puts $::components "{name} $::step [expr {{round(([machine_info time]-$::{name}_begin)*3579545)}}]"}}'])
            for name,begin,ends in (('wall',0x94e0,(0x9506,0x950b)),('ai_logic',0x8cd6,(0x8e47,)),('visibility',0x95bd,(0x95c1,0x9619))):
                lines.append(f'debug set_bp {begin} {{[reg IM]==2}} {{set ::{name}_begin [machine_info time]}}')
                for end in ends:
                    gate=' && ([reg AF]&64)!=0' if name=='visibility' and end==0x95c1 else ''
                    lines.append(f'debug set_bp {end} {{[reg IM]==2 && [info exists ::{name}_begin]{gate}}} {{puts $::components "{name} $::step [expr {{round(([machine_info time]-$::{name}_begin)*3579545)}}]";unset ::{name}_begin}}')
            lines.extend([
                'set gpu_duration [open [file join $out gpu-duration.tsv] w]',
                'debug probe set_bp VDP.commandExecuting {[info exists ::begin] && [debug probe read VDP.commandExecuting]} {set ::gpu_begin [machine_info time];set ::gpu_step $::step}',
                'debug probe set_bp VDP.commandExecuting {![debug probe read VDP.commandExecuting] && [info exists ::gpu_begin]} {puts $::gpu_duration "$::gpu_step [expr {round(([machine_info time]-$::gpu_begin)*3579545)}]";unset ::gpu_begin}'])
        if info.get('enemy_rendered'):
            for name,begin,end in (('enemy_prepare','Enemy_Prepare','Enemy_AfterPrepare'),('enemy_draw','Enemy_Draw','Enemy_DrawDone'),('enemy_radar','update_radar','update_radar.player')):
                lines.extend([
                    f'debug set_bp {syms[begin]} {{[reg IM]==2}} {{set ::{name}_begin [machine_info time]}}',
                    f'debug set_bp {syms[end]} {{[reg IM]==2 && [info exists ::{name}_begin]}} {{puts $::components "{name} $::step [expr {{round(([machine_info time]-$::{name}_begin)*3579545)}}]";unset ::{name}_begin}}'])
        script='\n'.join(lines)+'\n'
        script=script.replace('set gpu [open', 'set components [open [file join $out components.tsv] w];set flags [open [file join $out flags.bin] wb]\nset gpu [open')
        flag_address=info.get('flag_display_state_address') or 0xc500
        script=script.replace('snapshot $::motion;', f'puts -nonewline $::flags [debug read_block memory {flag_address} 11];snapshot $::motion;')
        script=script.replace('set ::shot($::step) [debug read_block memory 0xc000 12288];',
            'set ::shot($::step) [debug read_block memory 0xc000 12288];set ::shotflags($::step) $::hudflags;')
        script=script.replace('unset ::shot($n)',
            'unset ::shot($n);set f [open [file join $::out "$n.hudflags"] wb];puts -nonewline $f $::shotflags($n);close $f;unset ::shotflags($n)')
        script=script.replace('close $::gpu;exit','close $::gpu;close $::flags;close $::components;exit')
    else:script='\n'.join(lines)+'\n'
    if info.get('player_blitter'):
        from .hud_verify import symbols
        syms=symbols(args.rom.parent/'raster-scroll.sym')
        script='set blitcost [open '+tcl(output/'blitter.tsv')+' w]\n'+script
        split=next(name for name in syms if name.endswith('.split_wait'))
        for name,begin,end in (('restore','Bitmap_Restore','Bitmap_Draw'),('draw','Bitmap_Draw',split),('native','Player_Advance','stage_stream'),('guard','stage_stream','stage_wait_command')):
            script+=f'\ndebug set_bp {syms[begin]} {{[info exists ::begin]}} {{set ::blit_{name} [machine_info time]}}\n'
            script+=f'debug set_bp {syms[end]} {{[info exists ::blit_{name}]}} {{puts $::blitcost "{name} $::step [expr {{1000*([machine_info time]-$::blit_{name})}}]";unset ::blit_{name}}}\n'
        script+=f'debug set_bp {syms["stage_stream"]} {{[info exists ::begin]}} {{set ::blit_stream [machine_info time]}}\n'
        script+='debug set_watchpoint write_mem 0xc000 {$wp_last_value==2 && [info exists ::blit_stream]} {puts $::blitcost "stream $::step [expr {1000*([machine_info time]-$::blit_stream)}]";unset ::blit_stream}\n'
        if 'guard_interrupt' in syms:
            script+=f'debug set_bp {syms["guard_interrupt"]} {{[info exists ::begin]}} {{puts $::blitcost "deadline $::step [expr {{1000*([machine_info time]-$::begin)}}]"}}\n'
    if info.get('enemy_rendered'):
        script=script.replace('if {$::step%60==0 ||',
            'if {([debug read memory 0xc5df] && [debug read memory 0xc5dc]) || $::step%60==0 ||')
    if info.get('hud_style',{}).get('radar_dirty_state_address'):
        from .hud_verify import symbols
        syms=symbols(args.rom.parent/'raster-scroll.sym')
        script+='\nset radar_queue [open [file join $out radar_queue.bin] wb]\n'
        script+=f'debug set_watchpoint write_mem 0xc000 {{$wp_last_value==2 && $::step>=0 && ![info exists ::radar_closed]}} {{puts -nonewline $::radar_queue [debug read_block memory {info["hud_style"]["radar_dirty_state_address"]} 2];puts -nonewline $::radar_queue [debug read_block memory {syms["hud_flags_dirty"]} 2];if {{$::step==$::frames-1}} {{close $::radar_queue;set ::radar_closed 1}}}}\n'
        if info['hud_style'].get('radar_ready_state_address'):
            script=script.replace(';if {$::step==$::frames-1} {close $::radar_queue;',f';puts -nonewline $::radar_queue [debug read_block memory {info["hud_style"]["radar_ready_state_address"]} 2];if {{$::step==$::frames-1}} {{close $::radar_queue;')
    if not headless:
        from .hud_verify import symbols
        capture_syms=symbols(args.rom.parent/'raster-scroll.sym')
        script+='\n'+scanout_recording_tcl(output,capture_syms['startup_mode'])+'\n'
        script=script.replace(';exit}', ';record stop;exit}')
    (output/'session.tcl').write_text(script)
    if headless:
        script=(output/'session.tcl').read_text()
        script=script.replace('screenshot -raw -size auto [file join $::out "$n.png"]; ','')
        (output/'session.tcl').write_text('set renderer none\n'+script)
    env=dict(os.environ,OPENMSX_HOME=str(output/'home'),OPENMSX_USER_DATA=str(output/'userdata'))
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (output/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(output/'session.tcl')],env=env,
                       stdout=log,stderr=subprocess.STDOUT,timeout=100,check=True)
    assert bios=={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    if not headless and not (output/'scanout.avi').is_file():raise ValueError('Complete-frame video recording missing')
    raw=(output/'motion.bin').read_bytes()
    records=[raw[i:i+FRAME_BYTES] for i in range(0,len(raw),FRAME_BYTES)]
    if len(records)!=1600 or any(len(r)!=FRAME_BYTES for r in records):raise ValueError('Incomplete MSX movement trace')
    commands=bytearray();previous=0;phase=0
    build_info=read_json(args.rom.parent/'build.json')
    rate=(build_info.get('native_clock') or {}).get('rate',round((build_info['timing']['frame_seconds']/.0165-1)*65536))
    for i,r in enumerate(records):
        ticks=int.from_bytes(r[4096+64:4096+66],'little')
        reset=i==0 or ticks<previous
        if reset!=(i in (0,1000)):raise ValueError('Player restart input was not applied exactly once')
        count=ticks if reset else ticks-previous
        if count not in (0,1,2):raise ValueError(f'Unexpected native tick delta: {i}, {count}')
        if (count==0)!=(160<=i<200):raise ValueError('Pause did not freeze/resume the native clock')
        if reset:phase=0
        if count:
            phase+=rate;expected=1+(phase>>16);phase&=65535
            if count!=expected:raise ValueError('Native/display clock resampling mismatch')
            mask=255 if i<80 or i>=1400 or i in (160,200,1000) else (247,223,251,239)[((i-80)//220)%4]
            if r[0x3f0]!=mask:raise ValueError(f'Keyboard direction mapping mismatch at {i}')
        commands.extend((count,r[0x3f0],reset));previous=ticks
    (output/'commands.bin').write_bytes(commands)
    env=dict(os.environ,PLAYER_VERIFY_OUTPUT=str(output.resolve()),PLAYER_CAMERA=str(int(bool(info.get('enemy_count',0)))))
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Player oracle requires MAME 0.289')
    json_write(output/'native-runtime.json',dict(version=version,script_sha256=digest(root/'src/toolchain/msx/player_native.lua')))
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/msx/player_native.lua'),
        '-cfg_directory',str(output/'mame-cfg'),'-nvram_directory',str(output/'mame-nvram'),'-seconds_to_run','40']
    with (output/'mame.log').open('w') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60,check=True)
    analyze(args,output,records,images_required=not headless)


def analyze(args,output,records,*,images_required=True):
    info=read_json(args.rom.parent/'build.json')
    occupied=info['sprites']['total_slots']
    slots=[list(map(int,row.split())) for row in (output/'slots.tsv').read_text().splitlines()]
    if slots != [[n,occupied] for n in range(len(records))]:
        raise ValueError('Missing or invalid compact SAT allocation evidence')
    native=(output/'native.bin').read_bytes()
    if len(native)!=4096*len(records):raise ValueError('Incomplete original Z80 trace')
    for i,r in enumerate(records):
        ref=native[i*4096:(i+1)*4096]
        for start,end in ((0x2d,0x2f),(0x48,0x5c),(0x68,0x7e)):
            if r[start:end]!=ref[start:end]:
                raise ValueError(f'Original movement mismatch: frame {i}, native ${start+0x8000:04x}: MSX {r[start:end].hex()}, arcade {ref[start:end].hex()}')
        x,y=coordinates(r)
        if (x,y)!=(int.from_bytes(r[4176:4178],'little'),int.from_bytes(r[4178:4180],'little')):
            raise ValueError('Native/world coordinate adapter mismatch')
    bundle=args.rom.parent
    world=(bundle/'stage-world.bin').read_bytes();palette=(bundle/'palette.bin').read_bytes()
    info=read_json(bundle/'build.json')
    if info.get('incremental_stage',0) in (6,7):
        # This common route has no lucky conversion or empty-fuel movement
        # divergence. The separate original oracle establishes this boundary.
        # Home starts a fresh counter; Space contributes zero logical ticks.
        for i,r in enumerate(records):
            ticks=int.from_bytes(r[4160:4162],'little')
            expected=600-max((ticks-1)//9,0)
            clock=1+(ticks-1)%9 if ticks else 0
            if (r[0x26a]+10*r[0x26b],r[0x269])!=(expected,clock):
                raise ValueError(f'Fuel logical clock/pause/Home mismatch at {i}')
    black=info['sprites']['black']
    hud_enabled=info.get('hud_enabled',True)
    collection=info.get('incremental_stage',0)>=4
    flag_records=read_json(bundle/'flags.json')['records'] if collection else []
    flag_states=(output/'flags.bin').read_bytes() if collection else b''
    if collection and len(flag_states)!=len(records)*11:raise ValueError('Incomplete collection state trace')
    if collection:
        # The original untouched board's empty-cell tile supplies the independent
        # terrain oracle. No atlas encoding/owner bits are used to derive it.
        from .stage_one import acquire,reconstruct
        root=__import__('pathlib').Path(__file__).resolve().parents[3]
        program,reference=acquire(root);cells,_,_=reconstruct(program,reference)
        cell=cells.index(0);tx=3+(cell%32)*3;ty=3+(cell//32)*3
        empty=bytes(world[(ty*8+y)*816+tx*8+x] for y in range(8) for x in range(8))
    # Pad the independent world oracle with the original 24-pixel flower period.
    width,height=1328,1904
    padded=bytearray(width*height)
    for y in range(height):
        sy=y-256
        for x in range(width):
            sx=x-256
            padded[y*width+x]=world[sy*816+sx] if 0<=sx<816 and 0<=sy<1392 else world[(sy%24)*816+sx%24]
    packed_map=packed(padded)
    def collected_pixels(data,states,stride,offset):
        data=bytearray(data)
        for n,f in enumerate(flag_records,1):
            if states[n]:continue
            for y in range(24):
                at=(f['tile_y']*8+y+offset)*stride+f['tile_x']*8+offset
                data[at:at+24]=(empty[y%8*8:y%8*8+8])*3
        return data
    flags=read_json(bundle/'player.json')['flags'];sprites=(bundle/'player-pixels.bin').read_bytes()
    collection_maps={}
    tile_decoder=None
    if info.get('tile_mode'):
        from .tilemap import CacheDecoder
        tile_decoder=CacheDecoder((bundle/'tile-patterns.bin').read_bytes(),(bundle/'tile-colors.bin').read_bytes())
    with (output/'cache.bin').open('rb') as cache:
        for i,r in enumerate(records):
            vram=cache.read(65536)
            if tile_decoder is not None:vram=tile_decoder.decode(vram)
            wx=int.from_bytes(r[-4:-2],'little',signed=True);wy=int.from_bytes(r[-2:],'little',signed=True)
            if collection:
                state=flag_states[i*11:i*11+11]
                if state not in collection_maps:collection_maps[state]=packed(collected_pixels(padded,state,width,256))
                bitmap=collection_maps[state]
            else:bitmap=packed_map
            bitmap=bytearray(bitmap)
            if info.get('player_blitter'):
                car=sprites[flags.index(r[4105])*256:][:256]
                for y in range(16):
                    for x,color in enumerate(car[y*16:y*16+16]):
                        if not color:continue
                        px,py=wx+PLAYER_X-8+x,wy+97+y
                        p=(py+256)*(width//2)+(px+256)//2
                        bitmap[p]=(bitmap[p]&15)|(color<<4) if px%2==0 else (bitmap[p]&240)|color
            elif r[4096+24]:
                px=int.from_bytes(r[4101:4103],'little');py=int.from_bytes(r[4103:4105],'little')
                car=sprites[flags.index(r[4105])*256:][:256]
                for x,color in enumerate(car[240:]):
                    if not color:continue
                    p=(py+7+256)*(width//2)+(px-8+x+256)//2
                    bitmap[p]=(bitmap[p]&15)|(color<<4) if (px-8+x)%2==0 else (bitmap[p]&240)|color
            check_cache(vram,bitmap,width,wx,wy,i)
    images=0;assets=load_assets(args.assets)
    for path in output.glob('*.state'):
        if not path.with_suffix('.png').is_file() and not images_required:continue
        ram=path.read_bytes();wx=int.from_bytes(ram[0xb0:0xb2],'little',signed=True);wy=int.from_bytes(ram[0xb2:0xb4],'little',signed=True)
        points=dict(read_json(bundle/'radar.json')['scenes'][0],player=[ram[0x93],ram[0x94]])
        style=info.get('hud_style',{})
        points['border']=style.get('radar_border',True)
        points['square']=style.get('radar_square',False)
        points['cells_only']=style.get('radar_cells_only',False)
        actors=[];merged=bool((info.get('enemy_logic') or {}).get('paired_radar') and ram[0x660])
        if info.get('enemy_rendered'):
            points['enemy']=[ram[0x95],ram[0x96]]
            if info.get('enemy_logic',{}).get('paired_radar'):
                points['enemy']=list(ram[0x666:0x668])
                if merged:points['extra_enemies']=[ram[0x638:0x63a]]
            from .enemy_population import actor_images
            actors=actor_images(ram,sprites,flags,info['enemy_count'],info.get('enemy_logic',{}).get('sprite_planes',2))
        if points['cells_only']:
            from .radar_cells import published_cells
            points['published_cells']=published_cells(ram,read_json(bundle/'radar.json')['scenes'][0]['flags'],style)
            points['player']=list(ram[0xf00:0xf02]);points['enemy']=list(ram[0xf02:0xf04])
            points['extra_enemies']=[ram[0xf04:0xf06]] if info.get('enemy_count',0)>1 else []
            if style.get('radar_player_sprite'):
                points['separate_player']=list(ram[0xf38:0xf3a])
                points['separate_player_visible']=bool(ram[0xf3a])
                points['separate_player_color']=ram[0xf3b]
        if info.get('player_blitter'):
            car=sprites[flags.index(ram[0x409])*256:][:256]
            actors.insert(0,(car,PLAYER_X,108))
        image_world=padded
        if collection:
            flag_at=(info.get('flag_display_state_address') or 0xc500)-0xc000
            image_world=collected_pixels(padded,ram[flag_at:flag_at+11],width,256)
            shown=path.with_suffix('.hudflags').read_bytes()
            hidden={f['hud_slot'] for n,f in enumerate(flag_records,1) if not shown[n]}
            points['flags']=[p for n,p in enumerate(points['flags']) if n not in hidden]
        displayed_score=displayed_high=0
        if info.get('incremental_stage',0)>=5:
            displayed_score=int(''.join(map(str,ram[0x30c:0x312])))
            displayed_high=int(''.join(map(str,ram[0x312:0x318])))
        expected=compose(image_world,header(assets,palette,displayed_score,displayed_high,background=style.get('header_background')) if hud_enabled and info.get('incremental_stage',0)>=5
                         else header(assets,palette) if hud_enabled else bytes([black])*(256*8),
            (bundle/'life.bin').read_bytes(),palette,wx+256,wy+256,2,
            points if hud_enabled else None,ram[0x97],
            life_digits=(bundle/'life-digits.bin').read_bytes() if hud_enabled else None,
            width=width,fuel_pixels=(ram[0x325] if info.get('incremental_stage',0)>=6 else 30) if hud_enabled else None,actors=actors,
            actor_top=info.get('enemy_logic',{}).get('sprite_body_top',11) if info.get('enemy_rendered') else 11,
            radar_back_points=([ram[0x690:0x692]] if info.get('enemy_count',0)==3 and hud_enabled else
                [ram[0x638:0x63a]] if info.get('enemy_count',0)>1 and hud_enabled and not merged and not points['cells_only'] else ()),
            life_outline=style.get('life_outline',True))
        colors=__import__('src.toolchain.msx.raster_scroll',fromlist=['palette_rgb']).palette_rgb(palette)
        car=sprites[flags.index(ram[0x409])*256:][:256]
        car_bias=info['sprites'].get('player_forbidden_y_bias',0) if (ram[0x1c]+107)&255==216 else 0
        for y in range(16):
            for x in range(16):
                if car[y*16+x] and not info.get('player_blitter'):expected.putpixel((PLAYER_X+DISPLAY_SHIFT+x,108+y+car_bias),colors[car[y*16+x]])
        expected=bordered(expected,palette)
        with Image.open(path.with_suffix('.png')) as image:actual=image.convert('RGB')
        diff=ImageChops.difference(actual,expected)
        if diff.getbbox():
            expected.save(path.with_name(path.stem+'-expected.png'));diff.save(path.with_name(path.stem+'-diff.png'))
            raise ValueError(f'Player RGB mismatch at frame {path.stem}: {diff.getbbox()}')
        images+=1
    if images_required and not images:raise ValueError('No rendered player frames were captured')
    stamps=[row.split() for row in (output/'times.tsv').read_text().splitlines()]
    target=read_json(bundle/'build.json')['timing']['frame_seconds']*1000
    periods={}
    for kind in ('main','2','4','6'):
        values=[(float(row[2])-(float(row[3]) if kind=='main' else 0))*1000 for row in stamps if row[0]==kind]
        indices=[int(row[1]) for row in stamps if row[0]==kind]
        deltas=[b-a for j,(a,b) in enumerate(zip(values,values[1:]))
                if b-a<100 and not any(n<=2 or 998<=n<=1002 for n in indices[j:j+2])]
        if any(abs(d-target)>.6 for d in deltas):raise ValueError(f'Player refresh deadline missed: {kind}, {max(deltas):.3f} ms')
        ordered=sorted(deltas)
        periods[kind]=dict(samples=len(deltas),min_ms=min(deltas),max_ms=max(deltas),
                          median_ms=statistics.median(deltas),p95_ms=ordered[(len(ordered)-1)*95//100])
    frame_work=[float(row[3])*1000 for row in stamps if row[0]=='main']
    ordered_work=sorted(frame_work)
    gpu_rows=[list(map(int,line.split())) for line in (output/'gpu.tsv').read_text().splitlines()]
    if len(gpu_rows)!=len(records) or any(n!=i or count<0 for i,(n,count) in enumerate(gpu_rows)):
        raise ValueError('Incomplete GPU command-count evidence')
    gpu_counts=[count for i,count in gpu_rows if i>2 and not 998<=i<=1002]
    report=dict(rom_sha256=digest(args.rom),native_frames=len(records),rgb_images=images,
        complete_frame_recording=(output/'scanout.avi').is_file(),
        incremental_stage=info.get('incremental_stage'),hud_enabled=hud_enabled,
        fuel_clock_pause_home_verified=info.get('incremental_stage',0) in (6,7),
        full_arcade_loop=info.get('full_arcade_loop'),
        frame_work_elapsed_ms=dict(median=statistics.median(frame_work),
            p95=ordered_work[(len(ordered_work)-1)*95//100],maximum=max(frame_work)),
        gpu_commands_per_steady_frame=dict(median=statistics.median(gpu_counts),maximum=max(gpu_counts),samples=len(gpu_counts)),
        measured_cost_scope='Main work elapsed time includes raster waits/interrupts; GPU command starts counted; per-subsystem CPU and GPU durations unmeasured',
        occupied_sprite_slots=occupied,free_sprite_slots=32-occupied,
        borders_verified=images_required,
        visible_cache_frames=len(records),strict_vram_timing=True,periods=periods,
        rendered_images_required=images_required,
        native_runtime=read_json(output/'native-runtime.json') if (output/'native-runtime.json').exists() else None,
        scope='Original movement/steering/wall probes/animation in MAME; real MSX keyboard, VRAM and timing'+('; complete rendered images' if images_required else '; display disabled, no RGB validation'))
    if collection:
        rows=[line.split() for line in (output/'components.tsv').read_text().splitlines()]
        costs={}
        for name in ('update','hud','dirty','score','fuel','fuel_hud','enemy_cleanup','enemy_ai','enemy_prepare','enemy_draw','enemy_radar','tile','wall','ai_logic','visibility'):
            values=sorted(int(row[2]) for row in rows if row[0]==name)
            if values:costs[name]=dict(samples=len(values),median_cycles=statistics.median(values),
                p95_cycles=values[(len(values)-1)*95//100],maximum_cycles=max(values))
        report['component_elapsed_cycles']=costs
        report['component_cost_scope']='Read-only live breakpoints; elapsed cycles include interrupts and VDP waits, not isolated CPU cost'
    if (output/'gpu-duration.tsv').is_file():
        values=sorted(int(row.split()[1]) for row in (output/'gpu-duration.tsv').read_text().splitlines())
        report['gpu_execution_cycles']=dict(samples=len(values),median=statistics.median(values),p95=values[(len(values)-1)*95//100],maximum=max(values))
        report['measured_cost_scope']='Main/component elapsed time includes raster waits/interrupts; GPU command starts and actual VDP command execution duration measured separately'
    if info.get('hud_style',{}).get('radar_dirty_state_address'):
        from .radar_cells import queue_metrics
        report['radar_queue']=queue_metrics(output/'radar_queue.bin',len(records),info['hud_style']['radar_pending_refresh_limit'],3 if info['hud_style'].get('radar_ready_state_address') else 2)
    json_write(output/'report.json',report)
    print(f'{len(records)} native movement/cache frames and {images} exact player images: {output}/report.json')


def check_cache(vram,data,width,wx,wy,frame):
    odd=wx&1;size=VIEWPORT_WIDTH//2+odd;bx=(wx&511)//2
    for y in range(201):
        row=((wy+y)&255)*128;remaining=size;pos=bx;actual=bytearray()
        while remaining:
            n=min(remaining,128-pos%128);address=(pos//128)*32768+row+pos%128
            actual.extend(vram[address:address+n]);pos=(pos+n)%256;remaining-=n
        start=(wy+y+256)*(width//2)+(wx+256)//2
        expected=bytearray(data[start:start+size])
        if odd:
            actual[0]&=15;expected[0]&=15;actual[-1]&=240;expected[-1]&=240
        if actual!=expected:
            differences=[(n,a,b) for n,(a,b) in enumerate(zip(actual,expected)) if a!=b]
            raise ValueError(f'Player cache mismatch: frame {frame}, camera {wx},{wy}, local row {y}, first bytes {differences[:8]}')
