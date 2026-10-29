"""Build inspectable component/frame aggregates from immutable profiler traces."""
import argparse, csv, json, math, statistics, re
from pathlib import Path

def stats(values):
    a=sorted(values)
    return dict(mean=statistics.mean(a),p95=a[math.ceil(.95*len(a))-1],max=max(a))

def read_calls(folder):
    with (folder/'calls.tsv').open() as f:
        return list(csv.DictReader(f,delimiter='\t'))

def schedule_ledger(folder,frames,calls,raster,cpu_hz):
    """Measure the foreground deadline relative to the previous publish edge.

    One/two/four refresh classification uses actual VDP epochs, not average CPU
    costs or sums of unrelated per-routine percentiles. The wait entry is an
    observed readiness point; interrupt-entry latency is not usable budget.
    """
    period=raster['calibration']['cycles_per_refresh']
    cal=raster['calibration']
    edge=cal['vblank_start_line']*228+cal['vblank_start_cycle_in_line']
    ids={f['frame'] for f in frames}
    with (folder/'frames.tsv').open() as file:
        states={int(r['presentation']):r for r in csv.DictReader(file,delimiter='\t')}
    for f in frames:
        state=states[f['frame']]
        assert (int(state['x']),int(state['y']),int(state['ticks']))==(f['cx'],f['cy'],f['elapsed_ticks']), 'Raster/CPU workload mismatch'
    endpoints=json.loads((folder/'endpoints.json').read_text())
    spans={n:{} for n in ids}
    for r in endpoints:
        n=int(r['presentation'])
        if n in ids and r['routine'] in ('Game_Prepare','render','wait_blank','commit'):
            assert r['routine'] not in spans[n]
            spans[n][r['routine']]=r
    def stamp(r):return int(r['start_vframe'])*period+int(r['start_vtick'])/6
    samples=[];reconciliation=[]
    for f in frames:
        n=f['frame'];s=spans[n];assert len(s)==4
        begin,ready,publish=(stamp(s[k]) for k in ('Game_Prepare','wait_blank','commit'))
        previous_edge=math.floor((begin-edge)/period)*period+edge
        count=math.floor((publish-edge)/period)-math.floor((begin-edge)/period)
        margin=previous_edge+2*period-ready
        # Commit return -> next prepare: loop bookkeeping34 + CALL18 cycles.
        predicted=count*period+s['commit']['start_from_previous_blank_edge_cycles']+float(s['commit']['duration'])+52-(begin-previous_edge)
        reconciliation.append(abs(predicted-f['cycles']))
        assert reconciliation[-1]<5.01,'VDP cadence does not reconcile with CPU interval'
        samples.append(dict(frame=n,refreshes=count,ready_margin_cycles=margin,
            foreground_cycles=ready-begin,start_offset_cycles=begin-previous_edge,
            native_ticks=f['elapsed_ticks'],work_cycles=f['work']))
    late={r['frame'] for r in samples if r['refreshes']>2}
    assert late
    assert all(r['ready_margin_cycles']<0 for r in samples if r['frame'] in late)
    owners=[]
    for name in sorted({r['routine'] for r in calls}):
        records=[r for r in calls if r['routine']==name]
        if name in ('wait_blank','clock_irq','commit','GameHUD_Commit','GameSprites_Commit'):continue
        owners.append(dict(name=name,self_per_frame=sum(float(r['self_cycles']) for r in records)/len(ids),
            self_per_late_frame=sum(float(r['self_cycles']) for r in records if int(r['frame']) in late)/len(late),
            inclusive_max=max(float(r['inclusive_cycles']) for r in records)))
    owners.sort(key=lambda r:r['self_per_late_frame'],reverse=True)
    margins=sorted(r['ready_margin_cycles'] for r in samples)
    return dict(frames=len(ids),late_frames=len(late),
        refresh_counts={str(n):sum(r['refreshes']==n for r in samples) for n in sorted({r['refreshes'] for r in samples})},
        ready_margin_cycles=dict(mean=statistics.mean(margins),p05=margins[max(0,math.ceil(.05*len(margins))-1)],min=min(margins)),
        late_shortfall_cycles=stats([max(0,-r['ready_margin_cycles']) for r in samples if r['frame'] in late]),
        foreground_cycles=stats([r['foreground_cycles'] for r in samples]),
        measured_two_refresh_fps=cpu_hz/(2*period),samples=samples,owners=owners,
        loop_tail_to_prepare_cycles=52,maximum_interval_reconciliation_error_cycles=max(reconciliation),
        method='Two-refresh readiness deadline measured from previous VBlank publication edge to wait_blank entry; actual publication classified with native VDP frame/tick counters. Self owners are disjoint within this instrumentation; inclusive maxima overlap and must not be added.',
        source=str(folder/'endpoints.json'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--raster',type=Path,required=True)
    p.add_argument('--actors',type=Path,nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--baseline',type=Path,help='Earlier component summary for a scoped comparison')
    p.add_argument('--target-fps',type=float,default=29.97)
    a=p.parse_args()
    d=json.loads((a.profile/'summary.json').read_text())
    active=d['active_ledger'];frames=active['frames'];ids={r['frame'] for r in frames}
    calls=[r for r in read_calls(a.profile) if int(r['frame']) in ids]
    rows=[]
    tracked={r['name'] for r in active['routines']}
    def aggregate(label,terms,scope,source=a.profile,records=calls,frame_ids=ids):
        if source==a.profile:
            assert set(terms)<=tracked, f'Uninstrumented component owners: {set(terms)-tracked}'
        selected=[r for r in records if r['routine'] in terms]
        frame_sums=dict.fromkeys(frame_ids,0.0)
        for r in selected:frame_sums[int(r['frame'])]+=float(r[terms[r['routine']]])
        per_frame=[frame_sums[n] for n in sorted(frame_ids)]
        per_call=[float(r[terms[r['routine']]]) for r in selected]
        rows.append(dict(label=label,scope=scope,frames=len(frame_ids),calls=len(selected),
            calls_per_frame=len(selected)/len(frame_ids),frame_cycles=stats(per_frame),
            call_cycles=stats(per_call) if per_call else None,terms=terms,source=str(source/'summary.json')))
    def add(label,names,scope):
        aggregate(label,{name:'inclusive_cycles' for name in names},scope)
    add('Simulation including audio',['Game_Frame'],'3 enemies; parent of logic/audio; do not add children')
    add('Gameplay tick',['Game_LogicTick'],'3 enemies; flags, fuel, motion and collisions')
    add('Player steering / wall probes',['Native_PlayerFinalize'],'Player logic subset; original 9052 routine')
    add('Player velocity cap',['Full_MSXPlayerSpeed'],'Player logic subset; not all native motion')
    add('Camera pan logic',['Full_MSXPan'],'Camera movement calculation; no drawing')
    add('Player / camera projection',['Game_Position'],'Coordinate conversion and camera clamp')
    add('Enemy AI dispatcher',['Full_MSXAI'],'3 enemies; includes individual AI decisions')
    add('Enemy contact scan',['Full_MSXContact'],'Shared collision pass over native enemies')
    add('Native motion dispatcher',['Native_MotionDispatcher'],'Shared player/enemy motion; overlaps player and enemy hooks; not individually attributable')
    add('Actor records',['Game_Actors'],'All player/enemy/effect descriptors to render list')
    add('World sprites prepare',['GameSprites_Prepare'],'All slots; includes individual preparation/uploads')
    add('World sprites publish',['GameSprites_Commit'],'Shared SAT/color work during final commit')
    add('Map drawing',['Ring_Prepare','Game_RingPatch','Ring_UploadNames','Game_DirtyTileUpload','GameDirty_Plan'],
        'Disjoint map owners: ring, overlays, terrain names/tiles and dirty planning')
    add('Map ring prepare',['Ring_Prepare'],'Child of map drawing')
    add('Map terrain names',['Ring_UploadNames'],'Child of map drawing; includes row/column transfers')
    add('Radar',['Game_Radar','Game_RadarUpload'],'Pattern preparation plus VRAM transfer; independent of terrain')
    add('HUD dynamic',['GameHUD_Prepare','GameHUD_Commit'],'Score, fuel, lives and round; preparation + publication')
    add('Phase cache selection',['GamePhase_Select'],'New foreground cache ownership hook; one call per presentation; included in background parent')
    aggregate('HUD static / border',{
        'hud_upload':'self_cycles','GameBoundary_Upload':'inclusive_cycles',
        'HUD_NameStores':'inclusive_cycles','left_names':'inclusive_cycles','boundaries':'inclusive_cycles'},
        'Static phase packet self + boundary packet + names; terrain/radar child spans excluded')
    aggregate('HUD total excluding radar',{
        'GameHUD_Prepare':'inclusive_cycles','GameHUD_Commit':'inclusive_cycles',
        'hud_upload':'self_cycles','GameBoundary_Upload':'inclusive_cycles',
        'HUD_NameStores':'inclusive_cycles','left_names':'inclusive_cycles','boundaries':'inclusive_cycles',
        'GamePhase_Select':'inclusive_cycles'},
        'Static/border + dynamic HUD + cache selection owners; radar and terrain excluded; overlaps the HUD/cache rows above')
    add('Audio total',['GameAudio_Tick'],'Parent: divider, music, effects and PSG; inside simulation')
    add('Music sequence',['GameAudio_MusicTick'],'30 Hz sequence advance; excludes shared PSG output')
    add('Engine / sound effects',['GameAudio_NoiseTick'],'30 Hz effect/engine worker; excludes shared PSG output')
    aggregate('Audio mix overhead',{'GameAudio_RenderMusic':'self_cycles'},'Mix/output dispatch self; PSG writes excluded')
    add('PSG register output',['GameAudio_WritePSG'],'Changed-register output shared by music and effects')
    for label,name in [('Flags','Flag_Update'),('Score events','Score_Update'),('Fuel','Fuel_Tick'),
                       ('Rocks','Rock_Update'),('Smoke','Smoke_Tick'),('Gameplay events','Game_Events')]:
        add(label,[name],'3 enemies; logic subset, already contained in simulation')
    add('Background owner',['render'],'Inclusive parent: map, radar, static HUD, other scaffolding')
    add('Atomic commit',['commit'],'Inclusive parent: registers, dynamic HUD and world sprite publication')
    add('Synchronization wait',['wait_blank'],'HALT + wake-up IRQ; waiting, not processing work')
    add('VBlank ISR body',['clock_irq'],'139-cycle body; hardware entry/vector charged to interrupted owner')
    # Detailed source inputs retain both inclusive and exclusive ownership.
    detail=[]
    for r in active['routines']:
        detail.append(dict(name=r['name'],calls=r['calls'],calls_per_frame=r['calls_per_frame'],
            mean=r['mean'],p95=r['p95'],max=r['max'],self_mean=r['self_mean'],
            self_per_frame=r['self_total']/len(ids),source=str(a.profile/'summary.json')))
    movement=[]
    mapnames={'Ring_Prepare','Game_RingPatch','Ring_UploadNames','Game_DirtyTileUpload','GameDirty_Plan'}
    costs=dict.fromkeys(ids,0.0)
    for c in calls:
        if c['routine'] in mapnames:costs[int(c['frame'])]+=float(c['inclusive_cycles'])
    for axis in ('horizontal','vertical','stationary','mixed'):
        for crossing in (False,True):
            sample=[r for r in frames if ('horizontal' if r['dx'] and not r['dy'] else 'vertical' if r['dy'] and not r['dx'] else 'mixed' if r['dx'] and r['dy'] else 'stationary')==axis and r['tile_crossing']==crossing]
            if not sample:continue
            movement.append(dict(axis=axis,transition='tile crossing' if crossing else 'within tile',samples=len(sample),
                work=stats([r['work'] for r in sample]),render=stats([r['render'] for r in sample]),
                map=stats([costs[r['frame']] for r in sample]),interval=stats([r['cycles'] for r in sample])))
    actor_sources=[]
    for folder in a.actors:
        actor=json.loads((folder/'actor-summary.json').read_text());actor_sources.append(actor)
        assert actor['rom_sha256']==d['rom_sha256']
        meta=json.loads((folder/'summary.json').read_text());actorids={r['frame'] for r in meta['active_ledger']['frames']}
        records=[r for r in read_calls(folder) if int(r['frame']) in actorids]
        count=actor['observed_active_enemy_counts'][0]
        for label,routine,allowed in [('Player graphics','GS_PrepareActor',{'0'}),
                                     (f'{count} enemy graphics','GS_PrepareActor',{str(n) for n in range(1,count+1)}),
                                     (f'{count} enemy AI decisions','Full_MSXActor',{str(n) for n in range(1,count+1)})]:
            aggregate(label,{routine:'inclusive_cycles'},f'{count}-enemy diagnostic, actual per-frame sum; shared dispatch/SAT/motion excluded',
                      folder,[r for r in records if r['actor'] in allowed],actorids)
    raster=json.loads((a.raster/'summary.json').read_text());assert raster['rom_sha256']==d['rom_sha256']
    raster['example_logic_span']=next(r for r in json.loads((a.raster/'endpoints.json').read_text()) if r['routine']=='Game_Frame')
    result=dict(cpu_hz=d['cpu_hz'],rom_sha256=d['rom_sha256'],machine=d['machine'],
        target_presented_fps=a.target_fps,
        frames=len(ids),presented_fps=active['presented_fps'],control=d['control_check'],
        frame_work_cycles=stats([r['work'] for r in frames]),
        frame_interval_cycles=stats([r['cycles'] for r in frames]),
        profile_path=str(a.profile/'summary.json'),raster_path=str(a.raster/'summary.json'),
        components=rows,routines=detail,movement=movement,actors=actor_sources,raster=raster)
    result['schedule']=schedule_ledger(a.raster,frames,calls,raster,d['cpu_hz'])
    root=Path(__file__).resolve().parents[2]
    phase_proof=root/'outputs/fixed-hud/phase-cache-proof.json'
    if phase_proof.exists() and json.loads(phase_proof.read_text())['rom_sha256']==d['rom_sha256']:
        result['phase_cache_proof']=json.loads(phase_proof.read_text())
    layout_proof=root/'outputs/fixed-hud/hud-layout-proof.json'
    if layout_proof.exists() and json.loads(layout_proof.read_text())['rom_sha256']==d['rom_sha256']:
        sprites=[json.loads((root/f'outputs/fixed-hud/sprite-clip-{part}/cycle-ledger.json').read_text()) for part in ('before','after')]
        hud=[json.loads((root/f'references/experiments/hud-program-proof-{part}/summary.json').read_text()) for part in ('before','active')]
        assert hud[1]['rom_sha256']==d['rom_sha256']
        def symbols_at(path):
            return {n:int(v,16) for n,v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)',path.read_text())}
        actual_symbols=symbols_at(a.profile/'measured.sym')
        probe=root/'outputs/fixed-hud/sprite-clip-after'
        probe_symbols=symbols_at(probe/'probe.sym')
        def clip_body(binary,symbols):
            return binary[symbols['GS_ClippedCopyFast']-0x4000:symbols['GS_ClippedCopyFast_End']-0x4000]
        expected=clip_body((probe/'probe.rom').read_bytes(),probe_symbols)
        for opcode,name,uses in ((0xcd,'GS_Attributes',2),(0xc3,'GS_UploadActor',1)):
            old=bytes((opcode,))+probe_symbols[name].to_bytes(2,'little')
            assert expected.count(old)==uses
            expected=expected.replace(old,bytes((opcode,))+actual_symbols[name].to_bytes(2,'little'))
        assert expected==clip_body((a.profile/'measured.rom').read_bytes(),actual_symbols)
        workers=[]
        for label in ('eight-interior-unchanged-warm','eight-interior-animation-change','four-vertical-clipped-animation-change','sentinel-animation-change'):
            workers.append(dict(name='GameSprites_Prepare',before=sprites[0]['timings'][label]['prepare_mean'],
                after=sprites[1]['timings'][label]['prepare_mean'],scope='Synthetic '+label+'; mean inclusive, no HUD/native game',
                source='outputs/fixed-hud/sprite-clip-{before,after}/cycle-ledger.json'))
        label='eight-interior-unchanged-warm'
        workers.append(dict(name='GameSprites_Commit',before=sprites[0]['timings'][label]['commit_mean'],
            after=sprites[1]['timings'][label]['commit_mean'],scope='Synthetic stable SAT/color publication;8cars, warm both sets',
            source='outputs/fixed-hud/sprite-clip-{before,after}/cycle-ledger.json'))
        workers.append(dict(name='hud_upload',before=hud[0]['mean_cycles'],after=hud[1]['mean_cycles'],
            scope='All8320 phase/back/cold combinations; inclusive wrapper, IRQ enabled; equal phase cases, layout differs',
            source='references/experiments/hud-program-proof-{before,active}/summary.json'))
        measured_size=(a.profile/'measured.rom').stat().st_size
        prior_size=(root/'references/experiments/stage-one-3-enemies/baseline-12e32699/fixed-hud.rom').stat().st_size
        result['hud_sprite_proofs']=dict(workers=workers,layout=json.loads(layout_proof.read_text()),hud=hud[1],sprite_cases=sprites[1]['cases'],
            same_compiled_clip_helper=True,rom_bytes=measured_size,before_rom_bytes=prior_size,extra_rom_bytes=measured_size-prior_size,extra_ram=0,
            placement='Clipping, bounds, cache pointers and fixed-slot dispatch in foreground. Compiled exact HUD transfers in ROM,50static slots, no new RAM. Pattern transfers stay in foreground; SAT/colors publish in VBlank.')
    result['video_modes']=dict(source='https://raw.githubusercontent.com/openMSX/openMSX/RELEASE_21_0/src/video/VDP.hh',
        scope='60Hz mode measured above.50Hz figures calculated from official313-line timing constants, not a50Hz runtime run. Same CPU clock per second; native tick/audio adaptation would be required.',
        rows=[dict(mode='60Hz nominal',lines=262,cycles=262*228,refresh_hz=d['cpu_hz']/(262*228),two_refresh_fps=d['cpu_hz']/(2*262*228)),
              dict(mode='50Hz nominal (calculated)',lines=313,cycles=313*228,refresh_hz=d['cpu_hz']/(313*228),two_refresh_fps=d['cpu_hz']/(2*313*228))])
    edge_proof=root/'outputs/fixed-hud/boundary-stable-proof.json'
    if edge_proof.exists() and json.loads(edge_proof.read_text())['after_sha256']==d['rom_sha256']:
        smoke_before=json.loads((root/'outputs/fixed-hud/smoke-row-decode-before/cycle-ledger.json').read_text())
        smoke_after=json.loads((root/'outputs/fixed-hud/smoke-row-decode/cycle-ledger.json').read_text())
        ring=json.loads((root/'outputs/fixed-hud/ring-refresh-synthetic/cycle-ledger.json').read_text())
        square=json.loads((root/'references/experiments/patch-square-row-loop/summary.json').read_text())
        assert square['after_sha256']==d['rom_sha256']
        current_rom=(a.profile/'measured.rom').read_bytes()
        # Ring refresh is in mapper bank4, atAA00 in its CPU window.
        worker=(root/'references/experiments/stage-one-3-enemies/game-ring-refresh.bin').read_bytes()
        assert current_rom[4*16384+0x2a00:4*16384+0x2a00+len(worker)]==worker
        assert (root/'outputs/fixed-hud/ring-refresh-synthetic/candidate/game-ring-refresh.bin').read_bytes()==worker
        rows=[]
        for label in ('three-live-rows','16-occupied-rows'):
            rows.append(dict(name='GameSmoke_BuildCache',before=smoke_before['workloads'][label]['candidate']['mean'],
                after=smoke_after['workloads'][label]['candidate']['mean'],scope='Synthetic '+label+'; exact ordered records; entry-to-return',
                source='outputs/fixed-hud/smoke-row-decode{,-before}/cycle-ledger.json'))
        for label in ('vertical-one-tile','horizontal-one-tile'):
            rows.append(dict(name='Ring_Prepare',before=ring['results']['baseline']['workloads'][label]['prepare']['mean'],
                after=ring['results']['candidate']['workloads'][label]['prepare']['mean'],scope='Synthetic '+label+'; metadata helper remains in parent',
                source='outputs/fixed-hud/ring-refresh-synthetic/cycle-ledger.json'))
        rows.append(dict(name='Game_PatchSquare',before=square['mean_accepted_cycles']['before'],
            after=square['mean_accepted_cycles']['after'],scope='Synthetic accepted squares,1280 compiled cases total; exact RAM/native guards',
            source='references/experiments/patch-square-row-loop/summary.json'))
        result['late_frame_proofs']=dict(edge=json.loads(edge_proof.read_text()),workers=rows,
            placement='Foreground only. The1934-byte unrolled worker occupies unused mapper-bank4 ROM; zero new RAM or banks. Costs stay inside measured parents; isolated probes must not be added to frame totals.')
    probe=Path(__file__).resolve().parents[2]/'outputs/fixed-hud/packet-fast-root'
    symbols=dict((n,int(v,16)) for n,v in re.findall(r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)',(a.profile/'measured.sym').read_text(),re.M))
    if 'GamePacketFast_Transfer' in symbols and (probe/'native-result.json').exists():
        ps=dict((n,int(v,16)) for n,v in re.findall(r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)',(probe/'probe.sym').read_text(),re.M))
        def body(rom,s):return rom[s['GamePacketFast_Transfer']-0x4000:s['GamePacketFast_End']-0x4000]
        assert body((a.profile/'measured.rom').read_bytes(),symbols)==body((probe/'probe.rom').read_bytes(),ps)
        result['packet_transfer']=json.loads((probe/'native-result.json').read_text())
        result['packet_transfer']['source']=str(probe/'native-result.json')
        result['packet_transfer']['same_compiled_helper_as_gameplay']=True
    if a.baseline:
        before=json.loads(a.baseline.read_text())
        assert before['cpu_hz']==result['cpu_hz'] and before['machine']==result['machine']
        result['comparison']=dict(source=str(a.baseline),rom_sha256=before['rom_sha256'],
            frames=before['frames'],presented_fps=before['presented_fps'],
            components=before['components'],frame_work_cycles=before['frame_work_cycles'],
            frame_interval_cycles=before['frame_interval_cycles'],
            scope='Same keyboard controller and active-state filter; actual native routes and sample sizes differ. Synthetic paired probes isolate individual adapter changes.')
        if before.get('schedule'):
            result['comparison']['schedule']={k:v for k,v in before['schedule'].items() if k not in ('samples','owners')}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(a.out)

if __name__=='__main__':main()
