"""Real ROM motion-snapshot predicate, bounded-step safety and buffer ownership.

Synthetic fine coordinates and native buffers; no gameplay-acceptance claim.
The six-unit bound covers the preserved2.75px challenge speed doubled per packet.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse,hashlib,json,os,re,statistics,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from src.toolchain.msx.emulator import reference_machine,tcl
from session_reference import configure


def verify(bundle,record_baseline=False):
    configure(bundle);bundle=Path(bundle).resolve()
    out=Path(tempfile.mkdtemp(prefix='motion-predicate-',dir=bundle))
    rom=(cartridge_path(bundle)).read_bytes();(out/'measured.rom').write_bytes(rom)
    s={n:int(v,16) for n,v in re.findall(r'(?m)^(\S+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    from session_reference import runtime_symbols,runtime_guard
    runtime_symbols(s)
    stub=bytes((0xf3,0x31,0xe0,0xf2,0xcd,s['Session_SaveMotion']&255,s['Session_SaveMotion']>>8,0xc3,0,0xf1))
    restore=bytes((0xf3,0x31,0xe0,0xf2,0xcd,s['Session_RestoreMotion']&255,s['Session_RestoreMotion']>>8,0xc3,0,0xf1))
    script=f'''
set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking motion_predicate
set phase boot;set age 0;set frames 0;set started 0;set index 0;set unsafe 0
set source1 [binary format cu* {{16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35}}]
set source2 [binary format cu* {{64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87}}]
set fill [string repeat [binary format c -86] 44]
set cases [open {tcl(out/'cases.tsv')} w]
set restores [open {tcl(out/'restores.tsv')} w]
proc nextcase {{}} {{
 if {{$::index==9604}} {{close $::cases;close $::restores;puts stderr "MOTION_DONE unsafe=$::unsafe cases=$::index";exit 0;return}}
 set ::stage save
 debug write_block memory 0xf000 [binary format H* {stub.hex()}]
 set ::x [expr {{$::index%49-24}}];set ::y [expr {{($::index/49)%49-24}}];set ::risk [expr {{$::index/4802*8}}]
 set ::axis [expr {{($::index/2401)%2*255}}]
 debug write_block memory 0xe048 $::source1
 debug write_block memory 0xe068 $::source2
 debug write memory 0xe06d [expr {{$::x&255}}];debug write memory 0xe06f [expr {{$::y&255}}]
 debug write memory 0xe06b $::axis
 debug write memory 0xc7e8 $::risk
 debug write_block memory 0xd200 $::fill
 set ::before [debug read_block memory 0xe048 20];append ::before [debug read_block memory 0xe068 24]
 reg IX 13579;reg IY 24680;reg BC 4660
 reg PC 0xf000
}}
debug set_bp {s['Session_SaveMotion']} {{$::started}} {{set ::begin [machine_info time]}}
debug set_bp {s['Session_RestoreMotion']} {{$::started}} {{set ::begin [machine_info time]}}
debug set_bp 0xf007 {{$::started}} {{
 if {{[reg SP]!=0xf2e0 || [reg IX]!=13579 || [reg IY]!=24680}} {{puts stderr "Motion stack/index ownership violation";exit 2}}
 if {{$::stage eq "restore"}} {{
  set after [debug read_block memory 0xe048 20];append after [debug read_block memory 0xe068 24]
  set expected [string replace $::before 18 19 [binary format H* 3412]]
  set expected [string replace $expected 21 23 [binary format H* 7856ff]]
  set observed_counter [expr {{[debug read memory 0xc7e6]+256*[debug read memory 0xc7e7]}}]
  if {{$after ne $expected || [reg BC]!=0 || $observed_counter!=(($::counter+1)&65535)}} {{puts stderr "Motion restore differs actual=[binary encode hex $after] expected=[binary encode hex $expected] BC=[reg BC] counter=$observed_counter prior=$::counter";exit 2}}
  puts $::restores "$::risk [expr {{([machine_info time]-$::begin)*3579545}}]"
  incr ::index;nextcase
  return
 }}
 set after [debug read_block memory 0xe048 20];append after [debug read_block memory 0xe068 24]
 set saved [debug read memory 0xc7e9]
 set required [expr {{$::risk || (abs($::x)+6>=8 && abs($::y)+6>=8)}}]
 if {{$required && !$saved}} {{incr ::unsafe}}
 if {{$after ne $::before || [reg IX]!=13579 || [reg IY]!=24680 || [reg BC]!=[expr {{$saved?0:4660}}]}} {{puts stderr "Motion input/register ownership violation";exit 2}}
 if {{[debug read_block memory 0xd200 44] ne [expr {{$saved?$::before:$::fill}}]}} {{puts stderr "Motion snapshot bytes differ";exit 2}}
 puts $::cases "$::x $::y $::risk $saved $required [expr {{([machine_info time]-$::begin)*3579545}}] $::axis"
 if {{$saved}} {{
  debug write_block memory 0xe048 [string repeat [binary format c -69] 20]
  debug write_block memory 0xe068 [string repeat [binary format c -69] 24]
  debug write_block memory 0xe05a [binary format H* 3412]
  debug write_block memory 0xe069 [binary format H* 7856ff]
  set ::counter [expr {{$::index%2?65535:65280}}]
  debug write memory 0xc7e6 [expr {{$::counter&255}}];debug write memory 0xc7e7 [expr {{$::counter>>8}}]
  debug write_block memory 0xf000 [binary format H* {restore.hex()}]
  set ::stage restore;reg PC 0xf000
  return
 }}
 incr ::index;nextcase
}}
debug set_bp {s['frame_done']} {{!$::started && ({runtime_guard(bundle)})}} {{
 incr ::frames
 if {{$::phase eq "start" && [debug read memory 0xc7d0]==0 && $::frames>5}} {{
  set ::started 1;debug write_block memory 0xf000 [binary format H* {stub.hex()}];nextcase
 }}
}}
proc poll {{}} {{
 if {{$::started}} {{return}}
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
  boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
  coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
  start {{if {{$::age==5}} {{keymatrixup 0 2}}}}
 }}
 after time 0.02 poll
}}
after time 0.02 poll
after time 90 {{puts stderr "Motion fixture timeout";exit 3}}
'''
    (out/'probe.tcl').write_text(script)
    with (out/'openmsx.log').open('w') as log:
        process=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],stdout=log,stderr=subprocess.STDOUT,
            timeout=150,env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    assert process.returncode==0,(out,(out/'openmsx.log').read_text()[-1500:])
    rows=[list(map(float,line.split())) for line in (out/'cases.tsv').read_text().splitlines()]
    assert len(rows)==9604
    unsafe=[r[:5] for r in rows if r[4] and not r[3]]
    restored=[list(map(float,line.split())) for line in (out/'restores.tsv').read_text().splitlines()]
    result=dict(passed=not unsafe,cases=len(rows),unprotected_reachable_corners=len(unsafe),counterexamples=unsafe[:8],
        rom_sha256=hashlib.sha256(rom).hexdigest(),path=str(out),bounded_contact_margin_units=6,axes=2,
        costs={str(saved):dict(calls=len(v),mean=statistics.mean(v),max=max(v)) for saved in (0,1) if (v:=[r[5] for r in rows if r[3]==saved])},
        shared_risk_snapshot_mean=statistics.mean(r[5] for r in rows if r[2]),
        restore=dict(cases=len(restored),shared_risk_mean=statistics.mean(r[1] for r in restored if r[0]),bytes_heading_velocity_counter_checked=True),
        scope='Actual ROM SaveMotion/RestoreMotion entry-through-RET, IRQ disabled; synthetic signed fine coordinates/risk flags. All44 snapshot/restore bytes, preserved new heading/velocity/centering, counter wrap, SP, BC and IX/IY checked. Component safety/cost, not presented FPS.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    if not record_baseline:assert result['passed'],result
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--record-baseline',action='store_true')
    args=p.parse_args();verify(args.bundle,args.record_baseline)
