"""Exhaustive synthetic logical-bank/AF/IFF ABI and cycle check in openMSX."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from compact_game_build import symbols
from src.toolchain.msx.emulator import reference_machine,tcl

ROOT=Path(__file__).resolve().parents[1]


def fast_mapper_source():
    """Logical A lookup, preserving all registers/flags/IFF and selecting FE.

    Add the table low byte to A, then carry into its high byte. DE is never
    touched, saving its stack pair and20 Z80 cycles versus the generic helper.
    No alignment, scratch or new mapping is needed; table IDs remain0..124.
    """
    return '''Compact_Map16:
 push af
 push hl
Mapper512_RawEnter:
 ld hl,Compact_Banks
 add a,l
 ld l,a
 ld a,0
 adc a,h
 ld h,a
 ld a,(hl)
 out ($fe),a
 pop hl
 pop af
 ret
Compact_MapPair:
 jp Compact_Map16
'''


def verify():
    out=ROOT/'references/build/game-mapper512-mapper-abi';out.mkdir(parents=True,exist_ok=True)
    source=''' OUTPUT "probe.bin"
 ORG $c300
Control:
 push af
 push hl
 push de
 ld e,a
 ld d,0
 ld hl,Compact_Banks
 add hl,de
 ld a,(hl)
 out ($fe),a
 pop de
 pop hl
 pop af
 ret
'''+fast_mapper_source()+'''Compact_Banks EQU $c6b8
'''
    (out/'probe.asm').write_text(source)
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo','--sym=probe.sym','probe.asm'],cwd=out,check=True,capture_output=True)
    s=symbols(out/'probe.sym')
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
reset
set ::bank 0;set ::flags 0;set ::iff 0;set ::variant 0;set ::cases 0
set ::costs {{}};set ::begin 0
proc enter {{}} {{
 reg IFF 0
 reg AF [expr {{$::bank*256+$::flags}}]
 foreach {{r v}} {{BC 17767 DE 35243 HL 52719 IX 4660 IY 43981 AF2 777 BC2 888 DE2 999 HL2 1111}} {{reg $r $v}}
 reg SP 62208
 debug write memory 62208 0;debug write memory 62209 241
 reg PC [lindex {{{s['Control']} {s['Compact_Map16']}}} $::variant]
 reg IFF $::iff
 set ::expected_iff [reg IFF]
 set ::begin [machine_info time]
}}
debug set_bp 0xf100 {{}} {{
 if {{[catch {{
  set cycles [expr {{([machine_info time]-$::begin)*3579545}}]
  set expected [expr {{$::variant?116:136}}]
  if {{abs($cycles-$expected)>.01}} {{error "Cycle mismatch $cycles vs $expected"}}
  if {{[reg AF]!=$::bank*256+$::flags || [reg SP]!=62210 || [reg IFF]!=$::expected_iff || [debug read ioports 254]%32!=($::bank*7+3)%32}} {{error "Mapper/AF/SP/IFF changed: AF=[reg AF] SP=[reg SP] IFF=[reg IFF] bank=[debug read ioports 254]"}}
  foreach {{r v}} {{BC 17767 DE 35243 HL 52719 IX 4660 IY 43981 AF2 777 BC2 888 DE2 999 HL2 1111}} {{if {{[reg $r]!=$v}} {{error "Clobbered $r"}}}}
  incr ::cases;incr ::variant
  if {{$::variant==2}} {{set ::variant 0;incr ::iff}}
  if {{$::iff==2}} {{set ::iff 0;incr ::flags}}
  if {{$::flags==256}} {{set ::flags 0;incr ::bank}}
  if {{$::bank==125}} {{puts stderr "PASS mapper ABI cases=$::cases control=136 candidate=116";exit}}
  enter
 }} e]}} {{puts stderr "FAIL $e bank=$::bank flags=$::flags iff=$::iff variant=$::variant";exit 2}}
}}
after time 5 {{
 reg IFF 0
 debug write {{VDP regs}} 1 2
 set f [open {tcl(out/'probe.bin')} rb];debug write_block memory 49920 [read $f];close $f
 for {{set i 0}} {{$i<125}} {{incr i}} {{debug write memory [expr {{50872+$i}}] [expr {{($i*7+3)%32}}]}}
 enter
}}
after time 40 {{puts stderr "FAIL timeout cases=$::cases";exit 3}}
'''
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='512',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    p=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=90)
    (out/'output.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0,p.stderr
    report=dict(passed=True,cases=125*256*2*2,logical_ids=125,af_flag_values=256,iff_values=2,control_cycles=136,candidate_cycles=116,saved_cycles_per_call=20,
                reference_hz=3579545,scope='Synthetic cross-page table; real MSX Z80 elapsed helper entry-to-RET, all primary/alternate registers, SP and IFF. No IRQ/NMI source during isolated probe; no gameplay FPS claim.',
                source_sha256=hashlib.sha256(source.encode()).hexdigest())
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':verify()
