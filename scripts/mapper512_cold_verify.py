"""Real DOS1/BASIC filesystem + bounded512KiB cold bridge, no cartridge.

The host only supplies files/BIOS and observes memory; no payload/OS context is
injected through the debugger. This is not a native-game boot/performance run.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from compact_game_build import symbols
from compact_game_report import distribution
from src.toolchain.msx.emulator import reference_machine,tcl


def verify(mode='dos',ram_kib=512,fault=None,batching=True):
    bundle=ROOT/('references/build/game-mapper512-cold'+('' if batching else '-per-resource'));game=ROOT/'references/build/game-mapper512-integrated'
    plan=json.loads((bundle/'plan.json').read_text());s=symbols(bundle/'mapper512-cold.asm.sym');loader=symbols(bundle/'mapper512-cold-loader.asm.sym')
    out=Path(tempfile.mkdtemp(prefix=f'{mode}-{ram_kib}-{fault or "valid"}-',dir=bundle));files=out/'files';files.mkdir()
    for p in (bundle/'files').glob('NRXCOLD.*'):shutil.copyfile(p,files/p.name)
    if mode=='dos':
        for n in ['msxdos.sys','command.com']:shutil.copyfile(ROOT/'references/cache/dos-validation'/n,files/n.upper())
        (files/'AUTOEXEC.BAT').write_bytes(b'NRXCOLD\r\n')
    if fault=='missing':(files/'NRXCOLD.DAT').unlink()
    elif fault=='truncated':(files/'NRXCOLD.DAT').write_bytes((files/'NRXCOLD.DAT').read_bytes()[:24])
    elif fault=='checksum':
        raw=bytearray((files/'NRXCOLD.DAT').read_bytes());raw[plan['records'][0]['offset']+1]^=1;(files/'NRXCOLD.DAT').write_bytes(raw)
    late_index=next(i for i,r in enumerate(plan['records']) if r['family']==1)
    if fault=='late':(files/'NRXCOLD.DAT').write_bytes((files/'NRXCOLD.DAT').read_bytes()[:plan['records'][late_index]['offset']+24])
    failure_index=late_index if fault=='late' else 0
    setup=[]
    for family in range(4):
        setup.append(f'set f [open {tcl(game/f"stage-{family}/hot-image.bin")} rb];set ::images({family}) [read $f];close $f')
    map_banks=json.loads((ROOT/'references/build/game/session-build.json').read_text())['map_banks']
    setup.append(f'set f [open {tcl(ROOT/"references/build/game/newrallyx.rom")} rb];set ::original [read $f];close $f')
    for family in range(4):
        for half,bank in [(0,2),(1,3)]:
            at=map_banks[family*2+half]*16384
            setup.append(f'set ::maps({family},{bank}) [string range $::original {at} {at+16383}]')
    # Copy spans are the independently re-read declared union mask, not a scan
    # of generated pixel values or the guest's own copy-directory instructions.
    union=(bundle/'union-mask.bin').read_bytes()
    for bank in range(32):
        ranges=[];start=0
        while start<16384:
            if not union[bank*16384+start]:start+=1;continue
            end=start+1
            while end<16384 and union[bank*16384+end]:end+=1
            ranges.extend([start,end-start]);start=end
        setup.append(f'set ::live({bank}) {{{" ".join(map(str,ranges))}}}')
    setup.append('set ::records {'+' '.join('{'+f"{r['family']} {r['bank']} {r['kind']}"+'}' for r in plan['records'])+'}')
    negative=ram_kib<512 or fault is not None
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
source [file join $::env(OPENMSX_SYSTEM_DATA) scripts _disasm.tcl]
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
diska {tcl(files)}
reset
{chr(10).join(setup)}
set ::started 0;set ::ready 0;set ::reads 0;set ::checks 0;set ::times {{}};set ::flush_times {{}};set ::start_time 0
set ::bdos_counts [dict create];set ::world_checks 0
set ::ram ""
foreach d [debug list] {{if {{[debug desc $d] eq "memory mapper" && [debug size $d]=={ram_kib*1024}}} {{set ::ram $d}}}}
if {{$::ram eq ""}} {{error "Wrong physical RAM size"}}
proc checked {{script}} {{if {{[catch {{uplevel 1 $script}} e]}} {{puts stderr "FAIL $e PC=[reg PC] reads=$::reads";exit 2}}}}
proc bankcheck {{family bank}} {{
 if {{$bank in {{2 3}}}} {{
  if {{[debug read_block $::ram [expr {{$bank*16384}}] 16384] ne $::maps($family,$bank)}} {{error "World map changed family=$family bank=$bank"}}
  incr ::checks;incr ::world_checks;return
 }}
 foreach {{offset length}} $::live($bank) {{
  set from [expr {{$bank*16384+$offset}}]
  if {{[debug read_block $::ram $from $length] ne [string range $::images($family) $from [expr {{$from+$length-1}}]]}} {{error "Live bytes changed family=$family bank=$bank offset=$offset length=$length"}}
  incr ::checks
 }}
}}
proc hotstate {{}} {{
 set values {{}}
 for {{set b 6}} {{$b<32}} {{incr b}} {{foreach {{o n}} $::live($b) {{lappend values [debug read_block $::ram [expr {{$b*16384+$o}}] $n]}}}}
 return $values
}}
proc savecosts {{}} {{
 set f [open {tcl(out/'cycles.json')} w];puts $f "\\[[join $::times ,]\\]";close $f
 set f [open {tcl(out/'flush-cycles.json')} w];puts $f "\\[[join $::flush_times ,]\\]";close $f
}}
proc countcalls {{function}} {{if {{[dict exists $::bdos_counts $function]}} {{return [dict get $::bdos_counts $function]}};return 0}}
proc statecheck {{}} {{
 if {{[reg SP]!=0xf380 || [reg I]!=0xd2 || [reg IFF]!=0}} {{error "SP/I/IFF not restored: [reg SP]/[reg I]/[reg IFF]"}}
 if {{[debug read_block $::ram 16384 16384] ne [string repeat [binary format c 90] 16384]}} {{error "Game mainPage0 changed"}}
 if {{[debug read memory 0xc0ee]!=1 || [debug read ioports 252]%32!=1 || [debug read ioports 255]%32!=0}} {{error "Game Page0/Page3/F10 lifetime changed"}}
 if {{[debug read_block $::ram 0 13056] ne $::game_low || [debug read_block $::ram 13312 3072] ne $::game_high}} {{error "Game Page3 outside private stack changed"}}
 if {{[debug read_block memory 20480 {s['Cold_Mode']-0x5000}] ne $::static_code || [debug read_block memory {s['Cold_FileName']} {s['Cold_End']-s['Cold_FileName']}] ne $::static_data}} {{error "Bridge/directory hole overwritten"}}
}}
debug set_bp {loader['Entry']} {{!$::started && [reg PC]=={loader['Entry']}}} {{
 set ::probe_before {{}}
 for {{set b 0}} {{$b<{ram_kib//16}}} {{incr b}} {{lappend ::probe_before [debug read_block $::ram [expr {{$b*16384+16352}}] 17]}}
 set ::started 1;puts stderr "LOADER mode={mode} mainRAM={ram_kib}"
}}
debug set_bp {loader['Fail']} {{$::started}} {{
 if {{{int(ram_kib<512)}}} {{checked {{
  for {{set b 0}} {{$b<{ram_kib//16}}} {{incr b}} {{if {{[debug read_block $::ram [expr {{$b*16384+16352}}] 17] ne [lindex $::probe_before $b]}} {{error "Capacity rejection changed probe tag $b"}}}}
  puts stderr "PASS reversible capacity rejection";exit
 }}}} else {{puts stderr "FAIL loader rejection DE=[reg DE]";exit 3}}
}}
debug set_bp {s['Cold_FixtureNext']} {{$::started && !$::ready && [debug read ioports 253]%32==30}} {{checked {{
 set ::game_low [debug read_block $::ram 0 13056];set ::game_high [debug read_block $::ram 13312 3072]
 set ::static_code [debug read_block memory 20480 {s['Cold_Mode']-0x5000}];set ::static_data [debug read_block memory {s['Cold_FileName']} {s['Cold_End']-s['Cold_FileName']}]
 set ::hot_before [hotstate]
 set ::ready 1
}}}}
debug set_bp {s['Cold_Read']} {{$::ready && [debug read ioports 253]%32==30}} {{set ::start_time [machine_info time];set ::hot_before [hotstate]}}
debug set_bp {s['Cold_Bdos']} {{$::ready && [debug read ioports 253]%32==30}} {{dict incr ::bdos_counts [reg C]}}
debug set_bp {s['Cold_FixtureStepDone']} {{$::ready && [debug read ioports 253]%32==30}} {{checked {{
 statecheck
 if {{[reg F]&1}} {{
  if {{{int(fault is not None)}}} {{
   if {{$::reads!={failure_index}}} {{error "Resource rejected before expected failure record"}}
    if {{[debug read memory {s['Cold_OsLive']}]!=0}} {{error "Rejected resource left OS batch open"}}
    if {{[debug read memory {s['Cold_FileOpen']}]!=0}} {{error "Rejected resource left file open"}}
   if {{[hotstate] ne $::hot_before}} {{error "Rejected resource changed live hot data"}}
   savecosts;puts stderr "PASS expected filesystem/decode rejection; game state, hot banks and bridge intact; reads=$::reads open=[countcalls 15] close=[countcalls 16] blocks=[countcalls 39] worlds=$::world_checks";exit
  }} else {{error "Unexpected cold failure A=[reg A] status=[debug read memory {s['Cold_Result']}]"}}
 }} else {{
  if {{{int(fault is not None)} && $::reads>={failure_index}}} {{error "Corrupt/missing resource accepted"}}
  lassign [lindex $::records $::reads] family bank kind
  if {{[debug read ioports 254]%32!=$bank}} {{error "Output bank not left selected"}}
  bankcheck $family $bank
  incr ::reads
  lappend ::times [expr {{([machine_info time]-$::start_time)*3579545}}]
 }}
}}}}
debug set_bp {s['Cold_EndBatch']} {{$::ready && [debug read ioports 253]%32==30}} {{set ::flush_start [machine_info time]}}
debug set_bp {s['Cold_FixtureBatchDone']} {{$::ready}} {{checked {{
 statecheck
 if {{[reg F]&1}} {{error "EndBatch rejected a valid map order"}}
 if {{[debug read memory {s['Cold_OsLive']}]!=0}} {{error "EndBatch did not release its cache ownership"}}
 if {{[debug read memory {s['Cold_FileOpen']}]!=0}} {{error "EndBatch left file open"}}
 lassign [lindex $::records [expr {{$::reads-1}}]] family bank kind
 for {{set b 6}} {{$b<32}} {{incr b}} {{bankcheck $family $b}}
 bankcheck $family 2;bankcheck $family 3
 lappend ::flush_times [expr {{([machine_info time]-$::flush_start)*3579545}}]
}}}}
debug set_bp {s['Cold_FixturePassed']} {{$::ready}} {{checked {{
 if {{$::reads!={len(plan['records'])}}} {{error "Not every compiled resource was read"}}
 savecosts
 if {{[countcalls 15]!={5 if batching else len(plan['records'])} || [countcalls 16]!=[countcalls 15] || [countcalls 39]!=$::reads+[countcalls 15]}} {{error "Unexpected filesystem call counts"}}
 puts stderr "PASS cartridge-free cold reads=$::reads masked-span-checks=$::checks open=[countcalls 15] close=[countcalls 16] blocks=[countcalls 39] worlds=$::world_checks";exit
}}}}
after time 900 {{puts stderr "TIMEOUT PC=[reg PC] SP=[reg SP] reads=$::reads started=$::started ready=$::ready";exit 4}}
'''
    if mode=='basic':script+=f'after time 10 {{type_via_keybuf {tcl(chr(13)+"run "+chr(34)+"NRXCOLD.BAS"+chr(34)+chr(13)).replace(chr(13),r"\r")}}}\n'
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB=str(ram_kib),OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    result=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=180)
    (out/'output.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0 and 'PASS ' in result.stderr,result.stderr[-2500:]
    costs=json.loads((out/'cycles.json').read_text()) if (out/'cycles.json').exists() else []
    flush=json.loads((out/'flush-cycles.json').read_text()) if (out/'flush-cycles.json').exists() else []
    report=dict(passed=True,mode=mode,ram_kib=ram_kib,fault=fault,negative=negative,resource_reads=len(costs),os_context_batching=batching,
                cold_cycles=distribution(costs) if costs else None,batch_flush_cycles=distribution(flush) if flush else None,
                batch_flushes=len(flush),total_cold_cycles=sum(costs)+sum(flush),script_sha256=hashlib.sha256(script.encode()).hexdigest(),
                source_bridge_sha256=plan['bridge']['sha256'],source_resource_sha256=plan['resource_sha256'],
                context_bytes=plan['context_bytes'],context_fragments=plan['context_fragments'],host_payload_injections=0,cartridge_attached=False,
                capacity_probe_restored=True if ram_kib<512 else None,
                rejected_hot_data_preserved=True if fault else None,
                expected_failure_index=failure_index if fault else None,
                masked_span_checks=int(m[1]) if (m:=re.search(r'masked-span-checks=(\d+)',result.stderr)) else None,
                filesystem_calls=dict(zip(['open','close','read_blocks','world_half_checks'],map(int,m.groups()))) if (m:=re.search(r'open=(\d+) close=(\d+) blocks=(\d+) worlds=(\d+)',result.stderr)) else None,
                scope=('Negative cold filesystem/capacity proof; game work state is synthetic.' if negative else 'Guest filesystem/decode/masked-copy/OS-state proof with all four production hot layouts and both world halves, including3->0 wrap.')+' No original-game bootstrap, active gameplay, F10 key activation or FPS qualification.',path=str(out.relative_to(ROOT)))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['dos','basic'],default='dos');p.add_argument('--ram-kib',type=int,default=512)
    p.add_argument('--fault',choices=['missing','truncated','checksum','late']);p.add_argument('--per-resource',action='store_true')
    a=p.parse_args();verify(a.mode,a.ram_kib,a.fault,not a.per_resource)
