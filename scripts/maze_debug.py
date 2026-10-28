#!/usr/bin/env python3
"""Run the game with F6 capturing a replay and machine state for transient bugs."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.emulator import reference_machine, tcl
from scripts.scenes.bundle import digest
from scripts.scenes.storage import json_write, require_ignored


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,default=Path('references/build/newrallyx.rom'))
    parser.add_argument('--self-test',action='store_true',help='Capture real keyboard coin/start automatically, then exit')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    rom=args.rom.resolve()
    if not rom.is_file():raise ValueError('Build the cartridge before starting the debug session')
    out=root/'references/build'/f'maze-debug-{uuid4().hex}'
    require_ignored(root,[out/'session.tcl']);out.mkdir(parents=True)
    json_write(out/'session.json',dict(rom=str(rom),rom_sha256=digest(rom),capture_key='F6'))
    lines=['set save_settings_on_exit false',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',
        f'set throttle {"off" if args.self_test else "on"}','set speed 100',
        'set z80_freq 3579545','set z80_freq_locked true','set cmdtiming real','set limitsprites true',
        'set pause_on_lost_focus false',f'cart {tcl(rom)} -romtype ASCII16','reset','reverse start',
        f'set maze_capture_dir {tcl(out)};set maze_capture_count 0',
        'proc maze_capture {} {',
        ' set base [file join $::maze_capture_dir capture-[incr ::maze_capture_count]]',
        ' reverse savereplay $base.omr',
        ' store_machine [machine] $base.oms',
        ' screenshot -raw $base.png',
        ' foreach {extension data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] vdp [debug read_block {VDP regs} 0 64]] {',
        '  set stream [open $base.$extension wb];puts -nonewline $stream $data;close $stream',
        ' }',
        ' set stream [open $base.txt w]',
        ' puts $stream "time=[machine_info time] PC=[reg PC] SP=[reg SP] primary=[debug read ioports 168] page0=[debug read ioports 252] page3=[debug read ioports 255]";close $stream',
        ' puts stderr "Maze capture saved: $base"',
        '}',
        'bind F6 maze_capture']
    if args.self_test:
        lines.extend(['set maze_test_phase boot;set maze_test_age 0',
            'proc maze_test_poll {} {',
            ' incr ::maze_test_age;set state [debug read memory 0xc7d0]',
            ' switch $::maze_test_phase {',
            ' boot {if {$state==1 && [debug read memory 0xc7dd]} {keymatrixdown 0 32;set ::maze_test_phase coin;set ::maze_test_age 0}}',
            ' coin {if {$::maze_test_age==4} {keymatrixup 0 32;set ::maze_test_phase release;set ::maze_test_age 0}}',
            ' release {if {$::maze_test_age==4} {keymatrixdown 0 2;set ::maze_test_phase start;set ::maze_test_age 0}}',
            ' start {if {$::maze_test_age==4} {keymatrixup 0 2};if {$state==0} {',
            f'  record start -videoonly {tcl(out/"capture-test.avi")}',
            '  after time 0.2 {if {[catch maze_test_capture problem]} {puts stderr $problem;exit 2};exit 0}',
            '  return',
            ' }}',
            ' }',
            ' after time 0.02 maze_test_poll',
            '}',
            'proc maze_test_capture {} {',
            ' maze_capture;record stop',
            ' set expected [debug read_block memory 0xc000 12288];set expected_vram [debug read_block VRAM 0 131072]',
            ' reverse loadreplay -goto savetime -viewonly [file join $::maze_capture_dir capture-1.omr]',
            ' set pause on',
            ' if {[debug read_block memory 0xc000 12288] ne $expected || [debug read_block VRAM 0 131072] ne $expected_vram} {error "Saved replay does not restore captured RAM/VRAM"}',
            '}',
            'after time 0.02 maze_test_poll',
            'after time 60 {puts stderr "Debug capture keyboard test timed out";exit 2}'])
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    print(f'F6 saves the current screen, machine state and preceding replay to {out}',flush=True)
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,
            timeout=120 if args.self_test else None,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    if args.self_test:
        required=('omr','oms','png','state','vram','vdp','txt')
        if any(not (out/f'capture-1.{extension}').is_file() for extension in required):
            raise ValueError(f'Incomplete F6 capture: inspect {out}/emulator.log')
        if (out/'capture-1.state').read_bytes()[0x7d0]!=0:
            raise ValueError('Capture test did not reach actual gameplay')
        from PIL import Image
        with Image.open(out/'capture-1.png') as screen:
            if not any(high for low,high in screen.convert('RGB').getextrema()):
                raise ValueError('Capture screenshot is blank')
        print('Replay/state/screenshot capture passes')


if __name__=='__main__':main()
