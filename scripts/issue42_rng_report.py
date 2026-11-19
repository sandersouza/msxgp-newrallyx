"""Summarize exact-hash RNG qualification without relabeling Issue41 evidence.

Requires accepted ASCII8 baseline and current ASCII8/MegaRAM profiles using
NRX_PROFILE_SEED=0x1234, plus current lifecycle/component/loader checks.
Raw contributor-derived snapshots stay ignored; durable data contains hashes
and measurements. Run before cleaning disposable emulator traces.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/toolchain/screen4'),str(ROOT)]
from compact_game_report import distribution,matrix_row,select,states
from session_report import report as timing_report


def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def profiles(bundle,sha):
    result=[]
    for p in bundle.glob('profile-*/summary.json'):
        d=read(p)
        if d['rom_sha256']!=sha or d.get('controlled_rng_seed')!=0x1234 or 'active_ledger' not in d:continue
        # Early seed-observer runs precede the adapter's metadata-prefix fix.
        # Recover only the workload already recorded and enforced by its Tcl
        # target-round/enemy guard; never infer it from the directory name.
        m=re.search(r'native round(\d+).*?, (\d+) native enemies;',d['workload'])
        assert m
        for k,v in [('profile_native_round',int(m[1])),('profile_enemy_count',int(m[2]))]:
            assert d.get(k,v)==v
            d[k]=v
        result.append((p.stat().st_mtime,p.parent,d))
    return result


def main(map_optimization=False):
    baseline='game-issue42-map-baseline' if map_optimization else 'game-issue42-baseline'
    baseline_sha='d1a1f9cf3fa98940acf2d234b127f224da79f5aaed37fc19e999718134e7c23f' if map_optimization else 'b5684933f5dcae72d5552b51cbca64a28458fa980795334d6491ce3f55c66e4a'
    bundles={k:ROOT/'references/build'/p for k,p in [('baseline',baseline),
        ('ASCII8','game-compact-runtime'),('MegaRAM','game-compact-megaram-runtime')]}
    hashes={k:digest(p/'newrallyx.rom') for k,p in bundles.items()}
    assert hashes['baseline']==baseline_sha
    rows={k:profiles(p,hashes[k]) for k,p in bundles.items()}
    comparisons=[];matrix=[]
    fields=['cx','cy','enemy_positions','elapsed_ticks','active_start','active_end','psg']
    for n in (3,5,6):
        chosen=[select(rows[k],'Panasonic_FS-A1WSX_NR64',64,n) for k in bundles]
        measured=[matrix_row(r,k) for r,k in zip(chosen,bundles)]
        data=[states(r[1]) for r in chosen]
        assert len({len(x) for x in data})==1
        for variant,m in zip(data[1:],measured[1:]):
            assert all(a[k]==b[k] for a,b in zip(data[0],variant) for k in fields)
            assert abs(m['presented_fps']-measured[0]['presented_fps'])<.00002
            assert all(m['work'][k]<=measured[0]['work'][k]+.01 for k in ('mean','p95','max'))
        comparisons.append(dict(enemies=n,controlled_rng_seed=0x1234,variants=measured,
            matched_rows=len(data[0]),matched_fields=fields,passed=True))
        matrix.extend(measured[1:])
    for machine,ram in [('Sony_HB-F1XDJ',64),('Panasonic_FS-A1WSX_NR128',128),
                        ('Panasonic_FS-A1ST',256),('Panasonic_FS-A1GT',512)]:
        matrix.append(matrix_row(select(rows['ASCII8'],machine,ram,3),'ASCII8'))
    regressions=[];components=[]
    for backend in ('ASCII8','MegaRAM'):
        bundle=bundles[backend]
        for p in bundle.glob('session-start-*/result.json'):
            d=read(p);g=p.with_name('graphics-contracts.json')
            if d['rom_sha256']!=hashes[backend] or not d['passed'] or not g.exists() or not d.get('rng_lifecycle'):continue
            graphic=read(g)
            assert graphic['passed'] and graphic['rom_sha256']==hashes[backend]
            assert d['rng_lifecycle']['passed']
            regressions.append(dict(backend=backend,machine=d['machine'],mapper_kib=d['mapper_ram_kib'],
                turbo=True,case=d['scenario'],passed=True,rom_sha256=d['rom_sha256'],
                snapshots=len(graphic['snapshots']),rng_lifecycle=d['rng_lifecycle'],log=str(p.relative_to(ROOT))))
        for pattern in ['steering-proof-*','audio-proof-*','boot-proof-*','boot-skip-proof-*',
                        'speed-proof-*','rocks-proof-*','sprite-clip-proof-*']:
            found=[(p.stat().st_mtime,p,read(p)) for p in bundle.glob(pattern+'/report.json')
                   if read(p).get('rom_sha256')==hashes[backend]]
            if found:
                _,p,d=max(found)
                assert d.get('passed',True)
                components.append(dict(machine='Panasonic_FS-A1WSX_NR64',mapper_kib=64,turbo=True,
                    case=pattern,passed=True,rom_sha256=hashes[backend],log=str(p.relative_to(ROOT)),result=d))
    for backend,required in [('ASCII8',{'start','integration','two-player','flags','attract','radar','smoke','controls'}),
                             ('MegaRAM',{'integration','two-player','flags','radar','controls'})]:
        assert required<={r['case'] for r in regressions if r['backend']==backend}
    for name in ('steering-proof-*','audio-proof-*','speed-proof-*','rocks-proof-*'):
        assert any(c['case']==name and c['rom_sha256']==hashes['ASCII8'] for c in components)
    loaders=[]
    for p in (ROOT/'references/sessions').glob('compact-megaram-*/report.json'):
        d=read(p)
        if d.get('rom_sha256')==hashes['MegaRAM']:
            assert d.get('passed',d.get('graphics',{}).get('passed',False))
            loaders.append(dict(source=str(p.relative_to(ROOT)),**d))
    assert {'dos','basic'}<={r['mode'] for r in loaders if not r.get('negative')}
    assert any(r.get('expanded_slot') for r in loaders) and any(r.get('negative')=='capacity' for r in loaders)
    disks=[read(ROOT/f'references/sessions/disk-{mode}-4096/report.json') for mode in ('dos','basic')]
    assert disks[0]['artifact_sha256']==disks[1]['artifact_sha256']==digest(ROOT/'references/build/game-disk/disk-image.bin')
    cold=[]
    for backend in ('baseline','ASCII8'):
        found=[(p.stat().st_mtime,p) for p in bundles[backend].glob('session-start-*/result.json')
               if read(p)['rom_sha256']==hashes[backend] and read(p).get('controlled_rng_seed')==0x1234
               and read(p)['scenario']=='integration' and read(p)['passed']]
        _,p=max(found)
        calls=list(csv.DictReader(p.with_name('cold-hooks.tsv').open(),delimiter='\t'))
        values=[float(r['inclusive_cycles']) for r in calls if r['routine']=='GameSession_ColdLoad']
        assert len(values)==13
        cold.append(dict(backend=backend,rom_sha256=hashes[backend],calls=len(values),
            inclusive=distribution(values),per_transition=values,log=str(p.relative_to(ROOT)),
            phase_rows=[r for r in calls if r['routine']=='GameSession_ColdLoad']))
    if map_optimization:
        assert all(cold[1]['inclusive'][k]<=cold[0]['inclusive'][k]+.01 for k in ('mean','p95','max'))
        phase=[]
        # Existing base-Z80 VDP poll: IN(11),AND(7),taken JR(12), plus three
        # MSX M1 waits. Faster construction may finish in another position of
        # this same33-cycle poll; require equal/earlier refresh, improved self
        # work and a bounded beam offset, retaining every raw longer case.
        for a,b in zip(cold[0]['phase_rows'],cold[1]['phase_rows']):
            refresh=lambda r:int(r['end_vframe'])-int(r['start_vframe'])
            delta=float(b['inclusive_cycles'])-float(a['inclusive_cycles'])
            own=float(b['self_cycles'])-float(a['self_cycles'])
            begin=(float(b['start_vtick'])-float(a['start_vtick']))/6
            end=(float(b['end_vtick'])-float(a['end_vtick']))/6
            assert refresh(b)<=refresh(a) and own<0 and abs(begin)<=33 and abs(end)<=33
            phase.append(dict(raw_inclusive_delta=delta,self_delta=own,baseline_refreshes=refresh(a),
                candidate_refreshes=refresh(b),start_beam_delta=begin,end_beam_delta=end))
    else:
        assert all(b<=a+.01 for a,b in zip(cold[0]['per_transition'],cold[1]['per_transition']))
    cold_comparison=dict(passed=True,controlled_rng_seed=0x1234,variants=cold,
        scope='13 matched cold board loads, native rounds2..14, all four layouts. Inclusive guest time includes children, IRQ, waits and display/audio setup; do not add child costs. F5 transitions are controlled, not naturally earned completion.')
    if map_optimization:
        saved=sum(r['candidate_refreshes']<r['baseline_refreshes'] for r in phase)
        longer=sum(r['raw_inclusive_delta']>0 for r in phase)
        cold_comparison.update(phase_comparison=phase,existing_vdp_poll_quantum=33,raw_longer_cases=longer,
            scope_note=f'Aggregate mean/P95/max improve; {saved} transitions save a refresh, {len(phase)-saved} use the same refresh count. {longer} raw durations are slightly longer within the unchanged33-cycle VDP poll; no additional refresh or active-frame work. Self work improves in all13 cases.')
    out=ROOT/('references/validation/issue42-map' if map_optimization else 'references/validation/issue42');primary=select(rows['ASCII8'],'Panasonic_FS-A1WSX_NR64',64,3)
    ledger=timing_report(bundles['ASCII8'],out,primary[1],None)
    ledger['workload']+='; controlled original initializer RNG=1234 hex before each board (RAM fixture)'
    ledger.update(rng_correction=True,map_optimization=map_optimization,controlled_rng_seed=0x1234,compact_backend=True,auto_policy=True,
        turbo_matrix=matrix,regression_matrix=regressions,long_matrix=components,base_mode_matrix=[],
        boot_matrix=[],capacity_matrix=[],mapper_comparisons=[],component_checks=[],
        factory_cpu_probe=dict(results=[],scope='Actual CPU/controller and ABI guards accompany current profiles.'),
        working_tree_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        qualification_hashes=hashes,compact_comparisons=comparisons,cold_rng_comparison=cold_comparison)
    authored=['scripts/issue42_rng_report.py','scripts/issue42_rng_verify.py','scripts/msx_flag_seed_probe.py',
        'src/toolchain/screen4/game_build.py','src/toolchain/screen4/session_build.py',
        'src/toolchain/screen4/session_profile_adapter.py','src/toolchain/screen4/session_report.py',
        'src/toolchain/screen4/session_verify.py','src/screen4/modules/session/boot.inc',
        'src/screen4/modules/session/world.inc','src/screen4/modules/session/lifecycle.inc']
    if map_optimization:
        authored+=['scripts/renderer_image_build.py','scripts/compact_game_build.py','scripts/compact_map_contract.py','tests/test_compact_backend.py']
    ledger['source_files']={n:digest(ROOT/n) for n in authored}
    ledger['limitations']+=' Issue42 matched fixture fixes the initializer RNG to separate performance from intentional first-board variation. Natural variation is checked separately. No physical hardware, PAL50 or subjective audio/perception acceptance.'
    (out/'cycle-ledger-enriched.json').write_text(json.dumps(ledger,indent=2)+'\n')
    artifacts={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in
        [ROOT/'dist/newrallyx.rom',ROOT/'dist/compact/megaram/newrallyx-megaram.zip',ROOT/'dist/disk/newrallyx-disk.zip']}
    expected_size=999424 if map_optimization else 1007616
    assert artifacts['dist/newrallyx.rom']['bytes']==expected_size<1048576
    tests=(ROOT/('references/build/issue42-map-tests.log' if map_optimization else 'references/build/issue42-final-tests.log')).read_text()
    counts=list(map(int,re.findall(r'Ran (\d+) tests',tests)))
    assert counts==([478,94] if map_optimization else [476,94]) and 'FAILED' not in tests and 'OK (skipped=1)' in tests
    result=dict(passed=True,hashes=hashes,artifacts=artifacts,natural_rng=read(ROOT/('docs/measurements/cartridge/issue42-map-rng.json' if map_optimization else 'docs/measurements/cartridge/issue42-rng-correction.json')),
        matched_performance=comparisons,cold_comparison=cold_comparison,cpu_matrix=matrix,regressions=regressions,components=components,
        megaram_loaders=loaders,system_mapper_disk=disks,source_files=ledger['source_files'],
        unit_tests=dict(passed=True,general=counts[0],components=counts[1],component_skips=1),
        publication='Local candidate only; release approval required',limitations=ledger['limitations'])
    if map_optimization:
        layout=read(bundles['ASCII8']/'layout.json')
        map_checks=[]
        for backend in ('baseline','ASCII8','MegaRAM'):
            found=[]
            for p in bundles[backend].glob('session-start-*/map-contract.tsv'):
                d=read(p.with_name('result.json'))
                if d['rom_sha256']==hashes[backend]:found.extend(csv.DictReader(p.open(),delimiter='\t'))
            assert len({r['logical_bank'] for r in found})==8
            map_checks.append(dict(backend=backend,rom_sha256=hashes[backend],calls=len(found),
                inclusive=distribution(float(r['inclusive_cycles']) for r in found),
                iff_values=sorted({int(r['iff']) for r in found}),exact_16k_maps=True,ix_iy_iff_preserved=True))
        assert all(r['inclusive']['max']<map_checks[0]['inclusive']['mean'] for r in map_checks[1:])
        result['map_storage']=dict(rom_saved_bytes=1007616-expected_size,constructor_count=len(layout['map_constructors']),
            previous_constructor_bytes=1003*35,constructor_bytes=layout['map_constructor_bytes'],descriptor_bytes=layout['map_table_bytes'],
            map_checks=map_checks,added_persistent_ram_bytes=0,hot_dispatch_changed=False)
        reproduction=read(ROOT/'references/build/issue42-map-reproduction.json')
        assert reproduction['matched_frozen_baseline'] and reproduction['baseline_sha256']==baseline_sha
        result['map_storage']['baseline_reproduction']=reproduction
        packing=[];boot=[]
        for filename in ('issue42-map-reproduce-baseline.log','issue42-map-final-build.log'):
            log=(ROOT/'references/build'/filename).read_text()
            packing.append({k:int(re.search(r'"'+k+r'": (\d+)',log)[1]) for k in ('allocated_bytes','boot_encoded_bytes','boot_chains')})
        for backend in ('baseline','ASCII8'):
            p=max(bundles[backend].glob('boot-proof-*/report.json'),key=lambda p:p.stat().st_mtime)
            d=read(p);assert d['passed'] and d['rom_sha256']==hashes[backend] and d['software_publication_ticks_verified']
            boot.append({k:d[k] for k in ('rom_sha256','boot_frames','seconds','max_state_timing_error_ms','publication_phase_ms','initial_clear_ms')})
        assert all(boot[0][k]==boot[1][k] for k in ('boot_frames','max_state_timing_error_ms','publication_phase_ms','initial_clear_ms'))
        assert abs(boot[0]['seconds']-boot[1]['seconds'])*3579545<=1.01
        result['map_storage'].update(boot_repacking=packing,boot_comparison=boot)
        ledger['map_storage']=result['map_storage']
        (out/'cycle-ledger-enriched.json').write_text(json.dumps(ledger,indent=2)+'\n')
    target='issue42-map-qualified.json' if map_optimization else 'issue42-qualified-candidate.json'
    (ROOT/'docs/measurements/cartridge'/target).write_text(json.dumps(result,indent=2)+'\n')
    print('Qualified local candidate:',hashes['ASCII8'])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--maps',action='store_true')
    main(parser.parse_args().maps)
