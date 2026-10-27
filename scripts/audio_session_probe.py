#!/usr/bin/env python3
"""Check real keyboard title/select/start audio ordering and a debug round load."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine, tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    rom = args.rom.resolve(); verify_manifest(rom.parent)
    s = symbols(rom.parent/'raster-scroll.sym')
    if not s.get('AUDIO_ENABLED'): raise ValueError('Audio-enabled ROM required')
    out = destination(root, args.output); require_ignored(root, [out/'audio.tsv']); out.mkdir(parents=True)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
        'set throttle off', 'set z80_freq 3579545', 'set z80_freq_locked false',
        'set cmdtiming real', 'set limitsprites true',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off',
        'activate_input_layer -blocking audio_session', f'cart {tcl(rom)} -romtype ASCII16', 'reset',
        f'set out {tcl(out)}', 'set phase boot;set age 0;set game_time 0',
        'set audio [open [file join $out audio.tsv] w]',
        'proc poll {} {',
        ' incr ::age;set state [debug read memory 0xc7d0]',
        ' switch $::phase {',
        ' boot {if {$state==1 && [debug read memory 0xc7dd]} {set ::phase title;set ::age 0}}',
        ' title {if {$::age==200} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}',
        ' coin {if {$::age==5} {keymatrixup 0 32;set ::phase select;set ::age 0}}',
        ' select {if {$::age==200} {keymatrixdown 0 2;set ::phase start;set ::age 0}}',
        ' start {if {$::age==5} {keymatrixup 0 2};if {$state==0} {set ::phase game;set ::age 0;set ::game_time [machine_info time]}}',
        ' game {if {$::age==150} {keymatrixdown 7 2;set ::phase advance;set ::age 0}}',
        ' advance {if {$::age==5} {keymatrixup 7 2};if {$::age>=200 && $state==0 && [debug read memory 0xe1b0]>=3} {set ::phase continued;set ::age 0}}',
        ' continued {if {$::age==100} {close $::audio;exit 0}}',
        ' };after time .01 poll', '}',
        f'debug set_bp {s["Audio_WorkReturn"]} {{[info exists ::phase] && $::phase ne "boot"}} {{',
        f' puts $::audio "[machine_info time] $::phase [debug read memory {s["Session_State"]}] [debug read memory {s["Audio_MusicMode"]}] [debug read {{PSG regs}} 8] [debug read {{PSG regs}} 9] [debug read memory 0xe1b0]"',
        '}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Session audio VDP timing violation";exit 2}',
        'after time 60 {puts stderr "Session audio timeout";exit 2}', 'after time .01 poll']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, timeout=120,
            stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    rows = [line.split() for line in (out/'audio.tsv').read_text().splitlines()]
    quiet = [r for r in rows if r[1] in ('title', 'coin', 'select')]
    intro = [r for r in rows if int(r[2]) == 5 and int(r[3]) == 3]
    game = [r for r in rows if r[1] in ('game', 'advance', 'continued') and int(r[2]) == 0]
    if len(quiet) < 90 or any(int(r[3]) or int(r[4]) or int(r[5]) for r in quiet):
        raise ValueError('Insert-coin/player-select leaked music')
    if not intro or not game or any(int(r[3]) == 3 for r in game):
        raise ValueError('Start cue did not stay before gameplay')
    duration = float(intro[-1][0])-float(intro[0][0])+2/59.9227434
    expected = (rom.parent/'audio-intro-frames.bin').stat().st_size/6*2/59.9227434
    if abs(duration-expected) > .1 or not any(int(r[4]) and int(r[5]) for r in intro):
        raise ValueError('Start cue was missing, silent or played at the wrong tempo')
    if max(int(r[6]) for r in game) < 3 or not any(int(r[3]) == 1 for r in game):
        raise ValueError('Gameplay music/debug round continuation missing')
    json_write(out/'report.json', dict(passed=True, rom_sha256=digest(rom),
        quiet_ui_packets=len(quiet), start_cue_seconds=duration, gameplay_packets=len(game),
        scope='Actual keyboard coin/start/F5, factory CPU, full HUD and real IRQs. '
              'Title/select have no music; start cue finishes before gameplay, and phase loading does not replay it. '
              'Register timing/order qualification, not a human listening verdict.'))
    require_ignored(root, [f for f in out.rglob('*') if f.is_file()]); seal(out)
    print(f'Session audio ordering passes: {out}/report.json')


if __name__ == '__main__': main()
