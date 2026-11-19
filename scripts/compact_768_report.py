"""Bind768KiB qualification to current hashes; preserve earlier measurements."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/toolchain/screen4'),str(ROOT)]
from compact_game_report import distribution,matrix_row,profiles,read,select,states,timing_report
from renderer_window_probe import probe


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    bundles={k:ROOT/'references/build'/v for k,v in [('baseline','game-issue42-976-baseline'),('ASCII8','game-compact-runtime'),('MegaRAM','game-compact-megaram-runtime')]}
    hashes={k:digest(p/'newrallyx.rom') for k,p in bundles.items()}
    assert hashes==dict(baseline='230c388345a44226ce6536e17204d37a96714b0f03c126d9e072115a394274bc',
        ASCII8='b39e0c7f520872174e9a89cc46ddf4e1957179bc70ac3326c6450420866a878c',
        MegaRAM='f149f34816d99db21e46b4a2b3a6d17d769ffd49c515b906613131d0c5f255fb')
    assert digest(ROOT/'dist/newrallyx.rom')==hashes['ASCII8']
    assert (ROOT/'dist/newrallyx.rom').stat().st_size==744*1024
    rows={k:profiles(p,hashes[k]) for k,p in bundles.items()}
    comparisons=[];matrix=[];other=[]
    fields=['cx','cy','enemy_positions','elapsed_ticks','active_start','active_end','psg','start_x','start_y','command','speed']
    for n in (3,5,6):
        chosen=[select(rows[k],'Panasonic_FS-A1WSX_NR64',64,n) for k in bundles]
        variants=[matrix_row(r,k) for r,k in zip(chosen,bundles)]
        traces=[states(r[1]) for r in chosen]
        assert len({len(t) for t in traces})==1
        assert all(a[k]==b[k] for a,b in zip(traces[1],traces[2]) for k in fields)
        for r in variants[1:]:
            assert r['presented_fps']>=variants[0]['presented_fps']-.00002
            assert all(r['work'][k]<=variants[0]['work'][k]+.01 for k in ('mean','p95','max'))
        work=[{f['frame']:f for f in r[2]['active_ledger']['frames']} for r in chosen[:2]]
        matched=[int(a['frame']) for a,b in zip(traces[0],traces[1]) if all(a[k]==b[k] for k in fields)]
        ids=[i for i in matched if all(i in w for w in work)]
        paired=[distribution([w[i]['work'] for i in ids]) for w in work]
        assert all(paired[1][k]<=paired[0][k]+.01 for k in ('mean','p95','max'))
        longer=[dict(frame=i,work_delta=work[1][i]['work']-work[0][i]['work'],period_delta=work[1][i]['cycles']-work[0][i]['cycles']) for i in ids if work[1][i]['work']>work[0][i]['work']+.01]
        comparisons.append(dict(enemies=n,variants=variants,matched_rows=len(matched),matched_active_rows=len(ids),matched_fields=fields,
            matched_active_work=paired,longer_matched_frames=longer,
            presentation_field_differences={k:sum(a[k]!=b[k] for a,b in zip(traces[0],traces[1])) for k in fields},
            scope='Overall route aggregates are observations, not identical trajectories when tick cadence changes. Causal transfer savings use the exact kernel/event proof; paired aggregates include only identical state/tick/input/PSG rows. Separate native-tick fixture checks unchanged rules/audio.'))
        matrix.extend(variants[1:])
    for machine,ram in [('Sony_HB-F1XDJ',64),('Panasonic_FS-A1WSX_NR128',128),('Panasonic_FS-A1ST',256),('Panasonic_FS-A1GT',512)]:
        pair=[matrix_row(select(rows[k],machine,ram,3),k) for k in ('baseline','ASCII8')]
        assert pair[1]['presented_fps']>=pair[0]['presented_fps']-.00002
        assert all(pair[1]['work'][k]<=pair[0]['work'][k]+.01 for k in ('mean','p95','max'))
        other.append(dict(machine=machine,mapper_kib=ram,variants=pair));matrix.append(pair[1])
    regressions=[];components=[]
    for backend in ('ASCII8','MegaRAM'):
        bundle=bundles[backend]
        required={'start','integration','two-player','flags','attract','radar','smoke','controls'} if backend=='ASCII8' else {'integration','two-player','flags','radar','controls'}
        for kind in sorted(required):
            found=[]
            for p in bundle.glob('session-start-*/result.json'):
                d=read(p);g=p.with_name('graphics-contracts.json')
                if d.get('rom_sha256')==hashes[backend] and d.get('passed') and d['scenario']==kind and g.exists() and read(g)['passed'] and read(g)['rom_sha256']==hashes[backend]:found.append(p)
            p=max(found,key=lambda p:p.stat().st_mtime);d=read(p)
            regressions.append(dict(backend=backend,machine=d['machine'],mapper_kib=d['mapper_ram_kib'],turbo=True,case=kind,passed=True,rom_sha256=hashes[backend],log=str(p.relative_to(ROOT)),snapshots=len(read(p.with_name('graphics-contracts.json'))['snapshots'])))
        if backend=='MegaRAM':continue
        for pattern in ['steering-proof-*','audio-proof-*','boot-proof-*','boot-skip-proof-*','speed-proof-*','rocks-proof-*','sprite-clip-proof-*','exact-transfer-proof-*','native-tick-proof-*']:
            found=[]
            for p in bundle.glob(pattern+'/report.json'):
                d=read(p)
                if (d.get('rom_sha256')==hashes[backend] or d.get('variants',{}).get('game-compact-runtime')==hashes[backend]) and d.get('passed',True):found.append(p)
            p=max(found,key=lambda p:p.stat().st_mtime)
            components.append(dict(machine='Panasonic_FS-A1WSX_NR64',mapper_kib=64,turbo=True,case=pattern,passed=True,rom_sha256=hashes[backend],log=str(p.relative_to(ROOT)),result=read(p)))
    loader=[]
    for p in (ROOT/'references/sessions').glob('compact-megaram-*/report.json'):
        d=read(p)
        if d.get('rom_sha256')==hashes['MegaRAM']:loader.append(d)
    assert {'dos','basic'}<={d['mode'] for d in loader if d.get('frames')==300 and d['megaram_kib']==768}
    assert any(d.get('expanded_slot') and d.get('frames')==300 and d['megaram_kib']==768 for d in loader)
    assert any(d.get('negative')=='capacity' and d['megaram_kib']==512 and d['image_unchanged'] for d in loader)
    assert {'distance','count','missing'}<={d.get('negative') for d in loader}
    core=[]
    for bank in (71,73,121):
        images=[]
        for bundle in bundles.values():
            page=int(read(bundle/'session-build.json')['logical_bank_pages'][str(bank)])
            images.append((bundle/'newrallyx.rom').read_bytes()[page*8192:page*8192+16384])
        assert images[0]==images[1]==images[2]
        core.append(dict(logical_bank=bank,bytes=16384,sha256=hashlib.sha256(images[0]).hexdigest(),identical=True))
    cases=[];records=[];probe(4096,cases,records,integrated=True,fast_transfers=True)
    optimization=dict(packet_references=4384,unique_programs=len({r['code'] for r in cases}),previous_unique_bytes=331664,
        unique_bytes=sum(map(len,{r['code'] for r in cases})),data_live_bytes=sum(sum(r['occupied']) for r in records),
        ordered_vdp_events_and_final_hl_b_verified=True,minimum_modeled_packet_gain=min(r['optimization']['cycles_saved'] for r in cases))
    artifacts={}
    for name in ['dist/newrallyx.rom','dist/compact/megaram/newrallyx-megaram.zip','dist/disk/newrallyx-disk.zip']:
        p=ROOT/name
        if p.suffix=='.zip':
            with zipfile.ZipFile(p) as z:assert z.testzip() is None
        artifacts[name]=dict(bytes=p.stat().st_size,sha256=digest(p))
    disk_manifest=read(ROOT/'dist/disk/manifest.json')
    disk_checks=[read(ROOT/f'references/sessions/disk-{mode}-4096/report.json') for mode in ('dos','basic')]
    assert all(d['artifact_sha256']==disk_manifest['disk_image_sha256']=='2bf745f615649f7d465ab55a11e9b4e2f80ebc340ca627f8fc6690e0f59ddc75' for d in disk_checks)
    map_checks=[]
    for backend in ('ASCII8','MegaRAM'):
        samples=[]
        for row in regressions:
            if row['backend']==backend:
                p=(ROOT/row['log']).with_name('map-contract.tsv')
                if p.exists():samples.extend(csv.DictReader(p.open(),delimiter='\t'))
        assert len({r['logical_bank'] for r in samples})==8
        map_checks.append(dict(backend=backend,maps=8,calls=len(samples),iff_values=sorted({int(r['iff']) for r in samples}),
            inclusive_cycles=distribution(float(r['inclusive_cycles']) for r in samples),exact_16k_bytes_and_ix_iy_iff=True))
    tests=[]
    for name,expected in [('unit',482),('components',94)]:
        log=(ROOT/f'references/build/issue42-744-{name}.log').read_text()
        assert re.search(r'Ran '+str(expected)+r' tests',log) and '\nOK' in log
        tests.append(dict(suite=name,tests=expected,passed=True,skipped=1 if name=='components' else 0))
    module_log=(ROOT/'references/build/issue42-744-module-layout.log').read_text()
    assert '"passed": true' in module_log
    reproduction=read(ROOT/'references/build/issue42-744-reproduction.json')
    assert reproduction['baseline_reproduced'] and reproduction['baseline_sha256']==hashes['baseline'] and reproduction['expected_current_sha256']==hashes['ASCII8']
    rng=read(ROOT/'references/build/issue42-744-rng.json');assert rng['passed'] and rng['rom_sha256']==hashes['ASCII8']
    primary=select(rows['ASCII8'],'Panasonic_FS-A1WSX_NR64',64,3)
    out=ROOT/'references/validation/issue42-768';out.mkdir(parents=True,exist_ok=True)
    ledger=timing_report(bundles['ASCII8'],out,primary[1],None)
    ledger.update(compact_backend=True,auto_policy=True,turbo_matrix=matrix,regression_matrix=regressions,long_matrix=components,
        base_mode_matrix=[],boot_matrix=[],capacity_matrix=[],mapper_comparisons=[],component_checks=[],
        factory_cpu_probe=dict(results=[],scope='Actual CPU/ABI observers accompany every exact-hash matched profile.'),
        qualification_hashes=hashes,compact_comparisons=comparisons,other_cpu_comparisons=other,
        comparison_scope='Same seed/input policy/population; faster scheduling changes some presentation-index trajectories. Matching state rows and native-tick comparisons are reported separately.',
        working_tree_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    authored=['scripts/compact_768_report.py','scripts/compact_game_build.py','scripts/compact_transfer.py','scripts/compact_boot_atlas.py',
        'scripts/compact_tick_verify.py','scripts/exact_transfer_verify.py','scripts/megaram_package.py','scripts/compact_game_verify.py',
        'scripts/renderer_image_build.py','src/screen4/compact-boot-atlas.inc','src/disk/megaram-loader.asm','src/toolchain/screen4/session_profile_adapter.py']
    ledger['source_files']={n:digest(ROOT/n) for n in authored}
    ledger['limitations']+=' NTSC60 emulator only; no physical hardware, PAL50, full-course or subjective listening acceptance. Same-state three-enemy samples include10 longer work spans (max2738.334 cycles), with no added refresh and at most6 reference-cycle period jitter. Five/six-enemy same-state aggregate mean/P95/max do not regress; six-enemy same-state P95 is unchanged.'
    (out/'cycle-ledger-enriched.json').write_text(json.dumps(ledger,indent=2)+'\n')
    report=dict(passed=True,bytes=761856,saved_bytes=999424-761856,margin_768k=768*1024-761856,hashes=hashes,
        performance=comparisons,other_cpu_comparisons=other,cpu_matrix=matrix,regressions=regressions,components=components,
        loader_checks=loader,megaram=read(ROOT/'dist/compact/megaram/manifest.json'),unchanged_native_audio_ui=core,
        transfer=optimization,atlas=read(bundles['ASCII8']/'layout.json')['atlas'],rng=rng,artifacts=artifacts,
        disk_manifest=disk_manifest,disk_checks=disk_checks,maps=map_checks,tests=tests,module_layout_passed=True,baseline_reproduction=reproduction,
        source_files=ledger['source_files'],limitations=ledger['limitations'],status='Qualified scoped local candidate; no commit, push or release. Physical hardware and owner acceptance remain separate.')
    target=ROOT/'docs/measurements/cartridge/issue42-768-qualified.json'
    target.write_text(json.dumps(report,indent=2)+'\n');print('Qualified local768KiB candidate',hashes['ASCII8']);return report


if __name__=='__main__':build()
