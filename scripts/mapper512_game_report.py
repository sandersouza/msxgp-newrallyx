"""Retain compact native512KiB loader evidence; no generated game data."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mapper512_game_verify import opening_contract
from compact_game_report import distribution

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def report():
    game=ROOT/'references/build/game-mapper512-game';runtime=ROOT/'references/build/game-mapper512-game-runtime'
    plan=read(game/'plan.json');control=ROOT/'references/build/game-mapper512-integrated'
    def latest(folder,predicate):
        for p in sorted(folder.glob('*/report.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            d=read(p)
            if predicate(d):
                if 'verification_script_sha256' in d:assert d['verification_script_sha256']==digest(p.parent/'verify.tcl')
                d['verification_script_sha256']=digest(p.parent/'verify.tcl')
                return p.parent,d
        raise AssertionError('Missing qualified evidence')
    def rows(p):return list(csv.DictReader((p/'frames.tsv').open(),delimiter='\t'))
    same=lambda d:d.get('resource_sha256')==plan['resource_sha256'] and d.get('bridge_sha256')==plan['bridge_sha256'] and d['passed']
    launches=[];transitions=[];timing=[]
    for mode,f10 in [('dos',False),('basic',True)]:
        p,d=latest(game,lambda d:same(d) and d['mode']==mode and d['native_round']==2 and d['f10']==f10 and d.get('opening'))
        assert d['host_payload_injections']==0 and not d['cartridge'] and not d.get('diagnostic_state_writes')
        d['opening']=opening_contract(p,runtime);launches.append(d)
    for mode,n in [('dos',4),('basic',8),('dos',12),('basic',16)]:
        p,d=latest(game,lambda d:same(d) and d['mode']==mode and d['native_round']==n and d.get('transitions'))
        assert d['f10'] and d['graphics']['passed'] and {int(r['round']) for r in rows(p)}=={n,n+1}
        d['stopped_transition_interval_cycles']=max(float(r['period']) for r in rows(p))
        transitions.append(d)
    for clock,n,mode in [('native',5,'dos'),('native',10,'dos'),('native',10,'basic'),('native',13,'dos'),('native',13,'basic'),('presentation',5,'dos')]:
        p,d=latest(game,lambda d:same(d) and d['mode']==mode and d['native_round']==n and d.get('seed')==4660 and d.get('input_clock','native')==clock)
        q,c=latest(control,lambda d:not d.get('candidate',True) and d['native_round']==n and d.get('input_clock')==clock and d['frames']==360)
        a,b=rows(q),rows(p);assert len(a)==len(b)==360
        keys=['cx','cy','round','enemies','ticks','psg','native']
        pairs=[(x,y) for x,y in zip(a,b) if x['active']==y['active']=='1' and all(x[k]==y[k] for k in keys)]
        assert pairs
        delta=[float(y['work'])-float(x['work']) for x,y in pairs]
        prefix=[]
        for x,y in zip(a,b):
            if any(x[k]!=y[k] for k in ['cx','cy','ticks','native']):break
            prefix.append((x,y))
        timing.append(dict(mode=mode,round=n,input_clock=clock,control=c,candidate=d,matching_state_psg_frames=len(pairs),
            matching_work_delta=distribution(delta),matching_work_slower_samples=sum(v>.01 for v in delta),
            identical_native_camera_prefix_frames=len(prefix),
            mean_work_delta_percent=100*(d['work']['mean']/c['work']['mean']-1),
            mean_period_delta_percent=100*(d['period']['mean']/c['period']['mean']-1),
            candidate_presented_fps=3579545/d['period']['mean'],control_presented_fps=3579545/c['period']['mean'],
            scope='Diagnostic two-byte RNG seed only; no payload/code/OS injection. Complete short-route distributions plus same-presentation camera/native/ticks/PSG subset. Renderer/cache/IRQ phase is not fully cloned; divergent trajectories are not equal workloads.'))
    log=(ROOT/'references/build/issue42-game-tests.log').read_text()
    assert re.findall(r'Ran (\d+) tests',log)==['505','94'] and 'FAILED' not in log
    assert '"passed": true' in (ROOT/'references/build/issue42-game-module.log').read_text()
    artifacts=[]
    for name,sha in [('dist/newrallyx.rom','44be6037d05ebf763283f14ef6deb6e4a8bd58b0a25fcc04c693d899c3704f00'),
        ('dist/compact/megaram/newrallyx-megaram.zip','ed50647304f1d647f1161a85f36f487129506cd76e3abdcecb8122ebf2c8768d'),
        ('dist/disk/newrallyx-disk.zip','fca5d77ade0bc83156e37279c8968f6108e762ccb128f651c8e54741d3668428'),
        ('docs/cycle-budget.xlsx','c19093e1953486e3b30108fceae49f2507381a2330668df77aa313befdb5d7cd')]:
        assert digest(ROOT/name)==sha;artifacts.append(dict(path=name,sha256=sha,bytes=(ROOT/name).stat().st_size))
    preserved=[]
    for name in ['compact-game','compact-megaram-dos-768','compact-megaram-basic-768','disk-dos-4096','disk-basic-4096']:
        d=read(ROOT/'references/sessions'/name/'report.json');preserved.append(d)
    old=read(ROOT/'docs/measurements/cartridge/issue42-512-cold-io.json')['plans'][1]['bridge']['sha256']
    assert read(ROOT/'references/build/game-mapper512-cold/plan.json')['bridge']['sha256']==old
    limits=['openMSX Panasonic FS-A1WSX, locked Z80,NTSC; no physical hardware/PAL/DOS2/Nextor qualification.',
        'No listening acceptance or complete manual course, player-switch/game-over/reset/error-lifecycle matrix for the native loader.',
        'Presentation-clock round5 route remains0.24% slower on aggregate after trajectories diverge; first divergence is an earlier candidate publication. Isolated matched-state work samples are slower too. This does not pass an unconditional no-regression gate.',
        'Directory-backed floppy timing is emulated; cold interval includes preparation, cache rebuild and first publication; no drive-speed promise.',
        'Experimental package only, no default format changes, commit/push/merge/release or stable512KiB claim.']
    result=dict(status='Native DOS/BASIC boot and real game/family transitions demonstrated within512KiB; final performance/audio/lifecycle qualification remains open.',
        plan={k:v for k,v in plan.items() if k not in ['records','context','map_staging']},
        launches=launches,transitions=transitions,timing=timing,preserved=preserved,artifacts=artifacts,
        tests=dict(general=505,components=94,skipped=1,module_layout=True,default_cold_bridge_byte_identical=True),limits=limits,
        cycle_ledger=dict(cpu_hz=3579545,refresh_hz=3579545/59736,refresh_cycles=59736,two_refresh_cycles=119472,
            method='Guest elapsed Z80-base-equivalent cycles, IRQ/VDP waits included. Work=GameTurbo_Loop to wait_blank; period=FrameDone to FrameDone. Active intervals exclude death/stopped/cold-epoch crossings. Inclusive, self unmeasured; never add work and period. Cold only separately scoped.',
            vblank='No new usable-VBlank bound measured;5000-cycle reserve remains an assumption.',remaining_budget='Per-sample two-refresh budget minus inclusive work; negative values are overloads, not extra VBlank.'))
    target=ROOT/'docs/measurements/cartridge/issue42-512-native-game.json';target.write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'docs/measurements/timing/mapper512-native-game.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],launches=len(launches),transitions=len(transitions),timing_routes=len(timing),tests=result['tests'],bytes=plan['resource_bytes']),indent=2))
    return result


if __name__=='__main__':report()
