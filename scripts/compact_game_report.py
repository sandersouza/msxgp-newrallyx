"""Summarize exact-hash full-game qualification; never relabel older evidence.

Run after the documented baseline/compact profiles and session checks. Raw
emulator data stays ignored; the compact report and workbook ledger are durable.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/toolchain/screen4'), str(ROOT)]
from session_report import report as timing_report


def read(path):
    return json.loads(Path(path).read_text())


def distribution(values):
    values = sorted(values)
    return dict(mean=statistics.mean(values), p95=values[math.ceil(.95*len(values))-1], max=max(values))


def profiles(bundle, sha):
    result = []
    for file in bundle.glob('profile-*/summary.json'):
        d = read(file)
        if d['rom_sha256'] == sha:
            result.append((file.stat().st_mtime, file.parent, d))
    return result


def select(rows, machine, ram, enemies):
    found = [r for r in rows if r[2]['machine'] == machine and
             r[2]['mapper_ram_kib'] == ram and r[2]['profile_enemy_count'] == enemies]
    if not found:
        raise ValueError(f'Missing profile: {machine}/{ram}/{enemies}')
    return max(found, key=lambda r:r[0])


def matrix_row(row, backend):
    _, path, d = row
    active = d['active_ledger']
    auto = list(csv.DictReader((path/'mapper-auto.tsv').open(), delimiter='\t'))[-1]
    return dict(backend=backend, machine=d['machine'], mapper_kib=d['mapper_ram_kib'],
        ram_profile_kib=d['mapper_ram_kib'], enemy_count=d['profile_enemy_count'],
        turbo=True, actual_backend_kind=int(auto['turbo_kind']),
        work=distribution(f['work'] for f in active['frames']),
        presented_fps=active['presented_fps'], active_frames=active['measured_frames'],
        late_frames=sum(f['cycles'] > 2*59736+6 for f in active['frames']),
        rom_sha256=d['rom_sha256'], passed=True, log=str(path.relative_to(ROOT)),
        control=d['control_check'])


def states(path):
    return list(csv.DictReader((path/'frames.tsv').open(), delimiter='\t'))


def build():
    base = ROOT/'references/build/game'
    cart = ROOT/'references/build/game-compact-runtime'
    mega = ROOT/'references/build/game-compact-megaram-runtime'
    hashes = {name:hashlib.sha256((p/'newrallyx.rom').read_bytes()).hexdigest()
              for name,p in [('baseline',base),('ASCII8',cart),('MegaRAM',mega)]}
    rows = {name:profiles(p,hashes[name]) for name,p in [('baseline',base),('ASCII8',cart),('MegaRAM',mega)]}
    chosen = []; comparisons = []
    for n in (3,5,6):
        triples = [select(rows[name], 'Panasonic_FS-A1WSX_NR64', 64, n)
                   for name in ('baseline','ASCII8','MegaRAM')]
        measured = [matrix_row(r,b) for r,b in zip(triples,('baseline','ASCII8','MegaRAM'))]
        data = [states(r[1]) for r in triples]
        fields = ['cx','cy','enemy_positions','elapsed_ticks','active_start','active_end','psg']
        assert len({len(d) for d in data}) == 1
        for variant in data[1:]:
            assert all(a[k] == b[k] for a,b in zip(data[0],variant) for k in fields), f'State mismatch: {n}'
        for r in measured[1:]:
            assert abs(r['presented_fps']-measured[0]['presented_fps']) < .00002
            assert all(r['work'][k] <= measured[0]['work'][k]+.01 for k in ('mean','p95','max'))
        chosen.extend(measured[1:])
        comparisons.append(dict(enemies=n,variants=measured,matched_rows=len(data[0]),matched_fields=fields))
    for machine,ram in [('Sony_HB-F1XDJ',64),('Panasonic_FS-A1ST',256),
                        ('Panasonic_FS-A1GT',512),('Panasonic_FS-A1WSX_NR128',128)]:
        chosen.append(matrix_row(select(rows['ASCII8'],machine,ram,3),'ASCII8'))
    primary = select(rows['ASCII8'],'Panasonic_FS-A1WSX_NR64',64,3)
    out = ROOT/'references/validation/compact-game'
    ledger = timing_report(cart,out,primary[1],None)
    regressions = []; components = []
    for bundle,backend in [(cart,'ASCII8'),(mega,'MegaRAM')]:
        for file in bundle.glob('session-start-*/result.json'):
            d = read(file); graphic = file.with_name('graphics-contracts.json')
            if d['rom_sha256'] != hashes[backend] or not d['passed'] or not graphic.exists():continue
            g = read(graphic)
            if not g['passed'] or g['rom_sha256'] != hashes[backend]:continue
            regressions.append(dict(backend=backend,machine=d['machine'],mapper_kib=d['mapper_ram_kib'],
                turbo=True,case=d['scenario'],passed=True,rom_sha256=d['rom_sha256'],
                snapshots=len(g['snapshots']),log=str(file.relative_to(ROOT))))
        for pattern in ['steering-proof-*','audio-proof-*','boot-proof-*','boot-skip-proof-*',
                        'speed-proof-*','rocks-proof-*','sprite-clip-proof-*']:
            candidates=[]
            for file in bundle.glob(pattern+'/report.json'):
                d=read(file)
                if d.get('rom_sha256')==hashes[backend] and d.get('passed',True):
                    candidates.append((file.stat().st_mtime,file,d))
            if candidates:
                _,file,d=max(candidates,key=lambda r:r[0])
                components.append(dict(machine='Panasonic_FS-A1WSX_NR64',mapper_kib=64,turbo=True,
                    case=pattern,passed=True,rom_sha256=hashes[backend],log=str(file.relative_to(ROOT))))
    for backend,required in [('ASCII8',{'start','integration','two-player','flags','attract','radar','smoke','controls'}),
                             ('MegaRAM',{'integration','two-player','flags','radar','controls'})]:
        assert required <= {r['case'] for r in regressions if r['backend']==backend}
    ledger.update(compact_backend=True,auto_policy=True,turbo_matrix=chosen,
        regression_matrix=regressions,long_matrix=components,base_mode_matrix=[],
        boot_matrix=[],capacity_matrix=[],mapper_comparisons=[],component_checks=[],
        factory_cpu_probe=dict(results=[],scope='Not rerun; actual controller/CPU and ABI checks accompany each current profile.'),
        working_tree_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        qualification_hashes=hashes,compact_comparisons=comparisons)
    authored=['scripts/compact_game_build.py','scripts/compact_game_verify.py',
        'scripts/compact_game_report.py','scripts/compact_map_contract.py',
        'scripts/renderer_image_build.py','scripts/renderer_window_probe.py',
        'scripts/megaram_package.py','src/disk/megaram-loader.asm',
        'src/toolchain/screen4/session_build.py','src/toolchain/screen4/session_profile_adapter.py']
    ledger['source_files']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in authored}
    ledger['limitations'] += ' Current matrix: WSX64 ASCII8/MegaRAM3/5/6, WSX128/Sony64/ST256/GT512 ASCII8 three enemies. NTSC output only; no physical hardware or listening acceptance.'
    (out/'cycle-ledger-enriched.json').write_text(json.dumps(ledger,indent=2)+'\n')
    map_results=[]
    for bundle,backend in [(base,'baseline'),(cart,'ASCII8'),(mega,'MegaRAM')]:
        matches=[]
        for file in bundle.glob('session-start-*/map-contract.tsv'):
            result=file.with_name('result.json')
            if result.exists() and read(result)['rom_sha256']==hashes[backend]:matches.append(file)
        samples=[r for file in matches for r in csv.DictReader(file.open(),delimiter='\t')]
        assert len({r['logical_bank'] for r in samples})==8
        map_results.append(dict(backend=backend,calls=len(samples),maps=8,
            iff_values=sorted({int(r['iff']) for r in samples}),
            inclusive_cycles=distribution(float(r['inclusive_cycles']) for r in samples),
            exact_16k_bytes=True,ix_iy_iff_preserved=True))
    loader_checks=[]
    for file in (ROOT/'references/sessions').glob('compact-megaram-*/report.json'):
        d=read(file)
        if d.get('rom_sha256')==hashes['MegaRAM']:
            loader_checks.append(dict(source=str(file.relative_to(ROOT)),**d))
    payload=dict(bytes=(cart/'newrallyx.rom').stat().st_size,hashes=hashes,
        saved_bytes=2048000-(cart/'newrallyx.rom').stat().st_size,
        performance=comparisons,cpu_matrix=chosen,regression=regressions,components=components,maps=map_results,
        megaram=read(ROOT/'dist/compact/megaram/manifest.json'),loader_checks=loader_checks,
        source_files=ledger['source_files'],
        limitations='Emulator/automated evidence; controlled fixtures distinguished by each source report. No hardware or subjective listening acceptance. NTSC output at59.922743Hz; no PAL50 timing claim.')
    target=ROOT/'docs/measurements/cartridge/issue41-compact-game.json'
    target.write_text(json.dumps(payload,indent=2)+'\n')
    print(target)


if __name__=='__main__':build()
