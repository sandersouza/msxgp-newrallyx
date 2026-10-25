#!/usr/bin/env python3
"""Drive full-game rounds through real credit/start, steering and smoke inputs."""
import argparse
import os
import re
from pathlib import Path
import subprocess
import sys

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.stage_one import acquire,cells_from_rom
from scripts.msx.completion_route_verify import verify_header_reservations
from scripts.msx.cadence import analyze as analyze_cadence
from scripts.msx.cadence import analyze_scroll
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rounds',type=int,choices=range(1,255),default=2)
    p.add_argument('--steering-margin',type=int,choices=range(3,10),default=6,help='Host driver turn-planning margin in pixels')
    p.add_argument('--avoid-enemies',action='store_true',help='Route around current enemy cells using host-side BFS')
    p.add_argument('--profile',action='store_true',help='Observe main-loop call durations without guest writes')
    p.add_argument('--record-round',type=int,help='Record eight seconds of actual scanout from this displayed round')
    p.add_argument('--trace-di',action='store_true',help='Observe interrupt-masked intervals without guest writes')
    p.add_argument('--radar-trace',action='store_true',help='Compare live radar SAT against latched R23 before each visible band')
    p.add_argument('--require-stable-radar',action='store_true')
    p.add_argument('--require-stable-fuel',action='store_true')
    p.add_argument('--require-stable-player',action='store_true')
    p.add_argument('--minimum-presentation-hz',type=float)
    p.add_argument('--minimum-vertical-update-hz',type=float)
    p.add_argument('--maximum-scroll-step',type=int)
    p.add_argument('--fixed-base-clock',action='store_true',help='Diagnostic: force 3.58 MHz instead of machine-controlled factory switching')
    p.add_argument('--minimum-native-hz',type=float,help='Require this active average in every measured round')
    p.add_argument('--bios',type=Path,default=Path('references/msxbios'))
    p.add_argument('--machine',default='Panasonic_FS-A1WSX');p.add_argument('--openmsx',default='openmsx')
    args=p.parse_args(argv);root=Path(__file__).resolve().parents[1]
    if args.record_round is not None and not 1<=args.record_round<=args.rounds:raise ValueError('Recorded round must be within the natural route')
    if args.require_stable_radar and not args.radar_trace:raise ValueError('Stable radar gate requires --radar-trace')
    if args.require_stable_fuel and not args.radar_trace:raise ValueError('Stable fuel gate requires --radar-trace')
    if args.require_stable_player and not args.radar_trace:raise ValueError('Stable player gate requires --radar-trace')
    if args.maximum_scroll_step is not None and not args.radar_trace:raise ValueError('Scroll gate requires --radar-trace')
    if args.minimum_vertical_update_hz is not None and not args.radar_trace:raise ValueError('Vertical cadence gate requires --radar-trace')
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    out=destination(root,args.output);require_ignored(root,[out/'board-0.bin']);out.mkdir(parents=True)
    program,_=acquire(root)
    for i in range(4):(out/f'board-{i}.bin').write_bytes(cells_from_rom(program,0x30+i))
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false',f'set renderer {"SDLGL-PP" if args.record_round else "none"}','set sound_driver null','set vsync off',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set throttle off','set pause_on_lost_focus false',
        'set z80_freq 3579545',f'set z80_freq_locked {str(not args.fixed_base_clock).lower()}','set cmdtiming real','set limitsprites true',
        'activate_input_layer -blocking full_route',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)};set rounds {args.rounds};set avoid_enemies {int(args.avoid_enemies)};set steering_margin {args.steering_margin}',
        'for {set i 0} {$i<4} {incr i} {set f [open [file join $out "board-$i.bin"] rb];set boards($i) [read $f];close $f}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Full route VRAM timing violation";exit 2}',
        'after time 900 {puts stderr "Full route emulated timeout: PC=[reg PC] SP=[reg SP] IFF=[reg IFF]";foreach {name data} [list timeout.state [debug read_block memory 0xc000 12288] timeout.page0 [debug read_block memory 0 16384] timeout.vram [debug read_block VRAM 0 131072]] {set f [open [file join $::out $name] wb];puts -nonewline $f $data;close $f};exit 2}']
    if args.record_round:
        lines.extend(['set recording_started 0',
            f'debug set_bp {syms["main"]} {{[info exists ::phase] && $::phase eq "game" && [debug read memory 0xe1b0]=={args.record_round+1} && !$::recording_started}} {{',
            ' set ::recording_started 1',
            f' record start -videoonly {tcl(out/"scanout.avi")}',
            f' after time 8 {{record stop;screenshot -raw {tcl(out/"scanout-last.png")};set renderer none}}',
            '}'])
    script=(root/'scripts/msx/full-route-probe.tcl').read_text().replace('@SHOW_SCENE@',str(syms['show_scene']))
    for token,name,read in [('CLOCK_DUE','Full_ClockDue','debug read memory'),('CAMERA_BLOCKED','Full_CameraBlocked','debug read memory'),('CLOCK_DROPPED','Full_ClockDropped','u16')]:
        script=script.replace('@'+token+'@',f'[{read} {syms[name]}]' if name in syms else '0')
    if 'Full_CameraValidated' in syms:
        script=script.replace('exit 0','set f [open [file join $::out camera-count.txt] w];puts $f $::camera_checks;close $f;exit 0')
    if 'Full_RadarIRQStart' in syms:
        lines.extend([
            f'debug set_watchpoint write_mem {{{syms["Full_RadarIRQStart"]} {syms["Full_RadarIRQEnd"]-1}}} {{[info exists ::phase] && $::phase eq "game"}} {{',
            'puts stderr "Raster IRQ RAM overwritten: $::wp_last_address value=$::wp_last_value PC=[reg PC] frame=$::frames";exit 2',
            '}',
        ])
    if 'Full_CacheEngineStart' in syms:
        engine=(args.rom.read_bytes()[syms['FULL_TERRAIN_BANK']*16384:])[:syms['Full_CacheEngineEnd']-syms['Full_CacheEngineStart']]
        (out/'terrain-code.bin').write_bytes(engine)
        lines.extend([
            'set f [open [file join $out terrain-code.bin] rb];set terrain_code [read $f];close $f',
            f'debug set_watchpoint write_mem {{{syms["Full_LoadStart"]} {syms["Full_LoadEnd"]-1}}} {{$::phase eq "game" && [debug read memory 0xc7d0]==0}} {{puts stderr "Cold RAM code overwritten: $::wp_last_address";exit 2}}',
            f'debug set_bp {syms["main"]} {{$::phase eq "game" && [debug read memory 0xc7d0]==0}} {{',
            f'if {{[debug read ioports 168]!=[debug read memory {syms["Full_CachePrimary"]}] || [debug read ioports 252]!=[debug read memory {syms["Full_CacheMapper"]}] || [debug read memory {syms["Full_CacheHeld"]}]}} {{puts stderr "Terrain mapper was not restored";exit 2}}',
            '}',
            f'debug set_bp {syms["Full_CameraValidated"]} {{$::phase eq "game" && [debug read memory 0xc7d0]==0}} {{if {{[debug read_block memory {syms["Full_CacheEngineStart"]} [string length $::terrain_code]] ne $::terrain_code}} {{puts stderr "Terrain overlay code overwritten";exit 2}}}}',
        ])
    if 'Full_CameraValidated' in syms:
        lines.extend([
            'set camera_checks 0;set camera_block_age 0',
            f'debug set_bp {syms["Full_CameraValidate"]} {{$::phase eq "game" && [debug read memory 0xc7d0]==0}} {{',
            f'if {{[debug read memory {syms["Full_CameraBlocked"]}]}} {{incr ::camera_block_age}} else {{set ::camera_block_age 0}}',
            'if {$::camera_block_age==64} {',
            'foreach {name data} [list camera-block.bin [debug read_block memory 0x2000 4096] camera-block.state [debug read_block memory 0xc000 12288] camera-block.vram [debug read_block VRAM 0 131072]] {set f [open [file join $::out $name] wb];puts -nonewline $f $data;close $f}',
            'puts stderr "Camera remained blocked for 64 consecutive loops: frame=$::frames";exit 2',
            '}',
            '}',
            f'debug set_bp {syms["Full_CameraValidated"]} {{$::phase eq "game" && [debug read memory 0xc7d0]==0}} {{',
            'set data [debug read_block memory 0x2000 4096];binary scan $data cu* tags',
            f'set x [debug read memory {syms["Full_TargetTileX"]}];set y [debug read memory {syms["Full_TargetTileY"]}]',
            'for {set dy 0} {$dy<26} {incr dy} {for {set dx 0} {$dx<32} {incr dx} {',
            'set wx [expr {($x+$dx)&255}];set wy [expr {($y+$dy)&255}];set at [expr {($wy&31)*128+($wx&63)*2}]',
            'if {[lindex $tags $at]!=$wx || [lindex $tags [expr {$at+1}]]!=$wy} {puts stderr "Camera exposed an unowned tile: frame=$::frames world=$wx,$wy";exit 2}',
            '}};incr ::camera_checks',
            '}',
        ])
    if 'Full_TurboEnabled' in syms:
        if not args.fixed_base_clock:
            lines.append(f'debug set_bp {syms["Full_NativeMotion"]} {{$::phase eq "game" && [debug read memory {syms["Full_TurboEnabled"]}]}} {{if {{[machine_info z80_freq]!=5369318}} {{puts stderr "Native motion did not receive factory CPU frequency";exit 2}}}}')
        for name in ('Sprite_Upload','stage_wait_command','Full_RadarIRQ'):
            lines.append(f'debug set_bp {syms[name]} {{$::phase eq "game" && [debug read memory {syms["Full_TurboEnabled"]}]}} {{if {{!([debug read ioports 65]&1) || [machine_info z80_freq]!=3579545}} {{puts stderr "VDP work entered at turbo clock: {name}";exit 2}}}}')
        if args.profile:
            lines.extend(['set clock_out [open [file join $out clocks.tsv] w];set clock_samples 0',
                f'debug set_bp {syms["Full_NativeMotion"]} {{$::phase eq "game" && $::clock_samples<256}} {{set ::clock_begin [machine_info time];set ::clock_active [debug read memory {syms["Full_TurboActive"]}];set ::clock_port [debug read ioports 65]}}',
                f'debug set_bp {syms["Full_NativeMotion"]+3} {{[info exists ::clock_begin]}} {{puts $::clock_out "$::clock_active $::clock_port [machine_info z80_freq] [expr {{[machine_info time]-$::clock_begin}}]";unset ::clock_begin;incr ::clock_samples}}'])
    if args.radar_trace:
        (out/'radar-table.bin').write_bytes((bundle/f'bank-{syms["RADAR_SAT_BANK"]}.bin').read_bytes())
        lines.extend([
            'set f [open [file join $out radar-table.bin] rb];set radar_table [read $f];close $f',
            'set radar_samples 0;set radar_mismatches 0;set radar_out [open [file join $out radar.tsv] w]',
            'set fuel_samples 0;set fuel_mismatches 0;set fuel_out [open [file join $out fuel.tsv] w]',
            'set footer_samples 0;set footer_mismatches 0',
            'set player_samples 0;set player_mismatches 0;set player_out [open [file join $out player.tsv] w]',
            'set camera_out [open [file join $out camera.tsv] w]',
            f'set camera_has_tags {int("Full_CacheSegment" in syms)}',
            'set camera_ram "";foreach device [debug list] {if {[debug desc $device] eq "memory mapper" && [debug size $device]>=131072} {set camera_ram $device;break}}',
            'if {$camera_ram eq ""} {error "Missing physical camera mapper"}',
            'proc camera_sample {} {',
            f' set sy [debug read {{VDP regs}} 23];set wx [u16 {syms["world_x"]}];set wy [u16 {syms["world_y"]}]',
            ' if {$wx>=32768} {incr wx -65536};if {$wy>=32768} {incr wy -65536}',
            ' set hardware_x [expr {[debug read {VDP regs} 26]*8+8-([debug read {VDP regs} 27]&7)}]',
            ' set wx [expr {$wx+(($hardware_x-$wx+256)&511)-256}]',
            f' set wy [expr {{$wy+(($sy+{syms["BODY_TOP"]}-$wy+128)&255)-128}}]',
            f' puts $::camera_out "[machine_info time] [debug read memory 0xe1b0] [debug read memory 0xc490] [debug read memory 0xc724] $sy [debug read memory {syms["scroll_y"]}] $wy [u16 0xc407] [u16 0xc452]"',
            ' if {!$::camera_has_tags || [debug read memory 0xc490] || [debug read memory 0xc724]} {return}',
            f' set segment [debug read memory {syms.get("Full_CacheSegment",0)}]',
            ' set base [expr {($segment&([debug size $::camera_ram]/16384-1))*16384+8192}]',
            ' binary scan [debug read_block $::camera_ram $base 4096] cu* tags',
            ' set x [expr {($wx>>3)&255}];set y [expr {($wy>>3)&255}]',
            ' set columns [expr {(($wx&7)+248+7)/8}]',
            ' for {set dy 0} {$dy<26} {incr dy} {for {set dx 0} {$dx<$columns} {incr dx} {',
            ' set tx [expr {($x+$dx)&255}];set ty [expr {($y+$dy)&255}];set at [expr {($ty&31)*128+($tx&63)*2}]',
            ' if {[lindex $tags $at]!=$tx || [lindex $tags [expr {$at+1}]]!=$ty} {error "Latched camera exposed an unowned tile: $tx,$ty at view $wx,$wy tags=[lrange $tags $at [expr {$at+1}]]"}',
            ' }}',
            '}',
            'proc fuel_sample {} {',
            ' if {$::phase ne "game" || $::skip_headers || [debug read memory 0xc7d0]!=0 || [debug read memory 0xc5c1]} {return}',
            ' incr ::fuel_samples;set scroll [debug read {VDP regs} 23]',
            ' set at [expr {$scroll*64+52}]',
            ' set expected [string range $::radar_table $at [expr {$at+11}]]',
            f' set actual [debug read_block VRAM {0x1c000+(syms["FUEL_ATTRIBUTES"]&0x3fff)} 12]',
            ' if {$actual ne $expected} {incr ::fuel_mismatches;puts $::fuel_out "$::frames $scroll [binary encode hex $actual] [binary encode hex $expected]"}',
            '}',
            'proc footer_sample {} {',
            ' if {$::phase ne "game" || $::skip_headers || [debug read memory 0xc7d0]!=0 || [debug read memory 0xc5c1]} {return}',
            ' incr ::footer_samples;set sy [expr {([debug read {VDP regs} 23]+193)&255}];set car 156;set digit 172',
            ' if {$sy==216} {incr sy -1;set car 164;set digit 176}',
            f' set expected [binary format c* [list $sy {syms["LIFE_X0"]} $car 0 $sy {syms["LIFE_X0"]} [expr {{$car+4}}] 0 $sy {syms["LIFE_X1"]} $digit 0]]',
            f' set actual [debug read_block VRAM {0x1c000+(syms["FUEL_ATTRIBUTES"]&0x3fff)} 12]',
            ' if {$actual ne $expected} {incr ::footer_mismatches;puts $::fuel_out "footer $::frames [binary encode hex $actual] [binary encode hex $expected]"}',
            '}',
            'proc player_sample {} {',
            ' if {$::phase ne "game" || $::skip_headers || [debug read memory 0xc7d0]!=0 || [debug read memory 0xc49a]} {return}',
            ' incr ::player_samples;set sy [expr {([debug read {VDP regs} 23]+107)&255}];if {$sy==216} {incr sy -1}',
            f' set expected [binary format c* [list $sy {syms["PLAYER_X"]} 180 0 $sy {syms["PLAYER_X"]} 184 0]]',
            f' set actual [debug read_block VRAM {0x1f600+syms["PLAYER_SLOT"]*4} 8]',
            ' if {$actual ne $expected} {incr ::player_mismatches;puts $::player_out "$::frames [debug read {VDP regs} 23] [binary encode hex $actual] [binary encode hex $expected]"}',
            '}',
            'proc radar_sample {band} {',
            ' if {$::phase ne "game" || [debug read memory 0xc7d0]!=0 || [debug read memory 0xc5c1]} {return}',
            ' incr ::radar_samples;set scroll [debug read {VDP regs} 23]',
            f' set offset [expr {{$scroll*64+4+$band*12}}];set address [expr {{0x1f604+$band*12}}]',
            ' set actual [debug read_block VRAM $address 12]',
            ' set expected [string range $::radar_table $offset [expr {$offset+11}]]',
            ' if {$actual ne $expected} {incr ::radar_mismatches;puts $::radar_out "$::frames $band $scroll [binary encode hex $actual] [binary encode hex $expected]"}',
            '}',
            f'set radar_x {syms["RADAR_X"]};set radar_y {syms["RADAR_Y"]};set radar_pattern {syms["RADAR_PLAYER_PATTERN"]}',
            r'''proc radar_dot_sample {} {
 if {$::phase ne "game" || [debug read memory 0xc7d0]!=0 || [debug read memory 0xc5c1]} {return}
 incr ::radar_samples;set scroll [debug read {VDP regs} 23]
 binary scan $::radar_point cu* point;lassign $point x y
 if {$x==255} {set y 192}
 set sy [expr {($scroll+$::radar_y-1+$y)&255}];set pattern $::radar_pattern
 if {$sy==216} {incr sy -1;incr pattern 4}
 set expected [binary format c* [list $sy [expr {($x+$::radar_x)&255}] $pattern 0]]
 set actual [debug read_block VRAM 0x1f600 4]
 if {$actual ne $expected} {incr ::radar_mismatches;puts $::radar_out "$::frames -1 $scroll [binary encode hex $actual] [binary encode hex $expected]"}
}''',
            (f'debug set_bp {syms["Full_RadarIRQ"]} {{$::phase eq "game" && !$::skip_headers}} {{' if 'Full_RadarIRQ' in syms else
             'debug set_watchpoint write_mem 0xc03c {$wp_last_value==4 && $::phase eq "game" && !$::skip_headers} {'),
            'if {[catch {camera_sample} problem]} {puts stderr $problem;exit 2}',
            f'after time {(syms["FUEL_Y"]-3-9)*228/3579545:.10f} fuel_sample',
            f'after time {(syms["LIFE_Y"]-3-9)*228/3579545:.10f} footer_sample',
            f'after time {(107-3-9)*228/3579545:.10f} player_sample',
            *([f'set ::radar_point [debug read_block memory {syms["Radar_PlayerPoint"]} 2]',
                f'after time {(syms["RADAR_Y"]+2-3-9)*228/3579545:.10f} radar_dot_sample'] if 'Full_RadarIRQ.point' in syms else []),
            *[f' after time {(syms["RADAR_Y"]+band*15-3-9)*228/3579545:.10f} {{radar_sample {band}}}' for band in range(4)],
            '}',
        ])
    if args.profile:
        lines.extend(['set profile_out [open [file join $out profile.tsv] w]',
            'set wait_out [open [file join $out waits.tsv] w]',
            f'debug set_bp {syms["main.wait"]} {{$::phase eq "game"}} {{if {{![info exists ::frame_wait_start]}} {{set ::frame_wait_start [machine_info time];set ::frame_wait_round [debug read memory 0xe1b0]}}}}',
            f'debug set_bp {syms["main.ready"]} {{$::phase eq "game" && [info exists ::frame_wait_start]}} {{puts $::wait_out "$::frames $::frame_wait_round [debug read memory 0xe1b0] [expr {{[machine_info time]-$::frame_wait_start}}] [machine_info time] [debug read memory 0xc7d0] [debug read memory 0xc724] [debug read memory 0xc490]";unset ::frame_wait_start}}',
            'set stream_out [open [file join $out stream.tsv] w]',
            'set tile_out [open [file join $out tiles.tsv] w]',
            f'debug set_bp {syms["stage_copy_destination"]} {{$::phase eq "game" && [debug read memory 0xc7d0]==0 && [debug read memory {syms["Stage_RowBatch"]}]>0}} {{puts $::tile_out "$::frames [debug read memory 0xe1b0] [debug read memory {syms["Stage_RowBatch"]}] [u16 {syms["stage_command"]+8}] [u16 {syms["stage_command"]+10}]"}}'])
        names={'keys','stage_position','HUD_PrepareEarlyCoordinates','Enemy_Prepare','Enemy_Draw','Full_EnemyFrame',
               'HUD_FinishCoordinates','Player_AdvanceEarly','HUD_PrepareFrame','HUD_DrawContent',
               'Player_Advance','Radar_WaitPublish','stage_stream','Enemy_PreMove','Enemy_AfterMove',
               'Full_NativeAI','FullEnemy_PrepareOne','FullEnemy_DrawOne','Smoke_Tick','Fuel_Tick'}
        names.update({'Player_Tick','Full_SimulationTail'})
        names.update({'Player_Draw','Player_Patch','Score_ReservedFrame','Flag_Stream','Death_Stream','Smoke_Stream',
                      'Flag_Frame','Death_Frame','Radar_CommitPublished','Life_Frame','Round_Frame','Session_Check','Player_Update'})
        aliases={'$8cd6':'NativeAI','$b600':'GuardedAI','$95bd':'NativeVisibility',
                 '$91bf':'NativeCameraX','$9207':'NativeCameraY','$838a':'NativeContact',
                 '$8069':'NativeMotion','$9052':'NativeSteering'}
        for row in (bundle/'raster-scroll.lst').read_text().splitlines():
            match=re.search(r'[+\s]([0-9A-F]{4}) (?:CD|C4|CC|D4|DC|E4|EC|F4|FC) [0-9A-F]{2} [0-9A-F]{2}\s+call (?:[a-z]+,)?([\w$]+)',row)
            if not match or match[2] not in names|aliases.keys():continue
            address=int(match[1],16);name=aliases.get(match[2],match[2])
            lines.extend([f'debug set_bp {address} {{$::phase eq "game"}} {{set ::profile_{name} [machine_info time]}}',
                f'debug set_bp {address+3} {{$::phase eq "game" && [info exists ::profile_{name}]}} {{puts $::profile_out "{name} $::frames [expr {{([machine_info time]-$::profile_{name})*3579545}}] [debug read memory 0xe1b0]"}}'])
            if name=='stage_stream':
                lines.extend([
                    f'debug set_bp {address} {{$::phase eq "game"}} {{set ::stream_before [list [machine_info time] [debug read memory 0xc0b6] [debug read memory 0xc0b7] [debug read memory {syms["Stage_GuardClosed"]}] [debug read memory {syms["raster_phase"]}]]}}',
                    f'debug set_bp {address+3} {{$::phase eq "game" && [debug read memory 0xc7d0]==0 && [debug read memory 0xc490]==0 && [debug read memory 0xc724]==0 && [info exists ::stream_before]}} {{puts $::stream_out "$::frames [debug read memory 0xe1b0] [debug read memory 0xc472] $::stream_before [machine_info time] [debug read memory 0xc0b6] [debug read memory 0xc0b7] [debug read memory {syms["Stage_GuardClosed"]}] [debug read memory {syms["raster_phase"]}]"}}',
                ])
    if args.trace_di:
        lines.extend(['set di_out [open [file join $out di.tsv] w]',
            'proc di_begin {} {set ::di_begin [machine_info time];set ::di_pc [reg PC]}',
            'proc di_end {} {if {[info exists ::di_begin]} {set cycles [expr {([machine_info time]-$::di_begin)*3579545}];if {$cycles>500} {puts $::di_out "$::frames $::di_pc [reg PC] $cycles"};unset ::di_begin}}'])
        seen=set()
        for row in (bundle/'raster-scroll.lst').read_text().splitlines():
            match=re.search(r'[+\s]([0-9A-F]{4}) (F3|FB)\s+(di|ei)\b',row)
            if not match:continue
            address=int(match[1],16)
            if address in seen or 0x8000<=address<0xc000:continue
            seen.add(address)
            condition='$::phase eq "game" && ![debug read memory 0xc5c1] && [debug read memory 0xc7d0]==0'
            if match[3]=='di':condition+=' && ([reg IFF]&1)'
            lines.append(f'debug set_bp {address} {{{condition}}} {{di_{"begin" if match[3]=="di" else "end"}}}')
    if args.radar_trace:
        script=script.replace('exit 0','set f [open [file join $::out radar-counts.txt] w];puts $f "$::radar_samples $::radar_mismatches $::fuel_samples $::fuel_mismatches $::footer_samples $::footer_mismatches $::player_samples $::player_mismatches";close $f;exit 0')
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=240,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=[list(map(int,line.split())) for line in (out/'events.tsv').read_text().splitlines()]
    if not rows or max(r[1] for r in rows)<args.rounds+2:raise ValueError('Natural round completion evidence missing')
    headers=verify_header_reservations(out/'headers.tsv',313*228/3579545)
    radar=None
    if args.radar_trace:
        samples,mismatches,fuel_samples,fuel_mismatches,footer_samples,footer_mismatches,player_samples,player_mismatches=map(int,(out/'radar-counts.txt').read_text().split())
        radar=dict(samples=samples,mismatches=mismatches,player_dot='Full_RadarIRQ.point' in syms,
            fuel_samples=fuel_samples,fuel_mismatches=fuel_mismatches,
            footer_samples=footer_samples,footer_mismatches=footer_mismatches,
            player_samples=player_samples,player_mismatches=player_mismatches,
            scope='Live SAT before each band fetch against actual latched R23; dot uses its IRQ point snapshot')
        if args.require_stable_radar and (mismatches or not samples):raise ValueError('Fixed radar missed its scanline-coherence gate')
        if args.require_stable_fuel and (fuel_mismatches or not fuel_samples or footer_mismatches or not footer_samples):raise ValueError('Fuel/footer sprites missed their scanline-coherence gate')
        if args.require_stable_player and (player_mismatches or not player_samples):raise ValueError('Player sprites missed their fixed-centre scanline gate')
    verify_manifest(bundle)
    cadence=analyze_cadence(out/'cadence.tsv')
    if args.record_round and not (out/'scanout.avi').is_file():raise ValueError('Requested scanout recording is missing')
    camera_motion=analyze_scroll(out/'camera.tsv') if args.radar_trace else None
    scroll_passed=args.maximum_scroll_step is None or camera_motion['maximum_vertical_step']<=args.maximum_scroll_step
    cadence_passed=args.minimum_native_hz is None or all(r['native_hz']>=args.minimum_native_hz for r in cadence['rounds'] if r['active_seconds']>=5)
    presentation_passed=args.minimum_presentation_hz is None or all(r['presentation_loop_hz']>=args.minimum_presentation_hz for r in cadence['rounds'] if r['active_seconds']>=5)
    moving_rounds=[r for r in camera_motion['moving_vertical_rounds'] if r['moving_seconds']>=2] if camera_motion else []
    vertical_passed=args.minimum_vertical_update_hz is None or bool(moving_rounds) and all(r['vertical_update_hz']>=args.minimum_vertical_update_hz for r in moving_rounds)
    clock_rows=[line.split() for line in (out/'clocks.tsv').read_text().splitlines()] if (out/'clocks.tsv').is_file() else []
    clock_evidence=dict(mode='fixed base diagnostic' if args.fixed_base_clock else 'machine controlled',
        native_instruction_samples=len(clock_rows),native_instruction_cpu_hz=sorted({int(row[2]) for row in clock_rows}),
        vdp_frequency_gate='3.58 MHz at every observed sprite upload, command wait and radar IRQ')
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),natural_completed_rounds=args.rounds,cpu_clock=clock_evidence,host_steering_margin=args.steering_margin,
        foreground_loops=len(rows),cadence=cadence,camera_motion=camera_motion,
        recorded_displayed_round=args.record_round,
        scroll_gate=dict(maximum_pixels=args.maximum_scroll_step,passed=scroll_passed),
        cadence_gate=dict(minimum_native_hz=args.minimum_native_hz,passed=cadence_passed),
        presentation_gate=dict(minimum_hz=args.minimum_presentation_hz,passed=presentation_passed),
        vertical_update_gate=dict(minimum_hz=args.minimum_vertical_update_hz,passed=vertical_passed),
        camera_ownership_checks=int((out/'camera-count.txt').read_text()) if 'Full_CameraValidated' in syms else None,
        header_reservations=headers,radar_coherence=radar,maximum_smoke_placements=max(r[6] for r in rows),
        scope='Real keyboard credit/start, steering and smoke; no guest-state writes. Dynamic sprite/cache images require separate scene checks.'))
    require_ignored(root,[x for x in out.rglob('*') if x.is_file()]);seal(out)
    if not cadence_passed:raise ValueError(f'Natural route missed its native simulation cadence gate; evidence retained at {out}/report.json')
    if not scroll_passed:raise ValueError(f'Natural route missed its vertical scroll gate; evidence retained at {out}/report.json')
    if not presentation_passed:raise ValueError(f'Natural route missed its presentation gate; evidence retained at {out}/report.json')
    if not vertical_passed:raise ValueError(f'Natural route missed its physical camera cadence gate; evidence retained at {out}/report.json')
    print(f'{args.rounds} naturally completed rounds: {out}/report.json')


if __name__=='__main__':main()
