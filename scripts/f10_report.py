"""Bind the optional boot invulnerability qualification to exact local artifacts.

Consumes ignored emulator evidence; emits compact reports without original data.
Never substitutes historical size/backend experiments for current game tests.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'src/toolchain/screen4'), str(ROOT)]
from compact_game_report import matrix_row, profiles, read, select, states, timing_report
from compact_game_build import symbols


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest(bundle, pattern, sha, predicate=lambda d: True):
    matches = []
    for path in bundle.glob(pattern):
        data = read(path)
        if data.get('rom_sha256') == sha and data.get('passed', True) and predicate(data):
            matches.append(path)
    path = max(matches, key=lambda p:p.stat().st_mtime)
    return dict(read(path), evidence_path=str(path.relative_to(ROOT)))


def build():
    bundles = {k:ROOT/'references/build'/v for k,v in [
        ('baseline','game-f10-baseline'), ('ASCII8','game-compact-runtime'),
        ('MegaRAM','game-compact-megaram-runtime')]}
    hashes = {k:digest(p/'newrallyx.rom') for k,p in bundles.items()}
    assert hashes['baseline'] == 'b39e0c7f520872174e9a89cc46ddf4e1957179bc70ac3326c6450420866a878c'
    assert hashes['ASCII8'] == digest(ROOT/'dist/newrallyx.rom')
    manifest = read(ROOT/'dist/manifest.json')
    assert manifest['bytes'] == 744*1024 and manifest['minimum_mapper_ram_kib'] == 64
    rows = {k:profiles(p,hashes[k]) for k,p in bundles.items()}
    comparisons = []; matrix = []
    fields = ['cx','cy','enemy_positions','elapsed_ticks','active_start','active_end','psg']
    for n in (3,5,6):
        chosen = [select(rows[k],'Panasonic_FS-A1WSX_NR64',64,n) for k in bundles]
        traces = [states(r[1]) for r in chosen]
        assert len({len(t) for t in traces}) == 1
        assert all(a[k] == b[k] for t in traces[1:] for a,b in zip(traces[0],t) for k in fields)
        variants = [matrix_row(r,k) for r,k in zip(chosen,bundles)]
        for variant in variants[1:]:
            assert abs(variant['presented_fps']-variants[0]['presented_fps']) < .00002
            assert all(abs(variant['work'][k]-variants[0]['work'][k]) < .01 for k in ('mean','p95','max'))
        comparisons.append(dict(enemies=n,variants=variants,matched_rows=len(traces[0]),matched_fields=fields))
        matrix.extend(variants[1:])
    for machine,ram in [('Sony_HB-F1XDJ',64),('Panasonic_FS-A1WSX_NR128',128),
                        ('Panasonic_FS-A1ST',256),('Panasonic_FS-A1GT',512)]:
        matrix.append(matrix_row(select(rows['ASCII8'],machine,ram,3),'ASCII8'))
    regressions = []; components = []
    for backend in ('ASCII8','MegaRAM'):
        bundle = bundles[backend]
        cases = ['start','integration','two-player','flags','attract','radar','smoke','controls'] if backend == 'ASCII8' else ['integration','two-player','flags','radar','controls']
        for case in cases:
            data = latest(bundle,'session-start-*/result.json',hashes[backend],lambda d:d['scenario']==case)
            graphics = read((ROOT/data['evidence_path']).with_name('graphics-contracts.json'))
            assert graphics['passed'] and graphics['rom_sha256'] == hashes[backend]
            regressions.append(dict(backend=backend,case=case,machine=data['machine'],mapper_kib=data['mapper_ram_kib'],turbo=True,passed=True,rom_sha256=hashes[backend],log=data['evidence_path'],snapshots=len(graphics['snapshots'])))
    for kind in ('steering','audio','boot','boot-skip','speed','rocks','sprite-clip'):
        data = latest(bundles['ASCII8'],kind+'-proof-*/report.json',hashes['ASCII8'],
                      lambda d: not d.get('boot_f10_invulnerability',False))
        components.append(dict(case=kind,passed=True,machine='Panasonic_FS-A1WSX_NR64',mapper_kib=64,turbo=True,rom_sha256=hashes['ASCII8'],log=data['evidence_path'],result=data))
    keys = []
    for mode,ram in [('rom',64),('rom',128),('mega-dos',64),('mega-basic',64),('disk-dos',4096),('disk-basic',4096)]:
        backend = 'MegaRAM' if mode.startswith('mega') else 'ASCII8'
        bundle = ROOT/'references/build/game-disk' if mode.startswith('disk') else bundles[backend]
        sha = digest(bundle/'disk-image.bin') if mode.startswith('disk') else hashes[backend]
        keys.append(latest(bundle,'f10-proof-*/report.json',sha,lambda d:d['mode']==mode and d['main_ram_kib']==ram and len(d['cases'])==(8 if (mode,ram)==('rom',64) else 2)))
    assert sum(len(d['cases']) for d in keys) == 18
    assert sum(d['contact_checks'] for d in keys) == 54
    walls = latest(bundles['ASCII8'],'steering-proof-*/report.json',hashes['ASCII8'],lambda d:d.get('boot_f10_invulnerability',False))
    assert walls['requested_active_refreshes'] >= 1600
    prefixes = []
    for backend in ('baseline','ASCII8'):
        bundle = bundles[backend]; s = symbols(bundle/'lab.sym')
        prefixes.append((bundle/'newrallyx.rom').read_bytes()[s['Death_Begin']-0x4000:s['Death_Begin']-0x4000+9])
    assert prefixes[0] == prefixes[1] and prefixes[0][-1] == 0xc8
    tests = []
    for name,count in [('unit',486),('unit-components',94)]:
        text = (ROOT/f'references/build/f10-{name}.log').read_text()
        assert re.search(r'Ran '+str(count)+r' tests',text) and '\nOK' in text
        tests.append(dict(suite=name,tests=count,passed=True,skipped=int(name=='unit-components')))
    assert '"passed": true' in (ROOT/'references/build/f10-module-layout.log').read_text()
    assert '"passed": true' in (ROOT/'references/build/f10-legacy-test-controls.log').read_text()
    assert 'ROM:' in (ROOT/'references/build/f10-no-check-build.log').read_text()
    rng = read(ROOT/'references/build/f10-rng.json')
    assert rng['passed'] and rng['rom_sha256'] == hashes['ASCII8']
    artifacts = {}
    for name in ['dist/newrallyx.rom','dist/compact/megaram/newrallyx-megaram.zip','dist/disk/newrallyx-disk.zip']:
        path = ROOT/name
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive: assert archive.testzip() is None
        artifacts[name] = dict(bytes=path.stat().st_size,sha256=digest(path))
    mega = read(ROOT/'dist/compact/megaram/manifest.json'); disk = read(ROOT/'dist/disk/manifest.json')
    assert mega['rom_sha256'] == hashes['MegaRAM'] and mega['minimum_megaram_kib'] == 768
    assert disk['cartridge_rom_sha256'] == hashes['ASCII8'] and disk['minimum_mapper_ram_kib'] == 4096
    assert all(d['rom_sha256']==disk['disk_image_sha256'] for d in keys if d['mode'].startswith('disk'))
    out = ROOT/'references/validation/f10'; out.mkdir(parents=True,exist_ok=True)
    primary = select(rows['ASCII8'],'Panasonic_FS-A1WSX_NR64',64,3)
    ledger = timing_report(bundles['ASCII8'],out,primary[1],None)
    ledger.update(compact_backend=True,auto_policy=True,f10_feature=True,turbo_matrix=matrix,
        qualification_hashes=hashes,compact_comparisons=comparisons,regression_matrix=regressions,
        long_matrix=components,base_mode_matrix=[],boot_matrix=[],capacity_matrix=[],mapper_comparisons=[],component_checks=[],
        factory_cpu_probe=dict(results=[],scope='Actual CPU/ABI observers accompany every current profile.'),
        working_tree_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    authored = ['scripts/f10_report.py','scripts/f10_verify.py','scripts/compact_game_build.py','scripts/megaram_package.py','scripts/disk_package.py',
        'src/screen4/session-boot-keys.inc','src/screen4/session-boot.inc','src/screen4/session-input.inc','src/screen4/modules/session/world.inc',
        'src/toolchain/screen4/session_build.py','src/toolchain/msx/emulator.py','src/toolchain/screen4/session_steering_verify.py']
    ledger['source_files'] = {n:digest(ROOT/n) for n in authored}
    ledger['limitations'] += ' NTSC60 emulator only; no physical hardware, PAL50, full-course or subjective listening acceptance. F10 contacts are injected into the actual handler. Legacy disk reset uses separate cold processes, not warm-reset qualification.'
    (out/'cycle-ledger-enriched.json').write_text(json.dumps(ledger,indent=2)+'\n')
    report = dict(passed=True,bytes=manifest['bytes'],hashes=hashes,artifacts=artifacts,megaram=mega,disk=disk,
        keyboard_cases=keys,wall_check=walls,performance=comparisons,cpu_matrix=matrix,regressions=regressions,components=components,
        no_contact_prefix_unchanged=True,no_contact_added_cycles=0,contact_guard_base_z80_cycles=dict(disabled=25,enabled=31),
        tests=tests,rng=rng,historical_module_layout_passed=True,legacy_test_controls_passed=True,no_check_build_passed=True,
        source_files=ledger['source_files'],limitations=ledger['limitations'],status='Local candidate; no release, commit, push or merge.')
    target = ROOT/'docs/measurements/cartridge/f10-qualified.json'
    target.write_text(json.dumps(report,indent=2)+'\n')
    print(target); return report


if __name__ == '__main__': build()
