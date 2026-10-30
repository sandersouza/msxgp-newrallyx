"""Execute real HUD setters with a separate Z80 consumer and verify their public ABI."""
import copy
import os
import re
import shutil
import subprocess
from PIL import Image,ImageChops
from .build import destination
from .emulator import tcl, reference_machine
from .hud_contract import native_values,DIGIT_OFFSETS
from .raster_scroll import compose,header,bordered
from . import sprite_fuel as fuel
from src.toolchain.scenes.bundle import load_assets,read_json,digest,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal


def measure_attributes(root, args):
    """Measure actual HUD SAT work across all 256 renderer scroll phases.

    The probe changes only the renderer's scroll shadow around the routine and
    restores it before returning. This is a cost microprobe, not an RGB proof.
    """
    verify_manifest(args.rom.parent)
    if read_json(args.rom.parent/'build.json').get('hud_style',{}).get('radar_cells_only'):
        from .hud_coordinates_verify import verify
        return verify(root,args)
    original_rom = digest(args.rom)
    original_manifest = digest(args.rom.parent/'manifest.json')
    sym = symbols(args.rom.parent/'raster-scroll.sym')
    output = destination(root,args.output)
    require_ignored(root,[output/'cycles.tsv',output/'session.tcl'])
    output.mkdir(parents=True)
    bios = {str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    lines = ['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(output)}','set n 0','set trace [open [file join $out cycles.tsv] w]',
        'puts $trace "phase\tcycles"',
        f'debug set_bp {sym["update_lives"]} {{[reg IM]==2 && [reg I]==208}} {{',
        'set ::saved [debug read memory 49180]; debug write memory 49180 $::n',
        'set ::start [machine_info time]', '}',
        f'debug set_bp {sym["point_attribute"]-1} {{[info exists ::start]}} {{',
        'if {[debug read memory [reg PC]]!=201} {puts stderr "HUD timing return changed";exit 2}',
        'puts $::trace "$::n\t[expr {round(([machine_info time]-$::start)*3579545)+10}]"',
        'debug write memory 49180 $::saved; unset ::start; incr ::n',
        'if {$::n==256} {close $::trace;exit 0}', '}',
        'set VDP.too_fast_vram_access_callback {puts stderr "VRAM timing violation";exit 2}',
        'after time 120 {puts stderr "HUD cost probe timeout";exit 2}']
    (output/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (output/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(output/'session.tcl')],check=True,timeout=130,
            env=dict(os.environ,OPENMSX_HOME=str(output/'home'),OPENMSX_USER_DATA=str(output/'userdata')),
            stdout=log,stderr=subprocess.STDOUT)
    rows=[list(map(int,row.split('\t'))) for row in (output/'cycles.tsv').read_text().splitlines()[1:]]
    if len(rows)!=256 or any(len(row)!=2 or row[0]!=n or not 0<row[1]<20000 for n,row in enumerate(rows)):
        raise ValueError('Incomplete or invalid HUD attribute-cost proof')
    verify_manifest(args.rom.parent)
    if original_rom != digest(args.rom) or original_manifest != digest(args.rom.parent/'manifest.json'):
        raise ValueError('Cartridge changed during HUD cost proof')
    if bios != {str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('BIOS changed during HUD cost proof')
    json_write(output/'report.json',dict(phases=256,rom_sha256=digest(args.rom),
        min_cycles=min(row[1] for row in rows),max_cycles=max(row[1] for row in rows),
        cpu_hz=3579545,scope='Isolated HUD attribute routine; not total frame CPU or RGB validation'))
    require_ignored(root,[p for p in output.rglob('*') if p.is_file()])
    seal(output)
    return output


def symbols(path):
    return {name:int(value,16) for name,value in
            re.findall(r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)',path.read_text(),re.M)}


def cases(native):
    result=[]
    def add(name,entry,a=0,b=0,c=0,payload=None,invalid=False,wait=8,skip_image=False,**change):
        result.append(dict(name=name,entry=entry,a=a,bc=b*256+c,payload=payload,
                           invalid=invalid,change=change,wait=wait,skip_image=skip_image))
    add('label-player-2','HUD_SetPlayerNumber',a=2,player_number=2)
    add('label-invalid','HUD_SetPlayerNumber',a=3,invalid=True)
    add('label-player-1','HUD_SetPlayerNumber',a=1,player_number=1)
    for value in (123456,999999,0,10,987650):
        add(f'score-{value}','HUD_SetScore',payload=bytes(map(int,f'{value:06d}')).hex(),score=value)
    add('cadence-stress-start','HUD_SetCadence',a=4,cadence=4)
    for value in (234560,234570,234580):
        add(f'coalesced-{value}','HUD_SetScore',payload=bytes(map(int,f'{value:06d}')).hex(),
            score=value,wait=1,skip_image=True)
    add('coalesced-final','HUD_SetScore',payload=bytes(map(int,'234590')).hex(),score=234590)
    add('cadence-stress-end','HUD_SetCadence',a=2,cadence=2)
    add('score-invalid','HUD_SetScore',payload=bytes([0,0,10,0,0,0]).hex(),invalid=True)
    for value in (654321,12345,20000):
        add(f'high-{value}','HUD_SetHiscore',payload=bytes(map(int,f'{value:06d}')).hex(),high=value)
    for n in range(10):add(f'lives-{n}','HUD_SetLives',a=n,lives=n)
    add('lives-invalid','HUD_SetLives',a=10,invalid=True)
    for n in (*range(55),255):add(f'fuel-{n}','HUD_SetFuel',a=n,fuel=min(n,54)*30//54)
    for entry,key in (('HUD_SetPlayer','player'),('HUD_SetEnemy','enemy')):
        for x,y in ((7,7),(15,15),(46,56),(255,255),(2,2)):
            add(f'{key}-{x}-{y}',entry,b=x,c=y,**{key:[x,y]})
        add(f'{key}-invalid',entry,b=47,c=57,invalid=True)
    for i,x,y in ((0,7,7),(0,15,12),(0,255,255),(0,15,15),(1,16,29),(10,24,44),(19,46,56),(19,255,255)):
        add(f'point-{i}-{x}-{y}','HUD_SetRadarPoint',a=i,b=x,c=y,point=[i,x,y])
    add('flag-invalid','HUD_SetFlag',a=10,b=2,c=2,invalid=True)
    add('native-point','HUD_SetNativePoint',a=10,b=63,c=111,point=[10,45,55])
    add('native-point-invalid','HUD_SetNativePoint',a=20,b=63,c=111,invalid=True)
    add('native-coordinate-invalid','HUD_SetNativePlayer',b=64,c=111,invalid=True)
    add('point-invalid','HUD_SetRadarPoint',a=20,b=2,c=2,invalid=True)
    add('native-player','HUD_SetNativePlayer',b=63,c=111,player=[45,55])
    add('native-enemy','HUD_SetNativeEnemy',b=20,c=40,enemy=[15,21])
    for n in (3,4,2):add(f'cadence-{n}','HUD_SetCadence',a=n,cadence=n)
    add('cadence-invalid','HUD_SetCadence',a=1,invalid=True)
    add('native-capture','HUD_SyncNative',payload=native.hex(),**native_values(native))
    synthetic=bytearray(native)
    score_pointer=int.from_bytes(synthetic[0x990:0x992],'little')-0x8000
    for offset,digit in zip(DIGIT_OFFSETS,map(int,'876540')):synthetic[score_pointer+offset]=digit
    fuel_pointer=int.from_bytes(synthetic[0x98e:0x990],'little')-0x8000
    synthetic[fuel_pointer:fuel_pointer+2]=bytes([9,27])
    life_pointer=int.from_bytes(synthetic[0x988:0x98a],'little')-0x8000
    synthetic[life_pointer]=8
    add('native-state','HUD_SyncNative',payload=synthetic.hex(),**native_values(synthetic))
    synthetic[score_pointer+6]=0x0a
    add('native-invalid-digit','HUD_SyncNative',payload=synthetic.hex(),invalid=True)
    synthetic=bytearray(native);synthetic[0x98e:0x990]=bytes([255,255])
    add('native-invalid-pointer','HUD_SyncNative',payload=synthetic.hex(),invalid=True)
    synthetic=bytearray(native);synthetic[0x990:0x992]=(0x8fff).to_bytes(2,'little')
    add('native-boundary-pointer','HUD_SyncNative',payload=synthetic.hex(),invalid=True)
    return result


def verify(root,args):
    output=destination(root,args.output);verify_manifest(args.rom.parent)
    require_ignored(root,[output/'test.rom',output/'report.json'])
    output.mkdir(parents=True)
    sym=symbols(args.rom.parent/'raster-scroll.sym')
    data_bank=max(int(p.stem.split('-')[1]) for p in args.rom.parent.glob('bank-*.bin'))+1
    commands=cases((root/'assets/arcade/native/native-v1/video.bin').read_bytes())
    data=bytearray(16384);native_banks=[];small=0x800
    for i,case in enumerate(commands):
        payload=bytes.fromhex(case['payload']) if case['payload'] else b''
        if len(payload)==4096:
            address=0x9000+len(native_banks)*256;native_banks.append(payload+bytes(12288))
        elif payload:
            address=0x8000+small;data[small:small+len(payload)]=payload;small+=len(payload)
        else:address=0x4567
        case['hl']=0xe000 if len(payload)==4096 else address
        record=(sym[case['entry']].to_bytes(2,'little')+bytes([case['a']])+
                case['bc'].to_bytes(2,'little')+address.to_bytes(2,'little')+bytes([case['invalid'],case['wait']]))
        data[i*16:i*16+16]=record+bytes(16-len(record))
    if len(commands)*16>0x800 or small>=0x1000:raise ValueError('HUD command fixtures exceed their data area')
    (output/'data.bin').write_bytes(data)
    (output/'hud-imports.inc').write_text(''.join(f'{k} EQU ${v:04x}\n' for k,v in sym.items() if '.' not in k)+f'COMMANDS EQU {len(commands)}\nTEST_DATA_BANK EQU {data_bank}\n')
    shutil.copyfile(root/'tests/fixtures/hud-api-driver.asm',output/'hud-api-driver.asm')
    subprocess.run([str(args.assembler.resolve()),'--nologo','hud-api-driver.asm'],cwd=output,
                   capture_output=True,text=True,check=True)
    rom=bytearray(args.rom.read_bytes());driver=(output/'hud-api-driver.bin').read_bytes()
    # The synthetic HUD consumer exercises inspection mode; production boots driving.
    startup=sym['startup_mode']-0x4000
    assert rom[startup:startup+2]==b'\x3e\x01','Expected production driving startup'
    rom[startup+1]=0
    assert rom[0x3800:0x3800+len(driver)]==bytes([255])*len(driver),'Test driver must fit unused fixed ROM'
    rom[0x3800:0x3800+len(driver)]=driver
    start,end=sym['main']-0x4000,sym['interrupt']-0x4000
    def replace_call(target,replacement):
        needle=bytes([0xcd,target&255,target>>8]);offset=rom.index(needle,start,end)
        rom[offset:offset+3]=replacement
    replace_call(sym['keys'],bytes([0xcd,0,0x78]))
    replace_call(sym['Player_Radar'],bytes(3))
    replace_call(sym['HUD_SetForce'],bytes(3))
    rom[data_bank*16384:(data_bank+1)*16384]=data
    for i,bank in enumerate(native_banks,data_bank+1):rom[i*16384:(i+1)*16384]=bank
    (output/'test.rom').write_bytes(rom)
    lines=['set save_settings_on_exit false',f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set throttle on','set speed 100','set z80_freq 3579545',
        'set cmdtiming real','set limitsprites true','set disablesprites false','set minframeskip 0','set maxframeskip 0',
        'set gamma 1','set brightness 0','set contrast 0','set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        'set blur 0','set noise 0','set scanline 0','set pause_on_lost_focus false',
        'activate_input_layer -blocking hud_contract',f'cart {tcl(output/"test.rom")} -romtype ASCII16','reset',
        f'set directory {tcl(output)}',f'set count {len(commands)}','set last 0',
        'set trace [open [file join $directory cadence.tsv] w]',
        'proc arguments {n} {global directory; set f [open [file join $directory "$n.ram"] wb]; puts -nonewline $f [debug read_block memory 0xc000 12288]; close $f}',
        'proc capture {} {global directory count last trace; set n [debug read memory 0xc3a0]; if {$n==0 || $n==$last || [debug read memory 0xc3a1]!=2} {return}; set last $n; screenshot -raw -size auto [file join $directory "$n.png"]; if {$n==$count} {close $trace; exit}}',
        'proc tick {} {global trace; set s {}; set h {}; for {set i 0} {$i<6} {incr i} {append s [debug read memory [expr {0xc30c+$i}]]; append h [debug read memory [expr {0xc312+$i}]]}; puts $trace "[debug read memory 0xc00a] [debug read memory 0xc00b] [debug read memory 0xc394] $s $h"}',
        'debug set_watchpoint write_mem 0xc3a0 {$wp_last_value>0 && $wp_last_value<=$count} {arguments $wp_last_value}',
        'debug set_watchpoint write_mem 0xc000 {$wp_last_value==2} tick',
        'debug set_watchpoint write_mem 0xc03c {$wp_last_value==6} {after time 0.001 capture}',
        'set VDP.too_fast_vram_access_callback {puts stderr "VRAM access violation"; exit 2}',
        'after time 90 {puts stderr "HUD contract timeout"; exit 2}']
    (output/'session.tcl').write_text('\n'.join(lines)+'\n')
    env=dict(os.environ,OPENMSX_HOME=str(output/'home'),OPENMSX_USER_DATA=str(output/'userdata'))
    bios={p.relative_to(args.bios).as_posix():digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (output/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(output/'session.tcl')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=110,check=True)
    assert bios=={p.relative_to(args.bios).as_posix():digest(p) for p in args.bios.rglob('*') if p.is_file()}
    analyze(args,output,commands)
    require_ignored(root,[p for p in output.rglob('*') if p.is_file()]);seal(output)


def analyze(args,output,commands):
    bundle=args.rom.parent;palette=(bundle/'palette.bin').read_bytes();assets=load_assets(args.assets)
    life=(bundle/'life.bin').read_bytes();digits=(bundle/'life-digits.bin').read_bytes();world=(bundle/'stage-world.bin').read_bytes()
    radar=read_json(bundle/'radar.json')['scenes'][0]
    state=dict(score=0,high=20000,lives=2,fuel=30,player=radar['player'],enemy=radar['enemy'],cadence=2,player_number=1)
    points=copy.deepcopy(radar['flags'])+[[255,255] for _ in range(10)]
    reports=[]
    for i,case in enumerate(commands,1):
        ram=(output/f'{i}.ram').read_bytes();regs=ram[0x3c0:0x3d8]
        values=[int.from_bytes(regs[n:n+2],'little') for n in range(0,24,2)]
        if values[:5]!=[case['bc'],0x5678,case['hl'],0x9abc,0xdef0] or bool(values[5]&1)!=case['invalid'] or values[6]!=values[7] or values[8:]!=[0x1111,0x2222,0x3333,0x4455]:
            raise ValueError(f'HUD ABI mismatch {case["name"]}: {values}')
        if case['entry']=='HUD_SyncNative' and ram[0x2000:0x3000]!=bytes.fromhex(case['payload']):
            raise ValueError('Native state was modified by the HUD adapter')
        if not case['invalid']:
            change=dict(case['change'])
            if 'point' in change:
                slot,x,y=change.pop('point');points[slot]=[x,y]
            state.update(change)
        if case['skip_image']:
            reports.append(dict(name=case['name'],abi_preserved=True,rgb_checked=False))
            continue
        frame_points=dict(flags=[p for p in points if p[0]!=255],player=state['player'],enemy=state['enemy'])
        expected=compose(world,header(assets,palette,state['score'],state['high'],player=state['player_number']),life,palette,
            264,1032,state['lives'],frame_points,player_color=read_json(bundle/'build.json')['sprites']['white'],
            life_digits=digits,width=816,fuel_pixels=state['fuel'])
        expected=bordered(expected,palette)
        expected.save(output/f'{i}-expected.png')
        with Image.open(output/f'{i}.png') as raw:actual=raw.convert('RGB')
        diff=ImageChops.difference(actual,expected)
        if diff.getbbox():
            diff.save(output/f'{i}-difference.png');raise ValueError(f'HUD image mismatch {case["name"]}: {diff.getbbox()}')
        reports.append(dict(name=case['name'],abi_preserved=True,rejected=case['invalid'],rgb_mismatches=0))
    last=[None,None]
    changes=0
    for line in (output/'cadence.tsv').read_text().splitlines():
        tick,cadence,force,score,high=map(int,line.split())
        for field,value in enumerate((score,high)):
            previous=last[field]
            if previous is None or value!=previous[0]:
                if previous and not force and not previous[2] and (tick-previous[1])%256<cadence:
                    raise ValueError('HUD numeric cadence was bypassed')
                last[field]=(value,tick,force);changes+=1
    image_checks=sum(not case['skip_image'] for case in commands)
    json_write(output/'report.json',dict(rom_sha256=digest(args.rom),cases=reports,
        complete_image_checks=image_checks,
        cadence_changes_checked=changes,
        scope='Separate synthetic Z80 consumer of the production API; native snapshots are read-only inputs, not ported gameplay'))
    print(f'{len(reports)} HUD API/ABI checks, {image_checks} complete-image checks: {output}/report.json')
