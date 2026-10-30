"""Real emulated joystick peripheral and output-latch preservation proof."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import os
import subprocess
import xml.etree.ElementTree as ET
from src.toolchain.scenes.bundle import verify_manifest,read_json,digest
from src.toolchain.scenes.storage import require_ignored,json_write,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .native_inputs import JOYSTICK_CASES,OUTPUT_CASES


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    if not read_json(bundle/'build.json').get('session'):raise ValueError('Session inputs require stage12')
    out=destination(root,args.output);out.mkdir(parents=True);require_ignored(root,[out/'base.oms'])
    syms=symbols(bundle/'raster-scroll.sym')
    common=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1']
    def execute(lines,folder):
        script=folder/'probe.tcl';script.write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
        with (folder/'emulator.log').open('w') as log:
            subprocess.run([args.openmsx,'-script',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
                env=dict(os.environ,OPENMSX_HOME=str(folder/'home'),OPENMSX_USER_DATA=str(folder/'userdata')))
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    execute(common+[reference_machine(root,args.machine),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        'catch {unplug joyporta}','plug joyporta msxjoystick1','set phase boot;set age 0',
        'proc start_game {} {',
        ' incr ::age;switch $::phase {',
        ' boot {if {[debug read memory 0xc7d0]==1 && [debug read memory 0xc7dd]==1} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}',
        ' coin {if {$::age==4} {keymatrixup 0 255;set ::phase release;set ::age 0}}',
        ' release {if {$::age==3} {keymatrixdown 0 2;set ::phase start;set ::age 0}}',
        ' start {if {$::age==4} {keymatrixup 0 255}}',' };after time 0.02 start_game','}',
        f'debug set_bp {syms["keys"]} {{[reg IM]==2 && [debug read memory 0xc7d0]==0 && ![info exists ::key_saved]}} {{set ::key_saved 1;store_machine [machine] {tcl(out/"game-base.oms")}}}',
        f'debug set_bp {syms["Session_Joystick"]} {{[reg IM]==2 && [debug read memory 0xc7d0]==0}} {{store_machine [machine] {tcl(out/"base.oms")};exit 0}}',
        'after time 0.02 start_game','after time 60 {puts stderr "Joystick base timeout";exit 2}'],out)
    base=gzip.decompress((out/'base.oms').read_bytes())
    cases=[(joy,prior,keyboard) for joy,_ in JOYSTICK_CASES for prior in OUTPUT_CASES for keyboard in ((0,0,0),(-1,1,2))]
    def case(item):
        n,(joy,prior,(kx,ky,smoke))=item;folder=out/f'case-{n:03d}';folder.mkdir()
        state=ET.fromstring(base);node=state.find('.//joystickportA/Connector/pluggable[@type="MSXJoystick"]/status')
        if node is None:raise ValueError('Emulated joystick peripheral missing')
        node.text=str(joy)
        (folder/'input.oms').write_bytes(gzip.compress(b'<?xml version="1.0" ?>\n<!DOCTYPE openmsx-serialize SYSTEM "openmsx-serialize.dtd">\n'+ET.tostring(state,encoding='utf-8')))
        pressed=joy^63;dx=kx+bool(pressed&8)-bool(pressed&4);dy=ky+bool(pressed&2)-bool(pressed&1)
        expected=(dx&255,dy&255,1 if pressed&16 else smoke);ppi=prior^160
        execute(common+[f'set selected [restore_machine {tcl(folder/"input.oms")}]',
            'set old [machine];if {$old ne ""} {delete_machine $old};activate_machine $selected','set throttle off',
            f'foreach {{a v}} {{0xc050 {kx&255} 0xc051 {ky&255} 0xc700 {smoke} 0xc019 0}} {{debug write memory $a $v}}',
            f'debug write "PSG regs" 15 {prior};debug write ioports 170 {ppi}',
            'set original [debug read_block memory 0xe000 4096]',
            f'debug set_bp {syms["Session_JoystickReturn"]} {{}} {{',
            f' set actual [list [debug read memory 0xc050] [debug read memory 0xc051] [debug read memory 0xc700]]',
            f' if {{$actual ne [list {expected[0]} {expected[1]} {expected[2]}] || [debug read {{PSG regs}} 15]!={prior} || [debug read ioports 170]!={ppi} || [debug read_block memory 0xe000 4096] ne $::original}} {{puts stderr "Joystick case{n} mismatch: $actual";exit 2}}',
            ' exit 0','}','after time 0.1 {puts stderr "Joystick return timeout";exit 2}'],folder)
        return dict(case=n,joystick_level=joy,psg_output=prior,keyboard=[kx,ky,smoke],expected=list(expected))
    rows=[case((0,cases[0]))]
    with ThreadPoolExecutor(max_workers=4) as pool:rows.extend(pool.map(case,list(enumerate(cases))[1:]))
    game_base=gzip.decompress((out/'game-base.oms').read_bytes())
    pairs=((63,0,0),(62,32,0),(61,64,0),(59,16,0),(55,128,0),(47,0,2),(31,0,0),(54,160,0),(46,32,2))
    def game_case(item):
        n,(joy,arrow,ctrl),keyboard=item;folder=out/f'game-{n:02d}-{"key" if keyboard else "joy"}';folder.mkdir()
        state=ET.fromstring(game_base);state.find('.//joystickportA/Connector/pluggable[@type="MSXJoystick"]/status').text=str(63 if keyboard else joy)
        (folder/'input.oms').write_bytes(gzip.compress(b'<?xml version="1.0" ?>\n<!DOCTYPE openmsx-serialize SYSTEM "openmsx-serialize.dtd">\n'+ET.tostring(state,encoding='utf-8')))
        execute(common+[f'set selected [restore_machine {tcl(folder/"input.oms")}]',
            'set old [machine];if {$old ne ""} {delete_machine $old};activate_machine $selected','set throttle off',
            'keymatrixup 0 255;keymatrixup 6 255;keymatrixup 8 255',
            *([f'keymatrixdown 8 {arrow}'] if keyboard and arrow else []),
            *(['keymatrixdown 8 1'] if keyboard and ctrl else []),
            'debug set_watchpoint write_mem 0xc000 {$wp_last_value==2} {',
            f' set f [open {tcl(folder/"native.bin")} wb];puts -nonewline $f [debug read_block memory 0xe000 4096];puts -nonewline $f [debug read_block memory 0xc440 2];close $f;exit 0','}',
            'after time 0.2 {puts stderr "Gameplay input-frame timeout";exit 2}'],folder)
        return n,keyboard,(folder/'native.bin').read_bytes()
    frames={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n,keyboard,data in pool.map(game_case,[(n,p,k) for n,p in enumerate(pairs) for k in (False,True)]):frames[n,keyboard]=data
    for n in range(len(pairs)):
        if frames[n,False]!=frames[n,True] or len(frames[n,True])!=4098:
            raise ValueError(f'Joystick/keyboard native gameplay frame differs at case{n}')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Joystick BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),peripheral_cases=len(rows),cases=rows,
        complete_native_gameplay_frame_equivalence_cases=len(pairs),native_frame_bytes=4098,
        native_game_ram_unchanged=True,psg_output_and_ppi_preserved=True,
        scope='Emulated joystick1 directions/triggerA plus keyboard merge; physical controller not claimed'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Session input: {len(rows)} peripheral and {len(pairs)} complete native gameplay-frame pairs: {out}/report.json')
