#!/usr/bin/env python3
"""Observe saved replays or reapply their keyboard inputs to a fresh cartridge."""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))

from src.toolchain.msx.build import destination
from src.toolchain.msx.emulator import reference_machine,tcl,scanout_recording_tcl
from src.toolchain.msx.hud_verify import symbols
from src.toolchain.msx.terrain_live import observer,analyze,camera_bounds
from src.toolchain.scenes.bundle import digest,verify_manifest
from src.toolchain.scenes.storage import require_ignored,json_write,seal


def verify_replay_rom(replay,rom):
    fingerprint=hashlib.sha1(rom.read_bytes()).hexdigest()
    snapshot=ET.fromstring(gzip.decompress(replay.read_bytes()))
    if fingerprint not in {node.text for node in snapshot.iter('resolvedSha1')}:
        raise ValueError('Replay does not contain the selected cartridge fingerprint')


def bind_replay_rom(replay,rom,target):
    """Relocate matching cartridge paths in a private copy; keep states intact.

    openMSX can warn and load a different ROM from an existing recorded path.
    Checking the saved hash alone therefore does not bind the loaded cartridge.
    """
    verify_replay_rom(replay,rom)
    fingerprint=hashlib.sha1(rom.read_bytes()).hexdigest()
    source=gzip.decompress(replay.read_bytes())
    snapshot=ET.fromstring(source)
    count=0
    for node in snapshot.iter('rom'):
        if node.findtext('resolvedSha1')!=fingerprint:continue
        for field in ('filename','resolvedFilename'):
            entry=node.find(field)
            if entry is not None:entry.text=str(rom.resolve())
        count+=1
    if not count:raise ValueError('Replay has no bindable cartridge references')
    # openMSX requires the original DOCTYPE/systemID, which ElementTree drops.
    prefix=source[:source.index(b'<serial')]
    target.write_bytes(gzip.compress(prefix+ET.tostring(snapshot,encoding='utf-8'),mtime=0))
    return dict(cartridge_references=count,rom_sha1=fingerprint,
                scope='Private replay copy with matching cartridge filenames relocated; snapshots, timing and inputs retained; source replay unchanged.')


def replay_keyboard(replay):
    """Extract keyboard timings for a fresh run, never edit replay snapshots."""
    snapshot=ET.fromstring(gzip.decompress(replay.read_bytes()))
    clock=3436363200
    end=int(snapshot.findtext('replay/currentTime/time'))/clock
    events=[]
    for node in snapshot.findall('replay/events/item'):
        if node.get('type')!='KeyMatrixState':continue
        time=int(node.findtext('StateChange/time/time'))/clock
        row,press,release=(int(node.findtext(n)) for n in ('row','press','release'))
        if not (0<=time<=end and 0<=row<16 and 0<=press<=255 and 0<=release<=255):
            raise ValueError('Invalid replay keyboard event')
        if events and time<events[-1][0]:raise ValueError('Unordered replay keyboard events')
        events.append((time,row,press,release))
    if not events:raise ValueError('Replay has no keyboard inputs')
    return end,events


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--replay',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--record',action='store_true',help='Also retain every actual raw scanout frame in scanout.avi')
    parser.add_argument('--require-map-bounds',action='store_true',help='Reject viewport exposure beyond the original maze border')
    parser.add_argument('--reapply-inputs',action='store_true',help='Apply only the saved keyboard timings to a fresh selected ROM; this is not deterministic replay validation')
    args=parser.parse_args();root=Path(__file__).resolve().parents[3]
    rom=args.rom.resolve();replay=args.replay.resolve();verify_manifest(rom.parent)
    if not args.reapply_inputs:verify_replay_rom(replay,rom)
    end,events=replay_keyboard(replay) if args.reapply_inputs else (None,[])
    s=symbols(rom.parent/'raster-scroll.sym');out=destination(root,args.output)
    require_ignored(root,[out/'terrain-latch.bin']);out.mkdir(parents=True)
    binding=None;playback=replay
    if not args.reapply_inputs:
        playback=out/'bound-input.omr'
        binding=bind_replay_rom(replay,rom,playback)
    lines=['set save_settings_on_exit false',f'set renderer {"SDLGL-PP" if args.record else "none"}','set sound_driver null',
        'set z80_freq 3579545','set z80_freq_locked true',
        'set gamma 1','set brightness 0','set contrast 0','set blur 0','set noise 0','set scanline 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),
        *([f'cart {tcl(rom)} -romtype ASCII16','set firmwareswitch off','reset'] if args.reapply_inputs else
          [f'reverse loadreplay -goto begin -viewonly {tcl(playback)}']),
        'set nr_loaded_cartridge 0;foreach device [machine_info device] {',
        ' set nr_device_info [machine_info device $device]',
        f' if {{[dict exists $nr_device_info actualSHA1] && [dict get $nr_device_info actualSHA1] eq "{hashlib.sha1(rom.read_bytes()).hexdigest()}"}} {{set nr_loaded_cartridge 1}}',
        '};if {!$nr_loaded_cartridge} {error "Loaded replay cartridge does not match the selected ROM"}',
        'set throttle off',
        *[f'after time {time:.10f} {{'+(';'.join(f'keymatrix{direction} {row} {mask}' for direction,mask in [('down',press),('up',release)] if mask))+'}' for time,row,press,release in events],
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
        f'set end {end:.10f}' if args.reapply_inputs else 'set end [dict get [reverse status] end]',
        *([f'after time 90 {{screenshot -raw {tcl(out/"camera-90.png")}}}'] if args.record else []),
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
    if 'has changed since the time this savestate was created' in (out/'emulator.log').read_text():
        raise ValueError('Replay loaded changed ROM content; reject these observations')
    terrain=analyze(root,rom.parent,out/'terrain-latch.bin')
    latches,mode_failures=map(int,(out/'counts.txt').read_text().split())
    bounds=camera_bounds(out/'terrain-latch.bin')
    report=dict(rom_sha256=digest(rom),replay_sha256=digest(replay),latches=latches,
        mode_failures=mode_failures,terrain=terrain,scanout_recorded=args.record,
        reapplied_keyboard_events=len(events),
        replay_cartridge_binding=binding,
        camera_bounds=bounds,
        passed=terrain['passed'] and mode_failures==0 and (not args.require_map_bounds or bounds['passed']),
        scope=('Fresh ROM with keyboard timings extracted from the saved session; execution can diverge from the original. No guest RAM writes. ' if args.reapply_inputs else 'Saved human-input replay, no new gameplay inputs or RAM writes. ')+
              'Original scenery grid and actual maze-mode/scroll registers at the physical latch. Not every pixel or continuous scanout.')
    json_write(out/'report.json',report);seal(out)
    if not report['passed']:raise ValueError(f'Human replay exposed a video mismatch: {out}/report.json')
    print(f'Human replay terrain/mode checks pass: {out}/report.json')


if __name__=='__main__':main()
