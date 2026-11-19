"""Execute bounded cold edge overlays in real512KiB mapper RAM.

Cartridge bootstrap and destructive host fixture injection are explicit. This
qualifies the stage decoder/overlay only, not a cartridge-free game or loader.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from mapper512_backend import prepare
from compact_game_build import symbols
from compact_game_report import distribution
from disk_package import compress_bank,decompress_bank
from mapper512_rank import ranking_basis
from src.toolchain.msx.emulator import reference_machine,tcl


def verify():
    out=ROOT/'references/build/game-mapper512-stage';out.mkdir(parents=True,exist_ok=True)
    assembler=ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'
    assembled=subprocess.run([str(assembler),'--nologo','--sym=decoder.sym',str(ROOT/'src/disk/mapper512-stage.asm')],cwd=out,capture_output=True,text=True)
    assert assembled.returncode==0,assembled.stdout+assembled.stderr
    ranked=subprocess.run([str(assembler),'--nologo','--sym=ranking.sym',str(ROOT/'src/disk/mapper512-ranking.asm')],cwd=out,capture_output=True,text=True)
    assert ranked.returncode==0,ranked.stdout+ranked.stderr
    ranking=(out/'ranking.bin').read_bytes()
    decoder=(out/'decoder.bin').read_bytes();s=symbols(ROOT/'references/build/game-compact-runtime/lab.sym')
    _,records,packed=prepare();raws=[b''.join(packed[n+i][0] for i in range(8)) for n in range(64,96,8)]
    streams=[compress_bank(raw) for raw in raws]
    assert all(decompress_bank(stream)==raw for stream,raw in zip(streams,raws))
    blob=b''.join(streams);assert len(blob)<=16384
    (out/'edges.lz').write_bytes(blob)
    setup=['set ::fixtures {}'];offsets=[];at=0
    for stream in streams:offsets.append(at);at+=len(stream)
    for previous in range(4):
        for target in range(4):
            # Load the previous family, then replace that exact16KiB buffer.
            for stage,kind in [(previous,'prepare'),(target,'transition')]:
                setup.append(f'lappend ::fixtures [list {kind} {previous} {target} {16384+offsets[stage]} {len(streams[stage])} 32768 0 {{}} [binary format H* {raws[stage].hex()}]]')
    overflow=b'\x00A'+b'\xff\x01\x00'*127
    bad=[('truncated',b'\x7fA',16384,32768),('zero-distance',b'\x80\0\0',16384,32768),
         ('before-start',b'\x80\x01\0',16384,32768),('overflow',overflow,16384,32768),
         ('trailing',streams[0]+b'\0',16384,32768),('source-end',b'AA',32767,32768),
         ('output-address',b'\0A',16384,32769),('empty',b'',16384,32768)]
    for name,raw,start,dest in bad:
        setup.append(f'lappend ::fixtures [list {name} -1 -1 {start} {len(raw)} {dest} 1 [binary format H* {{{raw.hex()}}}] {{}}]')
    basis=ranking_basis(records).ljust(16384,b'\xff')
    for layout in range(4):
        expected=b''.join(bytes(r['data'][0x800+layout*256:0x841+layout*256]) for r in records[:64])+b'\xee'*(16384-4160)
        setup.append(f'lappend ::fixtures [list ranking -1 {layout} 16384 16384 32768 0 [binary format H* {basis.hex()}] [binary format H* {expected.hex()}]]')
    (out/'fixtures.tcl').write_text('\n'.join(setup)+'\n')
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
cart {tcl(ROOT/'dist/newrallyx.rom')} -romtype ASCII8
reset
source {tcl(out/'fixtures.tcl')}
set ::started 0;set ::phase boot;set ::age 0;set ::i 0
set ::results [open {tcl(out/'cycles.tsv')} w]
proc issue {{}} {{
 if {{$::i==[llength $::fixtures]}} {{close $::results;puts stderr "PASS cold overlays=32 negatives=8 ranks=4";exit;return}}
 lassign [lindex $::fixtures $::i] kind prev next start size dest bad raw expected
 if {{$kind eq "ranking"}} {{set source $raw}} elseif {{$bad}} {{
  set source [binary format c* [lrepeat 16384 255]]
  set at [expr {{$start-16384}}];set last [expr {{min(16383,$at+[string length $raw]-1)}}]
  if {{$last>=$at}} {{set source [string replace $source $at $last [string range $raw 0 [expr {{$last-$at}}]]]}}
 }} else {{set source $::source}}
 debug write_block $::ram [expr {{$::source_bank*16384}}] $source
 debug write_block $::ram [expr {{$::target_bank*16384}}] [binary format c* [lrepeat 16384 238]]
 set ::before [debug read_block $::ram 0 524288]
 set ::vram [debug read_block VRAM 0 131072]
 set ::source_now $source;set ::expected $expected;set ::bad $bad
 set ::expected_de [expr {{$kind eq "ranking"?36928:49152}}]
 set entry [expr {{$kind eq "ranking"?51712:50944}}]
 # Caller code and stack are Page3 diagnostics. CPU performs all page/slot
 # writes; host never installs decoded output or writes the cheat latch.
 set code [list 243 49 128 243 62 $::source_bank 211 253 62 $::target_bank 211 254 62 $::secondary 50 255 255 62 $::primary 211 168 33 [expr {{$start&255}}] [expr {{$start>>8}}] 1 [expr {{$size&255}}] [expr {{$size>>8}}] 17 [expr {{$dest&255}}] [expr {{$dest>>8}}] 62 [expr {{$next&3}}] 205 [expr {{$entry&255}}] [expr {{$entry>>8}}] 195 240 198]
 debug write_block memory 0xc600 [binary format c* $code]
 reg IX 17767;reg IY 26505;reg IFF 0;reg PC 0xc600
}}
proc checked {{script}} {{if {{[catch {{uplevel 1 $script}} error]}} {{puts stderr "FAIL $error";exit 2}}}}
debug set_bp 0xc620 {{$::started}} {{set ::begin [machine_info time]}}
debug set_bp 0xc6f0 {{$::started}} {{checked {{
 set cycles [expr {{([machine_info time]-$::begin)*3579545}}]
 if {{([reg AF]&1)!=$::bad || [reg IX]!=17767 || [reg IY]!=26505 || [reg SP]!=62336 || [reg IFF]!=0}} {{error "Decoder result/register failure case=$::i AF=[reg AF] IX=[reg IX] IY=[reg IY] SP=[reg SP]"}}
 if {{!$::bad && ([reg DE]!=$::expected_de || [debug read_block $::ram [expr {{$::target_bank*16384}}] 16384] ne $::expected)}} {{error "Decoded stage mismatch case=$::i"}}
 if {{[debug read_block VRAM 0 131072] ne $::vram}} {{error "Cold decoder touched VRAM"}}
 if {{[debug read_block $::ram [expr {{$::source_bank*16384}}] 16384] ne $::source_now}} {{error "Cold decoder changed retained backing"}}
 for {{set bank 0}} {{$bank<32}} {{incr bank}} {{
  if {{$bank in [list $::p3 $::target_bank]}} continue
  set at [expr {{$bank*16384}}]
  if {{[debug read_block $::ram $at 16384] ne [string range $::before $at [expr {{$at+16383}}]]}} {{error "Unrelated RAM bank changed $bank"}}
 }}
 set p3_bytes [debug read_block $::ram [expr {{$::p3*16384}}] 16384]
 set before [string range $::before [expr {{$::p3*16384}}] [expr {{($::p3+1)*16384-1}}]]
 # Exact allowed diagnostic lifetimes: C600 caller, C700 decoder/scratch,
 # F340..F37F stack. All other native state is protected, even on rejection.
 foreach {{a b}} [list 1536 1599 1792 [expr {{1791+{len(decoder)}}}] 2560 [expr {{2559+{len(ranking)}}}] 13120 13183 16383 16383] {{
  set p3_bytes [string replace $p3_bytes $a $b [string range $before $a $b]]
 }}
 if {{$p3_bytes ne $before}} {{error "Decoder changed protected Page3 state"}}
 puts $::results "$::i [lindex [lindex $::fixtures $::i] 0] $::bad $cycles";flush $::results
 incr ::i;issue
}}}}
debug set_bp {s['GameTurbo_FrameDone']} {{!$::started && $::phase eq "active"}} {{checked {{
 set ::started 1;reg IFF 0;debug write {{VDP regs}} 1 66
 set ::ram ""
 foreach name [debug list] {{if {{[debug desc $name] eq "memory mapper" && [debug size $name]==524288}} {{set ::ram $name}}}}
 if {{$::ram eq ""}} {{error "512KiB mapper missing"}}
 # These readable mapper ports belong to this private diagnostic machine;
 # a production allocator must discover/reserve segments through the OS API.
 set ::p3 [expr {{[debug read ioports 255]&31}}]
 set p0 [expr {{[debug read ioports 252]&31}}]
 set free {{}};for {{set n 0}} {{$n<32}} {{incr n}} {{if {{$n!=$p0 && $n!=$::p3}} {{lappend free $n}}}}
 set ::source_bank [lindex $free 0];set ::target_bank [lindex $free 1]
 set f [open {tcl(out/'edges.lz')} rb];set bytes [read $f];close $f
 set ::source [string cat $bytes [binary format c* [lrepeat [expr {{16384-[string length $bytes]}}] 255]]]
 set f [open {tcl(out/'decoder.bin')} rb];set bytes [read $f];close $f
 debug write_block memory 0xc700 $bytes
 set f [open {tcl(out/'ranking.bin')} rb];set bytes [read $f];close $f
 debug write_block memory 0xca00 $bytes
 set ppi [debug read ioports 168];set sec [expr {{255-[debug read memory 65535]}}]
 set ::primary [expr {{($ppi&195)|(($ppi>>4)&12)|(($ppi>>2)&48)}}]
 set ::secondary [expr {{($sec&195)|(($sec>>4)&12)|(($sec>>2)&48)}}]
 issue
}}}}
proc poll {{}} {{
 if {{$::started}} return
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{if {{$::age==5}} {{keymatrixup 0 2}};if {{$state==0 && [debug read memory 0xc00c]}} {{set ::phase active}}}}
 }}
 after time .02 {{checked poll}}
}}
after time .02 {{checked poll}}
after time 180 {{puts stderr "TIMEOUT cold stage $::i";exit 2}}
'''
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='512',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    result=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=180)
    (out/'output.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0 and 'PASS cold overlays=32 negatives=8 ranks=4' in result.stderr,result.stderr[-2000:]
    rows=[line.split() for line in (out/'cycles.tsv').read_text().splitlines()]
    costs=distribution(float(row[3]) for row in rows if row[1]=='transition')
    rank_costs=distribution(float(row[3]) for row in rows if row[1]=='ranking')
    report=dict(passed=True,reference_rom_sha256=hashlib.sha256((ROOT/'dist/newrallyx.rom').read_bytes()).hexdigest(),
        main_ram_kib=512,decoder_bytes=len(decoder),ranking_code_bytes=len(ranking),backing_bytes=len(blob),active_edge_bytes=16384,previous_active_edge_bytes=65536,
        saved_active_source_bytes=49152,transition_pairs=16,successful_decodes=32,malformed_rejections=8,
        retained_source_unchanged=True,unrelated_ram_and_vram_unchanged=True,transition_cycles=costs,
        transition_ms={k:v/3579545*1000 for k,v in costs.items()},
        rank_bytes_checked=16640,ranking_basis_bytes=8896,ranking_basis_lz_bytes=len(compress_bank(basis)),
        ranking_cycles=rank_costs,ranking_ms={k:v/3579545*1000 for k,v in rank_costs.items()},
        measurement='Inclusive CALL/decode/RET/terminal JP on base Z80 at3579545Hz; VDP IRQ generation off. Extra cold preparation, not complete phase-transition duration.',
        stages=[dict(layout=i,compressed_bytes=len(streams[i]),expanded_sha256=hashlib.sha256(raws[i]).hexdigest()) for i in range(4)],
        scope='Destructive real-RAM cold overlay component after cartridge keyboard bootstrap. CPU replaces one16KiB edge-data window. Original metadata bytes preserved, not relinked/executed. No complete512KiB allocation, DOS/BASIC startup, production IRQ, audio or gameplay-speed qualification.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':verify()
