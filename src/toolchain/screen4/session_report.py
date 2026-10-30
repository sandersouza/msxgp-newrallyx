"""Bind full-session costs and native VDP endpoint evidence to one cartridge."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse,csv,hashlib,json,math,statistics
from pathlib import Path


def distribution(values):
    a=sorted(values)
    return dict(min=a[0],mean=statistics.mean(a),p95=a[math.ceil(.95*len(a))-1],max=a[-1])


def report(bundle,out,profile=None,comparison=None):
    profile=Path(profile or (bundle/'last-profile.txt').read_text().strip())
    data=json.loads((profile/'summary.json').read_text())
    assert hashlib.sha256((cartridge_path(bundle)).read_bytes()).hexdigest()==data['rom_sha256']
    with (profile/'calls.tsv').open() as f:calls=list(csv.DictReader(f,delimiter='\t'))
    with (profile/'frames.tsv').open() as f:states=list(csv.DictReader(f,delimiter='\t'))
    hz=data['cpu_hz'];period=262*228;active=data['active_ledger'];ids={f['frame'] for f in active['frames']}
    assert len({(s['r9'],s['r18']) for s in states})==1
    r9,r18=int(states[0]['r9']),int(states[0]['r18']);assert not r9&2
    line=25+(0 if r9&128 else 10)+((r18>>4)^7)
    display=line*1368+202
    blank_start=display+(212 if r9&128 else 192)*1368
    blank_end=262*1368+display-1368
    raster=[]
    for c in calls:
        start=int(c['start_vtick']);end=int(c['end_vtick'])+(int(c['end_vframe'])-int(c['start_vframe']))*period*6
        assert abs((end-start)/6-float(c['inclusive_cycles']))<.01
        for side in ('start','end'):
            vt=int(c[side+'_vtick']);vr=vt<display-1368 or vt>=blank_start
            assert vr==bool(int(c[side+'_s2'])&64),(c['routine'],side)
            c[side+'_line']=vt//1368;c[side+'_cycle']=(vt%1368)/6
        blank=sum(max(0,min(end,k*period*6+blank_end)-max(start,k*period*6+blank_start))
                  for k in range(-1,math.floor(end/(period*6))+1))/6
        c['blank_cycles']=blank;c['outside_cycles']=max(0,float(c['inclusive_cycles'])-blank)
    selected=[c for c in calls if int(c['frame']) in ids]
    for routine in active['routines']:
        rows=[c for c in selected if c['routine']==routine['name']]
        per_frame=[sum(float(c['inclusive_cycles']) for c in rows if int(c['frame'])==n) for n in ids]
        routine['frame_cycles']=distribution(per_frame)
        routine['self_frame_cycles']=distribution([sum(float(c['self_cycles']) for c in rows if int(c['frame'])==n) for n in ids])
        routine['self_call_cycles']=distribution([float(c['self_cycles']) for c in rows]) if rows else None
        routine['self_per_frame']=routine['self_frame_cycles']['mean']
        if rows:
            raster.append(dict(name=routine['name'],calls=len(rows),
                start_line=distribution([c['start_line'] for c in rows]),
                start_cycle=distribution([c['start_cycle'] for c in rows]),
                blank=distribution([c['blank_cycles'] for c in rows]),
                outside=distribution([c['outside_cycles'] for c in rows]),
                all_inside=sum(c['outside_cycles']<.01 for c in rows),
                all_outside=sum(c['blank_cycles']<.01 for c in rows)))
    def stamp(c):return int(c['start_vframe'])*period+int(c['start_vtick'])/6
    samples=[]
    for f in active['frames']:
        spans={c['routine']:c for c in selected if int(c['frame'])==f['frame'] and c['routine'] in ('Game_Prepare','wait_blank','commit')}
        begin,ready,publish=(stamp(spans[k]) for k in ('Game_Prepare','wait_blank','commit'))
        previous=math.floor((begin-blank_start/6)/period)*period+blank_start/6
        refreshes=math.floor((publish-blank_start/6)/period)-math.floor((begin-blank_start/6)/period)
        margin=previous+2*period-ready
        assert refreshes==round(f['cycles']/period),(f['frame'],refreshes)
        if refreshes>2:assert margin<0
        samples.append(dict(frame=f['frame'],refreshes=refreshes,ready_margin=margin,
            interval_cycles=f['cycles'],work_cycles=f['work'],logic_cycles=f['Game_Prepare'],
            render_cycles=f['render'],wait_cycles=f['wait_blank'],commit_cycles=f['commit'],
            untracked_cycles=f['untracked_loop_overhead'],cx=f['cx'],cy=f['cy'],dx=f['dx'],dy=f['dy']))
    positions=[]
    for actor in range(data.get('profile_enemy_count',3)):
        positions.append(len({bytes.fromhex(s['enemy_positions'])[actor*32+8:actor*32+11] for s in states if int(s['frame']) in ids}))
    assert min(positions)>1,'Stationary enemy workload'
    movement=[]
    for axis in ('horizontal','vertical','stationary'):
        rows=[f for f in active['frames'] if ('horizontal' if f['dx'] else 'vertical' if f['dy'] else 'stationary')==axis]
        if rows:movement.append(dict(axis=axis,frames=len(rows),work=distribution([f['work'] for f in rows])))
    result=dict(rom_sha256=data['rom_sha256'],source_revision=json.loads((bundle/'session-build.json').read_text())['revision'],
        timing_units=data.get('timing_units','Z80 cycles at fixed 3579545 Hz'),cpu_policy=data.get('cpu_policy','Fixed base Z80 clock'),
        cpu_hz=hz,machine=data['machine'],mapper_ram_kib=data.get('mapper_ram_kib',128),emulator=data['emulator'],workload=data['workload'],
        native_round=data.get('profile_native_round',5),enemy_count=data.get('profile_enemy_count',3),
        profile_path=str(profile.resolve()),method=data['method'],control=data['control_check'],
        limitsprites=True,hud=True,audio=True,total_intervals=len(states),active_frames=len(ids),
        active_seconds=sum(f['cycles'] for f in active['frames'])/hz,presented_fps=active['presented_fps'],
        work=distribution([f['work'] for f in active['frames']]),interval=distribution([f['cycles'] for f in active['frames']]),
        cadence={str(n):sum(s['refreshes']==n for s in samples) for n in sorted({s['refreshes'] for s in samples})},
        late_frames=sum(s['refreshes']>2 for s in samples),enemy_distinct_positions=positions,
        calibration=dict(cycles_per_line=228,cycles_per_refresh=period,refresh_hz=hz/period,
            two_refresh_fps=hz/(2*period),nominal_target_fps=29.97,vblank_cycles=(blank_end-blank_start)/6,
            vblank_start_line=blank_start//1368,vblank_start_cycle=(blank_start%1368)/6,
            vblank_end_line=(blank_end%(period*6))//1368,vblank_end_cycle=(blank_end%1368)/6,
            reserve_planning_cycles=5000,all_status2_and_duration_checks_passed=True),
        routines=active['routines'],raster=raster,frames=samples,movement=movement,
        limitations=f'Short directional workload, not a complete phase. Active endpoints require native round{data.get("profile_native_round",5)}, {data.get("profile_enemy_count",3)} enemies, no death/bonus and active session. Excludes{len(states)-len(ids)} stopped/death intervals. UI/cold and capture costs use separate controlled event ledgers; never mix their samples with active FPS. Inclusive parents overlap children; never sum them. IRQ spans exclude hardware entry/vector. No physical hardware measurement.')
    scenarios=[]
    for kind in ('start','integration','two-player','flags','attract','radar','smoke'):
        matches=[]
        for file in bundle.glob('session-start-*/result.json'):
            value=json.loads(file.read_text());graphics=file.parent/'graphics-contracts.json'
            if value['rom_sha256']==data['rom_sha256'] and value['scenario']==kind and graphics.exists():
                image_result=json.loads(graphics.read_text())
                if image_result['passed'] and image_result.get('rom_sha256')==data['rom_sha256']:
                    matches.append((file.stat().st_mtime,file,value,image_result))
        if matches:
            _,file,value,image_result=max(matches,key=lambda row:row[0])
            scenarios.append(dict(scenario=kind,path=str(file.parent.resolve()),passed=True,active_snapshots=len(image_result['snapshots']),
                silence_checks=value.get('cold_silence_checks',0)))
            if kind=='smoke' and 'smoke_regression' in value:result['smoke_regression']=value['smoke_regression']
            if kind=='integration' and 'challenge_speed' in value:result['challenge_motion']=value['challenge_speed']
            if kind=='integration' and (file.parent/'cold-hooks.tsv').exists():
                with (file.parent/'cold-hooks.tsv').open() as stream:hooks=list(csv.DictReader(stream,delimiter='\t'))
                result['cold_ledger']=[dict(name=name,calls=sum(h['routine']==name for h in hooks),
                    inclusive=distribution([float(h['inclusive_cycles']) for h in hooks if h['routine']==name]),
                    own=distribution([float(h['self_cycles']) for h in hooks if h['routine']==name])) for name in sorted({h['routine'] for h in hooks})]
                result['cold_scope']=dict(source=str((file.parent/'cold-hooks.tsv').resolve()),
                    method=value['cold_hook_method'],scope='Separate controlled full-session integration, native rounds2..14, UI/cold restoration; not part of the active frame statistics.')
            if kind=='flags' and (file.parent/'cold-hooks.tsv').exists():
                with (file.parent/'cold-hooks.tsv').open() as stream:hooks=list(csv.DictReader(stream,delimiter='\t'))
                flag_hooks=[h for h in hooks if h['routine']=='GameSession_RemoveFlag']
                if flag_hooks:
                    result['flag_event']=dict(calls=len(flag_hooks),inclusive=distribution([float(h['inclusive_cycles']) for h in flag_hooks]),
                        own=distribution([float(h['self_cycles']) for h in flag_hooks]),
                        source=str((file.parent/'cold-hooks.tsv').resolve()),method=value['cold_hook_method'],
                        scope=('Controlled real flag contact handler,10 captures; clears eight valid CPU records; immutable VRAM records receive the captured mask when loaded.' if result['mapper_ram_kib']==64 else 'Controlled real flag contact handler,10 captures; clears the normal and S-hidden caches.')+' No recurring overload is hidden as a capture pause.')
    result['verification']=dict(scenarios=scenarios,stable_graphics_snapshots=sum(s['active_snapshots'] for s in scenarios),
        cold_silence_checks=sum(s['silence_checks'] for s in scenarios))
    for kind,key in (('steering-proof-*','steering'),('audio-proof-*','audio'),('sprite-clip-proof-*','sprite_clip'),('speed-proof-*','challenge_speed'),('rocks-proof-*','enemy_rocks'),('boot-skip-proof-*','boot_skip')):
        matches=[]
        for file in bundle.glob(kind+'/report.json'):
            value=json.loads(file.read_text())
            if value.get('rom_sha256')==data['rom_sha256']:matches.append((file.stat().st_mtime,value))
        if matches:result['verification'][key]=max(matches,key=lambda row:row[0])[1]
    clear_cases={}
    for file in bundle.glob('session-start-*/result.json'):
        value=json.loads(file.read_text());seq=value.get('clear_sequence')
        if value.get('passed') and value.get('rom_sha256')==data['rom_sha256'] and seq:
            key=(seq['flag_order'],bool(seq.get('pause_cursor_and_timer_frozen')))
            if key not in clear_cases or file.stat().st_mtime>clear_cases[key][0]:clear_cases[key]=(file.stat().st_mtime,value)
    if clear_cases:
        cases=[v for _,v in clear_cases.values()];groups={}
        for case in cases:
            for line in (Path(case['source'])/'clear-costs.tsv').read_text().splitlines():
                name,value=line.split();groups.setdefault(name,[]).append(float(value))
        result['verification']['clear_sequence']=dict(passed=True,cases=cases,
            original=json.loads((bundle.parents[0]/'arcade-clear-audio/reference.json').read_text()),
            cost_groups=[dict(name='GameSession_CompletionWait ('+n+')',calls=len(v),inclusive=distribution(v)) for n,v in groups.items()],
            extra_active_selector_cycles_per_call=5,extra_state_ram_bytes=0,extra_resident_code_ram_bytes=33,extra_vram_bytes=0,
            scope='Controlled first-phase normal/S/L last-flag contacts and paused clear; foreground settlement, not VBlank or a scanline hook. Minimum/flag wait and converter-entry groups do not overlap. Converter entry includes the original Completion_Begin child; self costs not separated.')
    if (bundle/'session-audio-corrections.json').exists():result['audio_assets']=json.loads((bundle/'session-audio-corrections.json').read_text())
    result['hud_module']=json.loads((bundle/'hud-module.json').read_text())
    result['cosmetics']=json.loads((bundle/'session-cosmetics.json').read_text())
    result['title']=json.loads((bundle/'session-title.json').read_text())
    result['boot']=json.loads((bundle/'session-boot.json').read_text())
    matches=[]
    for file in bundle.glob('boot-proof-*/report.json'):
        value=json.loads(file.read_text())
        if value.get('passed') and value['rom_sha256']==data['rom_sha256']:matches.append((file.stat().st_mtime,value))
    if matches:
        value=max(matches,key=lambda row:row[0])[1]
        value['elapsed_inclusive_cycles']=value['seconds']*hz
        value['cycle_scope']='One startup call only. Elapsed cycles include IRQs, decode/upload and synchronization waits; self/CPU-only/wait costs are not separated. Never add to active-frame work.'
        result['verification']['boot']=value
    controls=[]
    variant_suffix='-64k' if result['mapper_ram_kib']==64 else ''
    for path in (bundle,bundle.with_name('full-session-test'+variant_suffix),bundle.with_name('full-session-hud-classic'+variant_suffix)):
        if not (cartridge_path(path)).exists():continue
        sha=hashlib.sha256((cartridge_path(path)).read_bytes()).hexdigest()
        for kind in ('controls','start') if '-hud-classic' in path.name else ('controls',):
            matches=[]
            for file in path.glob('session-start-*/result.json'):
                value=json.loads(file.read_text());graphics=file.parent/'graphics-contracts.json'
                if value.get('passed') and value['rom_sha256']==sha and value['scenario']==kind and graphics.exists():
                    checked=json.loads(graphics.read_text())
                    if checked.get('passed') and checked['rom_sha256']==sha:matches.append((file.stat().st_mtime,value))
            if matches:controls.append(max(matches,key=lambda row:row[0])[1])
    result['verification']['build_variants']=controls
    no_logo=bundle.with_name('full-session-no-logo'+variant_suffix)
    if (cartridge_path(no_logo)).exists():
        sha=hashlib.sha256((cartridge_path(no_logo)).read_bytes()).hexdigest();matches=[]
        for file in no_logo.glob('boot-proof-*/report.json'):
            value=json.loads(file.read_text())
            if value.get('passed') and value['rom_sha256']==sha:matches.append((file.stat().st_mtime,value))
        if matches:result['verification']['no_logo']=max(matches,key=lambda r:r[0])[1]
    if (bundle/'session-challenge-reveal.json').exists():result['challenge_reveal']=json.loads((bundle/'session-challenge-reveal.json').read_text())
    result['phase_policy']=dict(pattern_sets=8,bytes_per_set=16384,names_base=2048,extra_mapper_segments=0,additional_cache_metadata_bytes=76,
        method='Cold prewarm, validated exact-phase lookup, then256-cycle-quantized estimates for seven inactive sets. Visible set never written.',
        cost_table_sha256=hashlib.sha256((bundle/'session-phase-costs.json').read_bytes()).hexdigest())
    result['rom_bytes']=(cartridge_path(bundle)).stat().st_size
    baseline=out/'baseline-5451bd/cycle-ledger.json'
    if baseline.exists():
        prior=json.loads(baseline.read_text())
        assert prior['cpu_hz']==hz and prior['workload']==result['workload']
        video=next(r for r in prior['cold_ledger'] if r['name']=='GameSession_Video')
        prior_rom=Path(prior['profile_path'])/'measured.rom'
        if prior_rom.exists():assert hashlib.sha256(prior_rom.read_bytes()).hexdigest()==prior['rom_sha256']
        result['baseline_comparison']=dict(source=str(baseline.resolve()),rom_sha256=prior['rom_sha256'],
            presented_fps=prior['presented_fps'],late_frames=prior['late_frames'],active_frames=prior['active_frames'],
            mean_work_ms=prior['work']['mean']/hz*1000,cold_video_mean_ms=video['inclusive']['mean']/hz*1000,rom_bytes=prior_rom.stat().st_size if prior_rom.exists() else None,
            scope='Same machine, source revision and scripted input; execution timing changes trajectories and active/death partitions. Not a matched marginal speedup or a full course.')
    if comparison and Path(comparison).exists():
        compared=json.loads(Path(comparison).read_text())
        # A retained comparison must never be silently attached to a new ROM.
        matching=[r for r in compared['profiles'] if r['rom_sha256']==data['rom_sha256']]
        if matching:
            result['ram_profile_comparison']=compared
    out.mkdir(parents=True,exist_ok=True)
    (out/'cycle-ledger.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out/'routines.csv').open('w') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(('Routine','Calls/frame','Mean incl cycles/call','P95 incl cycles/call','Max incl cycles/call','Self cycles/frame','Mean incl ms/frame','P95 incl ms/frame','Max incl ms/frame','Mean self cycles/call','P95 self cycles/call','Max self cycles/call','P95 self cycles/frame','Max self cycles/frame'))
        for r in result['routines']:w.writerow((r['name'],r['calls_per_frame'],r['mean'],r['p95'],r['max'],r['self_per_frame'],*[r['frame_cycles'][k]/hz*1000 for k in ('mean','p95','max')],*[r['self_call_cycles'][k] if r['self_call_cycles'] else '' for k in ('mean','p95','max')],*[r['self_frame_cycles'][k] for k in ('p95','max')]))
    print(json.dumps({k:result[k] for k in ('rom_sha256','active_frames','active_seconds','presented_fps','cadence','late_frames','enemy_distinct_positions')},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=Path('references/build/game'));p.add_argument('--out',type=Path,default=Path('references/validation/game'));p.add_argument('--profile',type=Path)
    p.add_argument('--comparison',type=Path,default=Path('docs/measurements/timing/ram-profile-comparison.json'))
    a=p.parse_args();report(a.bundle,a.out,a.profile,a.comparison)
