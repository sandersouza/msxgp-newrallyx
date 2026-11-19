"""Observe the accepted cartridge's first-round RNG/flags with real keyboard input.

Natural runs are read-only. One separate diagnostic injects a declared RNG
word in RAM before placement; no program bytes or guest registers are changed.
Private logs retain raw positions;
the durable comparison stores only hashes and RNG state metadata.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.toolchain.msx.emulator import reference_machine,tcl


def run(delay,override_seed=None,advance_after=None,*,baseline=True,repeat=0):
    rom=ROOT/'dist/newrallyx.rom';bundle=ROOT/'references/build/game-compact-runtime'
    if baseline:
        assert hashlib.sha256(rom.read_bytes()).hexdigest()=='b5684933f5dcae72d5552b51cbca64a28458fa980795334d6491ce3f55c66e4a', 'Baseline diagnostic only; use issue42_rng_verify.py for the correction'
    syms={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    layout=json.loads((bundle/'layout.json').read_text());page=layout['raw_bank_pages']['71']
    prefix=rom.read_bytes()[page*8192+0x2e00:page*8192+0x2e40].hex()
    out=ROOT/f'references/build/game-issue42/msx-delay{delay:g}'
    if override_seed is not None:out=out.with_name(out.name+f'-controlled{override_seed}')
    if advance_after is not None:out=out.with_name(out.name+f'-next{advance_after:g}')
    if not baseline:out=out.with_name(out.name+f'-candidate-repeat{repeat}')
    out.mkdir(parents=True,exist_ok=True)
    injection='' if override_seed is None else f'debug write memory 0xe000 {override_seed&255};debug write memory 0xe001 {override_seed>>8};'
    candidate_hooks='' if baseline else f'''
set ui_stream [open {tcl(out/'ui-rng.tsv')} w]
puts $ui_stream "remaining\\trng"
debug set_bp {syms['GameSession_UI.random']} {{[debug read_block memory 0xae00 64] eq $::prefix}} {{puts $::ui_stream "[reg HL]\\t[word 0xe000]";flush $::ui_stream}}
debug set_bp {syms['GameSession_ColdLoad']} {{$::phase eq "starting"}} {{emit cold_begin}}
'''
    (out/'measured.rom').write_bytes(rom.read_bytes())
    code=f'''set save_settings_on_exit false
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
cart {tcl(rom)} -romtype ASCII8
reset
set phase boot;set age 0;set recorded 0;set captured 0
set advance_after {-1 if advance_after is None else advance_after}
set f [open {tcl(out/'events.tsv')} w]
puts $f "event\\ttime\\trng\\tflags\\tround\\trocks"
proc word {{a}} {{expr {{[debug read memory $a]+256*[debug read memory [expr {{$a+1}}]]}}}}
proc emit {{name}} {{
 set p [word 0xe992]
 puts $::f "$name\\t[machine_info time]\\t[word 0xe000]\\t[binary encode hex [debug read_block memory $p 20]]\\t[debug read memory 0xe1b0]\\t[debug read memory 0xe251]";flush $::f
}}
set prefix [binary format H* {prefix}]
{candidate_hooks}
debug set_bp {syms['Full_FirstBody.seed_ready']} {{$::phase eq "starting" && [debug read_block memory 0xae00 64] eq $::prefix}} {{emit seed_before}}
debug set_bp {syms['Full_FirstBody.seed_ready']+6} {{$::phase eq "starting" && [debug read_block memory 0xae00 64] eq $::prefix}} {{emit seed_after}}
debug set_bp {syms['Full_NextBody']} {{$::phase in {{starting advancing}} && [debug read_block memory 0xae00 64] eq $::prefix}} {{emit prepare_begin}}
debug set_bp 0x9379 {{$::phase in {{starting advancing}} && [debug read_block memory 0xae00 64] eq $::prefix}} {{{injection}emit flags_begin}}
debug set_bp 0x940c {{$::phase in {{starting advancing}} && [debug read_block memory 0xae00 64] eq $::prefix}} {{emit flags_end;set ::recorded 1}}
debug set_bp {syms['GameTurbo_FrameDone']} {{$::phase in {{starting advancing}} && $::recorded && !$::captured && [debug read memory 0xc7d0]==0 && [debug read memory 0xc00c]==1}} {{
 foreach {{device name size}} {{memory final.ram 65536 VRAM final.vram 131072 {{VDP regs}} final.regs 64}} {{
  set snapshot_stream [open [file join {tcl(out)} $name] wb];puts -nonewline $snapshot_stream [debug read_block $device 0 $size];close $snapshot_stream
 }}
 set ::captured 1
}}
proc step {{}} {{
 incr ::age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
  boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
  coin {{
   if {{$::age==5}} {{keymatrixup 0 32}}
   if {{$::age>8 && $state==6 && $ready}} {{set ::selected [machine_info time];set ::phase waiting}}
  }}
  waiting {{if {{[machine_info time]-$::selected>={delay}}} {{keymatrixdown 0 2;set ::phase starting;set ::age 0}}}}
  starting {{
   if {{$::age==5}} {{keymatrixup 0 2}}
   if {{$::captured}} {{
    if {{$::advance_after<0}} {{close $::f;exit}}
    set ::played [machine_info time];set ::phase playing
   }}
  }}
  playing {{
   if {{[machine_info time]-$::played>=$::advance_after}} {{keymatrixdown 7 2;set ::phase advancing;set ::age 0;set ::captured 0;set ::recorded 0}}
  }}
  advancing {{
   if {{$::age==5}} {{keymatrixup 7 2}}
   if {{$::captured}} {{close $::f;exit}}
  }}
 }}
 after time 0.02 step
}}
after time 0.02 step
after time 100 {{puts stderr "Seed probe timeout $::phase";exit 2}}
'''
    (out/'probe.tcl').write_text(code)
    with (out/'openmsx.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'probe.tcl')],check=True,timeout=90,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,NRX_REFERENCE_RAM_KIB='64',
                OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=list(csv.DictReader((out/'events.tsv').open(),delimiter='\t'))
    by={r['event']:r for r in rows}
    assert set(by)=={'seed_before','seed_after','prepare_begin','flags_begin','flags_end'} | (set() if baseline else {'cold_begin'})
    if baseline:assert int(by['seed_after']['rng'])==1
    else:
        first_prepare=next(r for r in rows if r['event']=='prepare_begin')
        assert int(by['cold_begin']['rng'])==int(by['seed_before']['rng'])==int(by['seed_after']['rng'])==int(first_prepare['rng'])
        from scripts.arcade_maze_flags_probe import advance
        ui=list(csv.DictReader((out/'ui-rng.tsv').open(),delimiter='\t'))
        assert ui and int(ui[0]['rng'])==257, 'Original default-DIP boot seed'
        for previous,current in zip(ui,ui[1:]):
            if int(previous['remaining']):
                assert int(current['remaining'])==int(previous['remaining'])-1
                assert int(current['rng'])==advance(int(previous['rng']))
            else:assert current['rng']==previous['rng']
    sys.path.insert(0,str(ROOT/'src/toolchain/screen4'))
    from session_contracts import validate
    graphics=validate(out,bundle)
    return dict(start_delay_seconds=delay,controlled_seed=override_seed,advance_after_seconds=advance_after,native_round=int(by['flags_end']['round']),rock_count=int(by['flags_end']['rocks']),rng_before_prepare=int(by['prepare_begin']['rng']),first_flag_positions_sha256=hashlib.sha256(bytes.fromhex(next(r for r in rows if r['event']=='flags_end')['flags'])).hexdigest(),graphics_passed=graphics['passed'],rng_before_reset=int(by['seed_before']['rng']),
        rng_after_reset=int(by['seed_after']['rng']),rng_before_placement=int(by['flags_begin']['rng']),
        rng_after_placement=int(by['flags_end']['rng']),
        flag_positions_sha256=hashlib.sha256(bytes.fromhex(by['flags_end']['flags'])).hexdigest(),
        ui_advances=None if baseline else sum(int(r['remaining'])>0 for r in ui),
        evidence=str(out.relative_to(ROOT)))


if __name__=='__main__':
    rows=[run(delay) for delay in (0,.5,2)]
    assert len({r['flag_positions_sha256'] for r in rows})==1
    controlled=run(0,override_seed=0x1234)
    later=[run(0,advance_after=d) for d in (.2,.6)]
    from scripts.arcade_maze_flags_probe import place_objects
    from src.toolchain.graphics.roms import load_metadata,validate_roms
    from scripts.extract_graphics import _region
    metadata=load_metadata()
    program=_region(validate_roms(ROOT/'references/roms/nrallyx',metadata),metadata,'maincpu',16384)
    layout=json.loads((ROOT/'references/build/game-compact-runtime/layout.json').read_text())
    native_at=layout['raw_bank_pages']['71']*8192
    assert (ROOT/'dist/newrallyx.rom').read_bytes()[native_at+0x3000:native_at+0x3400]==program[0x3000:0x3400]
    for r in rows+[controlled]+later:
        state,calls,flags,_=place_objects(program,r['rng_before_placement'] if r['controlled_seed'] is not None else r['rng_before_prepare'],0x30, r['rock_count'])
        assert r['rng_after_placement']==state and r['flag_positions_sha256']==hashlib.sha256(flags).hexdigest()
    assert controlled['flag_positions_sha256']!=rows[0]['flag_positions_sha256']
    assert len({r['flag_positions_sha256'] for r in later})==2
    assert all(r['native_round']==3 and r['first_flag_positions_sha256']==rows[0]['flag_positions_sha256'] for r in later)
    delivery=json.loads((ROOT/'dist/release/newrallyx-1.0.0.json').read_text())
    preserved={}
    for name,path in [('newrallyx.rom','dist/newrallyx.rom'),('newrallyx-megaram.zip','dist/compact/megaram/newrallyx-megaram.zip'),('newrallyx-disk.zip','dist/disk/newrallyx-disk.zip')]:
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        assert actual==delivery['artifacts'][name]['sha256']
        preserved[path]=actual
    report=dict(rom_sha256=hashlib.sha256((ROOT/'dist/newrallyx.rom').read_bytes()).hexdigest(),preserved_artifacts=preserved,
        original_geometry_pages_already_in_cartridge=True,runs=rows,controlled_seed_probe=controlled,next_round_probes=later,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),main_ram_kib=64,scope='Accepted ASCII8 cartridge, real credit/start and read-only observers. First game and next-round F5 probes (not naturally earned completion). Separate controlled-seed probe changes one RAM word before placement, checks original algorithm and independent display oracle. No runtime implementation or performance claim.')
    target=ROOT/'docs/measurements/cartridge/issue42-msx-flag-seed.json'
    target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
