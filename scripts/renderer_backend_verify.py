"""Execute compact transfer/map/replay components on64KiB ASCII8 and MegaRAM.

An isolated diagnostic, not a complete-game backend. It uses real guest bank
writes and VDP I/O; host injection supplies cases and checks all16KiB of VRAM.
Original-derived test payloads stay ignored and are disposable after summary.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from renderer_window_probe import probe
from renderer_image_build import build,replay
from megaram_window_probe import extension_setup
from src.toolchain.msx.emulator import reference_machine,tcl


def verify(megaram=False, control=False):
    cases=[];records=[]
    probe(4096,cases,records)
    allocation=ROOT/'references/build/game-compact-allocation'
    layout=json.loads((allocation/'layout.json').read_text())
    out=ROOT/'references/build'/('game-original-ascii16-test' if control else 'game-compact-megaram-test' if megaram else 'game-compact-ascii8-test')
    out.mkdir(parents=True,exist_ok=True)
    pages=[];locations={}
    for code in sorted({r['code'] for r in cases},key=lambda c:(-len(c),c)):
        choices=[(8192-len(p)-len(code),n) for n,p in enumerate(pages) if len(p)+len(code)<=8192]
        if choices: _,n=min(choices)
        else: n=len(pages);pages.append(bytearray())
        locations[code]=(layout['code_base']+n,0xa000+len(pages[n]))
        pages[n].extend(code)
    original=(ROOT/'references/build/game/newrallyx.rom').read_bytes()
    syms={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(ROOT/'references/build/game/lab.sym').read_text())}
    helper=original[syms['GamePacketFast_Transfer']-0x4000:syms['GamePacketFast_End']-0x4000]
    (out/'helper.bin').write_bytes(helper)
    source=''' OUTPUT "header.bin"
 ORG $4000
 db "AB"
 dw Boot,0,0,0,0,0,0
Boot:
 di
 ld sp,$f380
 call $0138
 rrca
 rrca
 and 3
 ld c,a
 ld b,0
 ld hl,$fcc1
 add hl,bc
 ld a,(hl)
 and $80
 or c
 ld c,a
 ld de,4
 add hl,de
 ld a,(hl)
 and $0c
 or c
 ld h,$80
 call $0024
 ld a,4
 call $005f
 di
 ld a,2
 out ($99),a
 ld a,$81
 out ($99),a
 xor a
 ld ($c027),a
 out ($99),a
 ld a,$8e
 out ($99),a
 jp Case
 defs $4300-$,0
Case:
 ld a,($c000)
 ld (DATAREG),a
 ld hl,($c002)
 ld a,(hl)
 ld (CODEREG),a
 inc hl
 ld e,(hl)
 inc hl
 ld d,(hl)
 ex de,hl
Execute:
 jp (hl)
 defs $4400-$,0
 INCBIN "helper.bin"
 defs $4500-$,0
Exit:
 jp Case
 defs $8000-$,0
'''.replace('DATAREG','$8000' if megaram else '$7000').replace('CODEREG','$7000' if control else '$a000' if megaram else '$7800')
    if megaram:
        # CHGMOD may temporarily remap cartridge slots. Invoke it before the
        # writable cartridge is selected; its BIOS bridge must not disturb the
        # MegaRAM bank registers containing the executing header.
        source=source.replace(' ld a,4\n call $005f\n','')
    decoder=(ROOT/'tests/fixtures/issue41-map-decoder.inc').read_text().replace('DATAREG','$8000' if megaram else '$7000')
    boot_source=(ROOT/'src/screen4/session-boot.inc').read_text().split('.stream:\n',1)[1].split('.clear:\n',1)[0]
    boot_source=boot_source.replace('ld ($7000),a','ld ($8000),a' if megaram else 'ld ($7000),a')
    boot_code='''
 defs $4900-$,0
BootNext:
 jp BootCase
BootCase:
 ld a,($c030)
 ld (DATAREG),a
 ld hl,($c031)
 call BootWorker.stream
 jp $4500
GameSession_BootSkip EQU $c0f5
GameSession_BootBack EQU $c0fa
BootWorker:
.stream:
'''.replace('DATAREG','$8000' if megaram else '$7000')+boot_source+'''
register:
 out ($99),a
 ld a,b
 or $80
 out ($99),a
 ret
'''
    source=source.replace(' defs $8000-$,0',' defs $4700-$,0\n'+decoder+boot_code+'\n defs $8000-$,0')
    (out/'header.asm').write_text(source)
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo','--sym=header.sym','header.asm'],cwd=out,check=True,capture_output=True)
    entries={n:int(v,16) for n,v in re.findall(r'(?m)^(\w+): EQU 0x([\da-fA-F]+)',(out/'header.sym').read_text())}
    module=(out/'header.bin').read_bytes()+(original if control else (allocation/'allocation.bin').read_bytes())[16384:]
    # Only two explicit callee relocations are changed. Source data, VDP spans
    # and every other transfer instruction were independently checked above.
    image=bytearray(module)
    patches=({r['original_offset']:r['code'] for r in cases} if control else
             {page*8192+address-0xa000:code for code,(page,address) in locations.items()})
    for at,code in patches.items():
        cursor=0
        while cursor<len(code):
            op=code[cursor]
            width=3 if op in (0x3a,0x21,0xcd,0xc3) else 2 if op in (0x0e,0x3e,0xf6,0xe6,0xd3,0x06,0xed) else 1
            if op in (0xcd,0xc3):
                target=0x4400 if op==0xcd else 0x4500
                image[at+cursor+1:at+cursor+3]=target.to_bytes(2,'little')
            cursor+=width
    (out/'backend.rom').write_bytes(image)
    commands=[]
    for row in cases:
        data=(row['original_bank'] if control else layout['data_base']+row['record']//2)
        table=((0xa600 if row['record']<64 else 0xa900) if control else
               0x8000+(row['record']%2)*4096+records[row['record']]['pointer_offset'])+row['index']*3
        writes=' '.join('{'+str(dest)+' '+raw.hex()+'}' for dest,raw in row['writes'])
        commands.append('{'+f'{data} {table} '+'{'+writes+'}'+'}')
    (out/'cases.tcl').write_text('set cases {\n'+'\n'.join(commands)+'\n}\n')
    map_cases=[]
    for row in layout['maps']:
        page,address=row['entry'];bank=row['old_bank']
        map_cases.append('{'+f'{page} {address} '+original[bank*16384:(bank+1)*16384].hex()+'}')
    (out/'maps.tcl').write_text('set maps {\n'+'\n'.join(map_cases)+'\n}\n')
    boot_cases=[]
    table=original[124*16384+0x1000:][:356]
    for n in range(71):
        oldbank=table[n*5];oldaddress=int.from_bytes(table[n*5+1:n*5+3],'little')
        page,address=(oldbank,oldaddress) if control else layout['boot_pointers'][str(n)]
        writes=' '.join('{'+str(dest)+' '+raw.hex()+'}' for dest,raw,_ in replay(original,oldbank,oldaddress))
        boot_cases.append('{'+f'{page} {address} '+'{'+writes+'}'+'}')
    (out/'boot.tcl').write_text('set boot_cases {\n'+'\n'.join(boot_cases)+'\n}\n')
    setup=''
    if megaram:
        bootstrap=bytes.fromhex('f33180f33e04cd5f00f33e012640cd24003e012680cd2400afd38e3200403c320060c31040')
        setup=f'''{extension_setup(out,1024,'MegaRAM_compact')}
reset
after time 10 {{
 foreach d [debug list] {{if {{[debug size $d]==1048576 && [string match *Mega* $d]}} {{set device $d}}}}
 set f [open {tcl(out/'backend.rom')} rb];set bytes [read $f];close $f
 debug write_block $device 0 $bytes
 debug write_block memory 0xc100 [binary format H* {bootstrap.hex()}]
 reg PC 0xc100
}}
'''
    else: setup=f'cart {tcl(out/"backend.rom")} -romtype {"ASCII16" if control else "ASCII8"}\n'
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq 3579545
set z80_freq_locked false
set cmdtiming real
set limitsprites true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
{setup}
source {tcl(out/'cases.tcl')}
source {tcl(out/'maps.tcl')}
source {tcl(out/'boot.tcl')}
proc start_boot {{}} {{
 set ::verification_phase boot;set ::m 0;set ::boot_entries 0;set ::boot_cycles {{}}
 set ::boot_expected [string repeat [binary format c 0] 65536]
 debug write_block VRAM 0 $::boot_expected
 debug write memory 0xc0f5 0
 foreach {{register value}} {{0 6 1 2 2 31 8 42 23 0 25 0 26 0 27 0}} {{debug write {{VDP regs}} $register $value}}
 reg PC {entries['BootNext']}
}}
set n 0
set verification_phase transfer
set cycles {{}}
debug set_bp 0x4300 {{}} {{
 if {{$::n<[llength $::cases]}} {{
 lassign [lindex $::cases $::n] data table writes
 debug write memory 0xc000 $data
 debug write memory 0xc002 [expr {{$table&255}}]
 debug write memory 0xc003 [expr {{$table>>8}}]
 set ::expected [string repeat [binary format c 0] 16384]
 debug write_block VRAM 0 $::expected
 foreach span $writes {{lassign $span dest raw;set bytes [binary format H* $raw];set ::expected [string replace $::expected $dest [expr {{$dest+[string length $bytes]-1}}] $bytes]}}
 }}
 set ::started [machine_info time]
}}
debug set_bp {entries['Execute']} {{}} {{set ::transfer_started [machine_info time]}}
debug set_bp {entries['MapEntry']} {{}} {{
 incr ::map_entries
 lassign [lindex $::maps $::m] page address expected
 debug write memory 0xc010 $page
 debug write memory 0xc011 [expr {{$address&255}}]
 debug write memory 0xc012 [expr {{$address>>8}}]
 set ::map_expected [binary format H* $expected]
 debug write_block memory 0 [string repeat [binary format c 165] 16384]
 set ::map_started [machine_info time]
}}
debug set_bp {entries['BootCase']} {{}} {{
 incr ::boot_entries
 lassign [lindex $::boot_cases $::m] page address spans
 debug write memory 0xc030 $page
 debug write memory 0xc031 [expr {{$address&255}}]
 debug write memory 0xc032 [expr {{$address>>8}}]
 set back [expr {{($::m%2)*2}}]
 debug write memory 0xc0fa $back
 foreach span $spans {{
  lassign $span dest raw
  set bytes [binary format H* $raw];set dest [expr {{$dest+$back*16384}}]
  set ::boot_expected [string replace $::boot_expected $dest [expr {{$dest+[string length $bytes]-1}}] $bytes]
 }}
 set ::boot_started [machine_info time]
}}
debug set_bp 0x4500 {{}} {{
 if {{$::verification_phase eq "boot"}} {{
  lappend ::boot_cycles [expr {{([machine_info time]-$::boot_started)*3579545}}]
  if {{[debug read_block VRAM 0 65536] ne $::boot_expected}} {{puts stderr "BOOT VRAM MISMATCH $::m";exit 5;return}}
  debug write {{VDP regs}} 1 66
  debug write {{VDP regs}} 2 [expr {{($::m%2)*32+31}}]
  incr ::m
  if {{$::m==[llength $::boot_cases]}} {{
   if {{$::boot_entries!=$::m}} {{error "Boot case arming count differs"}}
   set f [open {tcl(out/'boot-cycles.json')} w];puts $f "\\[[join $::boot_cycles ,]\\]";close $f
   puts stderr "PASS $::m boot states;full64KiB VRAM comparison";exit;return
  }}
  reg PC {entries['BootNext']};return
 }}
 if {{$::verification_phase eq "maps"}} {{
  lappend ::map_cycles [expr {{([machine_info time]-$::map_started)*3579545}}]
  if {{[debug read_block memory 0 16384] ne $::map_expected}} {{puts stderr "MAP MISMATCH $::m";exit 4;return}}
  incr ::m
  if {{$::m==[llength $::maps]}} {{
   if {{$::map_entries!=$::m}} {{error "Map case arming count differs"}}
   set f [open {tcl(out/'maps-cycles.json')} w];puts $f "\\[[join $::map_cycles ,]\\]";close $f
   puts stderr "PASS $::m decoded maps;no extra RAM segment";start_boot;return
  }}
  reg PC {entries['MapNext']};return
 }}
 lappend ::cycles [expr {{([machine_info time]-$::transfer_started)*3579545}}]
 lappend ::inclusive [expr {{([machine_info time]-$::started)*3579545}}]
 if {{[debug read_block VRAM 0 16384] ne $::expected}} {{puts stderr "VRAM mismatch case=$::n";exit 2}} else {{incr ::n}}
 if {{$::n==[llength $::cases]}} {{
  set f [open {tcl(out/'cycles.json')} w]
  puts $f "\\{{\\"transfer\\":\\[[join $::cycles ,]\\],\\"with_dispatch\\":\\[[join $::inclusive ,]\\]\\}}"
  close $f
  set f [open {tcl(out/'environment.json')} w]
  puts $f "\\{{\\"cpu_hz\\":[machine_info z80_freq],\\"cpu\\":\\"[get_active_cpu]\\"\\}}";close $f
  puts stderr "PASS $::n executing transfers;64KiB system RAM"
  set ::verification_phase maps;set ::m 0;set ::map_entries 0;set ::map_cycles {{}};reg PC {entries['MapSetup']}
 }}
}}
after time 120 {{puts stderr "TIMEOUT case=$::n PC=[reg PC]";exit 3}}
'''
    (out/'verify.tcl').write_text(script)
    if control:
        script=script.replace('set ::verification_phase maps;set ::m 0;set ::map_entries 0;set ::map_cycles {};reg PC '+str(entries['MapSetup']),'start_boot')
        (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='64',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    run=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=90)
    print(run.stderr[-1300:])
    assert run.returncode==0 and f'PASS {len(cases)} ' in run.stderr and 'PASS 71 boot states;' in run.stderr and (control or 'PASS 10 decoded maps;' in run.stderr),run.stderr[-1500:]
    measured=json.loads((out/'cycles.json').read_text())
    observed=json.loads((out/'environment.json').read_text())
    assert observed==dict(cpu_hz=3579545,cpu='z80'),observed
    def summary(values):
        ordered=sorted(values)
        return dict(mean=sum(values)/len(values),p95=ordered[int(len(values)*.95)],maximum=max(values))
    return dict(backend='ASCII16 control' if control else 'MegaRAM' if megaram else 'ASCII8',transfers=len(cases),passed=True,
        system_ram_kib=64,diagnostic_bytes=len(image),
        diagnostic_sha256=hashlib.sha256(image).hexdigest(),
        machine='Panasonic_FS-A1WSX_NR64',cpu=observed['cpu'],cpu_hz=observed['cpu_hz'],
        vdp='V9958;128KiB VRAM;cmdtiming real;hardware sprite limits enabled',
        transfer_video='SCREEN4;display off',boot_video='SCREEN5;display on after state0;IRQ disabled',
        transfer_timing_scope='One transfer per diagnostic dispatch; no frame, IRQ audio, gameplay, visible drawing or synchronization workload',
        decoder_and_setup_bytes=entries['MapEnd']-entries['MapSetup'],
        source_files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ['scripts/renderer_backend_verify.py','scripts/megaram_window_probe.py','tests/fixtures/issue41-map-decoder.inc','src/screen4/session-boot.inc']},
        transfer_cycles=summary(measured['transfer']),with_dispatch_cycles=summary(measured['with_dispatch']),
        decoded_map_banks=0 if control else 10,map_decode_cycles=None if control else summary(json.loads((out/'maps-cycles.json').read_text())),
        boot_states=71,boot_draw_cycles=summary(json.loads((out/'boot-cycles.json').read_text())),
        scope='Guest transfer/map/replay components with independent RAM/VRAM checks. No complete game, disk-to-MegaRAM loader, integrated deadlines or full-frame performance qualification')


if __name__=='__main__':
    build()
    result=[verify(control=True),verify(False),verify(True)]
    baseline=json.loads((ROOT/'references/build/game-original-ascii16-test/cycles.json').read_text())['transfer']
    for row,directory in zip(result[1:],['game-compact-ascii8-test','game-compact-megaram-test']):
        values=json.loads((ROOT/'references/build'/directory/'cycles.json').read_text())['transfer']
        delta=[round(after-before,3) for before,after in zip(baseline,values)]
        row['transfer_delta_cycles_vs_ascii16']=dict(mean=sum(delta)/len(delta),minimum=min(delta),maximum=max(delta),
            slower=sum(d>0 for d in delta),unchanged=sum(d==0 for d in delta),faster=sum(d<0 for d in delta))
        prior=json.loads((ROOT/'references/build/game-original-ascii16-test/boot-cycles.json').read_text())
        current=json.loads((ROOT/'references/build'/directory/'boot-cycles.json').read_text())
        changes=[round(n-o,3) for o,n in zip(prior,current)]
        table=(ROOT/'references/build/game/newrallyx.rom').read_bytes()[124*16384+4096:][:356]
        ticks=[int.from_bytes(table[i*5+3:i*5+5],'little') for i in range(71)]
        row['boot_delta_cycles_vs_ascii16']=dict(mean=sum(changes)/71,minimum=min(changes),maximum=max(changes),
            slower=sum(d>0 for d in changes),unchanged=sum(d==0 for d in changes),faster=sum(d<0 for d in changes))
        margins=[(ticks[i]-ticks[i-1])*59736-current[i] for i in range(1,71)]
        row['boot_original_tick_gap_probe']=dict(minimum_remaining_cycles=min(margins),overruns=sum(v<0 for v in margins),
            caveat='Drawing only with visible SCREEN5 from the second state. IRQ, key scanning, publication and integrated cold scheduling excluded; not deadline acceptance.')
    (ROOT/'docs/measurements/cartridge/issue41-backend-execution.json').write_text(json.dumps(result,indent=2)+'\n')
