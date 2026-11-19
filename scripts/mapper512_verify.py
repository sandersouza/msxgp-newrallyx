"""Execute experimental packets in real512KiB mapper Page1/Page2 RAM.

The unchanged cartridge provides keyboard startup/VDP/Page0 initialization.
After freezing gameplay, CPU slot writes remove cartridge windows from both
Page1 and Page2. Diagnostic host injection supplies real mapper RAM fixtures;
this is explicitly not a DOS loader or a complete cartridge-free game claim.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from mapper512_backend import prepare,compact_programs,hoisted_programs,absolute_programs,flat_windows,suffix_windows,instructions
from compact_game_build import symbols
from compact_transfer import events as baseline_events
from mapper512_backend import events,cycles
from src.toolchain.msx.emulator import reference_machine,tcl


def verify(variant='compact'):
    out=ROOT/'references/build/game-mapper512'/('proof-'+variant);out.mkdir(parents=True,exist_ok=True)
    bundle=ROOT/'references/build/game-compact-runtime';s=symbols(bundle/'lab.sym');rom=ROOT/'dist/newrallyx.rom'
    cases,records,packed=prepare();prefixes=compact_programs(cases)
    header=hoisted_programs(cases)
    if variant in ('absolute','absolute-flat'):header=absolute_programs(cases,records)
    field='absolute' if variant=='absolute-flat' else variant
    linker=flat_windows if variant=='absolute-flat' else suffix_windows
    windows=linker([c[field] for c in cases],limit=0x3b00 if variant=='compact' else 0x3e40,exit_address=0xc7e0)
    locations={code:(i,entry,w['jumps'][code]) for i,w in enumerate(windows) for code,entry in w['entries'].items()}
    head=rom.read_bytes()[s['Compact_ExactHead']-0x4000:s['Compact_ExactHead']-0x4000+385]
    assert len(head)==385 and head[-3]==0xc3
    def link(code,terminal=False):
        result=bytearray();parts=instructions(code)
        for ins in parts:
            if ins[0]==0xcd:
                target=int.from_bytes(ins[1:],'little');n=target&255;kind=target&0xff00
                if kind==0x100:target=s['Compact_ExactTailEnd']-2*n if n<=64 else s['Compact_ExactHead']+2*(255-n)
                elif kind==0x200:target=s['Compact_ExactShortEnd']-2*n
                elif kind==0x300:target=0x7b00+24*n
                else:raise ValueError('Unknown helper marker')
                ins=b'\xcd'+target.to_bytes(2,'little')
            if terminal and ins[0]==0xc3:ins=b'\xc3\xe0\xc7'
            result.extend(ins)
        return bytes(result)
    def code_page(body):
        image=bytearray(b'\xff'*16384);image[:len(body)]=link(body)
        if variant=='compact':
            for i,prefix in enumerate(prefixes):assert len(prefix)==23;image[0x3b00+i*24:0x3b00+(i+1)*24]=prefix+b'\xc9'
        image[0x3e40:0x3e40+385]=head
        return bytes(image)
    pages=[code_page(w['data']) for w in windows]
    setup=['set ::records {}','set ::packed {}','set ::code_pages {}','set ::cases {}']
    for r,p in zip(records,packed):
        setup.append('lappend ::records [binary format H* '+bytes(r['data']).hex()+']')
        setup.append('lappend ::packed [binary format H* '+p[0].hex()+']')
    for page in pages:setup.append('lappend ::code_pages [binary format H* '+page.hex()+']')
    for i,c in enumerate(cases):
        page,entry,jumps=locations[c[field]];slot=c['slot'];d=0x80+slot*8;e=d+(2 if records[c['record']]['kind']=='hud' else 4)
        _,hlb,b=baseline_events(c['baseline']);_,hlr,_=events(c['relative'],d,e)
        bc=152+((b[1] if b[0]=='zero' else (165+b[1])&255)<<8)
        expected='[list '+' '.join('[list '+str(dest)+' [binary format H* '+data.hex()+']]' for dest,data in c['writes'])+']'
        candidate_cycles=c[{'hoisted':'relative_cycles','absolute':'absolute_cycles','absolute-flat':'absolute_cycles','compact':'compact_cycles'}[variant]]+11*jumps
        setup.append('lappend ::cases [list '+' '.join(map(str,[i,c['record'],slot,d,e,bc,hlb if hlb is not None else 0xdead,hlr if hlr is not None else 0xdead,1 if c['writes'] else 0,page,entry,c['baseline_cycles'],c['relative_cycles'],candidate_cycles]))+' '+link(c['baseline'],True).hex()+' '+link(c['relative'],True).hex()+' '+expected+']')
    (out/'fixtures.tcl').write_text('\n'.join(setup)+'\n')
    (out/'empty-code.bin').write_bytes(code_page(b''))
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
source {tcl(out/'fixtures.tcl')}
set ::started 0;set ::phase boot;set ::age 0;set ::i 0;set ::stage 0;set ::back 0;set ::fast 0
set ::poison [binary format c* [lrepeat 131072 238]]
set ::blank [binary format c* [lrepeat 16384 255]]
set ::results [open {tcl(out/'cycles.tsv')} w]
set VDP.too_fast_vram_access_callback {{if {{$::started}} {{incr ::fast}}}}
proc issue {{}} {{
 if {{$::i==[llength $::cases]}} {{close $::results;puts stderr "PASS packets=$::i stages=3 back_tables=2 strict=$::fast";exit;return}}
 lassign [lindex $::cases $::i] i record slot d e bc hlb hlr iff page entry old_c relative_c compact_c baseline relative expected
 set bank [expr {{$::stage==2?[lindex $::banks $page]:$::flat_bank}}]
 if {{$::stage!=2}} {{debug write_block $::ram [expr {{$bank*16384}}] [binary format H* [expr {{$::stage?$relative:$baseline}}]];set entry 16384}}
 debug write_block $::ram [expr {{$::source_bank*16384}}] $::blank
 set offset [expr {{$::stage?$slot*2048:($record%2)*4096}}]
 debug write_block $::ram [expr {{$::source_bank*16384+$offset}}] [lindex [set [expr {{$::stage?"::packed":"::records"}}]] $record]
 debug write {{VDP regs}} 1 66
 debug write_block VRAM 0 $::poison
 debug write memory 0xc027 $::back
 set ::expected $::poison
 foreach write $expected {{lassign $write dest data;set at [expr {{$dest+$::back*16384}}];set ::expected [string replace $::expected $at [expr {{$at+[string length $data]-1}}] $data]}}
 set code [list 243 49 128 243 219 153 62 $bank 211 253 62 $::source_bank 211 254 62 $::secondary 50 255 255 62 $::primary 211 168 1 152 165 17 $e $d 33 173 222 221 33 103 69 253 33 137 103]
 while {{[llength $code]<64}} {{lappend code 0}}
 if {{$::stage==2 && $iff && {1 if variant in ('hoisted','absolute','absolute-flat') else 0}}} {{foreach byte {{{' '.join(map(str,header))}}} {{lappend code $byte}}}}
 lappend code 195 [expr {{$entry&255}}] [expr {{$entry>>8}}]
 while {{[llength $code]<256}} {{lappend code 0}}
 debug write_block memory 0xc700 [binary format c* $code]
 reg IFF 0;reg PC 0xc700
}}
debug set_bp 0xc740 {{$::started}} {{
 if {{[get_active_cpu] ne "z80" || [machine_info z80_freq]!=3579545}} {{puts stderr "CPU CLOCK MISMATCH";exit 6}}
 set ::begin [machine_info time]
}}
debug set_bp 0xc7e0 {{$::started}} {{
 set ::elapsed [expr {{([machine_info time]-$::begin)*3579545-11}}]
 lassign [lindex $::cases $::i] i record slot d e bc hlb hlr iff page entry old_c relative_c compact_c
 set hl [expr {{$::stage?$hlr:$hlb}}]
 if {{[reg BC]!=$bc || [reg HL]!=$hl || [reg DE]!=(($d<<8)|$e) || [reg IX]!=0x4567 || [reg IY]!=0x6789 || [reg SP]!=0xf380 || ([reg IFF]&1)!=$iff}} {{puts stderr "ABI FAIL i=$i stage=$::stage BC=[reg BC]/$bc HL=[reg HL]/$hl IFF=[reg IFF]/$iff";exit 3;return}}
 set model [lindex [list $old_c $relative_c $compact_c] $::stage]
 if {{abs($::elapsed-$model)>1.01}} {{puts stderr "CYCLE FAIL i=$i stage=$::stage measured=$::elapsed model=$model";exit 4;return}}
 reg PC 0xc7f0
}}
debug set_bp 0xc7ff {{$::started}} {{
 if {{[debug read_block VRAM 0 131072] ne $::expected}} {{puts stderr "VRAM FAIL i=$::i stage=$::stage back=$::back";exit 5;return}}
 puts $::results "$::i $::stage $::back $::elapsed"
 incr ::stage
 if {{$::stage==3}} {{set ::stage 0;if {{!$::back}} {{set ::back 7}} else {{set ::back 0;incr ::i}}}}
 issue
}}
debug set_bp {s['GameTurbo_FrameDone']} {{!$::started && $::phase eq "active"}} {{
 set ::started 1
 set ::ram ""
 foreach name [debug list] {{if {{[debug desc $name] eq "memory mapper" && [debug size $name]==524288}} {{set ::ram $name}}}}
 if {{$::ram eq ""}} {{puts stderr "512KiB mapper missing";exit 2;return}}
 set p0 [expr {{[debug read ioports 252]&31}}];set p3 [expr {{[debug read ioports 255]&31}}]
 set free {{}};for {{set b 0}} {{$b<32}} {{incr b}} {{if {{$b!=$p0 && $b!=$p3}} {{lappend free $b}}}}
 set ::banks [lrange $free 0 {len(windows)-1}];set ::flat_bank [lindex $free {len(windows)}];set ::source_bank [lindex $free {len(windows)+1}]
 foreach bank $::banks bytes $::code_pages {{debug write_block $::ram [expr {{$bank*16384}}] $bytes}}
 set f [open {tcl(out/'empty-code.bin')} rb];set empty [read $f];close $f
 debug write_block $::ram [expr {{$::flat_bank*16384}}] $empty
 set ppi [debug read ioports 168];set sec [expr {{255-[debug read memory 65535]}}]
 set ::primary [expr {{($ppi&195)|(($ppi>>4)&12)|(($ppi>>2)&48)}}]
 set ::secondary [expr {{($sec&195)|(($sec>>4)&12)|(($sec>>2)&48)}}]
 puts stderr "RAM-only packet windows p0=$p0 p3=$p3 code=$::banks source=$::source_bank"
 issue
}}
proc poll {{}} {{
 if {{$::started}} return
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{if {{$::age==5}} {{keymatrixup 0 2}};if {{$state==0 && [debug read memory 0xc00c]}} {{set ::phase active}}}}
 }}
 after time 0.02 poll
}}
after time 0.02 poll
after time 600 {{puts stderr "TIMEOUT packets i=$::i stage=$::stage PC=[reg PC]";exit 2}}
'''
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='512',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    r=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=180)
    (out/'output.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and 'PASS packets=4384 stages=3 back_tables=2 strict=0' in r.stderr,r.stderr[-1800:]
    rows=[line.split() for line in (out/'cycles.tsv').read_text().splitlines()]
    assert len(rows)==4384*3*2
    timings={(int(i),int(stage),int(back)):float(value) for i,stage,back,value in rows}
    deltas=[timings[i,2,b]-timings[i,0,b] for i in range(4384) for b in (0,7)]
    if variant=='absolute-flat':assert max(abs(x) for x in deltas)<1.01
    report=dict(passed=True,scope='Isolated real-RAM packet execution, not complete512KiB game or DOS startup. Cartridge keyboard startup initializes video/Page0, then CPU unmaps cartridge Page1/Page2. Host fixture injection, all4384 production packet references, baseline/relative/selected candidate, both extreme pattern tables. All128KiB VRAM, BC/DE/HL/IX/IY/SP/IFF checked. VDP IRQ generation disabled; actual Page1 return/dispatch and whole-game IRQ/audio not qualified.',
        reference_rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),main_ram_kib=512,packet_references=4384,executions=len(rows),strict_vram_callbacks=0,
        variant=variant,packet_delta_cycles=dict(mean=sum(deltas)/len(deltas),p95=sorted(deltas)[int(.95*len(deltas))],min=min(deltas),max=max(deltas),slower=sum(x>1.01 for x in deltas),unchanged=sum(abs(x)<=1.01 for x in deltas)),
        costs=[dict(stage=name,mean=sum(v)/len(v),p95=sorted(v)[int(.95*len(v))],max=max(v),samples=len(v)) for stage,name in enumerate(('baseline','relative',variant)) for v in [[float(value) for i,s_,b,value in rows if int(s_)==stage]]],
        component_performance_gate=('Packet body cost unchanged; resident capacity, complete mapping/dispatch, IRQ and whole-game costs remain unqualified.' if variant=='absolute-flat' else 'Not qualified for production: some packet bodies regress; complete mapping/dispatch and whole-game costs remain unmeasured. This does not prove every conceivable512KiB backend impossible.'))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--variant',choices=['compact','hoisted','absolute','absolute-flat'],default='compact')
    verify(parser.parse_args().variant)
