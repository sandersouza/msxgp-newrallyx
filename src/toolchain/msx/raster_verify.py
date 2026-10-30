"""Real keyboard, raster-register, full-image and immutable-world integration checks."""
import os
import subprocess
from PIL import Image, ImageChops

from .build import destination
from .emulator import tcl, reference_machine
from .screen5 import packed
from .raster_scroll import BODY_TOP, compose, bordered
from .display import VIEWPORT_WIDTH, VIEWPORT_HALF, HORIZONTAL_ADJUST
from . import sprite_radar as radar
from . import sprite_fuel as fuel
from . import sprite_lives as life_counter
from src.toolchain.scenes.bundle import digest, read_json, verify_manifest
from src.toolchain.scenes.storage import json_write, require_ignored


def stage_scenarios():
    cases = [dict(name='initial',kind='initial',row=0,mask=0,count=0),
             dict(name='top-left',kind='scene',row=0,mask=4,count=1,scene=1)]
    cases += [dict(name=f'fine-{i}',kind='move',row=8,mask=128,count=1,delta=[1,0])
              for i in range(1,9)]
    cases += [dict(name='ring-page-and-row-crossings',kind='move',row=8,mask=192,
                   count=576,delta=[1,1]),
              dict(name='bottom-right-clamp',kind='move',row=8,mask=192,
                   count=630,delta=[1,1]),
              dict(name='bottom-left-clamp',kind='move',row=8,mask=16,
                   count=590,delta=[-1,0]),
              dict(name='full-height-up',kind='move',row=8,mask=32,
                   count=1200,delta=[0,-1]),
              dict(name='top-left-clamp',kind='move',row=8,mask=48,
                   count=10,delta=[-1,-1]),
              dict(name='reverse-diagonal',kind='move',row=8,mask=192,
                   count=273,delta=[1,1]),
              dict(name='reverse-direction',kind='move',row=8,mask=48,
                   count=265,delta=[-1,-1])]
    for scene in (2,3,4):
        cases.append(dict(name=f'landmark-{scene+1}',kind='scene',row=0,mask=2<<scene,
                          count=1,scene=scene))
    cases += [dict(name='start-landmark',kind='scene',row=0,mask=2,count=1,scene=0),
              dict(name='home',kind='home',row=8,mask=2,count=1)]
    cases += [dict(name=f'lives-{i}',kind='life',row=0,mask=1,count=1) for i in range(10)]
    cases += [dict(name=f'fuel-{i}',kind='fuel',row=3,mask=8,count=1) for i in range(5)]
    cases += [dict(name=f'score-{i}',kind='score',row=1,mask=2,count=1) for i in range(6)]
    for cadence,row,mask in ((3,0,128),(4,1,1),(2,0,64)):
        cases += [dict(name=f'cadence-{cadence}',kind='cadence',row=row,mask=mask,count=1,cadence=cadence),
                  dict(name=f'score-cadence-{cadence}',kind='score',row=1,mask=2,count=1),
                  dict(name=f'fuel-cadence-{cadence}',kind='fuel',row=3,mask=8,count=1)]
    cases += [dict(name='loaded-diagonal',kind='score',row=1,mask=2,count=1,
                   move_mask=192,delta=[1,1],move_count=2,fuel_key=True,life_key=True)]
    return cases


def rock_scenarios(positions):
    """Keyboard-only edge clipping, reversal and cache eviction at each rock."""
    cases=[dict(name='initial',kind='initial',row=0,mask=0,count=0)]
    for i,point in enumerate(positions):
        x,y=point['world_origin']
        wx,wy=x-(VIEWPORT_WIDTH-24),y-80
        if not 4 <= wx <= 568 or not 320 <= wy <= 1191:
            raise ValueError('Rock focus route requires a supported interior original placement')
        cases.append(dict(name=f'rock-{i}-top-left',kind='scene',row=0,mask=4,count=1,scene=1))
        for label,dx,dy,count in [('horizontal',1,0,wx),('right-edge',0,1,wy),
                ('edge-clipped',-1,0,4),('edge-return',1,0,4),
                ('evict-horizontal',-1,0,wx),('reload-horizontal',1,0,wx),
                ('evict-vertical',0,-1,320),('reload-vertical',0,1,320)]:
            cases.append(dict(name=f'rock-{i}-{label}',kind='move',row=8,
                              mask={(1,0):128,(-1,0):16,(0,1):64,(0,-1):32}[(dx,dy)],
                              count=count,delta=[dx,dy]))
    return cases


def verify(root, args):
    output = destination(root, args.output)
    verify_manifest(args.rom.parent)
    info = read_json(args.rom.parent/'build.json')
    if info.get('experiment') != 'full-screen-hardware-raster':
        raise ValueError('Select a sealed raster build bundle with --rom, not the published ROM copy')
    if not args.bios.is_dir():
        raise ValueError('Contributor-supplied BIOS directory missing')
    bios = {p.relative_to(args.bios).as_posix():digest(p) for p in sorted(args.bios.rglob('*')) if p.is_file()}
    require_ignored(root, [output/'session.tcl', output/'report.json'])
    output.mkdir(parents=True)
    rock_fixture=read_json(args.rom.parent/'stage-one.json').get('rock_fixture')
    if getattr(args,'rock_focus',False) and not rock_fixture:
        raise ValueError('Rock focus requires a stage 01 rock fixture')
    cases = rock_scenarios(rock_fixture['positions']) if getattr(args,'rock_focus',False) else stage_scenarios()
    actions = ' '.join('{'+f'{c["kind"]} {c["row"]} {c["mask"]} {c["count"]} {c.get("move_mask",0)} {int(c.get("fuel_key",False))} {int(c.get("life_key",False))}'+'}' for c in cases)
    lines = [
        'set save_settings_on_exit false',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine), 'set firmwareswitch off', 'set speed 100', 'set throttle on',
        'set z80_freq 3579545', 'set z80_freq_locked false', 'set cmdtiming real', 'set vsync off',
        'set disablesprites false', 'set limitsprites true', 'set pause_on_lost_focus false',
        'set minframeskip 0', 'set maxframeskip 0', 'set gamma 1', 'set brightness 0', 'set contrast 0',
        'activate_input_layer -blocking raster_verification',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}', 'set blur 0', 'set noise 0', 'set scanline 0',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16', 'reset',
        f'set directory {tcl(output)}', f'set actions {{{actions}}}',
        f'set rs_body_top {BODY_TOP}',
        'set current 0; set phase boot; set stable 0; set moved 0; set action_armed 0',
        'set rs_samples [open [file join $directory samples.tsv] w]',
        'set stages [open [file join $directory stages.tsv] w]',
        'proc active {} {expr {[debug read memory 0xc002]==165 && [debug read memory 0xc003]==90 && [debug read memory 0xc004]==83 && [debug read memory 0xc005]==82}}',
        'proc release {} {foreach row {0 1 3 8} {keymatrixup $row 255}}',
        'proc checked {body} {if {[catch {uplevel #0 $body} problem]} {puts stderr $problem; exit 2}}',
        'proc capture_case {} {',
        ' global current directory rs_samples stages phase stable moved actions action_armed',
        ' puts $rs_samples "$current\t[debug read memory 0xc001]\t[debug read memory 0xc006]\t[debug read memory 0xc007]\t[debug read memory 0xc009]\t[debug read memory 0xc00b]\t[debug read memory 0xc011]\t[debug read memory 0xc013]\t[debug read memory 0xc014]\t[debug read memory 0xc015]\t[debug read memory 0xc091]\t[debug read memory 0xc093]\t[debug read memory 0xc094]\t[debug read memory 0xc097]\t[expr {[debug read memory 0xc09a]+256*[debug read memory 0xc09b]}]\t[expr {[debug read memory 0xc09c]+256*[debug read memory 0xc09d]}]\t[debug read memory 0xc0a2]\t[debug read memory 0xc0a3]\t[expr {[debug read memory 0xc0b0]+256*[debug read memory 0xc0b1]}]\t[expr {[debug read memory 0xc0b2]+256*[debug read memory 0xc0b3]}]"; flush $rs_samples',
        ' screenshot -raw -size auto [file join $directory "$current.png"]',
        ' set f [open [file join $directory "$current.vram"] wb]; puts -nonewline $f [debug read_block VRAM 0 131072]; close $f',
        ' incr current',
        ' if {$current == [llength $actions]} {set phase finished; close $rs_samples; close $stages; exit; return}',
        ' lassign [lindex $actions $current] kind row mask count move_mask fuel_key life_key',
        ' release; set moved 0; set action_armed 0',
        ' if {$kind eq "move" || $kind eq "score"} {keymatrixdown 8 1}',
        ' if {$move_mask!=0} {keymatrixdown 8 $move_mask}',
        # Release Space before the 0/9/F/arrow chord; otherwise matrix ghosting
        # physically synthesizes key 7 and changes the cadence.
        ' if {$fuel_key!=0 && !$life_key} {keymatrixdown 3 8}',
        ' if {!$life_key} {keymatrixdown $row $mask}',
        ' if {$kind eq "move"} {set phase moving} elseif {$kind eq "score" && $life_key} {set phase score_arm} elseif {$kind eq "score"} {set phase score_input} elseif {$kind eq "fuel" || $kind eq "life"} {set phase fuel_input} else {set phase input}',
        '}',
        'proc mark {} {',
        ' global wp_last_value phase stable moved current actions workstart stages action_armed',
        ' set value $wp_last_value',
        ' if {$phase eq "finished"} {return}',
        ' if {$value==1} {set workstart [machine_info time]; set action_armed 1}',
        ' if {$value==3 && $phase eq "boot"} {if {[debug read memory 0xc400]} {keymatrixdown 7 128; return}; keymatrixup 7 128; keymatrixdown 8 1; set phase pausing; return}',
        ' if {$value!=2 || !$action_armed} {return}',
        ' puts -nonewline $::stage_probe [debug read_block memory 0xc0b0 4]; puts -nonewline $::stage_probe [debug read_block VRAM 0 65536]',
        ' if {[info exists workstart]} {puts $stages "main\t$current\t[expr {[machine_info time]-$workstart}]\t[machine_info time]\t$phase\t[debug read memory 0xc018]\t[debug read memory 0xc050]\t[debug read memory 0xc051]"; flush $stages}',
        ' if {$phase eq "pausing"} {release; set stable 0; set phase settling; return}',
        ' if {$phase eq "moving"} {incr moved; if {$moved == [lindex [lindex $actions $current] 3]} {release; set phase stopping}; return}',
        ' if {$phase eq "stopping"} {keymatrixdown 8 1; set phase pausing; return}',
        ' if {$phase eq "input"} {release; set stable 0; set phase settling; return}',
        ' if {$phase eq "fuel_input"} {incr moved; if {$moved == [lindex [lindex $actions $current] 3]} {release; set stable 0; set phase settling}; return}',
        ' if {$phase eq "score_arm"} {lassign [lindex $actions $current] kind row mask count move_mask fuel_key life_key; release; keymatrixdown $row $mask; keymatrixdown 8 $move_mask; keymatrixdown 3 8; keymatrixdown 0 1; set phase score_input; return}',
        ' if {$phase eq "score_input"} {release; set phase score_wait; return}',
        ' if {$phase eq "score_wait" && [debug read memory 0xc014]==[debug read memory 0xc013] && [debug read memory 0xc00c]==0} {keymatrixdown 8 1; set phase pausing}',
        '}',
        'proc raster {} {',
        ' global wp_last_value phase stable irqstart stages current rs_body_top',
        ' set v $wp_last_value',
        ' if {$phase eq "finished"} {return}',
        ' if {$v==1 || $v==3 || $v==5} {set irqstart [machine_info time]; return}',
        ' if {$v!=2 && $v!=4 && $v!=6} {return}',
        ' if {$::z80_freq!=3579545 || $::speed!=100 || $::cmdtiming ne "real"} {error "Timing changed"}',
        ' foreach {reg expected} {0 22 1 98 2 95 8 42 18 %d 23 0 25 0 26 0 27 0 19 7} {' % HORIZONTAL_ADJUST,
        '  if {$v==4 || $v==6} {switch $reg {0 {set expected [expr {$v==4?22:6}]} 2 {set expected 63} 8 {set expected 40} 19 {set expected [expr {([debug read memory 0xc007]-$rs_body_top+176)&255}]} 23 {set expected [expr {([debug read memory 0xc007]-$rs_body_top)&255}]} 25 {set expected 3} 26 {set expected [expr {(([debug read memory 0xc0b0]+256*[debug read memory 0xc0b1]-1)&511)>>3}]} 27 {set expected [expr {(-[debug read memory 0xc006])&7}]}}}',
        '  if {[debug read {VDP regs} $reg]!=$expected} {error "Raster register $reg: [debug read {VDP regs} $reg], expected $expected; world [debug read memory 0xc0b0],[debug read memory 0xc0b1],[debug read memory 0xc0b2],[debug read memory 0xc0b3]; raw [debug read memory 0xc006],[debug read memory 0xc007]; caches [debug read memory 0xc01a],[debug read memory 0xc01b]"}',
        ' }',
        ' if {[debug read {VDP regs} 9]!=%d} {error "Unexpected refresh"}' % info['timing']['vdp_r9'],
        ' puts $stages "$v\t$current\t[expr {[machine_info time]-$irqstart}]\t[machine_info time]"; flush $stages',
        ' if {$v==2 && $phase eq "settling"} {incr stable; if {$stable==3} {set phase capture_wait}}',
        ' if {$v==6 && $phase eq "capture_wait"} {set phase capture_pending; after time 0.001 {checked {capture_case}}}',
        '}',
        'proc overrun {} {if {[active]} {puts stderr "VRAM access timing violation"; exit 2}}',
        'set VDP.too_fast_vram_access_callback overrun',
        'debug set_watchpoint write_mem 0xc000 {[active] && [reg PC]>=0x4000 && [reg PC]<0x8000} {checked {mark}}',
        'debug set_watchpoint write_mem 0xc03c {[active] && [reg PC]>=0x4000 && [reg PC]<0x8000} {checked {raster}}',
        'after time 180 {puts stderr "Raster verification timed out"; exit 2}',
    ]
    lines.insert(0, f'set stage_probe [open {tcl(output/"movement.bin")} wb]')
    (output/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem; exit 2}\n')
    env = dict(os.environ, OPENMSX_HOME=str(output/'home'), OPENMSX_USER_DATA=str(output/'userdata'))
    with (output/'emulator.log').open('w') as log:
        result = subprocess.run([args.openmsx, '-script', str(output/'session.tcl')], env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=210)
    if bios != {p.relative_to(args.bios).as_posix():digest(p) for p in sorted(args.bios.rglob('*')) if p.is_file()}:
        raise ValueError('BIOS files changed during emulation')
    if result.returncode:
        raise ValueError(f'Raster verification failed: {output}/emulator.log')
    analyze_stage(args.rom, output, cases)
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])


def analyze_stage(rom, output, cases):
    """Compare every visible pixel with the full native-derived map, independently of cache jobs."""
    from . import stage_one
    info = read_json(rom.parent/'build.json')
    palette = (rom.parent/'palette.bin').read_bytes()
    life = (rom.parent/'life.bin').read_bytes()
    digits = (rom.parent/'life-digits.bin').read_bytes()
    states = (rom.parent/'hud-states.bin').read_bytes()
    world = (rom.parent/'stage-world.bin').read_bytes()
    points = read_json(rom.parent/'radar.json')['scenes']
    expected = dict(scene=0, wx=stage_one.START[0], wy=stage_one.START[1], lives=2,
                    score=0, high=4, cadence=2, fuel=0)
    reports = []
    for i,(case,line) in enumerate(zip(cases,(output/'samples.tsv').read_text().splitlines(),strict=True)):
        values=list(map(int,line.split('\t')))
        (ident,scene,cx,cy,paused,cadence,lives,goal,score,high,clock,px,py,color,
         ignored_x,ignored_y,fuel_goal,fuel_state,wx,wy)=values
        kind=case['kind']
        if kind in ('home','scene'):
            if kind=='scene': expected['scene']=case['scene']
            x,y=stage_one.LANDMARKS[expected['scene']]
            expected.update(wx=x,wy=y,lives=2,score=0,high=4,fuel=0)
        if 'delta' in case:
            n=case['count'] if kind=='move' else case.get('move_count',1)
            expected['wx']=max(0,min(stage_one.WIDTH-VIEWPORT_WIDTH,expected['wx']+case['delta'][0]*n))
            expected['wy']=max(0,min(stage_one.HEIGHT-201,expected['wy']+case['delta'][1]*n))
        if kind=='cadence': expected['cadence']=case['cadence']
        if kind=='life' or case.get('life_key'): expected['lives']=(expected['lives']+1)%10
        if kind=='fuel' or case.get('fuel_key'): expected['fuel']=(expected['fuel']+1)%5
        if kind=='score':
            expected['score']+=1;expected['high']=max(4,expected['score'])
        actual=dict(scene=scene,wx=wx,wy=wy,lives=lives,score=score,high=high,cadence=cadence,fuel=fuel_state)
        if expected!=actual or paused!=1 or goal!=score or fuel_goal!=fuel_state or (cx,cy)!=((wx-8)&255,wy&255):
            raise ValueError(f'Stage keyboard mismatch {case["name"]}: {actual}, expected {expected}')
        if ((px,py)!=(2+(wx+VIEWPORT_HALF)*44//stage_one.WIDTH,2+(wy+100)*54//stage_one.HEIGHT)
                or (ignored_x,ignored_y)!=(wx+VIEWPORT_HALF,wy+100)
                or color!=(info['sprites']['black'] if clock&16 else info['sprites']['white'])):
            raise ValueError(f'Stage radar camera mismatch {case["name"]}: {px},{py}')
        vram=(output/f'{i}.vram').read_bytes()
        check_stage_pixels(vram,world,wx,wy,info['sprites']['black'])
        hud=bytearray(states[score*1024:(score+1)*1024])
        for y in range(8):
            hud[y*128+36:y*128+60]=states[high*1024+y*128+36:high*1024+y*128+60]
        if vram[0x10000:0x10400]!=hud:
            raise ValueError(f'Stage header mismatch: {case["name"]}')
        frame_points=dict(points[scene],player=[px,py])
        oracle=compose(world,bytes(p for b in hud for p in (b>>4,b&15)),life,palette,wx,wy,
                       lives,frame_points,color,fuel_state,digits,width=stage_one.WIDTH)
        oracle=bordered(oracle,palette)
        oracle.save(output/f'expected-{i}.png')
        with Image.open(output/f'{i}.png') as raw:
            active=raw.convert('RGB')
        active.save(output/f'active-{i}.png')
        diff=ImageChops.difference(active,oracle)
        if diff.getbbox():
            diff.save(output/f'difference-{i}.png')
            raise ValueError(f'Stage RGB mismatch {case["name"]}: {diff.getbbox()}')
        reports.append(dict(name=case['name'],**actual,rgb_mismatches=0,visible_vram_mismatches=0))
    stages=[line.split('\t') for line in (output/'stages.tsv').read_text().splitlines()]
    times={}
    for kind in ('main','2','4','6'):
        values=[float(row[2])*1000 for row in stages if row[0]==kind]
        times[kind]=dict(samples=len(values),min_ms=min(values),max_ms=max(values))
    periods=[]
    for i,case in enumerate(cases):
        stamps=[float(row[3])-float(row[2]) for row in stages if row[0]=='main' and int(row[1])==i
                and len(row)>4 and row[4]=='moving']
        periods.extend((b-a)*1000 for a,b in zip(stamps,stamps[1:]))
    values=[float(row[2])*1000 for row in stages if row[0]=='main'
            and cases[int(row[1])]['kind'] not in ('initial','home','scene')]
    times['main_excluding_scene_loads']=dict(samples=len(values),min_ms=min(values),max_ms=max(values))
    target=info['timing']['frame_seconds']*1000
    for kind,name in (('4','raster_commit_periods'),('6','life_footer_periods')):
        commits=[]
        for i,case in enumerate(cases):
            if case['kind'] in ('initial','home','scene'): continue
            stamps=[float(row[3]) for row in stages if row[0]==kind and int(row[1])==i]
            commits.extend((b-a)*1000 for a,b in zip(stamps,stamps[1:]))
        if any(abs(v-target)>.02 for v in commits):
            raise ValueError(f'Stage {name} missed a refresh')
        times[name]=dict(samples=len(commits),min_ms=min(commits),max_ms=max(commits))
    packed_map=packed(world)
    probes=0
    with (output/'movement.bin').open('rb') as stream:
        while record:=stream.read(65540):
            if len(record)!=65540:
                raise ValueError('Truncated movement VRAM probe')
            x=int.from_bytes(record[:2],'little');y=int.from_bytes(record[2:4],'little')
            check_stage_pixels(record[4:],world,x,y,info['sprites']['black'],packed_world=packed_map)
            probes+=1
    times['continuous_map_checks']=dict(frames=probes,pixels_per_frame=VIEWPORT_WIDTH*201)
    target=info['timing']['frame_seconds']*1000
    if any(abs(value-target)>.02 for value in periods):
        raise ValueError('Stage streaming missed a movement refresh')
    times['held_movement_periods']=dict(samples=len(periods),min_ms=min(periods),max_ms=max(periods))
    json_write(output/'report.json',dict(schema_version=1,rom_sha256=digest(rom),cases=reports,
        incremental_stage=info.get('incremental_stage'),rock_sprite_slots=info.get('rock_sprite_slots',0),
        rock_collision=info.get('rock_collision',False),
        timings=times,native_tiles_checked=read_json(rom.parent/'stage-one.json')['native_tiles_checked'],
        scope='Original first-stage static map; real keyboard, settled RGB, visible VRAM and movement periods'))
    print(f'{len(reports)} exact full-stage keyboard/raster images: {output}/report.json')


def check_stage_pixels(vram, world, wx, wy, black, *, packed_world=None):
    from . import stage_one
    data = packed(world) if packed_world is None else packed_world
    odd=wx&1
    size=VIEWPORT_WIDTH//2+odd
    bx=(wx&511)//2
    for y in range(201):
        row=((wy+y)&255)*128
        remaining=size
        pos=bx
        actual=bytearray()
        while remaining:
            n=min(remaining,128-(pos%128))
            address=(pos//128)*32768+row+(pos%128)
            actual.extend(vram[address:address+n])
            pos=(pos+n)%256
            remaining-=n
        start=(wy+y)*(stage_one.WIDTH//2)+wx//2
        expected=bytearray(data[start:start+size])
        if odd:
            actual[0]&=15;expected[0]&=15
            actual[-1]&=240;expected[-1]&=240
        if actual!=expected:
            raise ValueError(f'Stage cache mismatch at camera {wx},{wy}, local row {y}')
