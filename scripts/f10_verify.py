"""Keyboard-only F10 boot latch plus explicitly injected real contact handlers.

Never writes the invulnerability flag. Car/rock fixture calls the real linked
Death_Begin, restoring CPU/Page3/mapping afterwards; no natural-course claim.
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

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from compact_game_build import symbols
from src.toolchain.msx.emulator import reference_machine,tcl,boot_test_key_bindings


def verify(mode='rom',ram=64,quick=False,only_case=None,fixed_ram=False,ram_kind='mapper'):
    mega=mode.startswith('mega-');disk=mode.startswith('disk-');basic=mode.endswith('basic')
    owner='game-fixedram' if fixed_ram else 'game-compact'
    bundle=ROOT/'references/build'/('game-disk' if disk else owner+'-megaram-runtime' if mega else owner+'-runtime')
    if disk and only_case is None:
        # The legacy takeover overwrites the DOS image in main RAM. A reset
        # inside that same process does not reproduce a clean DOS bootstrap.
        # Use independent cold machines, keeping this limitation explicit.
        parts=[verify(mode,ram,True,name,fixed_ram,ram_kind) for name in ('held','normal')]
        out=Path(tempfile.mkdtemp(prefix='f10-proof-',dir=bundle))
        report=dict(parts[0],cases=['held','normal'],contact_checks=sum(p['contact_checks'] for p in parts),
            events=[name+': '+line for name,p in zip(('held','normal'),parts) for line in p['events']],
            reset_policy='Separate cold emulator processes; no legacy warm-reset qualification',children=parts)
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report
    rom=bundle/('disk-image.bin' if disk else 'newrallyx.rom')
    s=symbols(bundle/('disk.sym' if disk else 'lab.sym'))
    assert 'GameSession_BootCommitF10' in s,'Missing boot F10 implementation'
    out=Path(tempfile.mkdtemp(prefix='f10-proof-',dir=bundle))
    boot_at=124*16384 if disk else json.loads((bundle/'session-build.json').read_text())['boot_source_offset']
    prefix=rom.read_bytes()[boot_at:boot_at+16].hex()
    startup=f'cart {tcl(rom)} -romtype ASCII8\nreset';basic_command=''
    if mega:
        from compact_game_verify import profile_startup
        startup=profile_startup(out)
        if basic:
            (out/'files/AUTOEXEC.BAT').unlink();basic_command='RUN "NRXMEGA.BAS"\r'
            for n in ('MSXDOS.SYS','COMMAND.COM'):(out/'files'/n).unlink()
    if disk:
        ram=4096;files=out/'files';files.mkdir()
        for p in (ROOT/'dist/disk').glob('NRALLYX.*'):shutil.copyfile(p,files/p.name)
        if not basic:
            for n in ('msxdos.sys','command.com'):shutil.copyfile(ROOT/'references/cache/dos-validation'/n,files/n.upper())
            (files/'AUTOEXEC.BAT').write_bytes(b'NRALLYX\r\n')
        else:basic_command='RUN "NRALLYX.BAS"\r'
        startup=f'diska {tcl(files)}\nreset'
    cases=[only_case] if only_case else ['held','normal'] if quick else ['held','normal','shift_first','release_early','title_only','f5_only','shift_only','skip_held']
    expected=[int(n in ('held','shift_first','skip_held')) for n in cases]
    stub=bytearray((0x31,0xe0,0xf2,0x3e,71))
    if disk:stub.extend((0xd3,0xfe))
    else:stub.extend(b'\xcd'+s['Compact_Map16'].to_bytes(2,'little'))
    stub.extend(b'\xcd'+s['Death_Begin'].to_bytes(2,'little'))
    code=f'''set save_settings_on_exit false
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
set ::cases {{{' '.join(cases)}}};set ::expect {{{' '.join(map(str,expected))}}};set ::i 0
set ::phase boot;set ::armed 0;set ::age 0;set ::presents 0;set ::contact 0;set ::pending 0
set ::events [open {tcl(out/'events.tsv')} w]
set f [open {tcl(rom)} rb];set ::image [read $f];close $f
set ::prefix [binary format H* {prefix}]
set VDP.too_fast_vram_access_callback {{puts stderr "VDP violation PC=[reg PC]";exit 6}}
if {{[string first nrx_boot_f10_down [bind F10]]<0 || [string first nrx_boot_f10_up [bind F10,release]]<0}} {{error "Host F10 bindings missing"}}
proc f10_down {{}} {{nrx_boot_f10_down}}
proc f10_up {{}} {{nrx_boot_f10_up}}
proc schedule_basic {{}} {{
 if {{{1 if basic else 0}}} {{after time 10 {{type_via_keybuf {tcl(basic_command).replace(chr(13),r'\r')}}}}}
}}
schedule_basic
proc pages {{}} {{
 if {{{1 if disk else 0}}} {{return [list [debug read ioports 254]]}}
 set result {{}}
 foreach address {{32768 40960}} {{
  set current [debug read_block memory $address 8192];set found -1
  for {{set n 0}} {{$n<[string length $::image]/8192}} {{incr n}} {{
   if {{[string range $::image [expr {{$n*8192}}] [expr {{$n*8192+8191}}]] eq $current}} {{set found $n;break}}
  }}
  if {{$found<0}} {{error "Cannot bind contact fixture source"}}
  lappend result $found
 }}
 return $result
}}
debug set_bp {s['GameSession_BootShow']} {{!$::armed && [debug read_block memory 0x2900 16] eq $::prefix}} {{
 set ::armed 1;set kind [lindex $::cases $::i]
 if {{[debug read memory {s['GameSession_Invulnerable']}]}} {{error "Reset retained invulnerability"}}
 switch $kind {{
 held {{f10_down}}
 shift_first {{keymatrixdown 6 1;after time .3 {{keymatrixdown 7 2}}}}
 release_early {{f10_down;after time 2 f10_up}}
 f5_only {{keymatrixdown 7 2}}
 shift_only {{keymatrixdown 6 1}}
 skip_held {{f10_down;after time 1 {{keymatrixdown 8 1}}}}
 }}
}}
debug set_bp {s['GameSession_BootShow.done']} {{$::armed && $::phase eq "boot"}} {{set ::boot_skipped [debug read memory {s['GameSession_BootSkip']}]}}
debug set_bp {s['GameSession_UI']} {{$::armed && $::phase eq "boot"}} {{
 set ::latched [debug read memory {s['GameSession_Invulnerable']}]
 if {{$::latched!=[lindex $::expect $::i]}} {{error "Wrong F10 latch case=[lindex $::cases $::i] value=$::latched"}}
 # After CommitF10, the release gate may set BootSkip again while consuming
 # held keys. The replay decision was already observed at BootShow.done.
 set skipped $::boot_skipped
 set want_skip [expr {{[lindex $::cases $::i] in {{f5_only skip_held}}}}]
 if {{$skipped!=$want_skip}} {{error "Unexpected skip case=[lindex $::cases $::i] skip=$skipped"}}
 puts $::events "$::i boot $::latched $skipped";flush $::events
 set ::phase title;set ::age 0
}}
proc poll {{}} {{
 incr ::age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 title {{if {{$state==1 && $ready}} {{set ::phase hold;set ::age 0;if {{[lindex $::cases $::i] eq "title_only"}} {{f10_down}}}}}}
 hold {{
  if {{[debug read memory {s['GameSession_Invulnerable']}]!=$::latched}} {{error "Title F10 changed latch"}}
  if {{[debug read memory {s['Session_Credits']}] || [debug read memory {s['Full_UIEdges']}]}} {{error "Held boot key leaked into title"}}
  if {{$::age==15}} {{f10_up;keymatrixup 8 1;set ::phase release;set ::age 0}}
 }}
 release {{if {{$::age>=8 && ![debug read memory {s['GameSession_BootKeyGate']}]}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{
  if {{$::age==5}} {{keymatrixup 0 2}}
  if {{$state==0 && [debug read memory 0xc00c]}} {{
   set round [debug read memory 0xe1b0]
   if {{[info exists ::initial_round] && $round!=$::initial_round}} {{error "Boot F10 leaked into F5 round advance"}}
   set ::initial_round $round
   puts $::events "$::i start $round $::latched";flush $::events
   set ::phase contacts;set ::contact 0;set ::age 0
  }}
 }}
 advance {{
  if {{$::age==5}} {{keymatrixup 7 2}}
  if {{$::age>8 && $state==0 && [debug read memory 0xc00c] && [debug read memory 0xe1b0]>$::round}} {{
   if {{[debug read memory {s['GameSession_Invulnerable']}]!=$::latched}} {{error "Round load reset F10 latch"}}
   puts $::events "$::i round [debug read memory 0xe1b0] $::latched";flush $::events
   incr ::i
   if {{$::i==[llength $::cases]}} {{close $::events;puts stderr "PASS F10 cases=$::i";exit;return}}
   for {{set r 0}} {{$r<11}} {{incr r}} {{keymatrixup $r 255}}
   set ::armed 0;set ::phase boot;set ::age 0;set ::contact 0;set ::pending 0
   {'set power off;set power on' if disk else 'reset'};schedule_basic
  }}
 }}
 }}
 after time .02 checked_poll
}}
proc checked_poll {{}} {{if {{[catch poll error]}} {{puts stderr "FAIL $error";exit 2}}}}
debug set_bp {s['GameTurbo_FrameDone']} {{$::phase eq "contacts" && !$::pending}} {{
 if {{[debug read memory {s['GameSession_Invulnerable']}]!=$::latched}} {{error "New game reset F10 latch"}}
 set ::pending 1;set ::saved {{}}
 foreach name {{AF BC DE HL IX IY SP PC}} {{lappend ::saved $name [reg $name]}}
 set ::saved_ram [debug read_block memory 0xc000 13056]
 set old_pages [pages]
 debug write memory {s['Rock_Contact']} [expr {{$::contact==1}}]
 debug write memory {s['Enemy_Contact']} [expr {{$::contact==0}}]
 debug write memory {s['Death_State']} 0
 set bytes [binary format H* {bytes(stub).hex()}]
 if {{{1 if disk else 0}}} {{append bytes [binary format c* [list 62 [lindex $old_pages 0] 211 254]]}} else {{
  lassign $old_pages lower upper
  append bytes [binary format c* [list 62 $lower 50 0 {128 if mega else 112} 62 $upper 50 0 {160 if mega else 120}]]
 }}
 append bytes [binary format H* c300f1]
 debug write_block memory 0xf000 $bytes
 reg PC 0xf000
}}
debug set_bp 0xf100 {{$::pending}} {{
 set expected [expr {{$::contact<2 && !$::latched}}]
 set actual [debug read memory {s['Death_State']}]
 if {{$actual!=$expected}} {{puts stderr "FAIL lethal contact case=$::i kind=$::contact expected=$expected actual=$actual";exit 3;return}}
 puts $::events "$::i contact $::contact $actual";flush $::events
 debug write_block memory 0xc000 $::saved_ram
 foreach {{name value}} $::saved {{reg $name $value}}
 set ::pending 0;incr ::contact
 if {{$::contact==3}} {{set ::round [debug read memory 0xe1b0];keymatrixdown 7 2;set ::phase advance;set ::age 0}}
}}
after time .02 checked_poll
after time 900 {{puts stderr "TIMEOUT F10 case=$::i phase=$::phase PC=[reg PC]";exit 4}}
'''
    # Fail callback assertions immediately; openMSX otherwise logs a warning
    # and continues, producing an unrelated timeout and hiding the first error.
    code='''proc f10_bp {address condition action} {
 debug set_bp $address $condition [list f10_checked_action $action]
}
proc f10_checked_action {action} {
 if {[catch {uplevel #0 $action} problem]} {puts stderr "FAIL $problem";exit 2}
}
'''+code.replace('debug set_bp ','f10_bp ')
    (out/'verify.tcl').write_text(code)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB=str(ram),NRX_REFERENCE_RAM_KIND=ram_kind,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    r=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=180)
    (out/'output.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and f'PASS F10 cases={len(cases)}' in r.stderr,r.stderr[-1800:]
    events_log=(out/'events.tsv').read_text().splitlines()
    assert sum(' contact ' in line for line in events_log)==len(cases)*3
    report=dict(passed=True,mode=mode,main_ram_kib=ram,main_ram_kind=ram_kind,rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),cases=cases,contact_checks=len(cases)*3,
        reset_policy='Single cold process for legacy main-RAM payload' if disk else 'Reset between cases',
        events=events_log,scope='Actual keyboard matrix/host binding commands; boot hold/release/skip/title gating, reset and real F5 round transition. Contact injection calls real Death_Begin with full Page3/CPU/mapping restoration. No direct invulnerability writes, no full natural-course or physical-keyboard claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['rom','mega-dos','mega-basic','disk-dos','disk-basic'],default='rom')
    p.add_argument('--ram-kib',type=int,default=64);p.add_argument('--quick',action='store_true')
    p.add_argument('--case',choices=['held','normal','shift_first','release_early','title_only','f5_only','shift_only','skip_held'])
    p.add_argument('--fixed-ram',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--ram-kind',choices=['mapper','plain'],default='mapper')
    a=p.parse_args();verify(a.mode,a.ram_kib,a.quick,a.case,a.fixed_ram,a.ram_kind)
