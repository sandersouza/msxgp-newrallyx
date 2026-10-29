"""Exercise actual key input and retain complete raw frames from openMSX."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import json
import hashlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.msx.emulator import reference_machine, scanout_recording_tcl, tcl

BASE=ROOT/'references/experiments/fixed-hud'
OUT=Path(tempfile.mkdtemp(prefix='probe-',dir=BASE))
mode='matrix' if '--matrix' in sys.argv else 'continuous' if '--continuous' in sys.argv else 'keyboard'
cases=[(264+fx,1032+fy) for fy in range(8) for fx in range(8)]
cases += [(x,y) for x in (0,1,7,8,511,512,605,611,612,615,616)
          for y in (0,1,7,8,63,64,127,128,255,256,1173,1179,1180)]
cases += [(271,1032+i%8) for i in range(16)]
cases += [(272,1032)]  # Eighth-pixel reset must use the same edge policy.
(OUT/'metadata.json').write_text(json.dumps(dict(mode=mode,
    rom_sha256=hashlib.sha256((BASE/'fixed-hud.rom').read_bytes()).hexdigest(),
    cases=cases if mode=='matrix' else None),indent=2)+'\n')
symbols={name:int(value,16) for name,value in re.findall(r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)',
                                                       (BASE/'lab.sym').read_text(),re.M)}
script=f'''
set save_settings_on_exit false
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
set speed 100
set throttle off
set z80_freq 3579545
set z80_freq_locked true
set gamma 1.0
set brightness 0
set contrast 0
set color_matrix {{{{1 0 0}} {{0 1 0}} {{0 0 1}}}}
set scanline 0
set blur 0
set noise 0
set minframeskip 0
set maxframeskip 0
cart {tcl(BASE/'fixed-hud.rom')} -romtype ASCII16
reset
{scanout_recording_tcl(OUT, symbols['boot'])}
set out {tcl(OUT)}
set log [open [file join $out frames.tsv] w]
set n 0
set matrix_mode {int(mode=='matrix')}
set continuous_mode {int(mode=='continuous')}
set cases {{{' '.join('{'+str(x)+' '+str(y)+'}' for x,y in cases)}}}
set case_index 0
set register_low -1
set register_writes 0
set vram_writes 0
set full_cache_rebuilds 0
set full_name_uploads 0
set world_ids_requested 0
set max_world_ids_per_update 0
set previous_world_ids 0
debug set_bp {symbols['Ring_Prepare.full']} {{[debug read memory 0xc00c]==1}} {{incr ::full_cache_rebuilds}}
debug set_bp {symbols['Ring_UploadNames.full']} {{[debug read memory 0xc00c]==1}} {{incr ::full_name_uploads}}
debug set_bp {symbols['Ring_LoadColumns']} {{[debug read memory 0xc00c]==1}} {{incr ::world_ids_requested [expr {{32*[debug read memory 0xc032]}}]}}
debug set_bp {symbols['Ring_Prepare.row']} {{[debug read memory 0xc00c]==1}} {{incr ::world_ids_requested 32}}
proc register_write {{}} {{
    global wp_last_value register_low register_writes
    if {{$register_low<0}} {{set register_low $wp_last_value;return}}
    if {{($wp_last_value&192)==128}} {{
        incr register_writes
        set reg [expr {{$wp_last_value&63}}]
        if {{$reg==46 && $register_low!=0}} {{puts stderr "Unexpected VDP command";exit 2}}
        if {{$reg==8 && !($register_low&2)}} {{puts stderr "Sprites enabled";exit 2}}
    }}
    set register_low -1
}}
proc finish {{}} {{
    set f [open [file join $::out traffic.json] w]
    puts $f [format {{{{"vram_writes":%d,"register_writes":%d,"vdp_commands":0,"sprites_enabled":false,"full_cache_rebuilds":%d,"full_name_uploads":%d,"world_ids_requested":%d,"max_world_ids_per_update":%d}}}} $::vram_writes $::register_writes $::full_cache_rebuilds $::full_name_uploads $::world_ids_requested $::max_world_ids_per_update]
    close $f;close $::log;close $::timing;exit
}}
set timing [open [file join $out render.tsv] w]
set VDP.too_fast_vram_access_callback {{
    if {{[debug read memory 0xc00c] == 1}} {{puts stderr "VRAM timing violation";exit 2}}
}}
debug set_bp {symbols['render']} {{}} {{set ::render_start [machine_info time]}}
debug set_bp {symbols['render.hud']} {{}} {{set ::hud_start [machine_info time]}}
debug set_bp {symbols['radar']} {{}} {{set ::upload_start [machine_info time]}}
debug set_bp {symbols['render_done']} {{}} {{
    puts $::timing "[debug read memory 0xc004] [debug read memory 0xc005] [expr {{($::hud_start-$::render_start)*1000}}] [expr {{($::upload_start-$::hud_start)*1000}}] [expr {{([machine_info time]-$::upload_start)*1000}}]"
}}
proc word {{a}} {{expr {{[debug read memory $a]+256*[debug read memory [expr {{$a+1}}]]}}}}
proc capture {{n x y}} {{
    screenshot -raw -size auto [file join $::out frame-$n.png]
    set f [open [file join $::out frame-$n.vram] wb]
    puts -nonewline $f [debug read_block VRAM 0 65536]
    close $f
}}
debug set_bp {symbols['frame_done']} {{}} {{
    incr ::n
    set requested [expr {{$::world_ids_requested-$::previous_world_ids}}]
    set ::max_world_ids_per_update [expr {{max($requested,$::max_world_ids_per_update)}}]
    set ::previous_world_ids $::world_ids_requested
    if {{$::n==1}} {{
        if {{!([debug read {{VDP regs}} 8]&2)}} {{puts stderr "Sprites enabled at startup";exit 2}}
        debug set_watchpoint write_io {{0x99}} {{}} {{register_write}}
        debug set_watchpoint write_io {{0x9b}} {{}} {{puts stderr "Unexpected indirect VDP write";exit 2}}
        debug set_watchpoint write_io {{0x98}} {{}} {{incr ::vram_writes}}
    }}
    set x [word 0xc000]; set y [word 0xc002]
    puts $::log "$::n [machine_info time] $x $y [debug read memory 0xc00a] [debug read memory 0xc026] [word 0xc024] [debug read memory 0xc00b]"
    if {{($::continuous_mode && $::n>=4 && $::n<=308) || ($::matrix_mode && $::n%4==0) || (!$::matrix_mode && !$::continuous_mode && $::n in {{4 8 12 16 20 24 28 32 40 48 56 64 72 80}})}} {{
        after frame [list capture $::n $x $y]
    }}
    keymatrixup 8 255
    keymatrixup 6 1
    if {{$::continuous_mode}} {{
        if {{$::n<48}} {{keymatrixdown 8 192}} elseif {{$::n<96}} {{keymatrixdown 8 48}} elseif {{$::n<160}} {{keymatrixdown 8 128;keymatrixdown 6 1}} elseif {{$::n<224}} {{keymatrixdown 8 64;keymatrixdown 6 1}} elseif {{$::n<260}} {{keymatrixdown 8 16;keymatrixdown 6 1}} elseif {{$::n<292}} {{keymatrixdown 8 32;keymatrixdown 6 1}}
    }} elseif {{$::matrix_mode && $::n%4==0}} {{
        incr ::case_index
        if {{$::case_index>=[llength $::cases]}} {{after time 0.1 finish}} else {{
            lassign [lindex $::cases $::case_index] xx yy
            debug write memory 0xc000 [expr {{$xx&255}}]
            debug write memory 0xc001 [expr {{$xx>>8}}]
            debug write memory 0xc002 [expr {{$yy&255}}]
            debug write memory 0xc003 [expr {{$yy>>8}}]
        }}
    }} elseif {{!$::matrix_mode && $::n%4==0}} {{
        if {{$::n<32}} {{keymatrixdown 8 128}} elseif {{$::n<48}} {{keymatrixdown 8 64;keymatrixdown 6 1}} elseif {{$::n<64}} {{keymatrixdown 8 16}} elseif {{$::n<80}} {{keymatrixdown 8 32}}
    }}
    if {{(!$::matrix_mode && !$::continuous_mode && $::n==84) || ($::continuous_mode && $::n==312)}} {{finish}}
}}
after time 90 {{puts stderr "ROM probe timed out";exit 2}}
'''
(OUT/'probe.tcl').write_text(script)
env=dict(os.environ,OPENMSX_HOME=str(OUT/'home'),OPENMSX_USER_DATA=str(OUT/'userdata'))
with (OUT/'openmsx.log').open('w') as log:
    subprocess.run(['openmsx','-script',str(OUT/'probe.tcl')],env=env,
                   stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True)
(BASE/'last-probe.txt').write_text(str(OUT)+'\n')
assert json.loads((OUT/'traffic.json').read_text())['vram_writes']>0
print(OUT)
