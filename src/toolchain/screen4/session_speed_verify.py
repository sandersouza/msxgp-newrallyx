"""Compare the cartridge speed limiter with actual original round parameters."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import argparse,hashlib,json,math,os,re,shutil,statistics,subprocess,tempfile
from pathlib import Path
from session_reference import cartridge_path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from src.toolchain.msx.emulator import reference_machine,tcl
from src.toolchain.graphics.roms import input_records,load_metadata,validate_roms

def reference():
    out=ROOT/'references/cache/arcade-challenge-speed';out.mkdir(parents=True,exist_ok=True)
    lua=source_path('arcade-challenge-speed.lua')
    version=subprocess.check_output(['mame','-version'],text=True).strip();assert version.startswith('0.289 ')
    key=dict(script_sha256=hashlib.sha256(lua.read_bytes()).hexdigest(),emulator=version,
             roms=input_records(validate_roms(ROOT/'references/roms/nrallyx',load_metadata())))
    marker=out/'reference.json';old=json.loads(marker.read_text()) if marker.exists() else {}
    cached=old.get('inputs')==key and (out/'complete').exists() and bool(old.get('hashes'))
    cached=cached and all((out/name).exists() and hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
                          for name,digest in old.get('hashes',{}).items())
    if not cached:
        (out/'complete').unlink(missing_ok=True)
        command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(ROOT/'references/roms'),
            '-video','none','-sound','none','-nothrottle','-noautosave','-skip_gameinfo','-autoboot_delay','0',
            '-autoboot_script',str(lua),'-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','200']
        with (out/'mame.log').open('w') as log:
            subprocess.run(command,check=True,timeout=120,stdout=log,stderr=subprocess.STDOUT,
                           env=dict(os.environ,NRX_CHALLENGE_SPEED_OUTPUT=str(out)))
    assert (out/'complete').exists(),(out/'mame.log').read_text()[-600:]
    cases=[]
    for round_ in (2,3,4,8,12,16):
        data=(out/f'round-{round_}.bin').read_bytes();word=lambda a:int.from_bytes(data[a:a+2],'little')
        cases.append(dict(native_round=round_,display_round=round_-1,enemy0=word(0x25),player=word(0x27),enemy1=word(0x29),
                          parked=not(word(0x25) or word(0x29))))
    assert all(c['parked']==(c['native_round']%4==0) for c in cases)
    report=dict(inputs=key,cases=cases,trace_sha256=hashlib.sha256((out/'frames.tsv').read_bytes()).hexdigest(),
        hashes={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['frames.tsv']+[f'round-{n}.bin' for n in (2,3,4,8,12,16)]},
        scope='Real original first credit/start; explicit seed for subsequent original08BF initialization.32 physical frames observed per round. No original ROM patches or speed-table edits; not naturally completed rounds.')
    marker.write_text(json.dumps(report,indent=2)+'\n');return report

def verify(bundle):
    from session_reference import configure
    configure(bundle)
    ref=reference();bundle=Path(bundle).resolve()
    out=Path(tempfile.mkdtemp(prefix='speed-proof-',dir=bundle))
    for source,target in ((cartridge_path(bundle),'measured.rom'),(bundle/'lab.sym','measured.sym')):shutil.copyfile(source,out/target)
    syms={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    from session_reference import runtime_symbols,runtime_guard
    runtime_symbols(syms)
    vectors=[]
    for case in ref['cases']:
        for sign in (-1,1):
            for magnitude in (0,96,511,512,case['player']):
                vectors.append(dict(**case,velocity=sign*magnitude,expected=sign*(magnitude if case['parked'] else min(512,magnitude))))
        if case['parked']:
            # Fuel exhaustion activates native enemy parameters: retain the old
            # cap even though the round number still identifies a challenge.
            vectors.append(dict(**(case|dict(enemy0=544,enemy1=576,parked=False)),velocity=case['player'],expected=512))
    native=json.loads((bundle/'game-resources.json').read_text())['banks']['GAME_NATIVE_BANK']
    stub=bytes((0xf3,0x31,0xe0,0xf2,0xcd,0x0c,0xb6,0xf3,0xc3,0,0xf1)).hex()
    source=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq 3579545
set z80_freq_locked true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking challenge_speed_proof
set cases {{{' '.join('{'+ ' '.join(str(c[k]) for k in ('native_round','enemy0','enemy1','velocity','expected'))+'}' for c in vectors)}}}
set index 0;set started 0;set phase boot;set age 0
set rows [open {tcl(out/'results.tsv')} w]
proc word {{at value}} {{debug write memory $at [expr {{$value&255}}];debug write memory [expr {{$at+1}}] [expr {{($value>>8)&255}}]}}
proc issue {{}} {{
 if {{$::index==[llength $::cases]}} {{close $::rows;exit 0}}
 lassign [lindex $::cases $::index] round e0 e1 velocity expected
 foreach {{a v}} [list 0xe1b0 $round] {{debug write memory $a $v}}
 word 0xe025 $e0;word 0xe029 $e1;word 0xe069 $velocity
 debug write memory 0x7000 {native}
 reg BC 0x1234
 debug write_block memory 0xf000 [binary format H* {stub}]
 reg PC 0xf000
}}
debug set_bp 0xb60c {{$::started}} {{set ::begin [machine_info time]}}
debug set_bp 0xf007 {{$::started}} {{set ::cycles [expr {{([machine_info time]-$::begin)*3579545}}]}}
debug set_bp 0xf100 {{$::started}} {{
 set v [expr {{[debug read memory 0xe069]+256*[debug read memory 0xe06a]}}]
 if {{$v>=32768}} {{set v [expr {{$v-65536}}]}}
 puts $::rows "$::index $v [reg BC] $::cycles";flush $::rows
 incr ::index;issue
}}
debug set_bp {syms['frame_done']} {{!$::started && [debug read memory 0xc7d0]==0 && [debug read memory 0xc00c]==1 && ({runtime_guard(bundle)})}} {{set ::started 1;issue}}
proc menu {{}} {{
 incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd]
 switch $::phase {{
 boot {{if {{$state==1 && $ready}} {{keymatrixdown 0 32;set ::phase coin;set ::age 0}}}}
 coin {{if {{$::age==5}} {{keymatrixup 0 32}};if {{$::age>8 && $state==6 && $ready}} {{keymatrixdown 0 2;set ::phase start;set ::age 0}}}}
 start {{if {{$::age==5}} {{keymatrixup 0 2}}}}
 }}
 if {{!$::started}} {{after time 0.02 menu}}
}}
after time 0.02 menu
after time 90 {{puts stderr "Speed verification timeout PC=[reg PC] SP=[reg SP] phase=$::phase state=[debug read memory 0xc7d0] started=$::started";exit 3}}
'''
    (out/'probe.tcl').write_text('if {[catch {\n'+source+'\n} e]} {puts stderr $::errorInfo;exit 2}\n')
    with (out/'openmsx.log').open('w') as log:
        run=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],timeout=120,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    assert run.returncode==0,(out,(out/'openmsx.log').read_text()[-600:])
    rows=[line.split() for line in (out/'results.tsv').read_text().splitlines()];assert len(rows)==len(vectors)
    failures=[]
    for c,row in zip(vectors,rows):
        c.update(actual=int(row[1]),bc=int(row[2]),cycles=float(row[3]))
        if c['actual']!=c['expected'] or c['bc']!=0x1234:failures.append(c)
    costs=[]
    for parked in (False,True):
        samples=sorted(v['cycles'] for v in vectors if v['parked']==parked)
        costs.append(dict(name='Full_MSXPlayerSpeed ('+('parked' if parked else 'ordinary')+')',calls=len(samples),
             inclusive=dict(mean=statistics.mean(samples),p95=samples[math.ceil(.95*len(samples))-1],max=max(samples))))
    report=dict(passed=not failures,rom_sha256=hashlib.sha256((out/'measured.rom').read_bytes()).hexdigest(),path=str(out),costs=costs,
                arcade=ref,vectors=vectors,failures=failures,
                scope='Actual cartridgeB60C limiter, both velocity signs, normal and parked challenge parameters and fuel-exhaustion exit. Guest entry-through-RET cycles; no full-course or scanout claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(path=str(out),passed=report['passed'],cases=len(vectors),failures=failures[:2],arcade=ref['cases']),indent=2))
    assert not failures,('Speed differs from the original challenge parameters',failures[0])
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,default=ROOT/'references/build/game')
    args=parser.parse_args();verify(args.bundle)
