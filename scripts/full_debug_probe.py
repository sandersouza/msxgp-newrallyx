#!/usr/bin/env python3
"""Exercise the real F5 debug key, held-key protection and normal preparation."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest,verify_manifest,load_assets
from scripts.scenes.storage import require_ignored,json_write,seal
from scripts.full_game_probe import check_header


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    s=symbols(bundle/'raster-scroll.sym');rom=args.rom.read_bytes()
    end=s['Full_Div3']-1
    if rom[end-0x4000]!=0xc9:raise ValueError('Expected next-round return before Full_Div3')
    out=destination(root,args.output);require_ignored(root,[out/'events.tsv']);out.mkdir(parents=True)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set cmdtiming real','set limitsprites true','activate_input_layer -blocking debug_probe',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set phase boot;set age 0;set skips 0;set target 0;set loaded 0',
        'set events [open [file join $out events.tsv] w]',
        'proc preserved {} {return [list [debug read_block memory 0xe0a0 8] [debug read_block memory 0xe060 8] [debug read memory 0xe00f] [debug read memory 0xc7d2] [debug read memory 0xc7ec] [debug read_block memory 0xd230 120]]}',
        'proc f5 {down} {if {$down} {keymatrixdown 7 2} else {keymatrixup 7 2}}',
        'proc step {} {',
        ' incr ::age;set state [debug read memory 0xc7d0]',
        ' switch $::phase {',
        ' boot {if {$state==1 && [debug read memory 0xc7dd]} {f5 1;set ::phase ui_hold;set ::age 0}}',
        ' ui_hold {if {$::age==10} {if {$state!=1 || $::skips} {error "F5 advanced title"};keymatrixdown 0 32;set ::phase coin;set ::age 0}}',
        ' coin {if {$::age==4} {keymatrixup 0 32;set ::phase release_coin;set ::age 0}}',
        ' release_coin {if {$::age==4} {keymatrixdown 0 2;set ::phase start;set ::age 0}}',
        ' start {if {$::age==4} {keymatrixup 0 2};if {$state==0} {set ::phase held_start;set ::age 0}}',
        ' held_start {if {$::age==20} {if {[debug read memory 0xe1b0]!=2 || $::skips} {error "Held title F5 leaked into gameplay"};f5 0;set ::phase release;set ::age 0}}',
        ' release {if {$::age==5} {set ::target [expr {$::skips+1}];f5 1;set ::phase skip_hold;set ::age 0;set ::loaded 0}}',
        ' skip_hold {if {$::loaded} {set ::phase post_hold;set ::age 0}}',
        ' post_hold {if {$::age==20} {',
        '  if {$::skips!=$::target || [debug read memory 0xe1b0]!=$::skips+2} {error "Held F5 repeated an advance"}',
        '  f5 0',
        '  if {$::skips==4} {if {[debug read memory 0xc009]} {error "Debug advance retained pause"};close $::events;exit 0}',
        '  if {$::skips==3} {keymatrixdown 4 32;set ::phase pause;set ::age 0} else {set ::phase release;set ::age 0}',
        ' }}',
        ' pause {if {$::age==4} {keymatrixup 4 32};if {$::age==8} {if {![debug read memory 0xc009]} {error "Pause was not entered"};set ::phase release;set ::age 0}}',
        ' }',' after time 0.02 poll','}',
        'proc poll {} {if {[catch step error]} {puts stderr $error;exit 2}}',
        f'debug set_bp {s["Full_NextRound"]} {{[info exists ::phase] && $::phase eq "skip_hold"}} {{',
        ' set ::saved [preserved];set ::round_before [debug read memory 0xe1b0];set ::sp_before [reg SP]',
        '}',
        f'debug set_bp {end} {{[info exists ::saved]}} {{',
        ' if {[preserved] ne $::saved || [reg SP]!=$::sp_before} {error "F5 changed score, record, lives, credits, player, inactive board or stack"}',
        ' if {[debug read memory 0xe1b0]!=$::round_before+1 || [debug read memory 0xc50b] || [debug read memory 0xc724]} {error "Debug round preparation differs"}',
        ' incr ::skips;set ::loaded 1',
        ' puts $::events "$::skips $::round_before [debug read memory 0xe1b0] [machine_info time]"',
        ' foreach {ext device start size} {state memory 49152 12288 vram VRAM 0 131072} {set f [open [file join $::out "$::skips.$ext"] wb];puts -nonewline $f [debug read_block $device $start $size];close $f}',
        ' unset ::saved','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Debug control VDP timing violation";exit 2}',
        'after time 120 {puts stderr "Debug key timeout";exit 2}','after time 0.02 poll']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} error]} {puts stderr $error;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=120,
                       stdout=log,stderr=subprocess.STDOUT,
                       env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    events=[line.split() for line in (out/'events.tsv').read_text().splitlines()]
    if len(events)!=4:raise ValueError('Expected four real F5 presses')
    assets=load_assets(root/'references/assets/nrallyx');palette=(bundle/'palette.bin').read_bytes()
    for i in range(1,5):check_header((out/f'{i}.state').read_bytes(),(out/f'{i}.vram').read_bytes(),assets,palette)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),advances=events,
        held_key_and_title_gate=True,score_lives_credits_inactive_player_preserved=True,
        pause_resumed=True,compact_header_verified=True,
        scope='Real credit/start/F5/P matrix inputs, no guest-state writes; four next-round preparations including challenge entry/exit, one advance per press and native packet preservation.'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Four F5 advances and compact HUD pass: {out}/report.json')


if __name__=='__main__':main()
