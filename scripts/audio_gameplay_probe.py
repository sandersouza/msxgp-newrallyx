#!/usr/bin/env python3
"""Replay identical logical inputs in live HUD gameplay, with sound on/muted."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1]
    rom=args.rom.resolve();verify_manifest(rom.parent);s=symbols(rom.parent/'raster-scroll.sym')
    if not s.get('AUDIO_ENABLED'):raise ValueError('Live mute replay requires audio')
    out=destination(root,args.output);require_ignored(root,[out/'on/game.bin']);out.mkdir(parents=True)
    for mute in (0,1):
        case=out/('muted' if mute else 'on');case.mkdir()
        lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
            'set throttle off','set z80_freq 3579545','set z80_freq_locked true',
            'set cmdtiming real','set limitsprites true',
            f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
            reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',
            'activate_input_layer -blocking audio_replay',f'cart {tcl(rom)} -romtype ASCII16','reset',
            f'set out {tcl(case)};set replay_mute {mute};set phase boot;set age 0;set step 0',
            'set result [open [file join $out game.bin] wb]',
            'proc poll {} {',
            ' incr ::age;set state [debug read memory 0xc7d0]',
            ' switch $::phase {',
            ' boot {if {$state==1 && [debug read memory 0xc7dd]} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}',
            ' coin {if {$::age==4} {keymatrixup 0 32;set ::phase release;set ::age 0}}',
            ' release {if {$::age==4} {keymatrixdown 0 2;set ::phase start;set ::age 0}}',
            f' start {{if {{$::age==4}} {{keymatrixup 0 2}};if {{$state==0}} {{debug write memory {s["Audio_Mute"]} $::replay_mute;set ::phase game}}}}',
            ' }',
            ' if {$::phase ne "game"} {after time .01 poll}',
            '}',
            f'debug set_bp {s["Player_Input"]} {{$::phase eq "game"}} {{',
            ' incr ::step;set direction [lindex {0 1 2 3 0} [expr {min(4,$::step/120)}]]',
            ' lassign [lindex {{0 255} {1 0} {0 1} {255 0}} $direction] dx dy',
            f' debug write memory {s["dx"]} $dx;debug write memory {s["dy"]} $dy;debug write memory {s["Smoke_Key"]} [expr {{$::step%180<8}}]',
            '}',
            f'debug set_bp {s["Player_CountTick"]} {{$::phase eq "game"}} {{',
            ' puts -nonewline $::result [debug read_block memory 0xe000 768]',
            ' puts -nonewline $::result [debug read_block memory 0xc711 2]',
            ' if {$::step==600} {close $::result;exit 0}',
            '}',
            'set VDP.too_fast_vram_access_callback {puts stderr "Live audio replay VDP timing violation";exit 2}',
            'after time 120 {puts stderr "Live audio replay timeout/game over";exit 2}',
            'after time .01 poll']
        (case/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
        with (case/'emulator.log').open('w') as log:
            subprocess.run(['openmsx','-script',str(case/'session.tcl')],check=True,timeout=120,
                stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ,OPENMSX_HOME=str(case/'home'),OPENMSX_USER_DATA=str(case/'userdata')))
    on=(out/'on/game.bin').read_bytes();muted=(out/'muted/game.bin').read_bytes()
    if len(on)!=600*770 or on!=muted:
        at=next((i for i,(a,b) in enumerate(zip(on,muted)) if a!=b),min(len(on),len(muted)))
        raise ValueError(f'Live mute gameplay differs: tick {at//770+1}, byte {at%770}')
    verify_manifest(rom.parent)
    json_write(out/'report.json',dict(rom_sha256=digest(rom),logical_ticks=600,passed=True,
        scope='Live full-HUD factory-clock gameplay with real keyboard credit/start. A deterministic logical input fixture '
              'overrides direction/smoke at each Player_Input entry; all 768 selected native gameplay bytes '
              '(score/fuel/lives/PRNG/enemy/player/round state) and the smoke-placement count agree at every tick '
              'with output enabled/muted. No render/audio-output state is compared; broader natural routes are separate gates.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'600 live gameplay ticks agree with sound on/muted: {out}/report.json')


if __name__=='__main__':main()
