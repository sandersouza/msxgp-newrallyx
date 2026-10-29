"""Differential stone/rebound fixtures against unmodified arcade Z80 execution."""
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile,statistics,math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.msx.emulator import reference_machine,tcl
from scripts.graphics.roms import input_records,load_metadata,validate_roms

def vectors():
    result=[]
    for axis in (0,255):
      for sign in (-1,1):
       for x in (-23,-13,-12,0,12,13,23):
        for y in (-23,-13,-12,0,12,13,23):
         for hit in (True,False):
            d=bytearray(32);d[1:3]=(sign*480&65535).to_bytes(2,'little');d[3]=axis
            d[4]=64;d[5]=x&255;d[6]=192;d[7]=y&255;d[8]=12;d[10]=20
            cell=0x9800+20*32+12;d[17:19]=cell.to_bytes(2,'little')
            result.append((bytes(d),cell if hit else cell+66))
    for immunity in (1,2,50):
      for axis in (0,255):
       for sign in (-1,1):
        d=bytearray(result[0][0]);d[19]=immunity;d[3]=axis;d[1:3]=(sign*480&65535).to_bytes(2,'little');d[5]=d[7]=0
        result.append((bytes(d),0x9800+20*32+12))
    return result

def reference(cases):
    out=ROOT/'references/experiments/arcade-enemy-rock';out.mkdir(parents=True,exist_ok=True)
    raw=b''.join(d+cell.to_bytes(2,'little') for d,cell in cases);(out/'vectors.bin').write_bytes(raw)
    script=Path(__file__).with_name('arcade-enemy-rock.lua')
    version=subprocess.check_output(['mame','-version'],text=True).strip();assert version.startswith('0.289 ')
    key=dict(script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(raw).hexdigest(),emulator=version,
             roms=input_records(validate_roms(ROOT/'references/roms/nrallyx',load_metadata())))
    marker=out/'reference.json';prior=json.loads(marker.read_text()) if marker.exists() else {}
    if prior.get('inputs')!=key or not (out/'results.bin').exists() or hashlib.sha256((out/'results.bin').read_bytes()).hexdigest()!=prior.get('results_sha256'):
        (out/'complete').unlink(missing_ok=True)
        args=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(ROOT/'references/roms'),'-video','none','-sound','none','-nothrottle','-noautosave','-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(script),'-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','30']
        with (out/'mame.log').open('w') as log:subprocess.run(args,check=True,timeout=60,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,NRX_ENEMY_ROCK_OUTPUT=str(out)))
        assert (out/'complete').exists(),(out/'mame.log').read_text()[-1000:]
    expected=(out/'results.bin').read_bytes();assert len(expected)==32*len(cases)
    marker.write_text(json.dumps(dict(inputs=key,results_sha256=hashlib.sha256(expected).hexdigest(),cases=len(cases),scope='Controlled RAM descriptors and stone cells, original181B/1885 execution; no ROM changes or natural-route claim.'),indent=2)+'\n')
    return expected

def verify(bundle):
    cases=vectors();expected=reference(cases);bundle=Path(bundle).resolve();out=Path(tempfile.mkdtemp(prefix='rocks-proof-',dir=bundle))
    for a,b in (('fixed-hud.rom','measured.rom'),('lab.sym','measured.sym')):shutil.copyfile(bundle/a,out/b)
    s={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(out/'measured.sym').read_text())}
    address=s['GameSession_EnemyRockProbe']
    bank=json.loads((bundle/'game-resources.json').read_text())['banks']['GAME_NATIVE_BANK']
    stub=bytes((0xf3,0x31,0xe0,0xf2,0xdd,0x21,0x88,0xe0,0xcd,address&255,address>>8,0xf3,0xc3,0,0xf1))
    nav_cases=[]
    for heading in range(4):
      for mask in range(16):
       for tag in (0,16):
        d=bytearray(cases[0][0]);d[5]=d[7]=0;d[19]=2;d[3]=255 if heading&1 else 0
        d[1:3]=((-480 if heading>=2 else 480)&65535).to_bytes(2,'little')
        nav_cases.append((bytes(d),mask|tag))
    actor=s['Full_MSXActor'];actor_stub=bytes((0xf3,0x31,0xe0,0xf2,0xdd,0x21,0x88,0xe0,0xcd,actor&255,actor>>8,0xf3,0xc3,0,0xf1))
    nav_fixture=' '.join('{'+d.hex()+' '+str(mask)+'}' for d,mask in nav_cases)
    fixture=' '.join('{'+d.hex()+' '+str(cell-0x9800+0x3000)+'}' for d,cell in cases)
    code=f'''set save_settings_on_exit false
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
activate_input_layer -blocking enemy_rock_proof
set kind probe;set navcases {{{nav_fixture}}}
set nav_results [open {tcl(out/'navigation.bin')} wb]
set cases {{{fixture}}};set index 0;set started 0;set phase boot;set age 0
set results [open {tcl(out/'results.bin')} wb];set costs [open {tcl(out/'costs.tsv')} w]
proc issue {{}} {{
 if {{$::index==[llength $::cases]}} {{close $::results;close $::costs;set ::kind navigation;set ::index 0;issue_nav;return}}
 lassign [lindex $::cases $::index] data stone
 debug write memory 0x7000 {bank}
 debug write_block memory 0x3000 [string repeat [binary format c 0] 2048]
 debug write memory $stone 16
 debug write_block memory 0xe088 [binary format H* $data]
 reg IY 0
 debug write_block memory 0xf000 [binary format H* {stub.hex()}]
 reg PC 0xf000
}}
proc issue_nav {{}} {{
 if {{$::index==[llength $::navcases]}} {{close $::nav_results;exit 0}}
 lassign [lindex $::navcases $::index] data mask
 debug write_block memory 0x3000 [string repeat [binary format c 0] 2048]
 debug write memory [expr {{0x3000+20*32+12}}] $mask
 debug write_block memory 0xe088 [binary format H* $data]
 debug write memory {s['Full_MSXIndex']} 0
 debug write memory {s['Full_MSXExits']} 0
 debug write_block memory {s['Full_MSXDecision']} [binary format H* ffff]
 foreach {{a v}} {{0xe070 12 0xe072 20 0xe025 224 0xe026 1 0xe029 224 0xe02a 1}} {{debug write memory $a $v}}
 reg IY 0
 debug write_block memory 0xf000 [binary format H* {actor_stub.hex()}]
 reg PC 0xf000
}}
debug set_bp {address} {{$::started && $::kind eq "probe"}} {{set ::begin [machine_info time]}}
debug set_bp 0xf00b {{$::started && $::kind eq "probe"}} {{puts $::costs [expr {{([machine_info time]-$::begin)*3579545}}]}}
debug set_bp 0xf100 {{$::started}} {{
 if {{$::kind eq "probe"}} {{puts -nonewline $::results [debug read_block memory 0xe088 32];incr ::index;issue}} else {{puts -nonewline $::nav_results [debug read_block memory 0xe088 32];incr ::index;issue_nav}}
}}
debug set_bp {s['frame_done']} {{!$::started && [debug read memory 0xc7d0]==0}} {{set ::started 1;issue}}
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
after time 90 {{puts stderr "Stone fixture timeout";exit 3}}
'''
    (out/'probe.tcl').write_text('if {[catch {\n'+code+'\n} e]} {puts stderr $::errorInfo;exit 2}\n')
    with (out/'openmsx.log').open('w') as log:r=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],timeout=120,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    assert r.returncode==0,(out,(out/'openmsx.log').read_text()[-1200:])
    actual=(out/'results.bin').read_bytes();assert len(actual)==len(expected)
    failures=[dict(case=i,byte=j,actual=a,expected=b) for i in range(len(cases)) for j,(a,b) in enumerate(zip(actual[i*32:i*32+32],expected[i*32:i*32+32])) if a!=b]
    costs=list(map(float,(out/'costs.tsv').read_text().split()));assert len(costs)==len(cases)
    grouped={name:[] for name in ('recoil','clear','immune')}
    for i,(descriptor,cell) in enumerate(cases):
        name='immune' if descriptor[19] else 'recoil' if actual[i*32]==0xe0 else 'clear'
        grouped[name].append(costs[i])
    describe=lambda name,values:dict(name=name,calls=len(values),inclusive=dict(mean=statistics.mean(values),p95=sorted(values)[math.ceil(.95*len(values))-1],max=max(values)))
    nav=(out/'navigation.bin').read_bytes();assert len(nav)==len(nav_cases)*32
    nav_failures=[i//2 for i in range(0,len(nav_cases),2) if nav[i*32:(i+1)*32]!=nav[(i+1)*32:(i+2)*32]]
    report=dict(navigation_tag_pairs=len(nav_cases)//2,navigation_failures=nav_failures,passed=not failures and not nav_failures,path=str(out),rom_sha256=hashlib.sha256((out/'measured.rom').read_bytes()).hexdigest(),cases=len(cases),failures=failures[:30],
        costs=[describe('GameSession_EnemyRockProbe',costs)],
        cost_groups=[describe('Enemy stone '+name,values) for name,values in grouped.items() if values],
        scope='All32 descriptor bytes compared with original181B/1885 collision/rebound, both axes/signs, fine-boundary hits/misses and immunity. Controlled fixtures, not a natural-course proof. Entry-through-RET inclusive cycles; no self-cost sum.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['passed'];return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/experiments/full-session');a=p.parse_args();verify(a.bundle)
