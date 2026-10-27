#!/usr/bin/env python3
"""Execute production music/noise scheduling, transient mailboxes and mute."""
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
from scripts.msx.audio_score import FRAME_BYTES as FRAME
from scripts.scenes.bundle import digest, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


SCENARIOS = ('background', 'intro', 'complete', 'challenge', 'effects', 'overflow', 'flag_adapter', 'smoke_adapter', 'gameover', 'gameover_adapter', 'late_clock', 'odd_clock', 'title', 'player_select', 'ui_transition')
STEPS = 900
STATE = 2560+768+64
STRIDE = STATE+14+2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    rom = args.rom.resolve(); verify_manifest(rom.parent)
    s = symbols(rom.parent/'raster-scroll.sym')
    if not s.get('AUDIO_ENABLED'): raise ValueError('Production probe requires audio')
    if 'Audio_ReadTone' not in s:raise ValueError('This probe requires the three-voice dictionary build')
    out = destination(root, args.output); require_ignored(root, [out/'result.bin']); out.mkdir(parents=True)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
        'set throttle off', 'set z80_freq 3579545', 'set z80_freq_locked false',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off',
        f'cart {tcl(rom)} -romtype ASCII16', 'reset', f'set out {tcl(out)}',
        'set started 0;set active 0;set index 0;set step 0',
        'set result [open [file join $out result.bin] wb];set costs [open [file join $out costs.tsv] w]',
        'proc begin_case {} {',
        f' if {{$::index=={len(SCENARIOS)*2}}} {{close $::result;close $::costs;exit 0;return}}',
        ' set ::step 0;set kind [expr {$::index/2}]',
        ' keymatrixup 7 1',
        ' debug write memory 0xc7d0 0;debug write memory 0xc7ee 0;debug write memory 0xc490 0;debug write memory 0xc5c0 0',
        ' if {$kind==1} {debug write memory 0xc7d0 5};if {$kind in {12 13}} {debug write memory 0xc7d0 1;debug write memory 0xc7d2 [expr {$kind==13?2:0}]}',
        ' debug write memory 0xc50b 0;debug write memory 0xc711 0;debug write memory 0xc00a 0',
        ' debug write_block memory 0xe000 $::native',
        ' debug write memory 0xe1b0 [expr {$kind==3?4:2}]',
        ' debug write memory 0xe9f4 64;debug write memory 0xe9f5 [expr {$kind==1?128:($kind==2?40:($kind==8?4:16))}];debug write memory 0xe9f6 0',
        ' debug write_block memory 0xd150 [string repeat [binary format c 0] 12]',
        ' debug write_block memory 0xe9a0 [string repeat [binary format c 0] 80]',
        ' debug write_block memory 0xe9b0 [string repeat [binary format c 255] 11]',
        ' debug write memory 0xe9cd 1',
        f' debug write memory {s["Audio_Mute"]} [expr {{$::index&1}}];debug write memory {s["Audio_NewScene"]} [expr {{$kind==1}}]',
        ' debug write_block $::mapper [expr {$::base+0x3800}] [string repeat [binary format c 0] 896]',
        ' debug write_block $::mapper [expr {$::base+0x3b20}] [string repeat [binary format c 255] 11]',
        ' if {$kind==5} {debug write memory 0xe9c0 8;debug write_block memory 0xe9e0 [binary format c* {1 2 3 4 5 6 7 8}]}',
        f' debug write memory {s["Full_CacheHeld"]} 0',
        ' if {$::expanded} {debug write memory 65535 $::sub}',
        ' debug write ioports 168 $::primary;debug write ioports 252 $::page',
        ' if {$kind&1} {',
        '  debug write ioports 252 $::cache',
        '  if {$::expanded} {debug write memory 65535 $::ram_sub}',
        '  debug write ioports 168 $::ram_primary',
        f'  debug write memory {s["Full_CacheHeld"]} 1',
        ' }',
        ' set ::expected_primary [debug read ioports 168];set ::expected_page [debug read ioports 252]',
        ' issue',
        '}',
        'proc issue {} {',
        f' if {{$::step=={STEPS}}} {{incr ::index;begin_case;return}}',
        ' set kind [expr {$::index/2}];set event 0;set credit 0',
        ' if {$kind==4 && $::step>=12 && $::step<=108 && $::step%12==0} {',
        '  set id [expr {$::step/12}];set event [lindex {0 2 16 32 1 0 4 8 128 0} $id];if {$id==5} {set credit 128};if {$id==9} {set credit 64}',
        ' }',
        ' if {$kind==5} {if {$::step==0} {set credit 64};if {$::step==2} {set event 128}}',
        ' if {$kind==5 && $::step==3} {set credit 64}',
        ' if {$kind==10} {set heading [expr {$::step/120%4}];debug write memory 0xe048 0;debug write memory 0xe06b [expr {$heading&1?0:255}];debug write memory 0xe06a [expr {$heading<2?2:254}]}',
        ' if {$kind==6 && $::step in {12 24 36}} {debug write memory 0xc50b [expr {$::step/12}];debug write memory 0xc50d [lindex {0 1 2 4} [expr {$::step/12}]]}',
        ' if {$kind==6 && $::step==100} {debug write memory 0xc50b 0}',
        ' if {$kind==7 && $::step in {12 24 36}} {debug write memory 0xc711 [expr {$::step/12}]}',
        ' if {$kind==9 && $::step==12} {debug write memory 0xc5c0 2}',
        ' if {$kind==14} {',
        '  if {$::step==12} {debug write memory 0xc7d0 1}',
        '  if {$::step==24} {debug write memory 0xc7d0 5;debug write memory 0xc490 1;debug write memory 0xe9f5 128}',
        f'  if {{$::step==270}} {{debug write memory 0xc7d0 0;debug write memory 0xc490 0;debug write memory 0xe9f5 144;debug write memory {s["Audio_NewScene"]} 1}}',
        ' }',
        ' debug write memory 0xe9f4 [expr {64|$event}];debug write memory 0xe9f6 $credit',
        ' if {$::step in {40 80}} {keymatrixdown 7 1};if {$::step in {45 85}} {keymatrixup 7 1}',
        f' debug write memory 0x7000 {s["PLAYER_BANK"]}',
        ' debug write memory 0xc00a [expr {([debug read memory 0xc00a]+($kind==10?4:($kind==11?3:2)))&255}]',
        f' set at 0xd140;foreach value {{243 205 {s["Audio_Work"]&255} {s["Audio_Work"]>>8} 243 195 95 209}} {{debug write memory $at $value;incr at}}',
        f' if {{$kind==9 && $::step==12}} {{set at 0xd140;foreach value {{243 205 {s["Session_Check"]&255} {s["Session_Check"]>>8} 205 {s["Audio_Work"]&255} {s["Audio_Work"]>>8} 243 195 95 209}} {{debug write memory $at $value;incr at}}}}',
        ' reg SP 0xf380;reg IX 0x4567;reg IY 0x6789;reg PC 0xd140;set ::active 1;set ::begin [machine_info time]',
        '}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;debug write {VDP regs} 0 6;debug write {VDP regs} 1 2',
        ' set ::primary [debug read ioports 168];set ::page [debug read ioports 252]',
        ' set ::native [debug read_block memory 0xe000 2560];set ::code [debug read_block memory 0xea00 1536];set ::vram [debug read_block VRAM 0 131072];set ::io [debug read_block {PSG regs} 14 2]',
        *[f' set ::{name} [debug read memory {s[label]}]' for name,label in (
            ('cache','Full_CacheSegment'),('expanded','Full_CacheExpanded'),('sub','Full_CacheSub'),
            ('ram_sub','Full_CacheRAMSub'),('ram_primary','Full_CacheRAMPrimary'))],
        ' foreach device [debug list] {if {[debug desc $device] eq "memory mapper" && [debug size $device]>=131072} {set ::mapper $device;set ::base [expr {(([debug read ioports 255]^2)&([debug size $device]/16384-1))*16384}];break}}',
        ' set ::audio_code [debug read_block $::mapper $::base 14336]',
        ' if {[catch begin_case problem]} {puts stderr $problem;exit 2}',
        '}',
        'debug set_bp 0xd15f {$::active} {',
        ' set ::active 0;puts $::costs [expr {([machine_info time]-$::begin)*1000}]',
        f' if {{[reg SP]!=0xf380 || [reg IX]!=0x4567 || [reg IY]!=0x6789 || [debug read ioports 168]!=$::expected_primary || [debug read ioports 252]!=$::expected_page || [debug read memory {s["Full_CacheHeld"]}]!=($::index/2&1) || [debug read_block memory 0xea00 1536] ne $::code || [debug read_block VRAM 0 131072] ne $::vram || [debug read_block {{PSG regs}} 14 2] ne $::io || [debug read_block $::mapper $::base 14336] ne $::audio_code}} {{puts stderr "Production audio damaged preserved state/mapping/code/VRAM/PSG I/O";exit 2}}',
        ' puts -nonewline $::result [debug read_block memory 0xe000 2560]',
        ' puts -nonewline $::result [debug read_block $::mapper [expr {$::base+0x3800}] 768]',
        ' puts -nonewline $::result [debug read_block memory 0xe9c0 64]',
        ' puts -nonewline $::result [debug read_block {PSG regs} 0 14]',
        f' puts -nonewline $::result [binary format cc [debug read memory {s["Audio_Mute"]}] [debug read memory {s["Audio_MusicMode"]}]]',
        ' incr ::step;if {[catch issue problem]} {puts stderr $problem;exit 2}',
        '}',
        'after time 180 {puts stderr "Production audio proof timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')], check=True, timeout=240,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'result.bin').read_bytes()
    if len(raw)!=len(SCENARIOS)*2*STEPS*STRIDE:raise ValueError('Incomplete production audio cases')
    scores={name:(rom.parent/f'audio-{name}-frames.bin').read_bytes() for name in ('normal','challenge','intro','complete','gameover')}
    intro_end=24+len(scores['intro'])//FRAME
    effects={i:(rom.parent/f'audio-fx-{i}-frames.bin').read_bytes() for i in range(1,10)}
    coverage=set();active_pairs={}
    for kind,name in enumerate(SCENARIOS):
        active=[0,0,0]
        for step in range(STEPS):
            rows=[raw[((kind*2+mute)*STEPS+step)*STRIDE:((kind*2+mute)*STEPS+step+1)*STRIDE] for mute in range(2)]
            states=[bytearray(row[:STATE]) for row in rows]
            for state in states: state[0x9b8:0x9bb]=bytes(3)  # Physical amplitude shadow is output, not gameplay.
            if states[0]!=states[1] or rows[0][STATE:STATE+8]!=rows[1][STATE:STATE+8]:
                raise ValueError(f'Mute changed production sequencing/game/queue/pitches: {name}, packet {step}')
            for initial,row in enumerate(rows):
                muted=initial ^ int(40<=step<80)
                if row[-2]!=muted:raise ValueError(f'F4 edge/hold/release failed: {name}, packet {step}')
                psg=row[STATE:STATE+14]
                terminal=name if name in ('complete','gameover') else 'gameover' if name=='gameover_adapter' and step>=12 else None
                terminal_step=step-12 if name=='gameover_adapter' else step
                if name=='ui_transition':
                    if 12<=step<24 or intro_end<=step<270:frame=bytes(FRAME)
                    else:
                        score=scores['intro'] if 24<=step<intro_end else scores['normal']
                        tick=step-24 if 24<=step<intro_end else step-270 if step>=270 else step
                        at=(tick%(len(score)//FRAME))*FRAME;frame=score[at:at+FRAME]
                elif name in ('title','player_select') or name=='intro' and step>=len(scores['intro'])//FRAME or terminal and terminal_step>=len(scores[terminal])//FRAME:
                    frame=bytes(FRAME)
                else:
                    score=scores['challenge'] if name=='challenge' else scores['normal']
                    tick=step*2 if name=='late_clock' else ((step+1)*3//2-1 if name=='odd_clock' else step)
                    if name=='intro':
                        if step<len(scores['intro'])//FRAME:score=scores['intro']
                        else:tick-=len(scores['intro'])//FRAME
                    if name=='complete':score=scores['complete']
                    if name=='gameover':score=scores['gameover']
                    if name=='gameover_adapter' and step>=12:score=scores['gameover'];tick=step-12
                    at=(tick%(len(score)//FRAME))*FRAME;frame=score[at:at+FRAME]
                for ch in range(3):
                    value=int.from_bytes(frame[ch*2:ch*2+2],'little')
                    volume=0 if muted else frame[6+ch]
                    actual_pitch=int.from_bytes(psg[ch*2:ch*2+2],'little') if ch<2 else int.from_bytes(row[0x9d4:0x9d6],'little')
                    actual_volume=psg[8+ch] if ch<2 else (0 if muted else row[0x9d6])
                    if actual_pitch!=value or actual_volume!=volume:
                        raise ValueError(f'Wrong production music voice/frequency: {name}, packet {step}, voice {ch}')
                    active[ch]+=int(initial==0 and volume>0)
                if psg[7]&0xdb!=0x98 or muted and any(psg[8:11]):
                    raise ValueError('PSG mix violated tone/FX isolation, I/O directions or mute')
                if name in ('intro','complete') and frame[8] and not muted:
                    if psg[4:6]!=frame[4:6] or psg[10]!=frame[8]:raise ValueError('Third music voice did not reach the PSG')
                if name=='late_clock':
                    heading=step//120%4;expected=s[f'Audio_Engine{heading}DriveEnvelope']
                    if int.from_bytes(psg[11:13],'little')!=expected or psg[13]!=8 or psg[10]!=(0 if muted else 16):
                        raise ValueError('Engine envelope did not follow native heading/velocity')
                if name=='effects' and step>=12:
                    effect=min(9,step//12);age=step-effect*12;source=effects[effect]
                    if age<len(source)//5:
                        f=source[age*5:age*5+5]
                        if psg[4:6]!=f[:2] or psg[10]!=(0 if muted else f[2]) or psg[6]!=f[3] or psg[7]&0x24!=f[4]:
                            raise ValueError(f'Pitched/noise effect contour changed: {effect}, frame {age}')
                if name in ('title','player_select') or name=='ui_transition' and (12<=step<24 or intro_end<=step<270):
                    if psg[10]:raise ValueError('Engine noise leaked into a non-gameplay screen')
            queue=rows[0][2560+768:STATE]
            noise=queue[3];drops=queue[5]
            if name=='effects' and step>=12 and step<=108 and step%12==0:
                effect=step//12
                if noise!=effect:raise ValueError(f'Transient effect mailbox lost/reordered ID {effect}')
                coverage.add(effect)
            if name=='overflow' and step in (0,1,2) and noise!=(1,1,8)[step]:
                raise ValueError('FIFO order/overflow/crash preemption failed')
            if name=='overflow' and step in (3,10) and noise!={3:8,10:9}[step]:
                raise ValueError('Fuel refill interrupted a crash or disappeared from the queue')
            if name=='flag_adapter' and step in (12,24,36,100) and noise!={12:6,24:7,36:7,100:0}[step]:
                raise ValueError('Persistent collected-flag adapter lost or invented an effect')
            if name=='smoke_adapter' and step in (12,24,36) and noise!=2:
                raise ValueError('Persistent smoke-placement adapter lost an effect')
            if drops != int(name=='overflow'):
                raise ValueError('Unexpected queue overflow/drop accounting')
        required=3 if name in ('intro','complete') else 2
        if name in ('background','intro','complete','challenge','gameover') and not all(active[:required]):
            raise ValueError(f'Missing one of the original music voices: {name}')
        active_pairs[name]=active
    costs=[float(v) for v in (out/'costs.tsv').read_text().splitlines()]
    verify_manifest(rom.parent)
    json_write(out/'report.json',dict(rom_sha256=digest(rom),cases=len(SCENARIOS)*2*STEPS,passed=True,
        effect_ids=sorted(coverage),active_music_packets=active_pairs,
        maximum_packet_ms=max(costs),mean_packet_ms=sum(costs)/len(costs),
        scope='Production Audio_Work execution: fifteen seeded scenarios, output on/muted, both BIOS and held-cache Page0 mappings; '
              'exact game/music/queue invariance and three-voice golden packets, actual F4 edges/holds, '
              'physical counter wrap, complete music loops, persistent flag/smoke retention, nine pitched/noise effects, '
              'coalescing, FIFO saturation/order, crash/refill priority and four engine-envelope directions. '
              'Code, stack/indices, VRAM, mapping and PSG I/O preserved. Display/IRQs off at forced 3.58 MHz; '
              'not natural gameplay, real IRQ or perceptual timbre qualification.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'{len(SCENARIOS)*2*STEPS} production music/noise/mute cases pass: {out}/report.json')


if __name__=='__main__':main()
