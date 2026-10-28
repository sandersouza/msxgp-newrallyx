#!/usr/bin/env python3
"""Observe a saved human-input replay without injecting gameplay or RAM state."""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl,scanout_recording_tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.terrain_live import observer,analyze
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def verify_replay_rom(replay,rom):
    fingerprint=hashlib.sha1(rom.read_bytes()).hexdigest()
    snapshot=ET.fromstring(gzip.decompress(replay.read_bytes()))
    if fingerprint not in {node.text for node in snapshot.iter('resolvedSha1')}:
        raise ValueError('Replay does not contain the selected cartridge fingerprint')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--replay',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--record',action='store_true',help='Also retain every actual raw scanout frame in scanout.avi')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    rom=args.rom.resolve();replay=args.replay.resolve();verify_manifest(rom.parent)
    verify_replay_rom(replay,rom)
    s=symbols(rom.parent/'raster-scroll.sym');out=destination(root,args.output)
    require_ignored(root,[out/'terrain-latch.bin']);out.mkdir(parents=True)
    lines=['set save_settings_on_exit false',f'set renderer {"SDLGL-PP" if args.record else "none"}','set sound_driver null',
        'set gamma 1','set brightness 0','set contrast 0','set blur 0','set noise 0','set scanline 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),
        f'reverse loadreplay -goto begin -viewonly {tcl(replay)}','set throttle off',
        f'set out {tcl(out)}',
        *(['set scanout_times [open [file join $out scanout-times.tsv] w]',
           'set sample_times [open [file join $out sample-times.tsv] w]',
           'proc scanout_frame {} {puts $::scanout_times "$::scanout_frames [machine_info time]";incr ::scanout_frames;after frame scanout_frame}',
           scanout_recording_tcl(out,s['startup_mode']).replace('set ::scanout_recording_started 1',
               'set ::scanout_recording_started 1;set ::scanout_frames 0;after frame scanout_frame')]
          if args.record else []),
        *observer(),
        'set latch_count 0;set mode_failures 0;set modes [open [file join $out modes.tsv] w]',
        'proc u16 {at} {expr {[debug read memory $at]+256*[debug read memory [expr {$at+1}]]}}',
        f'debug set_bp {s["Full_RadarIRQ"]} {{[debug read memory 0xc7d0]==0 && ![debug read memory {s["Full_Attract"]}]}} {{',
        ' incr ::latch_count',
        f' set wx [u16 {s["world_x"]}];set wy [u16 {s["world_y"]}]',
        ' if {$wx>=32768} {incr wx -65536};if {$wy>=32768} {incr wy -65536}',
        ' set sx [expr {[debug read {VDP regs} 26]*8+8-([debug read {VDP regs} 27]&7)}]',
        ' set sy [debug read {VDP regs} 23]',
        ' set wx [expr {$wx+(($sx-$wx+256)&511)-256}]',
        f' set wy [expr {{$wy+(($sy+{s["BODY_TOP"]}-$wy+128)&255)-128}}]',
        ' set actual [list [debug read {VDP regs} 0] [debug read {VDP regs} 1] [debug read {VDP regs} 2] [debug read {VDP regs} 25] [debug read {VDP regs} 26] [debug read {VDP regs} 27] $sy]',
        f' set expected [list {s["MAZE_R0"]+16} 98 {s["MAZE_R2"]} 3 [debug read memory {s["Full_PresentActiveX"]}] [debug read memory {s["Full_PresentActiveX"]+1}] [debug read memory {s["irq_scroll_y"]}]]',
        ' puts $::modes "[machine_info time] $actual"',
        ' if {$actual ne $expected} {incr ::mode_failures}',
        *([' set before [tell $::terrain_latch_out]'] if args.record else []),
        ' terrain_capture $wx $wy $::terrain_latch_out',
        *([' if {[tell $::terrain_latch_out]>$before} {puts $::sample_times "$before [machine_info time]"}'] if args.record else []),
        '}',
        'set end [dict get [reverse status] end]',
        'after time [expr {$end-[machine_info time]}] {',
        *([' record stop;close $::scanout_times;close $::sample_times'] if args.record else []),
        ' set pause on;close $::terrain_latch_out;close $::terrain_live_out;close $::modes',
        ' set stream [open [file join $::out counts.txt] w];puts $stream "$::latch_count $::mode_failures";close $stream;exit 0',
        '}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=240,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    terrain=analyze(root,rom.parent,out/'terrain-latch.bin')
    latches,mode_failures=map(int,(out/'counts.txt').read_text().split())
    report=dict(rom_sha256=digest(rom),replay_sha256=digest(replay),latches=latches,
        mode_failures=mode_failures,terrain=terrain,scanout_recorded=args.record,
        passed=terrain['passed'] and mode_failures==0,
        scope='Saved human-input replay, no new gameplay inputs or RAM writes; original scenery grid and actual maze-mode/scroll registers at the physical latch. Not every pixel or continuous scanout.')
    json_write(out/'report.json',report);seal(out)
    if not report['passed']:raise ValueError(f'Human replay exposed a video mismatch: {out}/report.json')
    print(f'Human replay terrain/mode checks pass: {out}/report.json')


if __name__=='__main__':main()
