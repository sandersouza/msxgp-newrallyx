"""Compare keyboard-controlled MSX movement with the original Z80 in MAME."""
import os
from pathlib import Path
import subprocess
from PIL import Image,ImageChops
from .build import destination
from .emulator import tcl, reference_machine
from .player import coordinates
from .raster_scroll import compose,header
from .screen5 import packed
from scripts.scenes.bundle import digest,read_json,verify_manifest,load_assets
from scripts.scenes.storage import json_write,require_ignored

FRAME_BYTES=4096+96+4


def verify(root,args):
    headless=getattr(args,'headless',False)
    output=destination(root,args.output);verify_manifest(args.rom.parent)
    require_ignored(root,[output/'commands.bin',output/'native.bin'])
    output.mkdir(parents=True)
    lines=['set save_settings_on_exit false',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set speed 100',f'set throttle {"off" if headless else "on"}',
        'set z80_freq 3579545','set cmdtiming real','set limitsprites true','set disablesprites false',
        'set pause_on_lost_focus false','set minframeskip 0','set maxframeskip 0',
        'set gamma 1','set brightness 0','set contrast 0','set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        'set blur 0','set noise 0','set scanline 0','activate_input_layer -blocking player_verify',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(output)}',
        'set step -1; set lastshot -1; set frames 1600',
        'set motion [open [file join $out motion.bin] wb]; set cache [open [file join $out cache.bin] wb]',
        'set times [open [file join $out times.tsv] w]',
        'proc snapshot {file} {puts -nonewline $file [debug read_block memory 0xe000 4096]; puts -nonewline $file [debug read_block memory 0xc400 96]; puts -nonewline $file [debug read_block memory 0xc0b0 4]}',
        'proc input {n} {keymatrixup 8 255; if {$n==160 || $n==200} {keymatrixdown 8 1; return}; if {$n==1000} {keymatrixdown 8 2; return}; if {$n<80 || $n>=1400} {return}; set m [lindex {128 32 16 64} [expr {int(($n-80)/220)%4}]]; keymatrixdown 8 $m}',
        'proc mark {} {',
        ' if {[info exists ::done]} {return}',
        ' if {$::wp_last_value==1} {set ::begin [machine_info time]; return}',
        ' if {$::wp_last_value!=2} {return}',
        ' if {![debug read memory 0xc400]} {puts stderr "Default ROM did not start in driving mode"; exit 2}',
        ' incr ::step',
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
        ' if {$::step%60==0 || ![info exists ::seen($flag)] || ([debug read memory 0xc418] && ![info exists ::patchseen])} {set ::seen($flag) 1; if {[debug read memory 0xc418]} {set ::patchseen 1}; set ::lastshot $::step; set ::shot($::step) [debug read_block memory 0xc000 12288]; after frame [list capture $::step]}',
        ' if {[info exists ::done]} {after time 0.004 {close $::motion;close $::cache;close $::times;exit}}',
        '}',
        'debug set_watchpoint write_mem 0xc000 {$wp_last_value==1 || $wp_last_value==2} mark',
        'debug set_watchpoint write_mem 0xc03c {$wp_last_value==2 || $wp_last_value==4 || $wp_last_value==6} raster',
        'set VDP.too_fast_vram_access_callback {puts stderr "VRAM timing violation"; exit 2}',
        'after time 75 {puts stderr "Player verification timeout";exit 2}']
    (output/'session.tcl').write_text('\n'.join(lines)+'\n')
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
    raw=(output/'motion.bin').read_bytes()
    records=[raw[i:i+FRAME_BYTES] for i in range(0,len(raw),FRAME_BYTES)]
    if len(records)!=1600 or any(len(r)!=FRAME_BYTES for r in records):raise ValueError('Incomplete MSX movement trace')
    commands=bytearray();previous=0;phase=0
    rate=round((read_json(args.rom.parent/'build.json')['timing']['frame_seconds']/.0165-1)*65536)
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
    env=dict(os.environ,PLAYER_VERIFY_OUTPUT=str(output.resolve()))
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Player oracle requires MAME 0.289')
    json_write(output/'native-runtime.json',dict(version=version,script_sha256=digest(root/'scripts/msx/player_native.lua')))
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/msx/player_native.lua'),
        '-cfg_directory',str(output/'mame-cfg'),'-nvram_directory',str(output/'mame-nvram'),'-seconds_to_run','40']
    with (output/'mame.log').open('w') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60,check=True)
    analyze(args,output,records,images_required=not headless)


def analyze(args,output,records,*,images_required=True):
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
    black=read_json(bundle/'build.json')['sprites']['black']
    # Pad the independent world oracle with the original 24-pixel flower period.
    width,height=1328,1904
    padded=bytearray(width*height)
    for y in range(height):
        sy=y-256
        for x in range(width):
            sx=x-256
            padded[y*width+x]=world[sy*816+sx] if 0<=sx<816 and 0<=sy<1392 else world[(sy%24)*816+sx%24]
    packed_map=packed(padded)
    flags=read_json(bundle/'player.json')['flags'];sprites=(bundle/'player-pixels.bin').read_bytes()
    with (output/'cache.bin').open('rb') as cache:
        for i,r in enumerate(records):
            vram=cache.read(65536)
            wx=int.from_bytes(r[-4:-2],'little',signed=True);wy=int.from_bytes(r[-2:],'little',signed=True)
            bitmap=bytearray(packed_map)
            if r[4096+24]:
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
        expected=compose(padded,header(assets,palette), (bundle/'life.bin').read_bytes(),palette,wx+256,wy+256,2,
            points,ram[0x97],life_digits=(bundle/'life-digits.bin').read_bytes(),width=width,fuel_pixels=30)
        colors=__import__('scripts.msx.raster_scroll',fromlist=['palette_rgb']).palette_rgb(palette)
        car=sprites[flags.index(ram[0x409])*256:][:256]
        for y in range(16):
            for x in range(16):
                if car[y*16+x]:expected.putpixel((120+x,108+y),colors[car[y*16+x]])
        with Image.open(path.with_suffix('.png')) as image:actual=image.convert('RGB').crop((32,14,288,226))
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
        periods[kind]=dict(samples=len(deltas),min_ms=min(deltas),max_ms=max(deltas))
    report=dict(rom_sha256=digest(args.rom),native_frames=len(records),rgb_images=images,
        visible_cache_frames=len(records),strict_vram_timing=True,periods=periods,
        rendered_images_required=images_required,
        native_runtime=read_json(output/'native-runtime.json') if (output/'native-runtime.json').exists() else None,
        scope='Original movement/steering/wall probes/animation in MAME; real MSX keyboard, VRAM and timing'+('; complete rendered images' if images_required else '; display disabled, no RGB validation'))
    json_write(output/'report.json',report)
    print(f'{len(records)} native movement/cache frames and {images} exact player images: {output}/report.json')


def check_cache(vram,data,width,wx,wy,frame):
    odd=wx&1;size=120+odd;bx=(wx&511)//2
    for y in range(201):
        row=((wy+y)&255)*128;remaining=size;pos=bx;actual=bytearray()
        while remaining:
            n=min(remaining,128-pos%128);address=(pos//128)*32768+row+pos%128
            actual.extend(vram[address:address+n]);pos=(pos+n)%256;remaining-=n
        start=(wy+y+256)*(width//2)+(wx+256)//2
        expected=bytearray(data[start:start+size])
        if odd:
            actual[0]&=15;expected[0]&=15;actual[-1]&=240;expected[-1]&=240
        if actual!=expected:raise ValueError(f'Player cache mismatch: frame {frame}, camera {wx},{wy}, local row {y}')
