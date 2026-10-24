#!/usr/bin/env python3
"""Seed distinct player boards, then execute real death/restore transitions.

These are explicit component fixtures, separate from the no-write session replay.
"""
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
from scripts.msx.round_prepare_verify import relocated_seed
from scripts.msx.stage_one import acquire
from scripts.msx.player import padded_world
from scripts.msx.player_verify import check_cache
from scripts.full_game_probe import world, check_header
from scripts.scenes.bundle import digest, verify_manifest, load_assets
from scripts.scenes.storage import json_write, require_ignored, seal
from scripts.msx.screen5 import packed
from scripts.msx.sprite_lives import digit_masks, digit_bitmap
from scripts.msx.raster_scroll import sprite_pattern


def packet(value):
    digits=bytes(map(int,f'{value:08d}'))
    return digits[4:]+digits[:4]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=Path('references/build/issue12-round-inventory-v13'))
    args=p.parse_args();root=Path(__file__).resolve().parents[1]
    bundle=args.rom.resolve().parent;verify_manifest(bundle);verify_manifest(args.reference)
    out=destination(root,args.output);require_ignored(root,[out/'p1.bin']);out.mkdir(parents=True)
    fields=[*range(0xa0,0xa8),0x0f,0x1b0,0x1b2,0x271,0x251,*range(0x1c8,0x228)]
    expected=[]
    for i,(round_,score,lives,collected) in enumerate(((2,12340,2,3),(6,54320,1,5)),1):
        state=bytearray(relocated_seed((args.reference/f'case-{round_:03d}-video.bin').read_bytes()))
        state[0xa0:0xa8]=packet(score);state[0xf]=lives;state[0x271]=collected;state[0x1b2]=i
        active=bytes([0]*collected+[1]*(10-collected))
        payload=bytes(state[at] for at in fields)+active+b'\0'
        assert len(payload)==120
        (out/f'p{i}.bin').write_bytes(payload);expected.append((state,active,payload))
    syms=symbols(bundle/'raster-scroll.sym')
    hud_cases=[]
    for n,(value,round_,lives) in enumerate(zip(
            (0,90,999990,1000000,99999990,99999999,12345678),
            (1,9,10,99,100,254,255),(0,1,2,9,10,254,255))):
        for player in (0,1):hud_cases.append((value,99999999,round_,lives,player))
    (out/'hud.bin').write_bytes(b''.join(packet(score)+packet(high)+bytes((round_,lives,player))
                                        for score,high,round_,lives,player in hud_cases))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked true','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set phase boot;set age 0;set count 0;set seeded 0',
        f'set fields {{{" ".join(str(0xe000+at) for at in fields)} {" ".join(str(syms["Flag_Active"]+i) for i in range(1,11))} {syms["Full_NewBoard"]}}}']
    script=r'''
proc readfile {name} {set f [open [file join $::out $name] rb];set d [read $f];close $f;return $d}
proc seed {} {
    binary scan [readfile p1.bin] cu* values
    foreach at $::fields value $values {debug write memory $at $value}
    debug write_block memory 0xd230 [readfile p2.bin]
    debug write memory @PLAYERS@ 2;debug write memory @PLAYER@ 0
    set ::seeded 1
}
proc death {} {
    debug write memory @DEATH@ 2;debug write memory @JOBS@ 0;debug write memory @LIFE@ 0
}
proc step {} {
    incr ::age
    set state [debug read memory 0xc7d0]
    switch $::phase {
        boot {if {$state==1 && [debug read memory 0xc7dd]} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}
        coin {if {$::age==4} {keymatrixup 0 32;set ::phase release;set ::age 0}}
        release {if {$::age==4} {keymatrixdown 0 2;set ::phase start;set ::age 0}}
        start {if {$::age==4} {keymatrixup 0 2};if {$state==0} {keymatrixdown 4 32;set ::phase pause;set ::age 0}}
        pause {
            if {$::age==4} {keymatrixup 4 32}
            if {[debug read memory 0xc009] && $::age>20} {seed;death;set ::phase capture;set ::age 0}
        }
        capture {if {$::age>=30 && [debug read memory @LIFE@]==0 && [debug read memory @PLAYER@]==(1-$::count)} {
            incr ::count
            foreach device {memory VRAM} suffix {state vram} start {49152 0} size {12288 131072} {
                set f [open [file join $::out "$::count.$suffix"] wb]
                puts -nonewline $f [debug read_block $device $start $size];close $f
            }
            if {$::count==2} {
                debug write memory @PLAYERS@ 1
                debug write memory 0xe1b0 4
                death;set ::phase challenge;set ::age 0
            } else {death;set ::age 0}
        }}
        challenge {if {$::age>30 && [debug read memory 0xe1b0]==5 && $state==0} {
            foreach device {memory VRAM} suffix {state vram} start {49152 0} size {12288 131072} {
                set f [open [file join $::out "challenge.$suffix"] wb]
                puts -nonewline $f [debug read_block $device $start $size];close $f
            }
            set ::huddata [readfile hud.bin];set ::hudindex 0;set ::phase hud_seed
        }}
        hud_wait {if {$::age>24} {
            foreach device {memory VRAM} suffix {state vram} start {49152 0} size {12288 131072} {
                set f [open [file join $::out "hud-$::hudindex.$suffix"] wb]
                puts -nonewline $f [debug read_block $device $start $size];close $f
            }
            incr ::hudindex
            if {$::hudindex==[string length $::huddata]/19} {exit 0}
            set ::phase hud_seed
        }}
    }
    after time 0.02 poll
}
proc poll {} {if {[catch {step} p]} {puts stderr $p;exit 2}}
set VDP.too_fast_vram_access_callback {puts stderr "State transition VRAM timing violation";exit 2}
after time 120 {puts stderr "State transition timeout";exit 2}
after time 0.02 poll
debug set_bp @MAIN@ {$::phase eq "hud_seed"} {
    set entry [string range $::huddata [expr {$::hudindex*19}] [expr {$::hudindex*19+18}]]
    debug write_block memory 0xe0a0 [string range $entry 0 7]
    debug write_block memory 0xe060 [string range $entry 8 15]
    binary scan [string range $entry 16 18] cu* values
    lassign $values round lives player
    debug write memory 0xe1b0 [expr {($round+1)&255}]
    debug write memory 0xe00f $lives
    debug write memory @PLAYER@ $player
    set ::savedsp [reg SP]
    set code [list 251 205 @SCORELO@ @SCOREHI@ 205 @LIFELO@ @LIFEHI@ 62 [expr {$player+1}] 205 @LABELLO@ @LABELHI@ 62 @BANK@ 50 0 112 205 21 184 195 112 209]
    set at 0xd150;foreach byte $code {debug write memory $at $byte;incr at}
    reg PC 0xd150;set ::phase hud_call
}
debug set_bp 0xd170 {$::phase eq "hud_call"} {
    if {[reg SP]!=$::savedsp} {error "HUD fixture changed stack"}
    reg PC @MAIN@;set ::phase hud_wait;set ::age 0
}
'''
    for key,name in [('PLAYERS','Full_Players'),('PLAYER','Full_Player'),('DEATH','Death_State'),('JOBS','Death_Jobs'),('LIFE','Life_State')]:
        script=script.replace('@'+key+'@',str(syms[name]))
    for key,name in [('SCORE','Score_Publish'),('LIFE','Life_Publish'),('LABEL','HUD_SetPlayerNumber')]:
        script=script.replace('@'+key+'LO@',str(syms[name]&255)).replace('@'+key+'HI@',str(syms[name]>>8))
    script=script.replace('@MAIN@',str(syms['main'])).replace('@BANK@',str(syms['SESSION_BANK']))
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    program,_=acquire(root);assets=load_assets(root/'references/assets/nrallyx')
    palette=(bundle/'palette.bin').read_bytes()
    checks=[]
    for n,player in ((1,1),(2,0)):
        state=(out/f'{n}.state').read_bytes();vram=(out/f'{n}.vram').read_bytes()
        seed,active,payload=expected[player]
        for at in fields:
            if state[0x2000+at]!=seed[at]:raise ValueError(f'Player {player+1} field {at:04x} diverged')
        if state[syms['Full_Player']-0xc000]!=player:raise ValueError('Incorrect restored player')
        if state[0x228f]!=seed[0x28f]:raise ValueError('Restored map does not belong to selected player')
        if state[syms['Full_Layout']-0xc000]!=(seed[0x28f]&3):raise ValueError('Renderer bank metadata belongs to previous player')
        if state[0x2250]!=0 or state[0x226b]!=60:raise ValueError('Life reset did not refill fuel/reset ordinal')
        actual_active=state[syms['Flag_Active']-0xc000+1:syms['Flag_Active']-0xc000+11]
        if actual_active!=active:raise ValueError('Collected flag ownership was lost')
        check_header(state,vram,assets,palette)
        data,width,_=padded_world(world(program,state[0x2000:],b'\0'+active,assets,palette))
        wx=int.from_bytes(state[0xb0:0xb2],'little');wy=int.from_bytes(state[0xb2:0xb4],'little')
        check_cache(vram,packed(data),width,wx,wy,n)
        checks.append(dict(player=player+1,round=seed[0x1b0]-1,partial_flags=seed[0x271],map=seed[0x28f]&3))
    state=(out/'challenge.state').read_bytes();vram=(out/'challenge.vram').read_bytes()
    if state[0x21b0]!=5 or state[0x2271]!=0 or state[0x2250]!=0 or state[0x226b]!=60:
        raise ValueError('Failed challenge did not advance/reset the original next board')
    if state[0x20a0:0x20a8]!=expected[0][0][0xa0:0xa8] or state[0x200f]!=2:
        raise ValueError('Challenge failure lost surviving player score/lives')
    check_header(state,vram,assets,palette)
    for n,(score,high,round_,lives,player) in enumerate(hud_cases):
        state=(out/f'hud-{n}.state').read_bytes();vram=(out/f'hud-{n}.vram').read_bytes()
        check_header(state,vram,assets,palette)
        value=min(9,max(0,lives-1))
        mask=sprite_pattern(digit_bitmap(digit_masks(assets),value))
        # Dynamic digit occupies COUNT_PATTERN (172) and its shifted alternative.
        if vram[0x1f800+172*8:0x1f800+172*8+32]!=mask:
            raise ValueError(f'Original life glyph differs for native count {lives}')
    verify_manifest(bundle);verify_manifest(args.reference)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),checks=checks,hud_boundary_cases=len(hud_cases),
        challenge_failure=True,
        scope='Explicit partial-board/challenge/HUD fixtures; real death dispatch, two restores, exact selected native fields, map banks, cache, full header and original life digits. Round 255 is presentation-only.'))
    require_ignored(root,[x for x in out.rglob('*') if x.is_file()]);seal(out)
    print(f'Per-player partial-board restoration passes: {out}/report.json')


if __name__=='__main__':main()
