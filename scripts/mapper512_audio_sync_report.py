"""Retain natural sound-clock and measured phase-cache optimization evidence."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from compact_game_build import symbols
from compact_game_report import distribution

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'references/build'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open(),delimiter='\t'))
def latest(folder,pattern,predicate):
    for p in sorted(folder.glob(pattern),key=lambda p:p.stat().st_mtime,reverse=True):
        d=read(p)
        if predicate(d):return p.parent,d
    raise AssertionError(f'Missing {pattern}')
def compact(d):
    out={k:v for k,v in d.items() if k not in ['opening','graphics']}
    if 'graphics' in d:out['graphics']=dict(passed=d['graphics']['passed'],snapshots=d['graphics']['snapshots'])
    if 'opening' in d:out['opening']=dict(passed=d['opening']['passed'],frames=d['opening']['frames'],publication_tick_error_max=d['opening']['publication_tick_error_max'])
    return out


def report():
    game=BUILD/'game-mapper512-game';runtime=BUILD/'game-mapper512-game-runtime';control=BUILD/'game-compact-runtime'
    base=BUILD/'game-mapper512-sync-baseline';base_runtime=BUILD/'game-mapper512-sync-baseline-runtime'
    plan=read(game/'plan.json');old=read(base/'plan.json');current=lambda d:d.get('resource_sha256')==plan['resource_sha256']
    assert old['resource_sha256']=='5586d1556408f3fcc4807b7bf162c40591463c683fdf77c76f934ca10ab183e5'
    assert plan['active_images']==old['active_images']
    assert symbols(runtime/'lab.sym')==symbols(base_runtime/'lab.sym')
    for f in plan['files']:assert sha(game/'files'/f['name'])==f['sha256']
    runs=[]
    for mode in ['dos','basic']:
        for n in [5,10,13]:
            predicate=lambda d:d['seed']==4660 and d['input_clock']=='native' and not d.get('profile_audio') and d['frames']==360
            p,a=latest(base,f'{mode}-r{n}-*/report.json',predicate)
            q,b=latest(game,f'{mode}-r{n}-*/report.json',lambda d:current(d) and predicate(d))
            x,y=rows(p/'frames.tsv'),rows(q/'frames.tsv');keys=['cx','cy','round','enemies','ticks','psg','native','active']
            assert len(x)==len(y)==360 and all(all(u[k]==v[k] for k in keys) for u,v in zip(x,y))
            delta=[float(v['work'])-float(u['work']) for u,v in zip(x,y) if u['active']==v['active']=='1']
            assert delta and all(abs(v+9)<.001 for v in delta)
            pd=[float(v['period'])-float(u['period']) for u,v in zip(x,y)]
            assert max(map(abs,pd))<10 and all(round(float(u['period'])/59736)==round(float(v['period'])/59736) for u,v in zip(x,y))
            runs.append(dict(mode=mode,round=n,control=compact(a),candidate=compact(b),equal_frame_states=360,
                active_pairs=len(delta),work_delta=distribution(delta),period_delta=distribution(pd),same_refresh_counts=True))
    before_path,_=latest(base,'tick-dos-f100-p2-*/report.json',lambda d:d['ticks']==4096 and d.get('audio_sync'))
    p,d=latest(game,'tick-dos-f100-p2-*/report.json',lambda d:current(d) and d.get('audio_sync'))
    a,b=rows(before_path/'phase-cycles.tsv'),rows(p/'phase-cycles.tsv')
    keys=['native','target','front','keys','lookup'];lookup={tuple(r[k] for k in keys):r for r in a}
    allpairs=[(lookup[tuple(r[k] for k in keys)],r) for r in b if tuple(r[k] for k in keys) in lookup]
    assert all(u['selected']==v['selected'] for u,v in allpairs)
    pairs=[(u,v) for u,v in allpairs if u['irq']==v['irq']=='0'];delta=[float(v['cycles'])-float(u['cycles']) for u,v in pairs]
    assert len(delta)>=2900 and all(abs(v+9)<.001 for v in delta)
    phase=dict(input_context_pairs=len(allpairs),no_irq_timing_pairs=len(pairs),inclusive_cycle_delta=distribution(delta),
        calls_per_normal_presented_frame=1,remaining_budget_gain_cycles=9,selected_slots_equal=True,
        all_symbols_identical=True,all_four_immutable_hot_images_identical=True,
        source='Generated session-phase.inc common exit: reuse original target B instead of reloading global phase; two unreachable padding bytes retain every downstream address.',
        method='Entry through matched PC/SP return, inclusive of optional bank-selector child. IRQ-overlapped calls excluded from exact-cycle cohort, not relabeled as self costs. No parent/child cost addition.')
    natural=[]
    for mode,f10,players in [('dos',False,2),('basic',False,2),('basic',True,1)]:
        p,a=latest(control,f'tick-rom-f10{int(f10)}-p{players}-*/report.json',lambda d:d['ticks']==4096 and d.get('audio_sync'))
        q,b=latest(game,f'tick-{mode}-f10{int(f10)}-p{players}-*/report.json',lambda d:current(d) and d['ticks']==4096 and d.get('audio_sync'))
        x=[r.split() for r in (p/'ticks.tsv').read_text().splitlines()];y=[r.split() for r in (q/'ticks.tsv').read_text().splitlines()]
        assert len(x)==len(y)==4096 and all(u[1]==v[1] and u[3:]==v[3:] for u,v in zip(x,y))
        assert a['cold_loads']==b['cold_loads']
        aw,bw=rows(p/'audio-worker.tsv'),rows(q/'audio-worker.tsv');lookup={(r['epoch'],r['age']):r for r in aw}
        assert len(aw)==len(bw) and len(bw)>=2047
        equal=0;dither=0
        for v in bw:
            u=lookup[v['epoch'],v['age']];up,vp=bytes.fromhex(u['psg']),bytes.fromhex(v['psg'])
            changed=[i for i,(i1,i2) in enumerate(zip(up,vp)) if i1!=i2]
            assert not changed or changed==[10] and {up[10],vp[10]}=={12,13}
            equal+=not changed
            changed_state=[i for i,(i1,i2) in enumerate(zip(bytes.fromhex(u['after']),bytes.fromhex(v['after']))) if i1!=i2]
            assert set(changed_state)<={10,26,46}
        for records in [aw,bw]:
            for r in records:
                if int(r['gain_clock'])<0:continue
                key=int(r['gain_key']);phase_value=(int(r['gain_clock'])>>1)&31
                expected=12+((phase_value*(5 if key==3 else 7)&31)<(5 if key==3 else 7))
                assert int(r['gain_volume'])==expected
                if records is bw:dither+=1
        ae,be=rows(p/'audio-events.tsv'),rows(q/'audio-events.tsv');assert ae==be
        latency=[]
        for event in be:
            ids={'death':[8],'flag':[6,7],'smoke':[2]}[event['event']]
            lat=[]
            for records in [aw,bw]:
                r=next(r for r in records if r['epoch']==event['epoch'] and int(r['clock'])>=int(event['clock']) and bytes.fromhex(r['after'])[35] in ids)
                lat.append([int(r['clock'])-int(event['clock']),int(r['return_clock'])-int(event['clock'])])
            assert lat[0]==lat[1]==[2,2]
            latency.append(dict(event=event,control_entry_return_ticks=lat[0],candidate_entry_return_ticks=lat[1]))
        natural.append(dict(mode=mode,f10=f10,players=players,native_states_equal=4096,control=compact(a),candidate=compact(b),
            worker_steps=len(bw),music_effect_and_envelope_registers_equal=len(bw),all14_psg_equal=equal,
            intentional_engine_gain_differences=len(bw)-equal,physical_gain_formula_checks=dither,event_latencies=latency,
            logical_audio_state_equal_except_engine_volume_shadow_and_dirty=True,worker_cycles=distribution(float(r['cycles']) for r in bw)))
    pcm=[]
    p,a=latest(control,'audio-proof-*/report.json',lambda d:d.get('passed',False))
    sound=lambda p:[r.split()[:2]+r.split()[3:] for r in (p/'psg.tsv').read_text().splitlines()]
    expected=sound(p)
    for mode in ['dos','basic']:
        q,b=latest(runtime,'audio-proof-*/report.json',lambda d:current(d) and d.get('mode')==mode)
        assert sound(q)==expected and len(expected)==857
        pcm.append(dict(mode=mode,matching_full_psg_samples=857,control=compact(a),candidate=compact(b),wave_sha256=sha(q/'engine-and-cues.wav')))
    p,wrap=latest(game,'basic-r16-*/report.json',lambda d:current(d) and d['f10'] and d['transitions'])
    assert {int(r['round']) for r in rows(p/'frames.tsv')}=={16,17}
    tests=(BUILD/'issue42-audiosync-final-tests.log').read_text();assert re.findall(r'Ran (\d+) tests',tests)==['508','94'] and 'FAILED' not in tests
    assert '"passed": true' in (BUILD/'issue42-audiosync-final-module.log').read_text()
    preserved=[]
    for name in ['compact-game','compact-megaram-dos-768','compact-megaram-basic-768','disk-dos-4096','disk-basic-4096']:
        p=ROOT/'references/sessions'/name/'report.json'
        preserved.append(dict(session=name,report_sha256=sha(p),report=read(p)))
    seals=read(ROOT/'docs/measurements/cartridge/issue42-512-native-game.json')['artifacts']
    for item in seals:assert sha(ROOT/item['path'])==item['sha256']
    _,route=latest(game,'dos-r5-*/report.json',lambda d:current(d) and d['input_clock']=='presentation')
    original=read(ROOT/'docs/measurements/cartridge/issue42-512-validation.json')['route']['control']
    result=dict(status='Natural sound synchronization explained and checked on observed events; nine-cycle phase-cache reduction validated across six matched DOS/BASIC gameplay routes. Experimental; no release.',
        baseline={k:old[k] for k in ['resource_sha256','bridge_sha256','files','active_images']},candidate={k:plan[k] for k in ['resource_sha256','bridge_sha256','files','active_images','resource_bytes','bridge_bytes']},
        phase=phase,performance=runs,natural_audio=natural,pcm=pcm,wrap=compact(wrap),
        presentation_clock_route=dict(candidate=compact(route),cartridge=compact(original),mean_interval_delta_percent=100*(route['period']['mean']/original['period']['mean']-1),scope='Different trajectories after earlier candidate publication; not a matched-workload speed comparison.'),
        tests=dict(general=508,components=94,skipped=1,module_layout=True),preserved=preserved,seals=seals,
        sources={n:sha(ROOT/n) for n in ['scripts/mapper512_game.py','scripts/mapper512_tick_verify.py','scripts/mapper512_game_verify.py','scripts/mapper512_sync_baseline.py','scripts/mapper512_audio_sync_report.py']},
        cycle_ledger=dict(cpu_hz=3579545,refresh_cycles=59736,refresh_hz=3579545/59736,two_refresh_cycles=119472,
            method='Work=Loop to wait_blank, period=FrameDone to FrameDone; elapsed Z80-reference cycles include IRQ/VDP stalls. Function inclusive means include children; self unmeasured. Parent work and child phase costs are not added.',
            vblank='No newly measured usable-VBlank bound;5000-cycle reserve remains an assumption.',scope='Natural sound workers and matched3/5/6-enemy full-game routes, standard locked Z80/NTSC, HUD and real sprite limits.'),
        limits=['Fixed-up natural route covers two captures, three deaths and player restores; F10 blocks24 contacts. Smoke/complete manual courses and every lifecycle/event combination remain separate.',
            'Per-native-tick raw PSG sampling is not synchronized to30Hz sound updates. Engine gain deliberately follows the free physical clock and must not be reset to force equality.',
            'No universal speedup, subjective listening, physical hardware, PAL, DOS2/Nextor or full reset/error qualification. No commit/push/merge/release.'])
    for target in ['docs/measurements/cartridge/issue42-512-audio-sync.json','docs/measurements/timing/mapper512-audio-sync.json']:
        (ROOT/target).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(routes=len(runs),equal_frame_states=sum(r['equal_frame_states'] for r in runs),phase_pairs=len(pairs),cycle_saving=9,
        audio=[{k:r[k] for k in ['mode','f10','worker_steps','all14_psg_equal','intentional_engine_gain_differences']} for r in natural]),indent=2))
    return result


if __name__=='__main__':report()
