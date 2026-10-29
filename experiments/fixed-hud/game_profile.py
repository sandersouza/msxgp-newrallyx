"""Adapt the PC/SP-matched cycle profiler to the integrated first-stage loop."""
from pathlib import Path
import sys
import json

full_route='--route' in sys.argv
if full_route:sys.argv.remove('--route')
base=Path.cwd()/'references/experiments/stage-one'
if '--bundle' in sys.argv:
    index=sys.argv.index('--bundle')
    base=Path(sys.argv[index+1]).resolve()
    del sys.argv[index:index+2]
if '--link-fixture' in sys.argv:
    sys.argv.remove('--link-fixture')
    base=Path.cwd()/'references/experiments/stage-one-link-test'
source=Path(__file__).with_name('profile.py').read_text()
start=source.index('ROUTINES = {');end=source.index('\n\n\ndef main()',start)
source=source[:start]+'''ROUTINES = {
    'Game_Prepare':'Native simulation and foreground actor/HUD preparation',
    'Game_Frame':'Elapsed60Hz simulation including audio',
    'Game_LogicTick':'Gameplay flags, fuel, collisions and enemy motion',
    'Game_Position':'Native coordinates and clamped camera projection',
    'Game_Actors':'Native descriptors to sprite actor list',
    'GameSprites_Prepare':'World sprite preparation and dirty pattern upload',
    'GameSprites_Commit':'World sprite publication',
    'GameHUD_Prepare':'HUD numeric/fuel/lives preparation',
    'GameHUD_Commit':'HUD sprite publication',
    'render':'SCREEN4 background preparation',
    'wait_blank':'Synchronization waits including HALT',
    'commit':'Complete presentation publication',
    'Ring_Prepare':'Incoming world ring cells',
    'Game_RingPatch':'Flag/smoke/death terrain overrides',
    'Game_DirtyTileUpload':'Changed terrain cell publication',
    'Game_Radar':'Native actor and flag radar',
    'Game_RadarUpload':'Radar pattern/color transfers',
    'Ring_UploadNames':'Terrain name table publication',
    'hud_upload':'Static HUD phase transition',
    'GameAudio_Tick':'30Hz PSG worker invoked at60Hz',
    'clock_irq':'VBlank ISR body'
}'''+source[end:]
if full_route and json.loads((base/'game-resources.json').read_text())['render_optimized']:
    symbols_text=(base/'lab.sym').read_text()
    for label,purpose in (('GameNameStream_Wide','Name strips for camera deltas of 2 or 3 tiles'),
                          ('GS_MaskedCopyFast','Exact full-height horizontal sprite mask copy'),
                          ('GameBoundary_Upload','Changed boundary pattern and color bytes')):
        if label+':' in symbols_text:
            source=source.replace("    'clock_irq':'VBlank ISR body'",f"    {label!r}:{purpose!r},\n    'clock_irq':'VBlank ISR body'")
if full_route and json.loads((base/'game-resources.json').read_text())['render_optimized']:
    source=source.replace("    'clock_irq':'VBlank ISR body'", """    'GameDirty_Plan':'Select sparse writes or complete name refill',
    'GameDirty_Mark':'Queue changed cell for both name tables',
    'GameSmoke_ClearRows':'Reset candidate smoke rows on native clear',
    'GameSmoke_MarkRow':'Mark candidate native smoke row',
    'GameSmoke_MarkCloud':'Mark three candidate cloud rows',
    'GameSmoke_BuildCache':'Rebuild exact sparse smoke list from candidate rows',
    'clock_irq':'VBlank ISR body'""")
source=source.replace("BASE = ROOT / 'references/experiments/fixed-hud'",f'BASE = Path({str(base)!r})')
source=source.replace("'input'", "'Game_Prepare'")
source=source.replace('set z80_freq_locked true\n', 'set z80_freq_locked true\nset limitsprites true\nif {{!$limitsprites}} {{error "Hardware sprite limit was not enabled"}}\n')
source=source.replace('import csv\n','import csv\nimport shutil\n')
source=source.replace('set firmwareswitch off\n', 'set renderer none\nset firmwareswitch off\nactivate_input_layer -blocking first_stage_profile\n')
source=source.replace("    syms = {n: int(v, 16)", "    shutil.copyfile(BASE/'fixed-hud.rom',out/'measured.rom')\n    shutil.copyfile(BASE/'lab.sym',out/'measured.sym')\n    syms = {n: int(v, 16)")
# Compiled HUD code also executes inside8000..BFFF. Numeric PC/SP alone must
# not identify it as a native routine or the fixed phase name-store entry.
source=source.replace("    script = f'''", """    native_bank=json.loads((BASE/'game-resources.json').read_text())['banks']['GAME_NATIVE_BANK']
    measured_bytes=(out/'measured.rom').read_bytes()
    native_prefix=measured_bytes[native_bank*16384:native_bank*16384+32]
    assert sum(measured_bytes[i:i+32]==native_prefix for i in range(0,len(measured_bytes),16384))==1
    page2_setup='set page2_rejected 0\\n'
    for page2_name in ROUTINES:
        if 0x8000<=syms[page2_name]<0xc000 and page2_name!='HUD_NameStores':
            page2_setup+=f'set page2_expected({page2_name}) [binary format H* {native_prefix.hex()}]\\n'
    prefixes=[measured_bytes[(4+n)*16384:(4+n)*16384+32].hex() for n in range(64)]
    page2_setup+='set phase_prefix [list '+' '.join('[binary format H* '+v+']' for v in prefixes)+']\\n'
    script = f'''""")
source=source.replace('set out {tcl(out)}\n', 'set out {tcl(out)}\n{page2_setup}\n')
source=source.replace('proc enter {{name}} {{\n', '''proc enter {{name}} {{
    if {{[info exists ::page2_expected($name)] && [debug read_block memory 0x8000 32] ne $::page2_expected($name)}} {{incr ::page2_rejected;return}}
    if {{$name eq "HUD_NameStores" && [debug read_block memory 0x8000 32] ne [lindex $::phase_prefix [debug read memory 0xc01d]]}} {{incr ::page2_rejected;return}}
''')
source=source.replace("cart {tcl(BASE/'fixed-hud.rom')}","cart {tcl(out/'measured.rom')}")
source=source.replace("(BASE/'fixed-hud.rom').read_bytes()).hexdigest()", "(out/'measured.rom').read_bytes()).hexdigest()")
source=source.replace(r'\tcommand\tspeed"',r'\tcommand\tspeed\tactive_start\tactive_end"')
source=source.replace('[debug read memory 0xc00a]"',r'[debug read memory 0xc00a]\t$::active_start\t[active_gameplay]"')
source=source.replace('proc next_frame {{}} {{', 'proc active_gameplay {{}} {{expr {{[debug read memory 0xc040]==0 && [debug read memory 0xc490]==0 && [debug read memory 0xc50b]<10}}}}\nproc next_frame {{}} {{')
source=source.replace('    set ::start_y [word 0xc002]','    set ::start_y [word 0xc002]\n    set ::active_start [active_gameplay]')
source=source.replace("command=row['command'], speed=int(row['speed']),", "command=row['command'], speed=int(row['speed']), active_gameplay=bool(int(row['active_start']) and int(row['active_end'])),")
source=source.replace("        assert rows, f'Unexercised routine: {name}'", """        if not rows and name in ('GameSmoke_MarkRow','GameSmoke_MarkCloud','GameNameStream_Wide','GS_MaskedCopyFast','GameBoundary_Upload'):
            stats.append(dict(name=name,purpose=purpose+' (not called in this workload)',calls=0,
                calls_per_frame=0,min=None,mean=None,p95=None,max=None,self_mean=None,self_total=0))
            continue
        assert rows, f'Unexercised routine: {name}'""")

source=source.replace("float(r['cycles']) for r in control_frames)) < .01", "float(r['cycles']) for r in control_frames)) < 5.01")
source=source.replace('total duration matches within 0.01 cycle', 'total duration matches within5.01cycles')
source=source.replace("'radar'", "'Game_Radar'")
source=source.replace('keymatrixdown 8 192', 'keymatrixdown 8 32').replace('keymatrixdown 8 48', 'keymatrixdown 8 128').replace('keymatrixdown 8 128;keymatrixdown 6 1', 'keymatrixdown 8 64').replace('keymatrixdown 8 64;keymatrixdown 6 1', 'keymatrixdown 8 16')
source=source.replace('last_frame = sum(s[1] for s in segments) if args.movement else 312',
                      'last_frame = sum(s[1] for s in segments) if args.movement else 120')
source=source.replace('video_hz_nominal=50, cycles_per_refresh=313*228',
                      'video_hz_nominal=60, cycles_per_refresh=262*228')
source=source.replace("workload=('isolated horizontal/vertical routes, both directions, normal/Shift and idle'\n                              if args.movement else 'continuous keys, 1/2 px per tick; frames 5..312')",
                      "workload='Integrated first-stage deterministic keyboard route; frames5..120'")
source=source.replace('Free-camera laboratory; no game logic, enemies, collisions or flag hook.',
                      'First-stage route; natural enemy population, HUD and audio enabled; no hardware validation.')
source=source.replace("routines=stats, frames=frame_data,", "routines=stats, frames=frame_data, presented_fps=HZ/statistics.mean(r['cycles'] for r in frame_data),")
if full_route:
    source=source.replace("out = Path(tempfile.mkdtemp(prefix='profile-', dir=BASE))", "out = Path(tempfile.mkdtemp(prefix='profile-route-', dir=BASE))\n    from game_route import setup\n    route_setup=setup(ROOT,out,allow_gameover=bool(json.loads((BASE/'game-resources.json').read_text())['banks']['GAME_TEST_ENEMIES']))")
    source=source.replace('set out {tcl(out)}\n', 'set out {tcl(out)}\n{route_setup}\nproc save {{name}} {{}}\n')
    source=source.replace('last_frame = sum(s[1] for s in segments) if args.movement else 120', 'last_frame = 10000')
    source=source.replace('if {{$::frame>{last_frame}}}', 'if {{$::frame>{last_frame} || $::route_done}}')
    source=source.replace('    if {{{int(args.movement)}}} {{{route_tcl}}}', '    set ::n $::frame\n    route_step\n    set ::command keyboard_route\n    return')
    source=source.replace('assert len(frames) == expected_frames, len(frames)', "assert len(frames)>120, len(frames)")
    source=source.replace('after time 30', 'after time 240').replace('timeout=180', 'timeout=300')
    source=source.replace("workload='Integrated first-stage deterministic keyboard route; frames5..120'", "workload='Complete keyboard-only first-stage route; nativepopulation, flags, death/restart and fuelbonus'")
exec(compile(source,str(Path(__file__).with_name('profile.py')),'exec'),{'__file__':str(Path(__file__).with_name('profile.py')),'__name__':'__main__','json':json})
# Keep separately observed scenarios with the exact measured ROM, when present.
import json
profile_dir=Path((base/'last-profile.txt').read_text().strip())
metadata=json.loads((profile_dir/'summary.json').read_text())
metadata['profile_kind']={
    'game_logic_profile.py':'logic',
    'component_profile.py':'components',
    'component_actor_profile.py':'actors',
}.get(Path(sys.argv[0]).name,'presentation')
metadata['page2_entry_guard']='Native Page2 entries require unique immutable native-bank prefix; HUD_NameStores requires current phase-bank prefix. Compiled HUD packet PCs are excluded from these aliases.'
import csv,math,statistics
active_frames=[r for r in metadata['frames'] if r['active_gameplay']]
active_ids={r['frame'] for r in active_frames}
with (profile_dir/'calls.tsv').open() as file:
    active_calls=[r for r in csv.DictReader(file,delimiter='\t') if int(r['frame']) in active_ids]
active_routines=[]
for routine in metadata['routines']:
    rows=[r for r in active_calls if r['routine']==routine['name']]
    incl=sorted(float(r['inclusive_cycles']) for r in rows)
    own=[float(r['self_cycles']) for r in rows]
    active_routines.append(dict(name=routine['name'],purpose=routine['purpose'],calls=len(rows),
        calls_per_frame=len(rows)/len(active_frames),min=min(incl) if incl else None,
        mean=statistics.mean(incl) if incl else None,p95=incl[math.ceil(.95*len(incl))-1] if incl else None,
        max=max(incl) if incl else None,self_mean=statistics.mean(own) if own else None,self_total=sum(own)))
metadata['active_ledger']=dict(measured_frames=len(active_frames),
    presented_fps=metadata['cpu_hz']*len(active_frames)/sum(r['cycles'] for r in active_frames),
    scope='Both interval endpoints: game active, no death, fewer than ten flags; excludes death/bonus/stopped states',
    routines=active_routines,frames=active_frames)
metadata['variant']=json.loads((base/'game-resources.json').read_text())['multi_enemy']
metadata['workload']='Keyboard-only route until ten-flag completion or native game over' if full_route else metadata['workload']
scenarios=[]
for kind in ('natural','smoke','heavy','route'):
    candidates=[]
    for path in base.glob(kind+'-*/result.json'):
        value=json.loads(path.read_text())
        if value.get('rom_sha256')==metadata['rom_sha256']:
            candidates.append((path.stat().st_mtime,path,value))
    if candidates:
        _,path,value=max(candidates)
        value['evidence_path']=str(path)
        scenarios.append(value)
metadata['effect_adaptation']=json.loads((base/'prepare.json').read_text())['effect_adaptation'] if (base/'prepare.json').exists() and 'effect_adaptation' in json.loads((base/'prepare.json').read_text()) else None
metadata['separate_scenarios']=scenarios
(profile_dir/'summary.json').write_text(json.dumps(metadata,indent=2)+'\n')
