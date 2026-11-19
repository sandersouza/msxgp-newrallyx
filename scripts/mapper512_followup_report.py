"""Compact continuation evidence: route causality, PCM/PSG and natural turns."""
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open(),delimiter='\t'))
def latest(folder,pattern,predicate=lambda d:True):
    for p in sorted(folder.glob(pattern),key=lambda p:p.stat().st_mtime,reverse=True):
        d=read(p)
        if predicate(d):return p.parent,d
    raise AssertionError(f'Missing evidence {pattern}')


def report():
    build=ROOT/'references/build';game=build/'game-mapper512-game';runtime=build/'game-mapper512-game-runtime';control=build/'game-compact-runtime'
    scratch=build/'game-mapper512-followup';plan=read(game/'plan.json');before=read(scratch/'before-plan.json')
    assert before['files']==plan['files'] and before['active_images']==plan['active_images'],'Rejected optimization not fully reverted'
    baseline=read(scratch/'before/report.json');cartridge=read(scratch/'control/report.json')
    a,b=rows(scratch/'control/frames.tsv'),rows(scratch/'before/frames.tsv')
    prefix=[]
    for x,y in zip(a,b):
        if any(x[k]!=y[k] for k in ['cx','cy','ticks','native']):break
        prefix.append((x,y))
    assert len(prefix)==51
    earlier=(float(a[50]['period'])-float(b[50]['period']))/59736
    assert .99<earlier<1.01
    route=dict(frames=360,identical_native_camera_tick_prefix=51,first_state_divergence_frame=52,
        first_earlier_candidate_publication_frame=51,earlier_refreshes=earlier,
        prefix_mean_work_control=sum(float(x['work']) for x,y in prefix)/len(prefix),
        prefix_mean_work_candidate=sum(float(y['work']) for x,y in prefix)/len(prefix),
        active_mean_interval_delta_percent=100*(baseline['period']['mean']/cartridge['period']['mean']-1),
        consumed_elapsed_refresh_ticks=[sum(int(r['ticks']) for r in a),sum(int(r['ticks']) for r in b)],
        end_camera_control=[int(a[-1]['cx']),int(a[-1]['cy'])],end_camera_candidate=[int(b[-1]['cx']),int(b[-1]['cy'])],
        control=cartridge,candidate=baseline,
        conclusion='Presentation-index keyboard schedule diverges after an earlier candidate publication; later aggregates are different workloads. This is not an isolated0.24% renderer slowdown, and does not prove universal no-regression.')
    audio=[]
    p,c=latest(control,'audio-proof-*/report.json',lambda d:d.get('passed',False))
    sound=lambda p:[r.split()[:2]+r.split()[3:] for r in (p/'psg.tsv').read_text().splitlines()]
    expected=sound(p);assert len(expected)==857
    for mode in ['dos','basic']:
        q,d=latest(runtime,'audio-proof-*/report.json',lambda d:d.get('mode')==mode and d.get('resource_sha256')==plan['resource_sha256'])
        assert sound(q)==expected
        audio.append(dict(mode=mode,control=c,candidate=d,matching_psg_samples=857,psg_content_sha256=hashlib.sha256(repr(expected).encode()).hexdigest(),
            pcm_sha256=sha(q/'engine-and-cues.wav'),scope='Synthetic velocity/event fixture after real disk boot. All14 PSG registers, engine, smoke, crash/retrigger and music assertions pass; PCM spectral/envelope checks pass. No listening or natural cue-timing acceptance.'))
    gameplay=[]
    for mode,f10,players in [('dos',False,2),('basic',False,2),('basic',True,1)]:
        q,d=latest(game,f'tick-{mode}-f10{int(f10)}-p{players}-*/report.json',lambda d:d['ticks']==4096 and d.get('cold_loads'))
        p,c=latest(control,f'tick-rom-f10{int(f10)}-p{players}-*/report.json',lambda d:d['ticks']==4096 and d.get('cold_loads'))
        x=[r.split() for r in (q/'ticks.tsv').read_text().splitlines()];y=[r.split() for r in (p/'ticks.tsv').read_text().splitlines()]
        assert len(x)==len(y)==4096
        assert all(a[1]==b[1] and a[3:]==b[3:] for a,b in zip(x,y)),'Original native state or host game/death/round mismatch'
        assert d['cold_loads']==c['cold_loads']
        if players==2:
            assert [r['player'] for r in d['cold_loads']]==['0','1','0','1']
            assert [r['kind'] for r in d['cold_loads']]==['0','1','2','2']
            assert 'deaths=3 turns=3 contacts=3' in d['observation']
        else:assert 'deaths=0 turns=0 contacts=24' in d['observation']
        gameplay.append(dict(mode=mode,f10=f10,players=players,native_ticks=4096,matching_native_snapshots=4096,matching_host_game_death_round_samples=4096,
            matching_psg_at_native_tick=sum(a[2]==b[2] for a,b in zip(x,y)),control=c,candidate=d,
            native_state_sha256=hashlib.sha256(''.join(r[1] for r in x).encode()).hexdigest(),
            scope='Original768-byte E000..E2FF state per natural tick; held-up input and two-byte controlled PRNG only. Includes original position/motion/board-state/RNG/score/lives fields. Full multi-route playthrough not covered. PSG is physical-clock driven; native-index PSG differences are retained, not called equal.'))
    abi=read(build/'game-mapper512-mapper-abi/report.json');assert abi['cases']==128000 and abi['saved_cycles_per_call']==20
    optimized=next(p for p in game.glob('dos-r5-*/report.json') if read(p).get('resource_sha256')=='07fa10fd0db49d9c0005d1ed88cb20500cd8ace7c64b1fa3fc67a8238a6605fe')
    optimized_rows=rows(optimized.parent/'frames.tsv');oldrows=rows(scratch/'before/frames.tsv')
    optimized_report=read(optimized)
    assert all(abs(optimized_report['work'][k]-baseline['work'][k])<.01 for k in ['mean','p95','max'])
    assert abs(optimized_report['period']['mean']-baseline['period']['mean'])<.01
    assert all(all(x[k]==y[k] for k in ['cx','cy','ticks','native','psg']) for x,y in zip(optimized_rows,oldrows))
    optimization=dict(retained=False,abi=abi,active_work_mean_tail_max_equivalent=True,mean_period_equivalent=True,
        raw_period_phase_delta_min=min(float(y['period'])-float(x['period']) for x,y in zip(oldrows,optimized_rows)),
        raw_period_phase_delta_max=max(float(y['period'])-float(x['period']) for x,y in zip(oldrows,optimized_rows)),
        reason='Generic bank helper saves20 cycles but gives zero active-work mean/P95/max or mean-cadence benefit in the360-presentation route. Generated active mappings already bypass it; one nonactive work span saves40 cycles. Raw publication-phase deltas stay within5 cycles. Reverted complete executable/bridge/resource/hot-image bytes; probe retained only as synthetic rejected experiment.')
    tests=(build/'issue42-followup-tests.log').read_text();assert re.findall(r'Ran (\d+) tests',tests)==['505','94'] and 'FAILED' not in tests
    seals=read(ROOT/'docs/measurements/cartridge/issue42-512-native-game.json')['artifacts']
    for item in seals:assert sha(ROOT/item['path'])==item['sha256']
    result=dict(status='512KiB validation advanced; production runtime and all supported artifact bytes unchanged; no universal performance/audio/hardware acceptance or release.',
        resource_sha256=plan['resource_sha256'],bridge_sha256=plan['bridge_sha256'],files=plan['files'],route=route,audio=audio,gameplay=gameplay,rejected_optimization=optimization,
        tests=dict(general=505,components=94,skipped=1),seals=seals,
        sources={p:sha(ROOT/p) for p in ['scripts/mapper512_audio_verify.py','scripts/mapper512_tick_verify.py','scripts/mapper512_mapper_verify.py','scripts/mapper512_followup_report.py']},
        limits=['PSG differences at native-index samples reflect a different clock/processing boundary; all natural sound-event timing/listening remains unqualified.',
            'Fixed-up input and controlled PRNG cover natural three-death/two-player and F10 paths, not every flag collection, challenge, game-over, reset or storage error.',
            'No hardware/PAL/DOS2/Nextor acceptance. Presentation-clock route divergence still prevents an unconditional no-regression verdict.'])
    (ROOT/'docs/measurements/cartridge/issue42-512-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    ledger=ROOT/'docs/measurements/timing/mapper512-native-game.json';d=read(ledger);d['followup']=result;ledger.write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps(dict(audio_cases=len(audio),audio_matching_samples=857,gameplay_cases=len(gameplay),native_matching_samples=[g['matching_native_snapshots'] for g in gameplay],earlier_frame=51,production_unchanged=True),indent=2))
    return result


if __name__=='__main__':report()
