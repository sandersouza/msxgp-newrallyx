"""Boot experimental NRX512 DOS/BASIC files and observe real native gameplay.

No cartridge, code/asset/OS debugger injection or cold-provider interception.
Keyboard is the input; the frozen ROM file is an independent graphics oracle.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/toolchain/screen4'),str(ROOT)]
from compact_game_build import symbols
from compact_game_report import distribution
from src.toolchain.msx.emulator import reference_machine,tcl,boot_test_key_bindings
from session_contracts import validate


def opening_contract(out,runtime):
    """Compare every published SCREEN5 state to contributor arcade captures."""
    from PIL import Image
    from session_boot import status_overlay
    meta=json.loads((runtime/'session-boot.json').read_text());colors=[tuple(c) for c in meta['palette']]
    raw=(out/'opening.bin').read_bytes();rows=list(csv.DictReader((out/'opening.tsv').open(),delimiter='\t'))
    assert len(rows)==len(meta['sample_frames']) and len(raw)==len(rows)*27136
    hashes=[]
    for i,(row,n) in enumerate(zip(rows,meta['sample_frames'])):
        src=list(Image.open(meta['frame_paths'][i]).convert('RGB').get_flattened_data())
        pix=[colors.index(src[y*288+x]) for y in range(212) for x in list(range(200))+list(range(232,288))]
        wanted=bytes(a*16+b for a,b in zip(pix[::2],pix[1::2]))
        if n in meta['hardware_status']['native_frames']:
            wanted=status_overlay(wanted,(runtime/'ui-font.bin').read_bytes(),meta['hardware_status']['ink'],512,int(row['turbo'])>0)
        actual=raw[i*27136:(i+1)*27136]
        assert actual==wanted,('Opening pixels',i,n)
        assert int(row['border'])&15==0
        hashes.append(hashlib.sha256(actual).hexdigest())
    errors=[int(row['ticks'])-int(rows[1]['ticks'])-(tick-meta['publication_ticks'][1]) for row,tick in zip(rows,meta['publication_ticks'])][1:]
    assert errors and max(map(abs,errors))==0,('Opening publication ticks changed',errors)
    return dict(passed=True,frames=len(rows),frame_sha256=hashes,publication_tick_error_max=0,scope='Published packed VRAM pixels, black border register and original publication cadence; original captures plus512KiB status overlay. No physical scanout/listening claim.')


def verify(mode='dos',frames=180,round_number=2,f10=False,transitions=False,seed=None,input_clock='native',bundle=None,runtime=None,profile_audio=False,script_transform=None):
    bundle=Path(bundle) if bundle is not None else ROOT/'references/build/game-mapper512-game'
    runtime=Path(runtime) if runtime is not None else ROOT/'references/build/game-mapper512-game-runtime'
    plan=json.loads((bundle/'plan.json').read_text());s=symbols(runtime/'lab.sym')
    bridge_owner=ROOT/'references/build/game-mapper512-testrom' if mode=='rom512' else bundle
    c=symbols(bridge_owner/'mapper512-cold.asm.sym')
    out=Path(tempfile.mkdtemp(prefix=f'{mode}-r{round_number}-f10{int(f10)}-',dir=bundle));files=out/'files';files.mkdir()
    for p in (bundle/'files').glob('NRX512.*'):shutil.copyfile(p,files/p.name)
    if mode=='dos':
        for n in ['msxdos.sys','command.com']:shutil.copyfile(ROOT/'references/cache/dos-validation'/n,files/n.upper())
        (files/'AUTOEXEC.BAT').write_bytes(b'NRX512\r\n')
    from mapper512_reference import reference
    shutil.copyfile(reference(),out/'measured.rom')
    carrier=ROOT/'dist/experimental/mapper512/newrallyx-512-test.rom'
    startup=f'cart {tcl(carrier)} -romtype ASCII8' if mode=='rom512' else f'diska {tcl(files)}'
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
{boot_test_key_bindings()}
{startup}
reset
set ::phase loading;set ::age 0;set ::count 0;set ::presents 0;set ::disk_calls 0;set ::callbacks 0;set ::started 0;set ::work_start 0;set ::work 0
set ::last 0;set ::start_active 0;set ::epoch 0;set ::start_epoch 0;set ::warm 0;set ::seeded 0
set ::audio_cost 0;set ::irq_cost 0;set ::audio_irq_cost 0;set ::audio_calls 0;set ::work_live 0;set ::audio_live 0
set ::trace [open {tcl(out/'frames.tsv')} w]
set ::opening [open {tcl(out/'opening.bin')} wb]
set ::opening_log [open {tcl(out/'opening.tsv')} w]
puts $::opening_log "turbo\tborder\tticks"
puts $::trace "frame\tcx\tcy\tround\tenemies\tactive\twork\tperiod\tticks\tpsg\tnative\taudio_cost\tirq_cost\taudio_irq_cost\taudio_calls"
proc checked {{script}} {{if {{[catch {{uplevel 1 $script}} e]}} {{puts stderr "FAIL $e PC=[reg PC] phase=$::phase disk=$::disk_calls";exit 2}}}}
proc word {{a}} {{expr {{[debug read memory $a]+256*[debug read memory [expr {{$a+1}}]]}}}}
proc ramcode {{bank}} {{
 set p [debug read ioports 168];set sub [expr {{255-[debug read memory 65535]}}]
 expr {{[debug read ioports 253]%32==$bank && ($p&12)==(($p>>4)&12) && ($sub&12)==(($sub>>4)&12)}}
}}
proc maincode {{}} {{
 set p [debug read ioports 168];set sub [expr {{255-[debug read memory 65535]}}]
 expr {{[debug read ioports 252]%32==1 && ($p&3)==(($p>>6)&3) && ($sub&3)==(($sub>>6)&3)}}
}}
proc active {{}} {{expr {{[debug read memory 0xc7d0]==0 && [debug read memory 0xc00c] && [debug read memory 0xc400] && ![debug read memory 0xc490] && ![debug read memory {s['Round_State']}]}}}}
proc snapshot {{name}} {{
 foreach {{d e n}} {{memory ram 65536 VRAM vram 131072 {{VDP regs}} regs 64}} {{set f [open [file join {tcl(out)} "$name.$e"] wb];puts -nonewline $f [debug read_block $d 0 $n];close $f}}
}}
set VDP.too_fast_vram_access_callback {{puts stderr "FAIL VDP timing PC=[reg PC]";exit 7}}
debug set_bp 0x4010 {{[ramcode 6] && !$::started}} {{set ::started 1;puts stderr "NATIVE BOOT disk=$::disk_calls";set ::phase boot;set ::age 0}}
debug set_bp {s['GameSession_BootShow']} {{$::started && $::phase eq "boot" && [maincode]}} {{puts stderr "OPENING";if {{{int(f10)}}} {{nrx_boot_f10_down}}}}
debug set_bp {s['GameSession_BootShow.published']} {{$::started && $::phase eq "boot" && [maincode]}} {{
 set base [expr {{([debug read {{VDP regs}} 2]&96)*1024}}]
 puts -nonewline $::opening [debug read_block VRAM $base 27136];flush $::opening
 puts $::opening_log "[debug read memory 0xd2f8]\t[debug read {{VDP regs}} 7]\t[word {s['clock_ticks']}]";flush $::opening_log
 foreach r {{8 9 10}} {{if {{[debug read {{PSG regs}} $r]}} {{puts stderr "FAIL opening sound";exit 8}}}}
}}
debug set_bp {s['GameSession_UI']} {{{int(seed is not None)} && !$::seeded && [maincode]}} {{debug write memory 0xe000 {(seed or 0)&255};debug write memory 0xe001 {((seed or 0)>>8)&255};set ::seeded 1}}
debug set_bp {c['Mapper512_GameFailed']} {{[ramcode 30]}} {{snapshot failed;puts stderr "FAIL native cold bridge PC=[reg PC] SP=[reg SP] callback=$::callbacks disk=$::disk_calls record=[debug read memory {c['Cold_Target']}]";exit 3}}
debug set_bp {c['Cold_Bdos']} {{[ramcode 30]}} {{checked {{
 incr ::disk_calls
}}}}
debug set_bp {c['Cold_Read']} {{[ramcode 30] && [maincode] && [debug read ioports 255]%32==0}} {{checked {{
 # BDOS exposes borrowed OS Page3: its Cxxx bytes are not native game state.
 # Check the read boundary while the real game state is still mapped instead.
 if {{$::started && [active]}} {{error "Filesystem access during active gameplay"}}
}}}}
debug set_bp {c['Mapper512_GameCommand']} {{[ramcode 30]}} {{checked {{
 if {{[reg IFF]!=0}} {{error "Cold callback entered with IRQ enabled"}}
 incr ::callbacks;puts stderr "CALLBACK op=[reg A] layout=[debug read memory 0xdfc9] ready=[debug read memory 0xc00c] SP=[reg SP]"
}}}}
debug set_bp {s['GameSession_ColdLoad']} {{$::phase eq "active" && [maincode]}} {{incr ::epoch}}
debug set_bp {s['GameTurbo_Loop']} {{$::phase eq "active" && [maincode]}} {{set ::work_start [machine_info time];set ::start_active [active];set ::start_epoch $::epoch;set ::audio_cost 0;set ::irq_cost 0;set ::audio_irq_cost 0;set ::audio_calls 0;set ::work_live 1}}
debug set_bp {s['wait_blank']} {{$::phase eq "active" && [ramcode 6]}} {{set ::work [expr {{([machine_info time]-$::work_start)*3579545}}];set ::work_live 0}}
debug set_bp {s['GameTurbo_FrameDone']} {{$::started && [maincode]}} {{checked {{
 incr ::presents
 if {{$::phase eq "active"}} {{
  incr ::warm
  if {{{int(seed is not None)} && $::warm<8}} {{set ::last [machine_info time]}} else {{
  incr ::count;set now [machine_info time];set period [expr {{($now-$::last)*3579545}}];set ::last $now
  set good [expr {{$::start_active && [active] && $::start_epoch==$::epoch}}]
  if {{[debug read memory 0xc0ee]!={int(f10)}}} {{error "F10 latch changed"}}
  puts $::trace "$::count\t[word 0xc000]\t[word 0xc002]\t[debug read memory 0xe1b0]\t[debug read memory 0xe24e]\t$good\t$::work\t$period\t[debug read memory 0xc026]\t[binary encode hex [debug read_block {{PSG regs}} 0 14]]\t[binary encode hex [debug read_block memory 0xe088 224]]\t$::audio_cost\t$::irq_cost\t$::audio_irq_cost\t$::audio_calls";flush $::trace
  if {{$good && $::count%40==0}} {{snapshot "frame-$::count"}}
  if {{$::count=={frames}}} {{snapshot final
   foreach device [debug list] {{if {{[debug desc $device] eq "memory mapper" && [debug size $device]==524288}} {{
    set f [open {tcl(out/'physical.dump')} wb];puts -nonewline $f [debug read_block $device 0 524288];close $f
   }}}}
   close $::trace;puts stderr "PASS native RAM game frames=$::count disk=$::disk_calls callbacks=$::callbacks";exit
  }} else {{
   keymatrixup 8 255;set clock {'[expr {[word 0xc440]/2}]' if input_clock=='native' else '$::count'}
   set mask [lindex {{128 64 16 32}} [expr {{($clock/24)%4}}]];if {{$clock%48<6}} {{set mask [expr {{$mask|1}}]}};keymatrixdown 8 $mask
   if {{{int(transitions)} && $::count==120}} {{keymatrixdown 7 2;after time .10 {{keymatrixup 7 2}}}}
  }}
  }}
 }}
}}}}
proc poll {{}} {{
 if {{$::phase eq "active"}} return
 # Filesystem calls temporarily expose OS workspace in Page3. Only observe
 # native lifecycle state after both main and resident game owners return.
 if {{$::started && (![maincode] || ![ramcode 6])}} {{after time .02 {{checked poll}};return}}
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{puts stderr "TITLE";nrx_boot_f10_up;set ::phase release;set ::age 0}}}}
 release {{if {{$::age>8 && ![debug read memory 0xc0fb]}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{
  if {{$::age==5}} {{keymatrixup 0 2}}
  if {{$state==0 && [debug read memory 0xc00c]}} {{
   if {{[debug read memory 0xe1b0]=={round_number}}} {{set ::phase active;set ::last [machine_info time]}} else {{set ::phase advance;set ::age 0}}
  }}
 }}
 advance {{
  if {{$::age==10}} {{set ::prior_round [debug read memory 0xe1b0];keymatrixdown 7 2;after time .10 {{keymatrixup 7 2}}}}
  if {{$::age>18 && $state==0 && [debug read memory 0xc00c] && [debug read memory 0xe1b0]>$::prior_round}} {{
   if {{[debug read memory 0xe1b0]=={round_number}}} {{set ::phase active;set ::last [machine_info time]}} else {{set ::age 0}}
  }}
 }}
 }}
 after time .02 {{checked poll}}
}}
after time .02 {{checked poll}}
after time 1500 {{snapshot timeout;puts stderr "TIMEOUT phase=$::phase PC=[reg PC] SP=[reg SP] disk=$::disk_calls callbacks=$::callbacks round=[debug read memory 0xe1b0]";exit 4}}
'''
    if profile_audio:
        source=(runtime/'assembly/session-audio-linked.bin').read_bytes()
        prefix=source[s['Audio_RuntimeStep']-0x8000:s['Audio_RuntimeStep']-0x8000+8].hex()
        hook=f'''
proc cost_audio_return {{}} {{
 set ::audio_cost [expr {{$::audio_cost+([machine_info time]-$::cost_audio_start)*3579545}}]
 incr ::audio_calls;set ::audio_live 0;debug remove_bp $::cost_audio_bp
}}
proc cost_irq_return {{}} {{
 set cost [expr {{([machine_info time]-$::cost_irq_start)*3579545}}]
 set ::irq_cost [expr {{$::irq_cost+$cost}}]
 if {{$::cost_irq_audio}} {{set ::audio_irq_cost [expr {{$::audio_irq_cost+$cost}}]}}
 debug remove_bp $::cost_irq_bp
}}
debug set_bp {s['Audio_RuntimeStep']} {{$::work_live && [debug read_block memory {s['Audio_RuntimeStep']} 8] eq [binary format H* {prefix}]}} {{
 set ::cost_audio_start [machine_info time];set ::audio_live 1
 set stack [reg SP];set ret [word $stack]
 set ::cost_audio_bp [debug set_bp $ret "\\[reg SP\\]==[expr {{$stack+2}}] && \\[maincode\\]" {{cost_audio_return}}]
}}
debug set_bp {s['Mapper512_IRQ']} {{$::work_live && [debug read ioports 255]%32==0}} {{
 set ::cost_irq_start [machine_info time];set ::cost_irq_audio $::audio_live
 set stack [reg SP];set ret [word $stack]
 set ::cost_irq_bp [debug set_bp $ret "\\[reg SP\\]==[expr {{$stack+2}}]" {{cost_irq_return}}]
}}
'''
        script=script.replace('proc poll {} {',hook+'\nproc poll {} {')
    if mode=='basic':script+=f'after time 10 {{type_via_keybuf {tcl(chr(13)+"run "+chr(34)+"NRX512.BAS"+chr(34)+chr(13)).replace(chr(13),r"\r")}}}\n'
    if script_transform is not None:script=script_transform(script,s,out)
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='512',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    p=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=180)
    (out/'output.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0 and 'PASS native RAM game' in p.stderr,p.stderr[-3000:]
    graphics=validate(out,runtime);assert graphics['passed']
    opening=opening_contract(out,runtime)
    family=(out/'final.ram').read_bytes()[s['Full_Layout']]
    actual=(out/'physical.dump').read_bytes();expected=(runtime/f'stage-{family}/hot-image.bin').read_bytes()
    mask=(runtime/f'stage-{family}/live-mask.bin').read_bytes();checked=0
    for bank in [7,8,9]+list(range(11,32)):
        lo=bank*16384;hi=lo+16384
        assert all(not mask[i] or actual[i]==expected[i] for i in range(lo,hi)),('Hot owner changed',bank)
        checked+=sum(mask[lo:hi])
    rows=list(csv.DictReader((out/'frames.tsv').open(),delimiter='\t'));active_rows=[r for r in rows if r['active']=='1'];assert active_rows
    if transitions:assert {int(r['round']) for r in rows}=={round_number,round_number+1},'Real F5 transition did not complete'
    report=dict(passed=True,mode=mode,frames=frames,native_round=round_number,f10=f10,transitions=transitions,seed=seed,input_clock=input_clock,profile_audio=profile_audio,diagnostic_state_writes=2 if seed is not None else 0,active_frames=len(active_rows),
                work=distribution(float(r['work']) for r in active_rows),period=distribution(float(r['period']) for r in active_rows),
                graphics=graphics,opening=opening,immutable_live_bytes_checked=checked,resource_sha256=plan['resource_sha256'],bridge_sha256=plan['bridge_sha256'],verification_script_sha256=hashlib.sha256((out/'verify.tcl').read_bytes()).hexdigest(),
                cartridge=mode=='rom512',host_payload_injections=0,scope=('Native RAM game from diagnostic embedded-resource cartridge; not filesystem proof.' if mode=='rom512' else 'Native game from real DOS/BASIC filesystem; no cartridge or intercepted cold provider.')+' Emulator/short-route proof, not hardware or full acceptance.',path=str(out.relative_to(ROOT)))
    if mode=='rom512':report['carrier_sha256']=hashlib.sha256(carrier.read_bytes()).hexdigest()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--mode',choices=['dos','basic','rom512'],default='dos');a.add_argument('--frames',type=int,default=180)
    a.add_argument('--round',type=int,default=2);a.add_argument('--f10',action='store_true');a.add_argument('--transitions',action='store_true')
    a.add_argument('--seed',type=int);a.add_argument('--input-clock',choices=['native','presentation'],default='native')
    a.add_argument('--bundle',type=Path);a.add_argument('--runtime',type=Path)
    a.add_argument('--profile-audio',action='store_true')
    p=a.parse_args();verify(p.mode,p.frames,p.round,p.f10,p.transitions,p.seed,p.input_clock,p.bundle,p.runtime,p.profile_audio)
