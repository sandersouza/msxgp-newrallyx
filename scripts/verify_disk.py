"""Boot the delivered Disk BASIC files using a real disk-ROM filesystem path."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.toolchain.msx.emulator import reference_machine, tcl


def verify(ram_kib=4096, mode='basic', expected_error=None, fault=None):
    if mode=='rom' and json.loads((ROOT/'dist/manifest.json').read_text()).get('mapper')=='ASCII8':
        from scripts.compact_game_verify import verify as verify_compact
        return verify_compact('rom',main_ram_kib=ram_kib,fixed_ram=True)
    output = ROOT/f'references/sessions/disk-{mode}-{ram_kib}{"-"+fault if fault else ""}'
    output.mkdir(parents=True,exist_ok=True)
    disk = output/'files'
    disk.mkdir(exist_ok=True)
    for source in (ROOT/'dist/disk').glob('NRALLYX.*'):
        shutil.copyfile(source,disk/source.name)
    if fault == 'missing':
        (disk/'NRALLYX.DAT').unlink()
    elif fault == 'truncated':
        (disk/'NRALLYX.DAT').write_bytes((disk/'NRALLYX.DAT').read_bytes()[:64])
    elif fault == 'checksum':
        damaged = bytearray((disk/'NRALLYX.DAT').read_bytes())
        damaged[10] ^= 1
        (disk/'NRALLYX.DAT').write_bytes(damaged)
    elif fault == 'distance':
        (disk/'NRALLYX.DAT').write_bytes(b'NRXDSK1\x7d\x03\x00\x00\x00\x80\x01\x80')
    if mode == 'dos':
        for name in ('msxdos.sys','command.com'):
            source = ROOT/'references/cache/dos-validation'/name
            if not source.is_file():
                raise ValueError('Supply MSX-DOS1 boot files in references/cache/dos-validation')
            shutil.copyfile(source,disk/name.upper())
        (disk/'AUTOEXEC.BAT').write_bytes(b'NRALLYX\r\n')
    sym_path = ROOT/('references/build/game/lab.sym' if mode == 'rom' else 'references/build/game-disk/disk.sym')
    syms = {n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',sym_path.read_text())}
    if 'GameTurbo_Loop' in syms:
        syms['loop'] = syms['GameTurbo_Loop']
        syms['frame_done'] = syms['GameTurbo_FrameDone']
    loader = {n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',
                                            (ROOT/'references/build/game-disk/loader.sym').read_text())}
    script = f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
source [file join $::env(OPENMSX_SYSTEM_DATA) scripts _disasm.tcl]
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
{('cart '+tcl(ROOT/'dist/newrallyx.rom')+' -romtype ASCII16') if mode == 'rom' else ('diska '+tcl(disk))}
reset
set ::booted 0
set ::loader_entered 0
debug set_bp {loader['BasicEntry'] if mode == 'basic' else loader['DosEntry']} {{}} {{set ::loader_entered 1;puts stderr "loader entry [machine_info time] BDOS=[binary encode hex [debug read_block memory 5 3]] SP=[reg SP]"}}
debug set_bp {loader['Entry.reserved']} {{}} {{puts stderr "mapper reserved [machine_info time]"}}
debug set_bp {loader['Entry.token']} {{{1 if fault == 'distance' else 0} && ![info exists ::initial_output]}} {{set ::initial_output [debug read memory 0x8000]}}
debug set_bp {loader['Fail']} {{$::loader_entered && !$::booted}} {{
 if {{{1 if fault == 'distance' else 0} && [info exists ::initial_output] && [debug read memory 0x8000] != $::initial_output}} {{puts stderr "OUTPUT MODIFIED by invalid distance";exit 8;return}}
 set ptr [reg DE]
 set message ""
 for {{set i 0}} {{$i<100}} {{incr i}} {{
  set c [debug read memory [expr {{$ptr+$i}}]]
  if {{$c==36}} break
  append message [format %c $c]
 }}
 puts stderr "LOADER ERROR: $message PC=[reg PC] DE=[reg DE] SP=[reg SP] bank=[debug read memory {loader['Bank']}] target=[debug read memory {loader['Target']}] P2=[debug read ioports 254] P3=[debug read ioports 255]"
 set f [open {tcl(output/'failed.ram')} wb];puts -nonewline $f [debug read_block memory 0 65536];close $f
 set ::error_observed 1
 if {{{0 if expected_error else 1}}} {{exit 2}}
}}
debug set_bp {loader['Fail.basic']} {{[info exists ::error_observed]}} {{
 if {{[debug read ioports 254] != [debug read memory {loader['OriginalP2']}]}} {{puts stderr "Error path did not restore Page2";exit 9;return}}
 after time 0.2 {{puts stderr "error returned to Disk BASIC";exit 0}}
}}
debug set_bp 0x4010 {{!$::booted && ({1 if mode == 'rom' else 0} || ($::loader_entered && [debug read memory {loader['Bank']}] == 125))}} {{
 set ::booted 1
 puts stderr "takeover [machine_info time]"
 if {{{0 if mode == 'rom' else 1}}} {{
 set stream [open {tcl(ROOT/'references/build/game-disk/disk-image.bin')} rb]
 set expected [read $stream];close $stream
 set device ""
 foreach d [debug list] {{if {{[debug desc $d] eq "memory mapper" && [debug size $d]==4194304}} {{set device $d}}}}
 if {{$device eq ""}} {{error "4 MiB mapper missing"}}
 set actual [debug read_block $device 0 [string length $expected]]
 if {{$actual ne $expected}} {{
  for {{set n 0}} {{$n<125}} {{incr n}} {{
   set offset [expr {{$n*16384}}]
   if {{[string range $actual $offset [expr {{$offset+16383}}]] ne [string range $expected $offset [expr {{$offset+16383}}]]}} {{puts stderr "BANK MISMATCH $n actual=[binary encode hex [string range $actual $offset [expr {{$offset+31}}]]] expected=[binary encode hex [string range $expected $offset [expr {{$offset+31}}]]]"}}
  }}
  exit 4
 }}
 puts stderr "all125 bank bytes verified"
 set ::image_device $device
 set ::expected_image $expected
 }}
 after time 3 {{keymatrixdown 8 1}}
 after time 3.2 {{keymatrixup 8 1}}
 set ::phase boot;set ::age 0
 after time 0.02 poll
}}
set ::phase loading
set ::periods {{}}
set ::work {{}}
set ::waits {{}}
set ::publication {{}}
set ::eligible {{}}
set ::active_frames 0
set ::psg_changed 0
set ::psg_prior ""
debug set_bp {syms['loop']} {{$::phase in {{armed active}}}} {{
 if {{$::phase eq "armed"}} {{
  set ::phase active;set ::age 0;set ::active_start [machine_info time]
  keymatrixdown 8 32
  puts stderr "active gameplay [machine_info time]"
 }}
 set ::frame_start [machine_info time]
 set ::frame_eligible [eligible]
}}
debug set_bp {syms['wait_blank']} {{$::phase eq "active" && [info exists ::frame_start]}} {{
 lappend ::work [expr {{([machine_info time]-$::frame_start)*3579545}}]
 set ::wait_start [machine_info time]
 unset ::frame_start
}}
debug set_bp {syms['commit']} {{$::phase eq "active" && [info exists ::wait_start]}} {{
 lappend ::waits [expr {{([machine_info time]-$::wait_start)*3579545}}]
 unset ::wait_start
 set ::publication_start [machine_info time]
}}
debug set_bp {syms['frame_done']} {{$::phase eq "active"}} {{
 if {{[info exists ::publication_start]}} {{lappend ::publication [expr {{([machine_info time]-$::publication_start)*3579545}}];unset ::publication_start}}
 if {{[info exists ::previous_frame]}} {{lappend ::periods [expr {{([machine_info time]-$::previous_frame)*3579545}}]}}
 set ::previous_frame [machine_info time]
 incr ::active_frames
 lappend ::eligible [expr {{$::frame_eligible && [eligible]}}]
 if {{$::active_frames==300}} {{finish}}
}}
proc poll {{}} {{
 if {{[catch step problem]}} {{puts stderr "VERIFY ERROR: $problem";exit 5}}
}}
proc eligible {{}} {{
 expr {{![debug read memory {syms['Death_State']}] && ![debug read memory {syms['Round_State']}] && ![debug read memory {syms['paused']}] && ![debug read memory {syms['Game_State']}] && ![debug read memory {syms['Full_Attract']}]}}
}}
proc step {{}} {{
 incr ::age
 set state [debug read memory 0xc7d0]
 set ready [debug read memory 0xc7dd]
 switch $::phase {{
  boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0;puts stderr "title ready"}}}}
  coin {{
   if {{$::age==5}} {{keymatrixup 0 32}}
   if {{$::age>8 && $state==6 && $ready}} {{
    if {{[debug read memory 0xc7d2]!=1}} {{error "Credit insertion failed"}}
    keymatrixdown 0 2;set ::phase start;set ::age 0
   }}
  }}
  start {{
   if {{$::age==5}} {{keymatrixup 0 2}}
   if {{$state==5}} {{set ::saw_intro 1}}
   if {{$state==0 && [info exists ::saw_intro] && ![debug read memory {syms['Full_Attract']}]}} {{
    set ::phase armed;set ::age 0
   }}
  }}
  active {{
   if {{$::age==20}} {{keymatrixdown 8 1}}
   if {{$::age==35}} {{keymatrixup 8 1}}
   set psg [debug read_block {{PSG regs}} 0 14]
   if {{$psg ne $::psg_prior}} {{incr ::psg_changed;set ::psg_prior $psg}}
  }}
 }}
 after time 0.02 poll
}}
proc finish {{}} {{
 if {{$::psg_changed<2}} {{puts stderr "PSG did not advance";exit 6;return}}
 if {{[info exists ::image_device] && [debug read_block $::image_device 0 [string length $::expected_image]] ne $::expected_image}} {{puts stderr "Game modified its immutable image banks";exit 7;return}}
 set f [open {tcl(output/'game.ram')} wb];puts -nonewline $f [debug read_block memory 0 65536];close $f
 set f [open {tcl(output/'game.vram')} wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f
 set f [open {tcl(output/'game.regs')} wb];puts -nonewline $f [debug read_block {{VDP regs}} 0 64];close $f
 set f [open {tcl(output/'game.psg')} wb];puts -nonewline $f [debug read_block {{PSG regs}} 0 14];close $f
 set f [open {tcl(output/'work.txt')} w];puts $f [join $::work \n];close $f
 set f [open {tcl(output/'periods.txt')} w];puts $f [join $::periods \n];close $f
 set f [open {tcl(output/'waits.txt')} w];puts $f [join $::waits \n];close $f
 set f [open {tcl(output/'publication.txt')} w];puts $f [join $::publication \n];close $f
 set f [open {tcl(output/'eligible.txt')} w];puts $f [join $::eligible \n];close $f
 puts stderr "PASS active_frames=$::active_frames PSG_changes=$::psg_changed seconds=[expr {{[machine_info time]-$::active_start}}]"
 exit
}}
after time 10 {{type_via_keybuf {tcl('run "NRALLYX.BAS"'+chr(13) if mode == 'basic' else chr(13)).replace(chr(13), r'\r')}}}
after time 600 {{puts stderr "TIMEOUT PC=[reg PC] SP=[reg SP] PPI=[debug read ioports 168] P2=[debug read ioports 254] P3=[debug read ioports 255] slot=[debug read memory 65535] bytes=[binary encode hex [debug read_block memory 0x4000 32]] RAMAD=[binary encode hex [debug read_block memory 0xf341 4]] booted=$::booted entered=$::loader_entered";exit 3}}
'''
    (output/'verify.tcl').write_text(script)
    env = dict(os.environ,OPENMSX_HOME=str(output/'home'),OPENMSX_USER_DATA=str(output/'userdata'),
               NRX_REFERENCE_RAM_KIB=str(ram_kib))
    with (output/'openmsx.log').open('w') as log:
        result = subprocess.run(['openmsx','-script',str(output/'verify.tcl')],env=env,
                                stdout=log,stderr=subprocess.STDOUT,timeout=150)
    print((output/'openmsx.log').read_text()[-3500:])
    if result.returncode:
        raise SystemExit(result.returncode)
    log_text = (output/'openmsx.log').read_text()
    if expected_error:
        expected = ('4 MiB main-slot RAM mapper required' if ram_kib < 4096 else
                    'NRALLYX.DAT not found' if fault == 'missing' else
                    'NRALLYX.DAT is truncated or corrupt')
        assert expected in log_text, log_text
        assert 'OUTPUT MODIFIED' not in log_text, log_text
        assert 'error returned to Disk BASIC' in log_text, log_text
    else:
        assert 'PASS active_frames=' in log_text, log_text
        flags = [int(v) for v in (output/'eligible.txt').read_text().split()]
        def statistics(name):
            mask = [a and b for a,b in zip(flags,flags[1:])] if name == 'periods.txt' else flags
            raw = [float(v) for v in (output/name).read_text().split()]
            assert len(raw) == len(mask), (name,len(raw),len(mask))
            values = sorted(v for v,eligible in zip(raw,mask) if eligible)
            return dict(samples=len(values),mean=sum(values)/len(values),
                        p95=values[int((len(values)-1)*.95)],maximum=max(values))
        report = dict(mode=mode,mapper_ram_kib=ram_kib,refresh_hz=3579545/59736,
                      nominal_refresh_hz=60,refresh_cycles=59736,two_refresh_budget_cycles=119472,
                      artifact_sha256=hashlib.sha256((ROOT/('dist/newrallyx.rom' if mode=='rom' else 'references/build/game-disk/disk-image.bin')).read_bytes()).hexdigest(),
                      workload='300 completed presentations of natural first-round three-enemy active gameplay, right held and one smoke pulse',
                      active_filter='Both interval endpoints exclude death, round transitions, pause, game-over and attract mode',
                      cycle_unit='elapsed Z80-base-equivalent cycles at 3579545 Hz; includes IRQ and VDP stalls',
                      work=statistics('work.txt'),synchronization_wait=statistics('waits.txt'),
                      publication=statistics('publication.txt'),presentation_period=statistics('periods.txt'))
        report['presented_fps']=3579545/report['presentation_period']['mean']
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['basic','dos','rom'], default='basic')
    parser.add_argument('--ram-kib',type=int,default=4096)
    parser.add_argument('--expect-error',action='store_true')
    parser.add_argument('--fault',choices=['missing','truncated','checksum','distance'])
    args = parser.parse_args()
    verify(args.ram_kib,args.mode,args.expect_error,args.fault)
