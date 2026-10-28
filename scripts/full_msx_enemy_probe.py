#!/usr/bin/env python3
"""Execute MSX steering, smoke, contact, speed and fractional motion on Z80."""
import argparse
import itertools
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.enemy_navigation import choose
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);s=symbols(bundle/'raster-scroll.sym')
    out=destination(root,args.output);require_ignored(root,[out/'result.bin']);out.mkdir(parents=True)
    cases=[];expected=bytearray();counts={'steering':0,'contact':0,'parked_contact':0,'smoke':0,'player_speed':0,'motion':0}
    enemy_divisor=s.get('Full_MSXEnemyMotionDivisor',1)
    player_cap=s['Full_MSXPlayerMaxSpeed'];enemy_cap=s['Full_MSXEnemyMaxSpeed']
    # Each case is a bounded list of memory writes, an entry, and result kind.
    def add(kind,writes,result,entry=None):
        if entry is None:entry=s['Full_MSXActor'] if kind!=1 else s['Full_MSXContact']
        cases.append([entry,kind,*[v for pair in writes for v in pair]])
        expected.extend(result)
    targets=((7,2),(-7,2),(2,7),(2,-7),(0,0),(-7,-7),(7,-7),(-7,7))
    for mask,heading,(dx,dy),actor in itertools.product(range(1,16),range(4),targets,range(2)):
        for style in (0,1,2,3,4):
            if style in (1,2) and not mask&(1<<heading):continue
            direction=choose(mask,heading,dx,dy,actor) if style in (0,4) else heading
            speed=0 if style==3 else 544 if style==2 else enemy_cap
            velocity=(-speed if direction>=2 else speed)&65535
            old_velocity=(-544 if heading>=2 else 544)&65535
            fine_x=(4 if style==4 else 12 if style==2 else 0) if heading&1 else 0
            fine_y=(4 if style==4 else 12 if style==2 else 0) if not heading&1 else 0
            writes=[(s['Full_MSXExits'],32 if style==3 else 0),(0xc701,0),(0xe070,15+dx),(0xe072,25+dy),
                (0xe025,0 if style==3 else 32),(0xe026,0 if style==3 else 2),
                (0xe029,0 if style==3 else 96),(0xe02a,0 if style==3 else 2),
                (s['Full_MSXIndex'],actor),(s['Full_MSXDecision']+actor*2,15 if style==1 else 255),
                (s['Full_MSXDecision']+actor*2+1,25),
                (0xe088,0),(0xe089,old_velocity&255),(0xe08a,old_velocity>>8),(0xe08b,255 if heading&1 else 0),
                (0xe08d,fine_x),(0xe08f,fine_y),(0xe090,15),(0xe092,25),(0xe09b,0),(0xe09d,0)]
            # Physical mapper write is represented by an address below C000.
            writes.append((0x332f,mask))
            add(0,writes,bytes((0,velocity&255,velocity>>8,255 if direction&1 else 0,0,0)))
            counts['steering']+=1
    # Cohort zero-speed changes override coasting, while a parked actor resumes
    # immediately even between centres. These execute the real cohort entry too.
    for parked,whole_cohort in itertools.product((False,True),(False,True)):
        speed=0 if parked else enemy_cap
        writes=[(s['player_native_ticks'],0),(s['Full_MSXExits'],0 if whole_cohort and parked else 32 if parked or whole_cohort else 0),
            (0xc701,0),(0xe070,22),(0xe072,27),(0xe24e,1),
            (0xe025,0 if parked else 32),(0xe026,0 if parked else 2),
            (0xe029,0 if parked else 96),(0xe02a,0 if parked else 2),
            (s['Full_MSXIndex'],0),(0xe088,0),(0xe089,32 if parked else 0),(0xe08a,2 if parked else 0),
            (0xe08b,0),(0xe08d,0),(0xe08f,12),(0xe090,15),(0xe092,25),(0xe09b,0),(0xe09d,0)]
        add(0,writes,bytes((0,speed&255,speed>>8,0,0,0)),s['Full_MSXAI'] if whole_cohort else None)
        counts['steering']+=1
    for velocity in sorted({0,1,255,511,544,575,576,577,608,1024,32767,32768,
            player_cap-1,player_cap,player_cap+1,-player_cap-1,-player_cap,-player_cap+1,
            *(-n for n in (1,255,511,544,575,576,577,608,1024,32767,32768))}):
        signed=velocity if velocity<32768 else velocity-65536
        expected_speed=max(-player_cap,min(player_cap,signed))&65535
        add(2,[(0xe069,velocity&255),(0xe06a,(velocity>>8)&255)],expected_speed.to_bytes(2,'little'),s['Full_MSXPlayerSpeed'])
        counts['player_speed']+=1
    for code,immunity,fine in itertools.product((0,0xbc,0xbd,0xbf,0xc5,0xc6),(0,1,130),(0,12)):
        x=4+15*3+(fine+3)//8;y=4+25*3+4//8
        smoke_at=0xe400+((y-10)&31)*32+((x-3)&31)
        writes=[(s['Full_MSXExits'],0),(0xc701,1),(0xc702,40),(0xc703,70),(smoke_at,code),
            (0xe070,18),(0xe072,27),(0xe025,32),(0xe026,2),(0xe029,96),(0xe02a,2),
            (s['Full_MSXIndex'],0),(s['Full_MSXDecision'],15),(s['Full_MSXDecision']+1,25),
            (0xe088,0),(0xe089,32),(0xe08a,2),(0xe08b,255),(0xe08d,fine),(0xe08f,0),
            (0xe090,15),(0xe092,25),(0xe09b,immunity),(0xe09d,0),(0x332f,15)]
        stunned=0xbd<=code<0xc6 and immunity==0
        speed=544 if stunned or fine else enemy_cap
        add(0,writes,bytes((136 if stunned else 0,speed&255,speed>>8,255,130 if stunned else max(0,immunity-enemy_divisor),int(stunned))))
        counts['smoke']+=1
    for player,parity,axis,velocity,fine,fraction in itertools.product((False,True),(0,1),(0,255),
            (0,544,-544,608,-608),(-23,0,23),(0,255)):
        at=0xe068 if player else 0xe088
        descriptor=bytearray(32);descriptor[1:3]=(velocity&65535).to_bytes(2,'little');descriptor[3]=axis
        offset=4 if axis else 6;coarse_offset=8 if axis else 10
        descriptor[offset]=fraction;descriptor[offset+1]=fine&255
        descriptor[8]=15;descriptor[10]=25;descriptor[17:19]=bytes.fromhex('cdab')
        writes=[(at+i,v) for i,v in enumerate(descriptor)]+[(s['player_native_ticks'],parity),(0xe05a,0),(0xe05b,0)]
        moving=not parity
        step=velocity*s.get("Full_MSXPlayerMotionDivisor",1) if player else max(-enemy_cap,min(enemy_cap,velocity))*enemy_divisor
        if moving:
            fixed=fine*256+fraction+step
            while fixed>=24*256:
                fixed-=24*256;descriptor[coarse_offset]+=(1 if axis else -1)
            while fixed<(-23)*256:
                fixed+=24*256;descriptor[coarse_offset]+=(-1 if axis else 1)
            descriptor[offset]=fixed&255;descriptor[offset+1]=(fixed>>8)&255
            descriptor[17:19]=(0x9800+descriptor[10]*32+descriptor[8]).to_bytes(2,'little')
        add(4 if player else 3,writes,bytes(descriptor[1:11]+descriptor[17:19]),s['Full_NativeMotion'])
        counts['motion']+=1
    for actor,px,py,cx,cy,dx,dy in itertools.product(range(7),(-23,-12,0,12,23),(-23,-12,0,12,23),(-2,-1,0,1,2),(-2,-1,0,1,2),(-11,-10,-9,0,9,10,11),(-11,-10,-9,0,9,10,11)):
        fx=dx-24*cx+px;fy=24*cy+py-dy
        if not -23<=fx<=23 or not -23<=fy<=23:continue
        writes=[(0xe24e,7),(0xe070,15),(0xe072,25),(0xe06d,px&255),(0xe06f,py&255),
            (0xc5d0,0),(s['Enemy_HitAddress'],255),(s['Enemy_HitAddress']+1,255)]
        writes.extend((0xe092+i*32,100) for i in range(7))
        at=0xe088+actor*32
        writes.extend(((at,0),(at+14,0),(at+8,15+cx),(at+10,25+cy),(at+5,fx&255),(at+7,fy&255)))
        hit=abs(dx)<=10 and abs(dy)<=10;pointer=at+14 if hit else 65535
        add(1,writes,bytes((int(hit),pointer&255,pointer>>8)));counts['contact']+=1
    # The MSX adapter does not maintain arcade OAM attributes. Startup contact
    # must include the first $88 pose, independently of stale arcade screen Y.
    for actor,round_,state,dx,dy in itertools.product(range(7),(2,3,4,8),(0,0x88,0x89,0x8a,0xff),
            (-15,-14,-11,-10,0,10,11,14,15),(-15,-14,-11,-10,0,10,11,14,15)):
        writes=[(0xe24e,7),(0xe1b0,round_),(0xe070,15),(0xe072,25),(0xe06d,0),(0xe06f,0),
                (0xc5d0,0),(s['Enemy_HitAddress'],255),(s['Enemy_HitAddress']+1,255)]
        writes.extend((0xe092+i*32,100) for i in range(7))
        at=0xe088+actor*32
        writes.extend(((at,state),(at+14,1),(at+8,15),(at+10,25),(at+5,dx&255),(at+7,(-dy)&255)))
        radius=14 if state>=0x88 and round_%4 else 10
        hit=abs(dx)<=radius and abs(dy)<=radius;pointer=at+14 if hit else 65535
        add(1,writes,bytes((int(hit),pointer&255,pointer>>8)));counts['parked_contact']+=1
    (out/'cases.tcl').write_text('set msx_cases {\n'+'\n'.join('{'+ ' '.join(map(str,c))+'}' for c in cases)+'\n}\n')
    enter=s['Full_CacheEnter'];leave=s['Full_CacheLeave']
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set vsync off',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked true','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        f'set player_cap {player_cap}',
        'source [file join $out cases.tcl];set msx_index 0;set msx_started 0;set msx_result [open [file join $out result.bin] wb]',
        'proc issue {} {',
        ' if {$::msx_index==[llength $::msx_cases]} {if {[debug read_block VRAM 0 131072] ne $::msx_vram} {error "Enemy contract changed VRAM"};close $::msx_result;exit 0;return}',
        ' lassign [lindex $::msx_cases $::msx_index] entry kind;set ::msx_kind $kind',
        ' foreach {at value} [lrange [lindex $::msx_cases $::msx_index] 2 end] {if {$at<0xc000} {debug write $::msx_mapper [expr {$::msx_base+$at}] $value} else {debug write memory $at $value}}',
        ' set ::msx_player [debug read_block memory 0xe000 136]',
        ' if {$kind==2} {set speed [expr {[debug read memory 0xe069]+256*[debug read memory 0xe06a]}];if {$speed>=32768} {incr speed -65536};set speed [expr {max(-$::player_cap,min($::player_cap,$speed))}];set ::msx_player [string replace $::msx_player 105 106 [binary format cc [expr {$speed&255}] [expr {($speed>>8)&255}]]]}',
        f' if {{$entry=={s["Full_MSXAI"]}}} {{binary scan [string index $::msx_player 34] cu clock;set ::msx_player [string replace $::msx_player 34 34 [binary format c [expr {{($clock+1)&255}}]]]}}',
        f' set at 0xd140;foreach value [list 243 205 {enter&255} {enter>>8} 205 [expr {{$entry&255}}] [expr {{$entry>>8}}] 205 {leave&255} {leave>>8} 195 80 209] {{debug write memory $at $value;incr at}}',
        f' debug write memory 0x7000 {s["PLAYER_BANK"]};reg IX [expr {{$kind==4?0xe068:0xe088}}];reg IY [expr {{$kind==4?1:0}}];reg SP 0xc7f0;reg PC 0xd140','}',
        f'debug set_bp {s["main"]} {{!$::msx_started}} {{set ::msx_started 1;set ::msx_vram [debug read_block VRAM 0 131072];foreach device [debug list] {{if {{[debug desc $device] eq "memory mapper" && [debug size $device]>=131072}} {{set ::msx_mapper $device;set ::msx_base [expr {{([debug read memory {s["Full_CacheSegment"]}]&([debug size $device]/16384-1))*16384}}];break}}}};if {{[catch issue p]}} {{puts stderr $p;exit 2}}}}',
        'debug set_bp 0xd150 {$::msx_started} {',
        ' set protected [expr {$::msx_kind==4?104:136}]',
        ' if {[reg SP]!=0xc7f0 || [debug read_block memory 0xe000 $protected] ne [string range $::msx_player 0 [expr {$protected-1}]]} {puts stderr "Enemy contract changed stack or protected native state";exit 2;return}',
        f' if {{$::msx_kind>=3}} {{set actor [expr {{$::msx_kind==4?0xe068:0xe088}}];set data [debug read_block memory [expr {{$actor+1}}] 10];append data [debug read_block memory [expr {{$actor+17}}] 2]}} elseif {{$::msx_kind==2}} {{set data [debug read_block memory 0xe069 2]}} elseif {{$::msx_kind==1}} {{set data [debug read_block memory 0xc5d0 1];append data [debug read_block memory {s["Enemy_HitAddress"]} 2]}} else {{set data [debug read_block memory 0xe088 4];append data [debug read_block memory 0xe09b 1] [debug read_block memory 0xe09d 1]}}',
        ' puts -nonewline $::msx_result $data;incr ::msx_index;if {[catch issue p]} {puts stderr $p;exit 2}','}',
        'after time 180 {puts stderr "MSX enemy contract timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'result.bin').read_bytes()
    if actual!=expected:
        offset=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),min(len(actual),len(expected)))
        raise ValueError(f'MSX enemy contract differs at result byte {offset}: actual={actual[offset:offset+6].hex()} expected={expected[offset:offset+6].hex()}')
    verify_manifest(bundle);json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=counts,
        protected_native_state_unchanged=True,player_motion_steps_tested=True,
        enemy_motion_divisor=enemy_divisor,player_speed_cap=player_cap,enemy_speed_cap=enemy_cap,
        stack_unchanged=True,vram_unchanged=True,
        scope='Synthetic executed Z80 contracts: legal centre decisions, cached/coasting headings, challenge activation/zero speed, smoke immunity in native tick units, signed speed caps, fractional player/enemy motion on both cadence phases, and all seven world-contact slots across two signed coarse cells. Normal startup states use radius 14; active/stunned and challenge retain radius 10.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'{sum(counts.values())} MSX enemy contracts pass: {out}/report.json')


if __name__=='__main__':main()
