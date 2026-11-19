"""Observe fixed-input original native ticks after cartridge or512KiB boot.

Two-byte PRNG seed is the only debugger state write. Code/OS/assets, clocks
and native catch-up are never injected or overridden. Natural deaths and
restarts remain enabled unless the real boot-held F10 option is selected.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]/'src/toolchain/screen4')]
from compact_game_build import symbols
from src.toolchain.msx.emulator import reference_machine,tcl,boot_test_key_bindings
from session_contracts import validate

ROOT=Path(__file__).resolve().parents[1]


def trace(mode='dos',ticks=512,f10=False,players=1,audio_sync=False,bundle=None,runtime=None):
    candidate=mode!='rom'
    source_bundle=Path(runtime) if runtime is not None else ROOT/'references/build'/('game-mapper512-game-runtime' if candidate else 'game-compact-runtime')
    owner=Path(bundle) if bundle is not None else ROOT/'references/build/game-mapper512-game' if candidate else source_bundle
    bundle=source_bundle
    s=symbols(bundle/'lab.sym');out=Path(tempfile.mkdtemp(prefix=f'tick-{mode}-f10{int(f10)}-p{players}-',dir=owner))
    from mapper512_reference import reference
    rom=reference();shutil.copyfile(rom,out/'measured.rom')
    source=(bundle/'assembly/newrallyx.rom').read_bytes() if candidate else rom.read_bytes()
    if candidate:native=(bundle/'assembly/game-native-linked.bin').read_bytes()
    else:
        layout=json.loads((bundle/'layout.json').read_text());at=layout['raw_bank_pages']['71']*8192;native=source[at:at+16384]
    def guard(name):
        pc=s[name]
        if pc<0x4000:return '[maincode]'
        if pc<0x8000:return f'[debug read_block memory {pc} 8] eq [binary format H* {source[pc-0x4000:pc-0x4000+8].hex()}]'
        return f'[debug read_block memory {pc} 8] eq [binary format H* {native[pc-0x8000:pc-0x8000+8].hex()}]'
    if candidate:
        files=out/'files';files.mkdir()
        for p in (owner/'files').glob('NRX512.*'):shutil.copyfile(p,files/p.name)
        if mode=='dos':
            for n in ['msxdos.sys','command.com']:shutil.copyfile(ROOT/'references/cache/dos-validation'/n,files/n.upper())
            (files/'AUTOEXEC.BAT').write_bytes(b'NRX512\r\n')
        startup=f'diska {tcl(files)}\nreset'
    else:startup=f'cart {tcl(rom)} -romtype ASCII8\nreset'
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set cmdtiming real
set limitsprites true
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
{boot_test_key_bindings()}
{startup}
set ::phase boot;set ::age 0;set ::count 0;set ::seeded 0;set ::deaths 0;set ::turns 0;set ::contacts 0;set ::f10 {int(f10)}
set ::f [open {tcl(out/'ticks.tsv')} w]
set ::life [open {tcl(out/'lifecycle.tsv')} w]
puts $::life "kind\tplayer\tplayers\tround\tf10"
proc maincode {{}} {{set p [debug read ioports 168];set sub [expr {{255-[debug read memory 65535]}}];expr {{[debug read ioports 252]%32==1 && ($p&3)==(($p>>6)&3) && ($sub&3)==(($sub>>6)&3)}}}}
proc dump {{}} {{
 foreach {{d e n}} {{memory ram 65536 VRAM vram 131072 {{VDP regs}} regs 64}} {{set f [open [file join {tcl(out)} "final.$e"] wb];puts -nonewline $f [debug read_block $d 0 $n];close $f}}
}}
set VDP.too_fast_vram_access_callback {{puts stderr "FAIL VDP timing";exit 7}}
debug set_bp {s['GameSession_BootShow']} {{[maincode]}} {{if {{$::f10}} {{nrx_boot_f10_down}}}}
debug set_bp {s['Full_FirstBody']} {{$::phase eq "start" && !$::seeded && ({guard('Full_FirstBody')})}} {{debug write memory 0xe000 52;debug write memory 0xe001 18;set ::seeded 1}}
debug set_bp {s['GameSession_ColdLoad']} {{[maincode]}} {{puts $::life "[debug read memory {s['GameSession_LoadKind']}]\t[debug read memory {s['Full_Player']}]\t[debug read memory {s['Full_Players']}]\t[debug read memory 0xe1b0]\t[debug read memory 0xc0ee]";flush $::life}}
debug set_bp {s['Death_Begin']} {{{guard('Death_Begin')} && ([debug read memory {s['Rock_Contact']}] || [debug read memory {s['Enemy_Contact']}])}} {{incr ::contacts;if {{!$::f10}} {{incr ::deaths}}}}
debug set_bp {s['GameSession_Death']} {{[maincode]}} {{incr ::turns}}
debug set_bp {s['Game_Events']} {{$::phase eq "active" && $::count<{ticks} && ({guard('Game_Events')})}} {{
 puts $::f "$::count [binary encode hex [debug read_block memory 0xe000 768]] [binary encode hex [debug read_block {{PSG regs}} 0 14]] [debug read memory 0xc040] [debug read memory 0xc490] [debug read memory 0xc50b]"
 incr ::count
}}
debug set_bp {s['GameTurbo_FrameDone']} {{$::count=={ticks} && [maincode]}} {{
 if {{[debug read memory 0xc0ee]!=$::f10}} {{puts stderr "FAIL F10 changed";exit 8}}
 dump;close $::f;close $::life;puts stderr "PASS native ticks=$::count deaths=$::deaths turns=$::turns contacts=$::contacts";exit
}}
proc poll {{}} {{
 if {{$::phase eq "active"}} return
 if {{$::phase ne "boot" && ![maincode]}} {{after time .02 poll;return}}
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready && [maincode]}} {{nrx_boot_f10_up;set ::phase release;set ::age 0}}}}
 release {{if {{$::age>8 && ![debug read memory 0xc0fb]}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{{players}==2 && $::age==10}} {{keymatrixdown 0 32}};if {{{players}==2 && $::age==15}} {{keymatrixup 0 32}};if {{$::age>{8 if players==1 else 18} && $state==6 && $ready}} {{keymatrixdown 0 {2 if players==1 else 4};keymatrixdown 8 32;set ::phase start;set ::age 0}}}}
 start {{if {{$::age==5}} {{keymatrixup 0 {2 if players==1 else 4}}};if {{$state==0 && [debug read memory 0xc00c]}} {{set ::phase active}}}}
 }}
 after time .02 poll
}}
after time .02 poll
after time 1500 {{puts stderr "FAIL timeout phase=$::phase ticks=$::count deaths=$::deaths turns=$::turns PC=[reg PC]";exit 3}}
'''
    if audio_sync:
        # Observe the worker's exact inputs and matched stack return; no code,
        # clocks, PSG registers or game state is written by these hooks.
        addresses=[s[n] for n in ['Audio_Mute','Audio_Held','Audio_NewScene','Audio_Elapsed','Session_State','Death_State','paused','Full_Attract','Round_State','Flag_Count','Flag_Kind','Smoke_Placements']]+[0xe048,0xe069,0xe06a,0xe06b,0xe1b0]
        if candidate:audio=(bundle/'assembly/session-audio-linked.bin').read_bytes()
        else:
            at=layout['raw_bank_pages']['73']*8192;audio=source[at:at+16384]
        audio_prefix=audio[s['Audio_RuntimeStep']-0x8000:s['Audio_RuntimeStep']-0x8000+8].hex()
        hook=f'''
set ::audio_epoch 0;set ::audio_age 0;set ::last_death 0;set ::last_flags 0;set ::last_smoke 0;set ::epoch_sample_pending 1
set ::sync [open {tcl(out/'audio-sync.tsv')} w]
puts $::sync "native\tclock\tlast_audio\telapsed\tworker_calls\tpsg"
set ::worker [open {tcl(out/'audio-worker.tsv')} w]
puts $::worker "native\tclock\tlast_audio\telapsed\tepoch\tage\tinputs\tbefore\tafter\tpsg\tcycles\tgain_clock\tgain_key\tgain_volume\treturn_clock"
set ::events [open {tcl(out/'audio-events.tsv')} w]
puts $::events "native\tclock\tepoch\tevent\tvalue"
set ::phase_profile [open {tcl(out/'phase-cycles.tsv')} w];set ::phase_pending 0;set ::phase_irq 0
puts $::phase_profile "native\ttarget\tfront\tkeys\tlookup\tselected\tcycles\tirq"
proc syncword {{a}} {{expr {{[debug read memory $a]+256*[debug read memory [expr {{$a+1}}]]}}}}
proc audiocode {{}} {{expr {{[maincode] && [debug read_block memory {s['Audio_RuntimeStep']} 8] eq [binary format H* {audio_prefix}]}}}}
proc audio_return {{}} {{
 puts $::worker "$::audio_n\t$::audio_clock\t$::audio_last\t$::audio_elapsed\t$::audio_epoch\t$::audio_age\t$::audio_input\t$::audio_before\t[binary encode hex [debug read_block memory 0xe9a0 80]]\t[binary encode hex [debug read_block {{PSG regs}} 0 14]]\t[expr {{([machine_info time]-$::audio_begin)*3579545}}]\t$::gain_clock\t$::gain_key\t$::gain_volume\t[syncword {s['clock_ticks']}]";flush $::worker
 debug remove_bp $::audio_return_bp
}}
proc phase_return {{}} {{
 puts $::phase_profile "$::count\t$::phase_target\t$::phase_front\t$::phase_keys\t$::phase_lookup\t[debug read memory 0xc027]\t[expr {{([machine_info time]-$::phase_begin)*3579545}}]\t$::phase_irq";flush $::phase_profile
 set ::phase_pending 0;debug remove_bp $::phase_return_bp
}}
debug set_bp {s['GameSession_PhaseSelect']} {{[maincode]}} {{
 if {{[reg A]!=[debug read memory {s['phase']}]}} {{puts stderr "FAIL phase input/global contract";exit 11}}
 if {{$::phase eq "active" && [debug read memory 0xc00c]}} {{
  set ::phase_target [reg A];set ::phase_front [debug read memory 0xc028];set ::phase_keys [binary encode hex [debug read_block memory 0x2820 8]];set ::phase_lookup [binary encode hex [debug read_block memory 0x28c0 64]]
  set ::phase_begin [machine_info time];set ::phase_pending 1;set ::phase_irq 0
  set stack [reg SP];set ret [syncword $stack]
  set ::phase_return_bp [debug set_bp $ret "\\[reg SP\\]==[expr {{$stack+2}}] && \\[maincode\\]" {{phase_return}}]
 }}
}}
debug set_bp {s.get('Mapper512_IRQ',s['clock_irq'])} {{$::phase_pending}} {{incr ::phase_irq}}
debug set_bp {s['GameSession_ColdLoad']} {{[maincode]}} {{incr ::audio_epoch;set ::audio_age 0;set ::epoch_sample_pending 1}}
debug set_bp {s['Audio_RuntimeStep']} {{$::phase eq "active" && [debug read memory {s['Audio_Elapsed']}]>0 && [audiocode]}} {{
 set ::audio_n $::count;set ::audio_clock [syncword {s['clock_ticks']}];set ::audio_last [debug read memory {s['Audio_LastUI']}];set ::audio_elapsed [debug read memory {s['Audio_Elapsed']}]
 set ::gain_clock -1;set ::gain_key -1;set ::gain_volume -1
 incr ::audio_age $::audio_elapsed
 set values {{}};foreach a {{{' '.join(map(str,addresses))}}} {{lappend values [debug read memory $a]}}
 set ::audio_input "$values [binary encode hex [debug read_block memory 0xe9f4 3]] [binary encode hex [debug read_block {{PSG regs}} 0 14]]"
 set ::audio_before [binary encode hex [debug read_block memory 0xe9a0 80]];set ::audio_begin [machine_info time]
 set stack [reg SP];set ret [syncword $stack]
 set ::audio_return_bp [debug set_bp $ret "\\[reg SP\\]==[expr {{$stack+2}}] && \\[maincode\\]" {{audio_return}}]
}}
debug set_bp {s['Audio_EngineGain']+3} {{$::phase eq "active" && [info exists ::audio_n] && [audiocode]}} {{set ::gain_clock [reg A];set ::gain_key [debug read memory {s['Audio_EngineKey']}]}}
debug set_bp {s['Audio_EngineGain.level']} {{$::phase eq "active" && [info exists ::audio_n] && [audiocode]}} {{set ::gain_volume [reg A]}}
debug set_bp {s['Game_Events']} {{$::phase eq "active" && ({guard('Game_Events')})}} {{
 puts $::sync "$::count\t[syncword {s['clock_ticks']}]\t[debug read memory {s['Audio_LastUI']}]\t[debug read memory {s['Audio_Elapsed']}]\t[syncword {s['Audio_Ticks']}]\t[binary encode hex [debug read_block {{PSG regs}} 0 14]]";flush $::sync
 foreach {{name address variable}} {{death {s['Death_State']} last_death flag {s['Flag_Count']} last_flags smoke {s['Smoke_Placements']} last_smoke}} {{
  set value [debug read memory $address]
  if {{!$::epoch_sample_pending && $value>[set ::$variable] && ($name ne "death" || $value==1)}} {{puts $::events "$::count\t[syncword {s['clock_ticks']}]\t$::audio_epoch\t$name\t$value";flush $::events}}
  set ::$variable $value
 }}
 set ::epoch_sample_pending 0
}}
'''
        script=script.replace('proc poll {} {',hook+'\nproc poll {} {')
    if mode=='basic':script+='after time 10 {type_via_keybuf "\\rrun \\"NRX512.BAS\\"\\r"}\n'
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='512',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    p=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=180)
    (out/'output.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0 and 'PASS native ticks' in p.stderr,p.stderr[-1500:]
    rows=(out/'ticks.tsv').read_text().splitlines();assert len(rows)==ticks
    graphics=validate(out,bundle)
    report=dict(passed=True,mode=mode,ticks=ticks,f10=f10,players=players,trace_sha256=hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest(),
        graphics=graphics,script_sha256=hashlib.sha256(script.encode()).hexdigest(),path=str(out.relative_to(ROOT)),
        observation=p.stderr.split('PASS native ticks')[-1].strip(),scope='Original E000..E2FF and14 PSG registers per native tick, held-up keyboard with seed1234; no clock override/code/OS/payload injection. Natural collisions/restarts enabled unless actual boot F10 is held.')
    import csv
    report['cold_loads']=list(csv.DictReader((out/'lifecycle.tsv').open(),delimiter='\t'))
    report['audio_sync']=audio_sync
    if candidate:
        plan=json.loads((owner/'plan.json').read_text());report.update(resource_sha256=plan['resource_sha256'],bridge_sha256=plan['bridge_sha256'])
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return out,rows


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--mode',choices=['rom','dos','basic'],default='dos');a.add_argument('--ticks',type=int,default=512)
    a.add_argument('--f10',action='store_true');a.add_argument('--players',type=int,choices=[1,2],default=1);a.add_argument('--audio-sync',action='store_true')
    a.add_argument('--bundle',type=Path);a.add_argument('--runtime',type=Path)
    p=a.parse_args();trace(p.mode,p.ticks,p.f10,p.players,p.audio_sync,p.bundle,p.runtime)
