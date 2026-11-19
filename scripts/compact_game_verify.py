"""Run the complete compact game with keyboard input, HUD and real VDP timing."""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from compact_game_build import symbols
from src.toolchain.msx.emulator import reference_machine,tcl
from megaram_window_probe import extension_setup


def profile_startup(out):
    """Real DOS filesystem startup for both matched profiler/control runs.

    The host supplies files and an empty MegaRAM extension, never image bytes
    through the debugger. The same game observers arm only after cold boot.
    """
    out=Path(out);files=out/'files';files.mkdir(exist_ok=True)
    fixed=any(p.name=='game-fixedram-megaram-runtime' for p in out.resolve().parents)
    source=ROOT/('dist/experimental/fixedram/megaram' if fixed else 'dist/compact/megaram')
    if not fixed:
        expected=hashlib.sha256((out.parent/'newrallyx.rom').read_bytes()).hexdigest()
        if json.loads((source/'manifest.json').read_text())['rom_sha256']!=expected:
            source=ROOT/'references/cache/fixedram-controls/megaram'
            assert json.loads((source/'manifest.json').read_text())['rom_sha256']==expected,'Historical MegaRAM control package unavailable'
    for p in source.glob('NRXMEGA.*'):shutil.copyfile(p,files/p.name)
    for n in ['msxdos.sys','command.com']:shutil.copyfile(ROOT/'references/cache/dos-validation'/n,files/n.upper())
    (files/'AUTOEXEC.BAT').write_bytes(b'NRXMEGA\r\n')
    required=json.loads((source/'manifest.json').read_text())['minimum_megaram_kib']
    size=int(os.environ.get('NRX_MEGARAM_KIB',required))
    return (extension_setup(out,size,'MegaRAM_profile')+
        f'source [file join $::env(OPENMSX_SYSTEM_DATA) scripts _disasm.tcl]\ndiska {tcl(files)}\nreset\n')


def verify(mode='rom',size=1024,expanded=False,fault=None,main_ram_kib=64,ram_kind='mapper',fixed_ram=False,topology='expanded',script_transform=None):
    mega=mode!='rom'
    owner='game-fixedram' if fixed_ram else 'game-compact'
    bundle=ROOT/'references/build'/(owner+'-megaram-runtime' if mega else owner+'-runtime')
    rom=bundle/'newrallyx.rom'
    if not mega and fixed_ram:
        default=ROOT/'dist/newrallyx.rom'
        rom=default if default.exists() and default.read_bytes()==rom.read_bytes() else ROOT/'dist/experimental/fixedram/newrallyx.rom'
    syms=symbols(bundle/'lab.sym')
    out=ROOT/'references/sessions'/('compact-game' if not mega else f'compact-megaram-{mode}-{size}'+('-expanded' if expanded else '')+('-'+fault if fault else ''))
    if main_ram_kib!=64:out=out.with_name(out.name+f'-ram{main_ram_kib}')
    if ram_kind=='plain':out=out.with_name(out.name+'-plain64')
    if fixed_ram:out=out.with_name(out.name+'-fixed')
    if topology!='expanded':out=out.with_name(out.name+'-'+topology)
    out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(rom,out/'measured.rom')
    startup=f'cart {tcl(rom)} -romtype ASCII8\nreset'
    if topology=='shared':startup=startup.replace('cart ','cartc ')
    hooks='';integrity=''
    mega_dist=ROOT/('dist/experimental/fixedram/megaram' if fixed_ram else 'dist/compact/megaram')
    required=json.loads((mega_dist/'manifest.json').read_text())['minimum_megaram_kib'] if mega else 0
    negative=mega and (size<required or fault is not None)
    if mega:
        loader=symbols(bundle/'megaram-loader.sym')
        files=out/'files';files.mkdir(exist_ok=True)
        for p in mega_dist.glob('NRXMEGA.*'):shutil.copyfile(p,files/p.name)
        if mode=='dos':
            for n in ['msxdos.sys','command.com']:shutil.copyfile(ROOT/'references/cache/dos-validation'/n,files/n.upper())
            (files/'AUTOEXEC.BAT').write_bytes(b'NRXMEGA\r\n')
        if fault=='missing':(files/'NRXMEGA.DAT').unlink()
        elif fault=='count':
            raw=bytearray((files/'NRXMEGA.DAT').read_bytes());raw[7]-=2;(files/'NRXMEGA.DAT').write_bytes(raw)
        elif fault=='distance':
            (files/'NRXMEGA.DAT').write_bytes(b'NRXMGR1'+bytes([rom.stat().st_size//8192])+b'\x03\0\0\0\x80\x01\0')
        startup=extension_setup(out,size,'MegaRAM_live')
        if topology=='shared':
            assert '{primary slot="1"}' in startup
            startup=startup.replace('{primary slot="1"}','{primary slot="3"}')
            startup=startup.replace('ext MegaRAM_live',f'''set f [open {tcl(out/'userdata/extensions/MegaRAM_live.xml')} r];set xml [read $f];close $f
set xml [string map [list {{secondary slot="any"}} {{secondary slot="3"}}] $xml]
set f [open {tcl(out/'userdata/extensions/MegaRAM_live.xml')} w];puts $f $xml;close $f
ext MegaRAM_live''')
        if expanded:
            startup=startup.replace('ext MegaRAM_live',f'''set f [open {tcl(out/'userdata/extensions/MegaRAM_live.xml')} r];set xml [read $f];close $f
set xml [string map [list {{secondary slot="any"}} {{secondary slot="2"}}] $xml]
set f [open {tcl(out/'userdata/extensions/MegaRAM_live.xml')} w];puts $f $xml;close $f
ext MegaRAM_live''')
        startup+=f'diska {tcl(files)}\nreset\n'
        loader_prefix=(bundle/'loader.bin').read_bytes()[:16].hex()
        hooks=f'''
set ::loader_started 0;set ::takenover 0;set ::loader_error 0
set ::mega_device ""
foreach d [debug list] {{if {{[debug size $d]=={size*1024} && [string match *Mega* $d]}} {{set ::mega_device $d}}}}
if {{$::mega_device eq ""}} {{error "MegaRAM device missing"}}
set f [open {tcl(rom)} rb];set ::expected_image [read $f];close $f
set ::before_image [debug read_block $::mega_device 0 {size*1024}]
debug set_bp {loader['Entry']} {{[debug read_block memory 0xc100 16] eq [binary format H* {loader_prefix}]}} {{set ::loader_started 1;puts stderr "LOADER entered"}}
debug set_bp {loader['Takeover']} {{$::loader_started}} {{
 if {{[debug read_block $::mega_device 0 [string length $::expected_image]] ne $::expected_image}} {{puts stderr "LOADED IMAGE MISMATCH";exit 7;return}}
 set ::takenover 1
 {'if {([debug read memory '+str(loader['MegaSlot'])+']&143)!=143} {error "MegaRAM is not in shared-primary slot3.3"}' if topology=='shared' else ''}
 puts stderr "LOADED all compact image bytes;slot=[debug read memory {loader['MegaSlot']}]"
}}
debug set_bp {loader['Fail']} {{$::loader_started && !$::takenover && !$::loader_error && [debug read_block memory 0xc100 16] eq [binary format H* {loader_prefix}]}} {{
 set ptr [reg DE];set message ""
 for {{set i 0}} {{$i<100}} {{incr i}} {{set c [debug read memory [expr {{$ptr+$i}}]];if {{$c==36}} break;append message [format %c $c]}}
 puts stderr "LOADER ERROR: $message"
 if {{{1 if negative else 0}}} {{
  set ::loader_error 1
  after time 1 {{
   if {{{1 if size<required or fault in ('distance','count','missing') else 0} && [debug read_block $::mega_device 0 {size*1024}] ne $::before_image}} {{puts stderr "REJECTED INPUT MODIFIED MEGARAM";exit 10;return}}
   puts stderr "PASS expected loader rejection;MegaRAM unchanged";exit
  }}
 }} else {{exit 6}}
}}
'''
        if mode=='basic':hooks+=f'after time 10 {{type_via_keybuf {tcl(chr(13)+"run "+chr(34)+"NRXMEGA.BAS"+chr(34)+chr(13)).replace(chr(13),r"\r")}}}\n'
        integrity='if {[debug read_block $::mega_device 0 [string length $::expected_image]] ne $::expected_image} {puts stderr "Game modified MegaRAM image";exit 7;return}'
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
source [file join $::env(OPENMSX_SYSTEM_DATA) scripts _disasm.tcl]
set cmdtiming real
set limitsprites true
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
{startup}
set ::test_phase boot;set ::age 0;set ::presents 0;set ::active 0
set ::periods {{}};set ::psg_changes 0;set ::psg_prior ""
{hooks}
debug set_bp {syms['Compact_InvalidBank']} {{[debug read_block memory {syms['Compact_InvalidBank']} 4] eq [binary format H* f37618fc]}} {{puts stderr "INVALID LOGICAL BANK [reg E] PC=[reg PC]";exit 9}}
set VDP.too_fast_vram_access_callback {{puts stderr "VDP timing violation PC=[reg PC]";exit 8}}
debug set_bp {syms['GameTurbo_FrameDone']} {{{'$::takenover' if mega else '1'}}} {{
 incr ::presents
 if {{$::test_phase eq "active"}} {{
  set t [machine_info time]
  if {{[info exists ::last]}} {{lappend ::periods [expr {{($t-$::last)*3579545}}]}}
  set ::last $t
  incr ::active
  set p [debug read_block {{PSG regs}} 0 14]
  if {{$p ne $::psg_prior}} {{incr ::psg_changes;set ::psg_prior $p}}
  if {{$::active==300}} {{
   {integrity}
   set f [open {tcl(out/'periods.json')} w];puts $f "\\[[join $::periods ,]\\]";close $f
   foreach {{device name size}} {{memory final.ram 65536 VRAM final.vram 131072 {{VDP regs}} final.regs 64 {{PSG regs}} final.psg 14}} {{
    set f [open [file join {tcl(out)} $name] wb];puts -nonewline $f [debug read_block $device 0 $size];close $f
   }}
   puts stderr "PASS300 gameplay presentations;PSG changes=$::psg_changes";exit
  }}
 }}
}}
proc step {{}} {{
 incr ::age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::test_phase {{
  boot {{if {{$state==1 && $ready}} {{puts stderr "TITLE ready";keymatrixdown 0 32;set ::test_phase coin;set ::age 0}}}}
  coin {{
   if {{$::age==5}} {{keymatrixup 0 32}}
   if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::test_phase start;set ::age 0}}
  }}
  start {{
   if {{$::age==5}} {{keymatrixup 0 2}}
   if {{$state==0 && $::presents>2}} {{puts stderr "ACTIVE gameplay";keymatrixdown 8 32;set ::test_phase active;set ::age 0}}
  }}
  active {{
   if {{$::age==20}} {{keymatrixdown 8 1}}
   if {{$::age==35}} {{keymatrixup 8 1}}
  }}
 }}
 after time 0.02 poll
}}
proc poll {{}} {{if {{[catch step problem]}} {{puts stderr "ERROR $problem";exit 2}}}}
after time 0.02 poll
after time {600 if mega else 120} {{puts stderr "TIMEOUT $::test_phase PC=[reg PC] state=[debug read memory 0xc7d0] presents=$::presents";exit 3}}
'''
    if script_transform is not None:script=script_transform(script,syms,out)
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB=str(main_ram_kib),NRX_REFERENCE_RAM_KIND=ram_kind,NRX_REFERENCE_PLAIN_TOPOLOGY=topology,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    r=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=120)
    print(r.stderr[-2000:]);(out/'output.log').write_text(r.stdout+r.stderr)
    match=re.search(r'Reference (?:plain RAM|RAM mapper): (\d+) bytes',r.stderr)
    assert match,'Missing actual reference RAM evidence'
    observed_ram=int(match[1])//1024
    if ram_kind=='plain':assert 'RAM mapper: 0 bytes' in r.stderr
    if negative:
        expected=('1 MiB MegaRAM required' if required==1024 else f'{required} KiB MegaRAM required') if size<required else 'NRXMEGA.DAT not found' if fault=='missing' else 'NRXMEGA.DAT is truncated or corrupt'
        assert r.returncode==0 and 'PASS expected loader rejection;' in r.stderr and 'LOADER ERROR: '+expected in r.stderr,r.stderr[-2000:]
        report=dict(passed=True,mode=mode,megaram_kib=size,negative=fault or 'capacity',image_unchanged=True,expanded_slot=expanded,main_ram_kib=observed_ram,main_ram_kind=ram_kind,main_mapper_bytes=0 if ram_kind=='plain' else observed_ram*1024,rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest())
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    if r.returncode or 'PASS300' not in r.stderr:raise RuntimeError(r.stderr[-2000:])
    periods=json.loads((out/'periods.json').read_text())
    sys.path.insert(0,str(ROOT/'src/toolchain/screen4'))
    from session_contracts import validate
    graphics=validate(out,bundle)
    report=dict(rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),bytes=rom.stat().st_size,mode=mode,megaram_kib=size if mega else None,expanded_slot=expanded,
        main_ram_kib=observed_ram,main_ram_kind=ram_kind,main_mapper_bytes=0 if ram_kind=='plain' else observed_ram*1024,slot_topology=topology,frames=len(periods)+1,smoke_presented_fps=3579545/(sum(periods)/len(periods)),
        period_mean=sum(periods)/len(periods),period_p95=sorted(periods)[int(len(periods)*.95)],period_max=max(periods),
        graphics=graphics,active_filter=f'Unfiltered{len(periods)+1} completed presentations; death/stopped intervals may be included; not active-play acceptance',scope='Complete-game smoke test; all-state/audio equivalence and matched performance use separate ledgers')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['rom','dos','basic'],default='rom')
    parser.add_argument('--size',type=int,default=1024);parser.add_argument('--expanded',action='store_true')
    parser.add_argument('--fault',choices=['missing','distance','count'])
    parser.add_argument('--ram-kib',type=int,default=64)
    parser.add_argument('--ram-kind',choices=['mapper','plain'],default='mapper')
    parser.add_argument('--fixed-ram',action=argparse.BooleanOptionalAction,default=True)
    parser.add_argument('--topology',choices=['expanded','unexpanded','shared'],default='expanded')
    args=parser.parse_args();verify(args.mode,args.size,args.expanded,args.fault,args.ram_kib,args.ram_kind,args.fixed_ram,args.topology)
