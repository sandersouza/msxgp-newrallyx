#!/usr/bin/env python3
"""Exercise two-player credit, alternating deaths and game over through keys."""
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
from scripts.msx.completion_route_verify import verify_header_reservations
from scripts.scenes.bundle import digest, verify_manifest, read_json
from scripts.scenes.storage import json_write, require_ignored, seal
from scripts.graphics.roms import input_records,load_metadata,validate_roms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bios', type=Path, default=Path('references/msxbios'))
    parser.add_argument('--reference',type=Path,default=Path('references/build/issue12-original-session-v3'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    bundle = args.rom.resolve().parent
    verify_manifest(bundle)
    syms=symbols(bundle/'raster-scroll.sym')
    verify_manifest(args.reference)
    original=read_json(args.reference/'report.json')
    if original.get('guest_state_writes') is not False or original.get('rejected_insufficient_credits') is not True:
        raise ValueError('Expected unmodified original credit/turn acquisition')
    if (original.get('script_sha256')!=digest(root/'scripts/msx/session_inventory.lua') or
            original.get('roms')!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())) or
            '[LUA ERROR]' in (args.reference/'mame.log').read_text()):
        raise ValueError('Original lifecycle provenance differs from verified acquisition')
    out = destination(root, args.output)
    require_ignored(root, [out/'events.tsv'])
    out.mkdir(parents=True)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off',
        'set throttle off', 'set z80_freq 3579545', 'set z80_freq_locked true',
        'set cmdtiming real', 'set limitsprites true',
        'activate_input_layer -blocking full_session',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16', 'reset',
        f'set out {tcl(out)}']
    script = r'''
set events [open [file join $out events.tsv] w]
set headers [open [file join $out headers.tsv] w]
set phase boot;set age 0;set frames 0;set skip 0;set turns 0;set previous -1
proc step {} {
    incr ::age
    set state [debug read memory 0xc7d0]
    switch $::phase {
        boot {if {$state==1 && [debug read memory 0xc7dd]} {
            keymatrixdown 0 4;set ::phase reject;set ::age 0
        }}
        reject {if {$::age==4} {
            if {$state!=1} {error "Two-player start accepted without credits"}
            keymatrixup 0 4;keymatrixdown 0 32;set ::phase coin1;set ::age 0
        }}
        coin1 {if {$::age==4} {keymatrixup 0 32;set ::phase release1;set ::age 0}}
        release1 {if {$::age==4} {keymatrixdown 0 4;set ::phase reject1;set ::age 0}}
        reject1 {if {$::age==4} {
            if {$state!=6 || [debug read memory 0xc7d2]!=1} {error "Two-player credit rule diverged"}
            keymatrixup 0 4;keymatrixdown 0 32;set ::phase coin2;set ::age 0
        }}
        coin2 {if {$::age==4} {keymatrixup 0 32;set ::phase release2;set ::age 0}}
        release2 {if {$::age==4} {keymatrixdown 0 4;set ::phase start;set ::age 0}}
        start {
            if {$::age==4} {keymatrixup 0 4}
            if {$state==0} {
                if {[debug read memory 0xc7eb]!=2 || [debug read memory 0xc7d2]!=0} {error "Two-player start state diverged"}
                set ::phase game;set ::skip 5
            }
        }
        game {
            incr ::frames
            if {$::skip} {incr ::skip -1}
            if {$state==2} {
                if {$::turns!=6 || [debug read memory 0xe00f]!=0 || [debug read memory 0xd238]!=0} {error "Final two-player lives/turns diverged"}
                close $::events;close $::headers;exit 0
            }
        }
    }
    after time 0.02 poll
}
debug set_watchpoint write_mem 0xc03c {$::phase eq "game" && !$::skip && $wp_last_value in {2 4}} {
    puts $::headers "$wp_last_value $::frames session [machine_info time] 0 0"
}
debug set_watchpoint write_mem 0xc7d0 {$wp_last_value==4} {
    puts $::headers "0 $::frames reload [machine_info time] 1 0";set ::skip 5
}
proc poll {} {if {[catch {step} p]} {puts stderr $p;exit 2}}
set VDP.too_fast_vram_access_callback {puts stderr "Session VRAM timing violation";exit 2}
after time 850 {puts stderr "Two-player natural session timeout";exit 2}
after time 0.02 poll
'''
    script+=f'''\n# Observe completed foreground boundaries, never a partially swapped player.
debug set_bp {syms['main']} {{$::phase eq "game" && [debug read memory 0xc7d0]==0 && ![debug read memory 0xc5c1]}} {{
 set player [debug read memory 0xc7ec]
 if {{$player!=$::previous}} {{
  incr ::turns
  puts $::events "$::frames $player [debug read memory 0xe00f] [debug read memory 0xd238] [debug read memory 0xe1b0]"
  set ::previous $player
 }}
}}
'''
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+
        '\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True,
            timeout=240, stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    turns = [list(map(int, row.split())) for row in (out/'events.tsv').read_text().splitlines()]
    if [row[1] for row in turns] != [0, 1, 0, 1, 0, 1]:
        raise ValueError('Missing original two-player turn sequence')
    for native,source in zip(turns,original['turns'],strict=True):
        player=native[1]
        lives=native[2:4] if player==0 else native[2:4][::-1]
        if source[1]!=player or source[2:4]!=lives or source[4+player]!=native[4]:
            raise ValueError('Native selected player/lives/round differ from real original lifecycle')
    headers = verify_header_reservations(out/'headers.tsv', 313*228/3579545)
    verify_manifest(bundle)
    verify_manifest(args.reference)
    json_write(out/'report.json', dict(rom_sha256=digest(args.rom), turns=turns,
        original_manifest_sha256=digest(args.reference/'manifest.json'),
        header_reservations=headers, scope='Real two-player credit/start and six natural enemy deaths; selected player/lives/round match real unmodified original lifecycle. No guest-state writes.'))
    require_ignored(root, [p for p in out.rglob('*') if p.is_file()])
    seal(out)
    print(f'Two-player natural session passes: {out}/report.json')


if __name__ == '__main__':
    main()
