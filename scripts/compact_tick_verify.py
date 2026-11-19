"""Compare native-tick gameplay/PSG after a renderer-only cadence improvement.

Real keyboard starts and held direction; explicit identical PRNG injection at
new-game preparation is a differential fixture, not a natural RNG test. Never
compare actors at the same presentation index when elapsed tick counts differ.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from compact_game_build import symbols
from src.toolchain.msx.emulator import reference_machine,tcl


def trace(bundle,ram_kind='mapper',ticks=256):
    bundle=Path(bundle);rom=bundle/'newrallyx.rom';s=symbols(bundle/'lab.sym')
    out=Path(tempfile.mkdtemp(prefix='native-tick-proof-',dir=bundle))
    startup=f'cart {tcl(rom)} -romtype ASCII8\nreset'
    if json.loads((bundle/'session-build.json').read_text())['cartridge_mapper']=='MegaRAM':
        from compact_game_verify import profile_startup
        startup=profile_startup(out)
    text=f'''set save_settings_on_exit false
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
{startup}
set ::phase boot;set ::age 0;set ::n 0
set ::f [open {tcl(out/'ticks.tsv')} w]
debug set_bp {s['Full_FirstBody']} {{$::phase eq "start"}} {{debug write memory 0xe000 52;debug write memory 0xe001 18}}
debug set_bp {s['Game_Events']} {{$::phase eq "active"}} {{
 puts $::f "$::n [binary encode hex [debug read_block memory 0xe000 768]] [binary encode hex [debug read_block {{PSG regs}} 0 14]] [debug read memory 0xc040] [debug read memory 0xc490] [debug read memory 0xc50b]"
 incr ::n
 if {{$::n=={ticks}}} {{close $::f;puts stderr "PASS{ticks} native ticks";exit}}
}}
proc poll {{}} {{
 incr ::age
 set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0;keymatrixdown 8 32}}}}
 start {{if {{$::age==5}} {{keymatrixup 0 2}};if {{$state==0 && [debug read memory 0xc00c]}} {{set ::phase active}}}}
 }}
 after time 0.02 poll
}}
after time 0.02 poll
after time 600 {{puts stderr "TIMEOUT native ticks $::n";exit 2}}
'''
    (out/'verify.tcl').write_text(text)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='64',NRX_REFERENCE_RAM_KIND=ram_kind,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    r=subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,capture_output=True,text=True,timeout=120)
    (out/'output.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and f'PASS{ticks} native ticks' in r.stderr,r.stderr[-1000:]
    return out,(out/'ticks.tsv').read_text().splitlines()


def verify():
    variants=['game-issue42-976-baseline','game-compact-runtime','game-compact-megaram-runtime']
    traces=[trace(ROOT/'references/build'/n) for n in variants]
    for name,(out,rows) in zip(variants[1:],traces[1:]):
        assert rows==traces[0][1],(name,out,next((i,a,b) for i,(a,b) in enumerate(zip(traces[0][1],rows)) if a!=b))
    report=dict(passed=True,native_ticks=256,held_input='up, set before game initialization',controlled_rng_seed=0x1234,
        variants={name:hashlib.sha256((ROOT/'references/build'/name/'newrallyx.rom').read_bytes()).hexdigest() for name in variants},
        trace_sha256=hashlib.sha256(('\n'.join(traces[0][1])+'\n').encode()).hexdigest(),
        scope='Per native tick: original E000..E2FF RAM,14 PSG registers, game/death/round state. Keyboard coin/start/held up.256 ticks of first round, not full-course acceptance.')
    for out,_ in traces:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':verify()
