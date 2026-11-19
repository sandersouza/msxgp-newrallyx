"""Verify actual linked exact workers against the retained transfer kernel.

Diagnostic-only RAM/VRAM fixtures begin after real keyboard startup. No game
bytes are embedded. Every length, both IFF states and both VRAM table sets
compare all VRAM plus the published BC/HL/DE/IX/IY/SP/IFF contract.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from compact_game_build import symbols
from compact_transfer import old_long_cycles,exact_long_cycles
from src.toolchain.msx.emulator import reference_machine,tcl


def verify():
    bundle=ROOT/'references/build/game-compact-runtime'
    rom=bundle/'newrallyx.rom';syms=symbols(bundle/'lab.sym')
    out=Path(tempfile.mkdtemp(prefix='exact-transfer-proof-',dir=bundle))
    cases=[(n,iff,back) for n in range(2,256) for iff in range(2) for back in range(2)]
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set cmdtiming real
set limitsprites true
set z80_freq 3579545
set z80_freq_locked true
source [file join $::env(OPENMSX_SYSTEM_DATA) scripts _disasm.tcl]
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(rom)} -romtype ASCII8
reset
set ::started 0;set ::index 0;set ::stage 0;set ::fast 0;set ::phase boot;set ::age 0
set ::cases {{{' '.join('{%d %d %d}'%c for c in cases)}}}
set ::seed [binary format c* [lmap i [lrepeat 256 0] {{set i}}]]
set data {{}};for {{set i 0}} {{$i<256}} {{incr i}} {{lappend data [expr {{($i*73+19)&255}}]}}
set ::seed [binary format c* $data]
set ::poison [binary format c* [lrepeat 131072 238]]
set ::timing [open {tcl(out/'cycles.tsv')} w]
set VDP.too_fast_vram_access_callback {{if {{$::started}} {{incr ::fast}}}}
proc issue {{}} {{
 if {{$::index==[llength $::cases]}} {{close $::timing;puts stderr "PASS exact workers cases=$::index strict=$::fast";exit;return}}
 lassign [lindex $::cases $::index] n iff back
 debug write {{VDP regs}} 1 66
 debug write_block VRAM 0 $::poison
 debug write_block memory 0xe800 $::seed
 set target [expr {{($n&1)?0x3ff0:0x4200}}]
 set page [expr {{($target>>14)+$back*2}}]
 if {{$n<16}} {{
  set helper {{}};for {{set j 0}} {{$j<15}} {{incr j}} {{lappend helper 237 163}};lappend helper 201
  debug write_block memory 0xf200 [binary format c* $helper]
  set entry [expr {{$::stage?{syms['Compact_ExactShortEnd']}-2*$n:0xf200+2*(15-$n)}}]
  set b 165
 }} else {{
  set entry [expr {{$::stage?($n<=64?{syms['Compact_ExactTailEnd']}-2*$n:{syms['Compact_ExactHead']}+2*(255-$n)):{syms['GamePacketFast_Transfer']}}}]
  set b [expr {{$::stage?165:$n}}]
 }}
 set code [list 243 49 128 243 62 $page 211 153 62 142 211 153 62 [expr {{$target&255}}] 211 153 62 [expr {{(($target>>8)&63)|64}}] 211 153 33 0 232 1 152 $b 17 254 202 221 33 103 69 253 33 137 103]
 if {{$iff}} {{lappend code 251 0}}
 while {{[llength $code]<64}} {{lappend code 0}}
 lappend code 205 [expr {{$entry&255}}] [expr {{$entry>>8}}] 0
 while {{[llength $code]<144}} {{lappend code 0}}
 debug write_block memory 0xf000 [binary format c* $code]
 reg IFF 0;reg PC 0xf000
}}
debug set_bp 0xf040 {{$::started}} {{set ::begin [machine_info time]}}
debug set_bp 0xf043 {{$::started}} {{
 lassign [lindex $::cases $::index] n iff back
 set ::elapsed [expr {{([machine_info time]-$::begin)*3579545}}]
 set bc [expr {{$n>=16?152:(((165-$n)&255)*256+152)}}]
 if {{[reg BC]!=$bc || [reg HL]!=0xe800+$n || [reg DE]!=0xcafe || [reg IX]!=0x4567 || [reg IY]!=0x6789 || [reg SP]!=0xf380 || ([reg IFF]&1)!=$iff}} {{puts stderr "ABI FAIL n=$n iff=$iff back=$back stage=$::stage BC=[reg BC] HL=[reg HL] SP=[reg SP] IFF=[reg IFF]";exit 3;return}}
 reg PC 0xf080
}}
debug set_bp 0xf090 {{$::started}} {{
 lassign [lindex $::cases $::index] n iff back
 set elapsed $::elapsed
 set at [expr {{(($n&1)?0x3ff0:0x4200)+$back*32768}}]
 set expected [string replace $::poison $at [expr {{$at+$n-1}}] [string range $::seed 0 [expr {{$n-1}}]]]
 if {{[debug read_block VRAM 0 131072] ne $expected}} {{puts stderr "VRAM FAIL n=$n stage=$::stage actual=[binary encode hex [debug read_block VRAM $at $n]] expected=[binary encode hex [string range $::seed 0 [expr {{$n-1}}]]] worker=[binary encode hex [debug read_block memory {syms['Compact_ExactShortEnd']-4} 5]]";set f [open {tcl(out/'failed.vram')} wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f;exit 4;return}}
 if {{!$::stage}} {{set ::old $elapsed;set ::stage 1}} else {{puts $::timing "$n $iff $back $::old $elapsed";incr ::index;set ::stage 0}}
 issue
}}
debug set_bp {syms['GameTurbo_FrameDone']} {{!$::started && $::phase eq "active"}} {{set ::started 1;issue}}
proc poll {{}} {{
 if {{$::started}} return
 incr ::age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{if {{$::age==5}} {{keymatrixup 0 2}};if {{$state==0 && [debug read memory 0xc00c]}} {{set ::phase active}}}}
 }}
 after time 0.02 poll
}}
after time 0.02 poll
after time 120 {{puts stderr "TIMEOUT exact workers index=$::index stage=$::stage PC=[reg PC]";exit 2}}
'''
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='64',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    r=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=120)
    (out/'output.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and f'PASS exact workers cases={len(cases)} strict=0' in r.stderr,r.stderr[-2000:]
    rows=[list(map(float,line.split())) for line in (out/'cycles.tsv').read_text().splitlines()]
    assert len(rows)==len(cases)
    for n,iff,back,old,new in rows:
        n=int(n)
        if n>=16:
            assert abs(old+8-old_long_cycles(n))<1.01,(n,old,old_long_cycles(n))
            assert abs(new-exact_long_cycles(n))<1.01,(n,new,exact_long_cycles(n))
        else:assert abs(old-new)<1.01,(n,old,new)
    report=dict(passed=True,rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),cases=len(cases),strict_vram_callbacks=0,
        lengths='2..255',iff=[0,1],back_tables=2,cycle_model_verified=True,
        scope='Real linked workers after keyboard startup; isolated synthetic display-on transfers. Long measurement includes CALL but adds original LD B,n only to the old cycle model; short worker CALL overhead is budgeted separately by the optimizer. All128KiB VRAM, BC/HL/DE/IX/IY/SP/IFF compared. VDP IRQ generation off for isolated cycles; gameplay IRQs covered separately.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':verify()
