"""Execute real64 KiB cache code for every phase/flag mask/blink combination.

Synthetic native-cell positions, real ROM/HUD data and VDP timing. Original
records/results stay ignored. Compare active glyph bytes and all name bytes,
not unused cache padding. This is a component fixture, not natural gameplay.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.msx.emulator import reference_machine,tcl
from session_reference import configure


def records(layout):
    positions=([(i*3,i*6) for i in range(10)] if layout=='scattered' else
               [(i,0) for i in range(5)]+[(i+25,55) for i in range(5)])
    data=bytearray()
    for i,(x,y) in enumerate(positions):
        cell=0x9800+y*32+x
        data.extend((cell&255,cell>>8,2 if i==9 else 4 if i==8 else 1,i,x*3+3,y*3+3))
    return data


def run(bundle,layout):
    bundle=Path(bundle).resolve()
    if configure(bundle)!=64:raise ValueError('This fixture targets the64 KiB cache API')
    out=Path(tempfile.mkdtemp(prefix='flag-cache-'+layout+'-',dir=bundle))
    rom=(bundle/'fixed-hud.rom').read_bytes();(out/'measured.rom').write_bytes(rom)
    s={n:int(v,16) for n,v in re.findall(r'(?m)^(\S+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    # All guest writes below belong to this explicitly synthetic component
    # fixture. Neither cartridge code nor immutable resource banks are patched.
    script=f'''
set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set minframeskip 0
set maxframeskip 0
set limitsprites true
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking flag_cache_component
set VDP.too_fast_vram_access_callback {{puts stderr "VRAM timing violation PC=[reg PC]";exit 2}}
set records [binary format H* {records(layout).hex()}]
set output [open {tcl(out/'records.bin')} wb]
set costs [open {tcl(out/'costs.tsv')} w]
fconfigure $output -translation binary
set phase boot;set age 0;set presents 0;set prepared 0;set index 0;set stage init
set clear {s['GameSession_ClearFlags']};set names {s['GameSession_FlagNames']}
set remove {s['GameSession_RemoveFlag']};set build {s['GameSession_BuildFlags']}
set phasebank {s['GameSession_PhaseBank']};set active {s['Flag_Active']+1}
set flagindex {s['GameSession_FlagIndex']}
proc callbytes {{address}} {{list 205 [expr {{$address&255}}] [expr {{$address>>8}}]}}
proc execute {{body}} {{
 set bytes [concat {{49 224 242}} $body {{195 0 241}}]
 debug write_block memory 0xf000 [binary format cu* $bytes]
 set ::begin_cycle [machine_info time]
 reg PC 0xf000
}}
proc begin {{}} {{
 set ::prepared 1
 debug write_block memory 0xdf80 $::records
 debug write_block memory $::active [string repeat [binary format c 1] 10]
 # Cold cache build with display off, then exercise real SCREEN4 display-on
 # read/write pacing across every raster position with the strict callback.
 execute [concat {{243 62 2 211 153 62 129 211 153}} [callbytes $::build] {{243 62 98 211 153 62 129 211 153 251}}]
}}
proc snapshot {{}} {{
 set at [expr {{0x3800+$::slot*256}}]
 set value [debug read_block memory $at 212]
 append value [debug read_block memory 0xd400 1024]
 set packed [zlib compress $value]
 puts $::output [string length $packed]
 puts -nonewline $::output $packed
}}
proc nextcase {{}} {{
 if {{$::index==131072}} {{close $::output;close $::costs;puts stderr "FLAG_CACHE_PASS states=262144";exit 0;return}}
 set ::mask [expr {{$::index&1023}}]
 set fine [expr {{$::index/2048}}];set ::blink [expr {{($::index/1024)%2*16}}]
 set ::slot [expr {{($fine+$::mask+$::blink/16)&7}}]
 foreach {{address value}} [list 0xc01d $fine 0xc004 [expr {{$fine&7}}] 0xc005 [expr {{$fine/8}}] 0xc027 $::slot 0xc0f6 $::blink] {{debug write memory $address $value}}
 for {{set i 0}} {{$i<10}} {{incr i}} {{debug write memory [expr {{$::active+$i}}] [expr {{($::mask>>$i)&1}}]}}
 debug write_block memory 0xd400 [string repeat [binary format c 0] 1024]
 set ::stage cold
 execute [concat [callbytes $::clear] [callbytes $::phasebank] [callbytes 41728] [callbytes $::names]]
}}
proc returned {{}} {{
 puts $::costs "$::stage [expr {{([machine_info time]-$::begin_cycle)*3579545}}]"
 switch $::stage {{
  init {{nextcase}}
  cold {{
   snapshot
   debug write_block memory $::active [string repeat [binary format c 1] 10]
   debug write memory 0xc0f6 [expr {{$::blink^16}}]
   set ::stage reload
   execute [concat [callbytes $::clear] [callbytes $::names]]
  }}
  reload {{
   set body {{}}
   for {{set i 0}} {{$i<10}} {{incr i}} {{
    if {{!($::mask&(1<<$i))}} {{
     debug write memory [expr {{$::active+$i}}] 0
     lappend body 62 $i 50 [expr {{$::flagindex&255}}] [expr {{$::flagindex>>8}}]
     set body [concat $body [callbytes $::remove]]
    }}
   }}
   debug write memory 0xc0f6 $::blink
   set ::stage warm
   execute [concat $body [callbytes $::names]]
  }}
  warm {{
   snapshot;incr ::index
   if {{$::index%16384==0}} {{puts stderr "FLAG_CACHE_PROGRESS cases=$::index";flush stderr}}
   nextcase
  }}
 }}
}}
debug set_bp 0xf100 {{$::prepared}} {{if {{[catch returned problem]}} {{puts stderr $problem;exit 2}}}}
debug set_bp {s['frame_done']} {{!$::prepared}} {{incr ::presents;if {{$::phase eq "start" && [debug read memory 0xc7d0]==0 && $::presents>5}} {{begin}}}}
proc poll {{}} {{
 if {{$::prepared}} {{return}}
 incr ::age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
  boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
  coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
  start {{if {{$::age==5}} {{keymatrixup 0 2}}}}
 }}
 after time 0.02 poll
}}
after time 0.02 poll
after time 7200 {{puts stderr "Flag cache fixture timed out";exit 3}}
'''
    (out/'probe.tcl').write_text(script)
    with (out/'openmsx.log').open('w') as log:
        result=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')),timeout=900)
    if result.returncode or 'FLAG_CACHE_PASS' not in (out/'openmsx.log').read_text():
        raise AssertionError(str(out)+'\n'+(out/'openmsx.log').read_text()[-2000:])
    return out


def samples(path):
    with Path(path).open('rb') as stream:
        while header:=stream.readline():
            data=zlib.decompress(stream.read(int(header)))
            if len(data)!=1236:raise ValueError('Truncated component record')
            count=data[0]
            yield data[:1]+data[1:2+count*5]+data[52:52+count*8]+data[132:132+count*8]+data[212:]


def compare(before,after):
    from itertools import zip_longest
    count=0
    for index,(a,b) in enumerate(zip_longest(samples(before/'records.bin'),samples(after/'records.bin'))):
        if a!=b:raise AssertionError(f'Cache mismatch case={index//2} mode={index%2}')
        count+=1
    if count!=262144:raise AssertionError(f'Incomplete component matrix: {count}')
    return count


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--layout',choices=['scattered','clustered'],default='scattered')
    args=parser.parse_args();out=run(args.bundle,args.layout)
    states=compare(args.baseline,out) if args.baseline else 262144
    result=dict(passed=True,states=states,phases=64,masks=1024,blink_states=2,cache_paths=['cold','warm after native RemoveFlag'],layout=args.layout,
        rom_sha256=hashlib.sha256((out/'measured.rom').read_bytes()).hexdigest(),baseline=str(args.baseline) if args.baseline else None,path=str(out),
        scope='Explicit synthetic position/mask fixtures. Active name program, every used glyph byte and all1024 name RAM bytes compared; strict real VDP callback. Not natural gameplay or physical hardware.')
    import statistics,math
    groups={}
    for line in (out/'costs.tsv').read_text().splitlines():
        name,value=line.split();groups.setdefault(name,[]).append(float(value))
    result['costs']={name:dict(calls=len(v),min=min(v),mean=statistics.mean(v),p95=sorted(v)[math.ceil(len(v)*.95)-1],max=max(v)) for name,v in groups.items()}
    result['cost_scope']='Guest elapsed inclusive cycles for each non-overlapping fixture stub, including CALL/RET/IRQ and common setup; init is a cold64-phase build. These controlled component fixtures are not active-frame costs.'
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
