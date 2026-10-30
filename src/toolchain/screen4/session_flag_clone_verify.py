"""Actual 64 KiB actor/flag clone bytes, scratch ownership and isolated cost.

Synthetic source bytes and RAM fixtures; no original payload is published.
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


def verify(bundle):
    if configure(bundle)!=64:raise ValueError('This fixture targets the 64 KiB clone API')
    bundle=Path(bundle).resolve();out=Path(tempfile.mkdtemp(prefix='flag-clone-',dir=bundle))
    rom=(cartridge_path(bundle)).read_bytes();(out/'measured.rom').write_bytes(rom)
    s={n:int(v,16) for n,v in re.findall(r'(?m)^(\S+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    from session_reference import runtime_symbols,runtime_guard
    runtime_symbols(s)
    stub=bytes((243,49,224,242,205,s['GameSession_CloneFlag']&255,s['GameSession_CloneFlag']>>8,195,0,241))
    script=f'''
set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set limitsprites true
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking clone_fixture
set phase boot;set age 0;set presents 0;set started 0;set index 0
set input {{}}
for {{set n 0}} {{$n<2048}} {{incr n}} {{lappend input [expr {{($n*17+($n/256)*31)&255}}]}}
set input [binary format cu* $input]
set fill [string repeat [binary format c 165] 512]
set costs [open {tcl(out/'costs.tsv')} w]
proc nextcase {{}} {{
 if {{$::index==640}} {{close $::costs;puts stderr CLONE_PASS;exit 0;return}}
 set ::record [expr {{$::index/80}}];set ::glyph [expr {{($::index/8)%10}}];set ::actor [expr {{$::index%8}}]
 debug write_block memory 0x3800 $::input
 debug write_block memory 0x2400 $::fill
 debug write memory 0xc027 $::record
 set ::expected $::fill
 set source [expr {{$::record*256+52+$::glyph*8}}];set target [expr {{$::actor*8}}]
 set ::expected [string replace $::expected $target [expr {{$target+7}}] [string range $::input $source [expr {{$source+7}}]]]
 set ::expected [string replace $::expected [expr {{$target+256}}] [expr {{$target+263}}] [string range $::input [expr {{$source+80}}] [expr {{$source+87}}]]]
 reg BC [expr {{$::actor*256+$::glyph+50}}];reg IX 13579;reg IY 24680
 reg PC 0xf000
}}
debug set_bp {s['GameSession_CloneFlag']} {{$::started}} {{set ::begin [machine_info time]}}
debug set_bp 0xf007 {{$::started}} {{
 if {{[debug read_block memory 0x2400 512] ne $::expected || [debug read_block memory 0x3800 2048] ne $::input || [reg SP]!=0xf2e0 || [reg IX]!=13579 || [reg IY]!=24680}} {{puts stderr "Clone byte/ownership mismatch case=$::index";exit 2}}
 puts $::costs [expr {{([machine_info time]-$::begin)*3579545}}]
 incr ::index;nextcase
}}
debug set_bp {s['frame_done']} {{!$::started && ({runtime_guard(bundle)})}} {{
 incr ::presents
 if {{$::phase eq "start" && [debug read memory 0xc7d0]==0 && $::presents>5}} {{
  set ::started 1;debug write_block memory 0xf000 [binary format H* {stub.hex()}];nextcase
 }}
}}
proc poll {{}} {{
 if {{$::started}} {{return}}
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
after time 120 {{puts stderr CLONE_TIMEOUT;exit 3}}
'''
    (out/'probe.tcl').write_text(script)
    with (out/'openmsx.log').open('w') as log:
        run=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],stdout=log,stderr=subprocess.STDOUT,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    if run.returncode or 'CLONE_PASS' not in (out/'openmsx.log').read_text():
        raise AssertionError(str(out)+'\n'+(out/'openmsx.log').read_text()[-2000:])
    costs=list(map(float,(out/'costs.tsv').read_text().split()));assert len(costs)==640
    report=dict(passed=True,cases=640,rom_sha256=hashlib.sha256(rom).hexdigest(),path=str(out),
                cycles=dict(mean=statistics.mean(costs),min=min(costs),max=max(costs)),
                scope='Actual CloneFlag entry-through-RET, IRQ disabled; eight CPU records x ten source glyphs x eight actor slots. Complete destination512 bytes, unchanged source2048 bytes, SP and IX/IY verified. AF/BC/DE/HL are caller-clobbered; the real caller restores BC. Synthetic data, not active FPS.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/build/game')
    verify(p.parse_args().bundle)
