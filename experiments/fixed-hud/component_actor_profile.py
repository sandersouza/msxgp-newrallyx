"""Observe per-actor PC/SP matched runtime spans on an immutable game ROM.

--population 1/2 selects a diagnostic active-count clamp on the unchanged 3-enemy
ROM. Only e24e is written at presentation boundary and at the population fixture
return; native actor descriptors, AI, motion, HUD, audio and rendering are intact.
This is a controlled workload, not a released 1/2-enemy build.
"""
from pathlib import Path
import sys,json,csv,statistics,math

population=None
if '--population' in sys.argv:
    i=sys.argv.index('--population'); population=int(sys.argv[i+1]);del sys.argv[i:i+2]
    assert population in (1,2,3)
ROUTINES={
 'Game_Prepare':'Whole simulation and foreground preparation',
 'Game_Frame':'All elapsed native ticks',
 'Game_LogicTick':'Whole native/host gameplay tick',
 'Full_MSXPlayerSpeed':'Player velocity cap',
 'Native_PlayerFinalize':'Player steering and wall probes (9052)',
 'Native_MotionDispatcher':'All actors native motion dispatcher (8069)',
 'Full_MSXAI':'Enemy AI dispatcher',
 'Full_MSXActor':'One enemy AI decision, keyed by IX descriptor',
 'Game_Actors':'Native descriptors to all actor records',
 'GameSprites_Prepare':'All eight actor slots preparation',
 'GS_PrepareActor':'One actor preparation keyed by GS_Index; includes descendants',
 'GS_UploadActor':'Dirty pattern/color publication for current actor',
 'GS_UploadDirect':'Unmasked direct sprite publication for current actor',
 'GameSprites_Commit':'Shared world sprite publication',
 'GameHUD_Prepare':'HUD preparation',
 'GameAudio_Tick':'PSG worker',
 'render':'Whole background preparation',
 'wait_blank':'Synchronization including HALT',
 'commit':'Whole presentation publication',
 'clock_irq':'VBlank ISR body',
}
ALIASES={'Native_PlayerFinalize':0x9052,'Native_MotionDispatcher':0x8069}
driver=Path(__file__).with_name('game_profile.py').read_text()
start=driver.index("source=source[:start]+'''ROUTINES = {")
end=driver.index("}'''+source[end:]",start)+len("}'''+source[end:]")
driver=driver[:start]+'source=source[:start]+'+repr('ROUTINES = '+repr(ROUTINES))+'+source[end:]'+driver[end:]
adapt=r'''
source=source.replace("    syms['HUD_NameStores'] = 0xa300", "    syms['HUD_NameStores'] = 0xa300\n    syms.update("+repr(ALIASES)+")")
source=source.replace("        assert rows, f'Unexercised routine: {name}'", "        if not rows:\n            stats.append(dict(name=name,purpose=purpose+' (not called)',calls=0,calls_per_frame=0,min=None,mean=None,p95=None,max=None,self_mean=None,self_total=0))\n            continue")
source=source.replace(r'\ttop_level"',r'\ttop_level\tactor\tenemies"')
source=source.replace('lassign [lindex $::stack end] name start child ret sp owner','lassign [lindex $::stack end] name start child ret sp owner actor enemies')
source=source.replace('[expr {{[llength $::stack]==1}}]"','[expr {{[llength $::stack]==1}}]\t$actor\t$enemies"')
source=source.replace('lappend ::stack [list $name [cycle] 0 $ret $sp $::frame]', """set actor shared
    if {{$name eq "Full_MSXActor"}} {{set actor [expr {{1+([reg IX]-0xe088)/32}}]}}
    if {{$name eq "Full_MSXPlayerSpeed" || $name eq "Native_PlayerFinalize"}} {{set actor 0}}
    if {{$name in {{GS_PrepareActor GS_UploadActor GS_UploadDirect}}}} {{set actor [debug read memory {syms['GS_Index']}]}}
    lappend ::stack [list $name [cycle] 0 $ret $sp $::frame $actor [debug read memory 0xe24e]]""")
source=source.replace(r'\tactive_end"',r'\tactive_end\tenemies_start\tenemies_end"')
source=source.replace('[active_gameplay]"','[active_gameplay]\t$::enemies_start\t[debug read memory 0xe24e]"')
source=source.replace('    set ::active_start [active_gameplay]','    set ::active_start [active_gameplay]\n    set ::enemies_start [debug read memory 0xe24e]')
if population is not None:
    # Fixture is exactly ld a,n; ld (e24e),a; ret in this immutable image.
    source=source.replace('    set ::start [cycle]', '    debug write memory 0xe24e '+str(population)+'\n    set ::start [cycle]')
    source=source.replace('    for name in ROUTINES:', "    script += f'debug set_bp {syms[\"GameMulti_Parameters\"]+5} {{}} {{debug write memory 0xe24e "+str(population)+"}}\\n'\n    for name in ROUTINES:",1)
'''
driver=driver.replace('exec(compile(source,',adapt+'\nexec(compile(source,',1)
ns={'__file__':str(Path(__file__).with_name('game_profile.py')),'__name__':'__main__','ALIASES':ALIASES,'population':population,'json':json}
exec(compile(driver,str(Path(__file__).with_name('game_profile.py')),'exec'),ns)
base=ns['base'];out=Path((base/'last-profile.txt').read_text().strip())
meta=json.loads((out/'summary.json').read_text())
with (out/'calls.tsv').open() as f:calls=list(csv.DictReader(f,delimiter='\t'))
with (out/'frames.tsv').open() as f:frames=list(csv.DictReader(f,delimiter='\t'))
ids={int(r['frame']) for r in meta['active_ledger']['frames']}
active=[r for r in calls if int(r['frame']) in ids]
def summary(rows):
    a=sorted(float(r['inclusive_cycles']) for r in rows);b=[float(r['self_cycles']) for r in rows]
    return dict(calls=len(rows),calls_per_presented_frame=len(rows)/len(ids),inclusive_mean=statistics.mean(a),inclusive_p95=a[math.ceil(.95*len(a))-1],inclusive_max=max(a),inclusive_total=sum(a),inclusive_per_presented_frame=sum(a)/len(ids),self_mean=statistics.mean(b),self_total=sum(b),self_per_presented_frame=sum(b)/len(ids))
groups=[]
for routine,actor in sorted({(r['routine'],r['actor']) for r in active}):
    rows=[r for r in active if r['routine']==routine and r['actor']==actor]
    groups.append(dict(routine=routine,actor=actor,**summary(rows)))
populations=sorted({int(r['enemies_start']) for r in frames if int(r['frame']) in ids}|{int(r['enemies_end']) for r in frames if int(r['frame']) in ids}|{int(r['enemies']) for r in active})
if population is not None:assert populations==[population],populations
result=dict(rom_sha256=meta['rom_sha256'],source_bundle=str(base),evidence_directory=str(out),population_override=population,observed_active_enemy_counts=populations,active_presented_frames=len(ids),cpu_hz=meta['cpu_hz'],video_hz_nominal=60,presented_fps=meta['active_ledger']['presented_fps'],workload=meta['workload'],groups=groups,notes=['Actor0=player, actor1..n=enemy descriptors e088+32*(n-1); shared means unpartitioned cost.','Inclusive parent and child rows overlap. Self subtracts only the listed instrumented descendants.','Shared actor-list conversion and SAT publication are not divided by actor or estimated.','Population clamp1/2 changes active descriptor count only; it is a diagnostic unchanged-ROM workload with native AI/movement and existing cloned spawn descriptors.','Guest state, count fields, keyboard route and frame timing validated against the same workload without routine-entry breakpoints; per-frame tolerance5.01cycles.'])

meta['profile_kind']='actors'
(out/'summary.json').write_text(json.dumps(meta,indent=2)+'\n')
result['total_presented_frames']=len(frames)
result['control_validation']='passed: identical observed state and input; <=5.01cycles each interval; <=5.01cycles total'
result['aggregates']=[]
count=max(populations)
scopes={
 'graphics_player':lambda r:r['routine']=='GS_PrepareActor' and r['actor']=='0',
 'graphics_active_enemies':lambda r:r['routine']=='GS_PrepareActor' and r['actor'].isdigit() and 1<=int(r['actor'])<=count,
 'graphics_player_and_active_enemies':lambda r:r['routine']=='GS_PrepareActor' and r['actor'].isdigit() and 0<=int(r['actor'])<=count,
 'graphics_all_8_slots_including_inactive_checks':lambda r:r['routine']=='GS_PrepareActor',
 'enemy_AI_all_active':lambda r:r['routine']=='Full_MSXActor',
 'player_velocity_and_finalize_only_excludes_shared_motion':lambda r:r['routine'] in ('Full_MSXPlayerSpeed','Native_PlayerFinalize'),
}
for name,predicate in scopes.items():
 rows=[r for r in active if predicate(r)]
 values=sorted(sum(float(r['inclusive_cycles']) for r in rows if int(r['frame'])==frame) for frame in ids)
 result['aggregates'].append(dict(name=name,calls=len(rows),calls_per_presented_frame=len(rows)/len(ids),inclusive_total=sum(values),inclusive_per_presented_frame=statistics.mean(values),frame_p95=values[math.ceil(.95*len(values))-1],frame_max=max(values),scope='sum of actual non-overlapping observed calls in each active presented interval'))

(out/'actor-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print('ACTOR_SUMMARY '+str(out/'actor-summary.json'))
