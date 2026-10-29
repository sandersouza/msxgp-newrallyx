"""Bind cycle, gameplay, graphics and real multi-car evidence to current ROMs."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import argparse
import copy

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'references/experiments'
OUT=ROOT/'outputs/first-stage'

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def latest(bundle,pattern,rom_hash):
    candidates=[]
    for p in bundle.glob(pattern):
        value=read(p)
        if value.get('rom_sha256')!=rom_hash:
            continue
        if pattern.startswith('profile-route'):
            # Detailed logic probes share the route and ROM, but do not measure
            # the rendering owners required by the presentation comparison.
            names={r['name'] for r in value.get('routines',[])}
            if value.get('profile_kind','presentation')!='presentation' or not {'Ring_UploadNames','Game_Radar','Ring_Prepare'}<=names:
                continue
        candidates.append(p)
    assert candidates,(bundle,pattern,rom_hash)
    return max(candidates,key=lambda p:p.stat().st_mtime)

def stats(d):
    intervals=sorted(r['cycles']/d['cpu_hz']*1000 for r in d['frames'])
    return dict(fps=d['presented_fps'],work_mean_ms=statistics.mean(r['work'] for r in d['frames'])/d['cpu_hz']*1000,
                interval_p95_ms=intervals[math.ceil(len(intervals)*.95)-1],interval_max_ms=max(intervals),
                within_two_refreshes_percent=sum(v<=33.6 for v in intervals)/len(intervals)*100)

def active(route):
    with (route.parent/'frames.tsv').open() as file:
        rows=list(csv.DictReader(file,delimiter='\t'))
    moving=lambda r: int(r['death'])==0 and int(r['state'])==0 and int(r['flags'])<10
    intervals=[float(b['time'])-float(a['time']) for a,b in zip(rows,rows[1:]) if moving(a) and moving(b)]
    return dict(fps=len(intervals)/sum(intervals),intervals=len(intervals),seconds=sum(intervals),
                scope='Excludes death, bonus and stopped/game-over states at both interval endpoints')

def action_profile(profile):
    value=copy.deepcopy(profile)
    ledger=profile['active_ledger']
    value.update(frames=ledger['frames'],routines=ledger['routines'],
                 measured_frames=ledger['measured_frames'],presented_fps=ledger['presented_fps'])
    return value

def main(enemies=3):
    bundle=BASE/('stage-one' if enemies==1 else 'stage-one-3-enemies')
    current_hash=sha(bundle/'fixed-hud.rom')
    profile=latest(bundle,'profile-route-*/summary.json',current_hash)
    d=read(profile)
    assert sha(profile.parent/'measured.rom')==current_hash
    baseline_path=(bundle/'profile-route-pvvteu39/summary.json' if enemies==1 else
        latest(bundle,'profile-route-*/summary.json',sha(bundle/'baseline-299b5380/fixed-hud.rom')))
    before=read(baseline_path)
    old_route=latest(bundle,'route-*/result.json',before['rom_sha256'])
    new_route=latest(bundle,'route-*/result.json',current_hash)
    if enemies==3:
        d=action_profile(d)
        before=action_profile(before)
    d['primary_enemies']=enemies
    d['target_presented_fps']=29.97
    d['primary_action_only']=enemies==3
    d['workload']='Three-enemy action intervals; both endpoints active; keyboard navigation until native game over' if enemies==3 else d['workload']
    d['optimization_comparison']=dict(baseline=stats(before),current=stats(d),
        baseline_active=active(old_route),current_active=active(new_route),
        baseline_rom_sha256=before['rom_sha256'],baseline_routines=before['routines'],
        baseline_profile=str(baseline_path),current_profile=str(profile),
        baseline_route=str(old_route),current_route=str(new_route))
    payloads=['terrain-patterns.bin','terrain-colors.bin','palette.bin','game-sprite-templates.bin',
              'game-hud-digits.bin','game-hud-life.bin','hud.bin']
    d['graphics_equivalence']={name:sha(bundle/name) for name in payloads}
    for name in payloads:
        assert (bundle/name).read_bytes()==(BASE/'stage-one/baseline-47e0112b'/name).read_bytes(),name
    if enemies==3:
        for path in bundle.glob('hud-??.bin'):
            assert path.read_bytes()==(bundle/'baseline-ca9e6ae6'/path.name).read_bytes(),path.name
    d['multi_car_workloads']=[]
    for count in (3,7):
        variant=BASE/f'stage-one-{count}-enemies'
        h=sha(variant/'fixed-hud.rom')
        smoke_path=latest(variant,'smoke-*/result.json',h)
        pop_path=latest(BASE/'fixed-hud',f'multi-native-{count}-optimized-final-*/report.json',h)
        value=dict(enemies=count,rom_sha256=h,smoke=read(smoke_path),population=read(pop_path),
                   active_smoke=active(smoke_path),smoke_path=str(smoke_path),population_path=str(pop_path))
        if count==3:
            r=latest(variant,'route-*/result.json',h)
            p=latest(variant,'profile-route-*/summary.json',h)
            baseline=BASE/'stage-one-3-enemies/baseline-299b5380'
            bp=latest(variant,'profile-route-*/summary.json',sha(baseline/'fixed-hud.rom'))
            value.update(route=read(r),active=active(r),profile=stats(read(p)),baseline=stats(read(bp)),
                         routines=read(p)['routines'],active_profile=read(p).get('active_ledger'),
                         profile_path=str(p),baseline_profile_path=str(bp))
        for name in payloads:assert (variant/name).read_bytes()==(bundle/name).read_bytes(),(count,name)
        d['multi_car_workloads'].append(value)
    d['synthetic_smoke_cache']=read(ROOT/'outputs/fixed-hud/smoke-row-decode/cycle-ledger.json')
    d['synthetic_dirty_names']=read(ROOT/'outputs/fixed-hud/dirty-synthetic/cycle-ledger.json') if (ROOT/'outputs/fixed-hud/dirty-synthetic/cycle-ledger.json').exists() else None
    d['synthetic_fast_radar']=read(ROOT/'outputs/fixed-hud/radar-fast-synthetic/cycle-ledger.json')
    d['synthetic_fast_masks']=read(ROOT/'outputs/fixed-hud/sprite-mask-fast-synthetic/cycle-ledger.json')
    d['synthetic_name_stream']=read(ROOT/'outputs/fixed-hud/name-stream-synthetic/cycle-ledger.json')
    d['boundary_packets']=read(bundle/'boundary-cost.json') if (bundle/'boundary-cost.json').exists() else None
    boundary_runtime=BASE/'fixed-hud/boundary-fast-bundle/native-result.json'
    if boundary_runtime.exists() and read(boundary_runtime)['rom_sha256']==current_hash:
        d['boundary_runtime']=read(boundary_runtime)
    d['evidence_scope']='Same controller policy; cadence changes input feedback and samples. Three-enemy navigation ends at native game over; seven-enemy smoke is a separate prior-ROM stress test. Multi-car overrides only population/spawns. No physical hardware validation.'
    d['sources_sha256']={p.name:sha(p) for p in sorted((ROOT/'experiments/fixed-hud').glob('game-*.inc'))}
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'summary.json'
    target.write_text(json.dumps(d,indent=2)+'\n')
    print(target)
    for n in d['multi_car_workloads']:print(n['enemies'],n['smoke']['presented_fps'],n['population']['maximum_simultaneously_visible_enemies'])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enemies',type=int,choices=(1,3),default=3)
    main(parser.parse_args().enemies)
