#!/usr/bin/env python3
"""Exercise typed cast, credit selection, Start, pause and challenge presentation."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.emulator import reference_machine,tcl,scanout_recording_tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.attract import cast
from scripts.msx.screen5 import packed
from scripts.scenes.bundle import digest,verify_manifest,load_assets,read_json
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path.cwd();rom=args.rom.resolve();verify_manifest(rom.parent)
    s=symbols(rom.parent/'raster-scroll.sym');out=args.output.resolve()
    require_ignored(root,[out/'session.tcl']);out.mkdir(parents=True)
    lines=['set save_settings_on_exit false','set renderer SDLGL-PP','set sound_driver null','set throttle off',
        'set gamma 1','set brightness 0','set contrast 0','set blur 0','set noise 0','set scanline 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','set limitsprites true','set cmdtiming real',
        'set z80_freq 3579545','set z80_freq_locked true',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',f'cart {tcl(rom)} -romtype ASCII16','reset',
        f'set out {tcl(out)}',scanout_recording_tcl(out,s['startup_mode'])]
    script=r'''
set nr_ui_phase boot;set nr_ui_age 0;set nr_ui_samples 0;set nr_ui_intro_parts 0
set nr_ui_events [open [file join $out events.tsv] w]
proc u16 {at} {expr {[debug read memory $at]+256*[debug read memory [expr {$at+1}]]}}
proc snapshot {name} {
 foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] regs [debug read_block {VDP regs} 0 64]] {
  set f [open [file join $::out "$name.$ext"] wb];puts -nonewline $f $data;close $f
 }
 after time 0.025 [list screenshot -raw [file join $::out "$name.png"]]
 puts $::nr_ui_events "$name [machine_info time]"
}
proc step {} {
 incr ::nr_ui_age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 set mode [debug read memory @MUSICMODE@]
 if {$::nr_ui_phase ne "boot" && $state in {1 6} && $mode} {error "Waiting UI played music mode $mode"}
 switch $::nr_ui_phase {
  boot {if {$state==1 && $ready} {snapshot cast-initial;set ::nr_ui_phase cast;set ::nr_ui_age 0}}
  cast {
   if {$::nr_ui_age==100} {snapshot cast-partial}
   if {[debug read memory @CASTDONE@]} {snapshot cast-complete;set ::nr_ui_phase complete_hold;set ::nr_ui_age 0}
  }
  complete_hold {if {$::nr_ui_age==3} {keymatrixdown 0 32;set ::nr_ui_phase coin;set ::nr_ui_age 0}}
  coin {
   if {$::nr_ui_age==4} {keymatrixup 0 32}
   if {$::nr_ui_age>5 && $state==6 && $ready} {
    if {[debug read memory 0xc7d2]!=1} {error "One coin was lost or counted twice"}
    snapshot select-one;keymatrixdown 0 4;set ::nr_ui_phase denied;set ::nr_ui_age 0
   }
  }
  denied {
   if {$::nr_ui_age==4} {keymatrixup 0 4}
   if {$::nr_ui_age==12} {
    if {$state!=6 || [debug read memory 0xc7d2]!=1 || $mode} {error "Insufficient two-player start consumed credit or played Start"}
    keymatrixdown 0 32;set ::nr_ui_phase second;set ::nr_ui_age 0
   }
  }
  second {
   if {$::nr_ui_age==4} {keymatrixup 0 32}
   if {$::nr_ui_age>5 && [debug read memory 0xc7d2]==2} {snapshot select-two;keymatrixdown 0 4;set ::nr_ui_phase start;set ::nr_ui_age 0}
  }
  start {
   if {$::nr_ui_age==4} {keymatrixup 0 4}
   if {$state==5 && ![info exists ::nr_ui_start_time]} {set ::nr_ui_start_time [machine_info time];snapshot start-cue}
   if {$mode==3} {
    set n 0;foreach reg {8 9 10} {if {[debug read {PSG regs} $reg]} {incr n}}
    set ::nr_ui_intro_parts [expr {max($::nr_ui_intro_parts,$n)}]
   }
   if {$state==0} {
    if {![info exists ::nr_ui_start_time] || [debug read memory 0xc7eb]!=2 || [debug read memory 0xc7d2]!=0 || [debug read memory 0xc7ee]} {error "Human two-player start diverged"}
    set ::nr_ui_start_seconds [expr {$::nr_ui_start_end-$::nr_ui_start_time}]
    if {$::nr_ui_start_seconds<3.8 || $::nr_ui_start_seconds>4.4 || $::nr_ui_intro_parts!=3} {error "Start duration/three-part cue diverged: $::nr_ui_start_seconds parts=$::nr_ui_intro_parts"}
    snapshot gameplay;set ::nr_ui_phase driving;set ::nr_ui_age 0
   }
  }
  driving {if {$::nr_ui_age==30} {keymatrixdown 4 32;set ::nr_ui_phase pause;set ::nr_ui_age 0}}
  pause {
   if {$::nr_ui_age==4} {keymatrixup 4 32}
   if {$::nr_ui_age==10} {
    if {![debug read memory 0xc009]} {error "P did not pause"}
    foreach reg {8 9 10} {if {[debug read {PSG regs} $reg]} {error "Pause left physical PSG channel audible"}}
    set ::nr_ui_pause_cursor [debug read_block memory @MUSICPTR@ 3];snapshot paused
   }
   if {$::nr_ui_age>10 && $::nr_ui_age<60} {
    if {[debug read_block memory @MUSICPTR@ 3] ne $::nr_ui_pause_cursor} {error "Paused music cursor advanced"}
    foreach reg {8 9 10} {if {[debug read {PSG regs} $reg]} {error "Paused output resumed"}}
   }
   if {$::nr_ui_age==60} {keymatrixdown 4 32;set ::nr_ui_phase resume;set ::nr_ui_age 0}
  }
  resume {
   if {$::nr_ui_age==4} {keymatrixup 4 32}
   if {$::nr_ui_age==15} {
    if {[debug read memory 0xc009] || $mode!=1} {error "Music/gameplay did not resume"}
    snapshot resumed
    debug write memory 0xc724 1;debug write memory 0xe24b 0
    set ::nr_ui_phase settle;set ::nr_ui_age 0
   }
  }
  settle {
   if {$::nr_ui_age==5} {
    if {$mode || [debug read {PSG regs} 8] || [debug read {PSG regs} 9]} {error "Level settlement retained driving music"}
    snapshot settled;set ::nr_ui_phase next_challenge;set ::nr_ui_age 0
   }
  }
  next_challenge {
   if {$::nr_ui_age==3} {
    set ::nr_ui_preserved [list [debug read memory 0xe00f] [debug read memory 0xc7d2] [debug read memory 0xc7ec] [debug read_block memory 0xd230 120]]
    debug write memory 0xe1b0 3;debug write memory 0xc724 3
    set ::nr_ui_phase challenge;set ::nr_ui_age 0
   }
  }
  challenge {
   if {$state==7 && $ready && ![info exists ::nr_ui_challenge_time]} {snapshot challenge;set ::nr_ui_challenge_time [machine_info time]}
   if {$mode==6} {incr ::nr_ui_samples}
   if {[info exists ::nr_ui_challenge_time] && $state==0} {
    if {[debug read memory 0xe1b0]!=4 || $::nr_ui_samples<30} {error "Challenge introduction was absent or advanced twice"}
    set preserved [list [debug read memory 0xe00f] [debug read memory 0xc7d2] [debug read memory 0xc7ec] [debug read_block memory 0xd230 120]]
    if {$preserved ne $::nr_ui_preserved} {error "Challenge transition changed lives, credit, active player or inactive board"}
    if {[u16 0xe025] || [u16 0xe029]} {error "Challenge UI resume activated parked enemies"}
    set ::nr_ui_challenge_seconds [expr {$::nr_ui_challenge_end-$::nr_ui_challenge_time}]
    snapshot challenge-gameplay
    set ::nr_ui_phase finish;set ::nr_ui_age 0
   }
  }
  finish {
   if {$::nr_ui_age==3} {
    record stop;close $::nr_ui_events
    set f [open [file join $::out timing.txt] w];puts $f "$::nr_ui_start_seconds $::nr_ui_intro_parts $::nr_ui_challenge_seconds $::nr_ui_samples";close $f;exit 0
   }
  }
 }
 after time 0.02 poll
}
proc poll {} {if {[catch step p]} {puts stderr "$::nr_ui_phase: $p";exit 2}}
set VDP.too_fast_vram_access_callback {puts stderr "UI VRAM timing violation";exit 2}
after time 180 {puts stderr "Arcade UI probe timeout: $::nr_ui_phase";exit 2}
after time 0.02 poll
'''
    for key,label in [('MUSICMODE','Audio_MusicMode'),('MUSICPTR','Audio_MusicPointer'),
                      ('CASTDONE','Full_UICastDone')]:
        script=script.replace('@'+key+'@',str(s[label]))
    lines.extend([
        f'debug set_bp {s["Full_UIFrame.start_wait"]} {{[info exists ::nr_ui_start_time] && !([debug read memory 0xe9f5]&128) && ![info exists ::nr_ui_start_end]}} {{set ::nr_ui_start_end [machine_info time]}}',
        f'debug set_bp {s["Full_UIChallengeWait"]} {{[info exists ::nr_ui_challenge_time] && !([debug read memory 0xe9f5]&64) && ![info exists ::nr_ui_challenge_end]}} {{set ::nr_ui_challenge_end [machine_info time]}}',
    ])
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=150,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    def bitmap(name):return (out/f'{name}.vram').read_bytes()[0x10000:0x16a00]
    final,background=cast(root,(rom.parent/'palette.bin').read_bytes())
    if bitmap('cast-complete')!=packed(final):raise ValueError('Final cast differs from original 1:1 pixels')
    def count(data):return sum(v!=background for byte in data for v in (byte>>4,byte&15))
    if not count(bitmap('cast-initial'))<count(bitmap('cast-partial'))<count(bitmap('cast-complete')):
        raise ValueError('Cast did not reveal progressively')
    assets=load_assets(root/'references/assets/nrallyx')
    def check_text(name,text,x,y,color):
        data=bitmap(name)
        for i,char in enumerate(text):
            source=0x18 if char=='@' else int(char) if char.isdigit() else ord(char)
            glyph=assets.pixels['tiles'][source*64:(source+1)*64]
            for dy in range(8):
                for dx in range(8):
                    ink=char!=' ' and bool(assets.palette['lookup'][38*4+glyph[dy*8+dx]])
                    xx=x+i*8+dx;byte=data[(y+dy)*128+xx//2]
                    actual=byte&15 if xx&1 else byte>>4
                    if actual!=(color if ink else s['BLACK']):raise ValueError(f'{name} text/black background mismatch: {text}, {i},{dx},{dy}')
    for name in ('select-one','select-two'):
        if any(v not in (s['BLACK'],s['WHITE'],s['RED']) for b in bitmap(name) for v in (b>>4,b&15)):
            raise ValueError('Player selection is not a solid black screen with white/red text')
        check_text(name,'PUSH START BUTTON',60,48,s['WHITE'])
        check_text(name,'1ST BONUS FOR 20000 PTS',40,96,s['WHITE'])
        check_text(name,'2ND BONUS FOR 80000 PTS',40,112,s['WHITE'])
        check_text(name,'@ NAMCO 1981 2ST',64,176,s['RED'])
        check_text(name,'@ RETROWORK 2026',64,192,s['RED'])
    check_text('select-one','   1 PLAYER     ',64,72,s['WHITE'])
    check_text('select-two','1 OR 2 PLAYERS  ',64,72,s['WHITE'])
    timing=list(map(float,(out/'timing.txt').read_text().split()))
    expected_frames=len((rom.parent/'audio-challenge_intro-frames.bin').read_bytes())//9
    expected_seconds=expected_frames*2*read_json(rom.parent/'build.json')['timing']['frame_seconds']
    if abs(timing[2]-expected_seconds)>.35:raise ValueError(f'Challenge cue/hold differs from two original phrases: {timing[2]} / {expected_seconds}')
    json_write(out/'report.json',dict(rom_sha256=digest(rom),passed=True,start_seconds=timing[0],start_parts=timing[1],
        challenge_seconds=timing[2],challenge_expected_seconds=expected_seconds,
        scope='Actual keyboard cast/credit/denied-2P/accepted-2P/Start/pause/resume; original cast pixels, requested black-selection text, physical PSG mute and frozen music cursor. Settlement and impending challenge are explicitly seeded; lives/credit/active/inactive player preserved. Natural completion remains separate.'))
    seal(out);print(f'Arcade UI/audio transitions pass: {out}/report.json')


if __name__=='__main__':main()
