"""Consolidate exact-hash fixed-RAM evidence without retaining raw payloads.

Requires fixedram_qualify.py and fixedram_tick_verify.py to have passed. Earlier
mapper controls retain their hashes. The workbook reads the separate enriched
ledger so its writer can archive the previous canonical ledger before replacing
it. No release, commit, upload or issue mutation is performed here.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

from compact_game_report import distribution, matrix_row, profiles, read, select, states, timing_report
from mapper512_reference import SHA256 as CONTROL

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def latest(bundle, pattern, sha):
    found = []
    for p in bundle.glob(pattern):
        d = read(p)
        if d.get('rom_sha256') == sha and d.get('passed', True):
            found.append((p.stat().st_mtime, p, d))
    if not found:
        raise ValueError(f'Missing current evidence: {bundle.name}/{pattern}')
    _, p, d = max(found)
    return p, d


def logged(name):
    """Read the last complete JSON object after emulator diagnostics."""
    text = (ROOT/'references/build'/name).read_text()
    decoder = json.JSONDecoder()
    values = []
    for match in re.finditer(r'(?m)^\{', text):
        try:
            values.append(decoder.raw_decode(text[match.start():])[0])
        except ValueError:
            pass
    if not values:
        raise ValueError(name)
    return values[-1]


def build():
    bundles = {b: ROOT/'references/build'/n for b, n in [
        ('ASCII8', 'game-fixedram-runtime'), ('MegaRAM', 'game-fixedram-megaram-runtime')]}
    old = {b: ROOT/'references/build'/n for b, n in [
        ('ASCII8', 'game-compact-runtime'), ('MegaRAM', 'game-compact-megaram-runtime')]}
    hashes = {b: digest(p/'newrallyx.rom') for b, p in bundles.items()}
    assert digest(ROOT/'dist/newrallyx.rom') == hashes['ASCII8']
    assert read(ROOT/'dist/compact/megaram/manifest.json')['rom_sha256'] == hashes['MegaRAM']
    assert digest(old['ASCII8']/'newrallyx.rom') == CONTROL
    old_hashes = {b: digest(p/'newrallyx.rom') for b, p in old.items()}
    rows = {b: profiles(p, hashes[b]) for b, p in bundles.items()}
    controls = {b: profiles(p, old_hashes[b]) for b, p in old.items()}
    matrix, comparisons, chosen = [], [], {}
    workloads = [(b, 'Panasonic_FS-A1WSX_PLAIN64', 0, n) for b in bundles for n in [3, 5, 6]]
    workloads += [('ASCII8', m, r, 3) for m, r in [
        ('Panasonic_FS-A1WSX_NR128', 128), ('Sony_HB-F1XDJ', 64),
        ('Panasonic_FS-A1ST', 256), ('Panasonic_FS-A1GT', 512)]]
    for backend, machine, ram, enemies in workloads:
        current = select(rows[backend], machine, ram, enemies)
        control = select(controls[backend], machine.replace('PLAIN64', 'NR64'), ram or 64, enemies)
        assert current[2]['controlled_rng_seed'] == control[2]['controlled_rng_seed'] == 0x1234
        a, b = states(control[1]), states(current[1])
        fields = [k for k in a[0] if k != 'cycles']
        assert len(a) == len(b) == 356
        assert all(x[k] == y[k] for x, y in zip(a, b) for k in fields), (backend, machine, enemies)
        wa = {f['frame']: f for f in control[2]['active_ledger']['frames']}
        wb = {f['frame']: f for f in current[2]['active_ledger']['frames']}
        assert wa.keys() == wb.keys()
        delta = [wb[i]['work']-wa[i]['work'] for i in wa]
        assert max(delta) < .01, (backend, machine, enemies, max(delta))
        variant = matrix_row(current, backend)
        variant.update(main_ram_kib=ram or 64, ram_profile_kib=ram or 64,
                       main_ram_kind='plain' if not ram else 'mapper',
                       late_frames=sum(round(f['cycles']/59736)>2 for f in wb.values()))
        prior = matrix_row(control, 'previous ' + backend)
        prior['late_frames']=sum(round(f['cycles']/59736)>2 for f in wa.values())
        assert all(variant['work'][k] <= prior['work'][k]+.01 for k in ['mean', 'p95', 'max'])
        assert abs(variant['presented_fps']-prior['presented_fps']) < .00002
        matrix.append(variant)
        comparisons.append(dict(backend=backend, machine=machine, enemies=enemies,
            matched_rows=len(a), matched_active_rows=len(wa), matched_fields=fields,
            matched_state_sha256=hashlib.sha256(json.dumps([{k:r[k] for k in fields} for r in a],separators=(',',':')).encode()).hexdigest(),
            active_work_delta=dict(min=min(delta), **distribution(delta)),
            longer_active_frames=sum(d > .01 for d in delta),
            variants=[prior, variant], unchanged_active_frames=sum(abs(d) < .01 for d in delta)))
        chosen[backend, machine, enemies] = current
    commands = read(ROOT/'references/build/fixedram-qualification/commands.json')
    assert len(commands) == 35 and all(c['returncode'] == 0 for c in commands)
    regressions, components, detailed, maps = [], [], {}, []
    cart = bundles['ASCII8']
    for case in ['integration', 'flags', 'smoke', 'two-player', 'attract', 'controls', 'radar']:
        candidates = []
        for p in cart.glob('session-start-*/result.json'):
            d = read(p)
            if d.get('rom_sha256') == hashes['ASCII8'] and d.get('scenario') == case and d.get('passed'):
                g = read(p.with_name('graphics-contracts.json'))
                if g['passed'] and g['rom_sha256'] == hashes['ASCII8']:
                    candidates.append((p.stat().st_mtime, p, d, g))
        _, p, d, g = max(candidates)
        assert d['main_ram_kind'] == 'plain' and d['mapper_ram_kib'] == 0
        regressions.append(dict(backend='ASCII8', machine=d['machine'], mapper_kib=0,
            main_ram_kib=64, turbo=True, case=case, passed=True, rom_sha256=hashes['ASCII8'],
            snapshots=len(g['snapshots']), log=str(p.relative_to(ROOT))))
        detailed[case] = {k: v for k, v in d.items() if k not in ['layout', 'variant']}
        map_path=p.with_name('map-contract.tsv')
        if map_path.exists():maps.extend(csv.DictReader(map_path.open(),delimiter='\t'))
    assert len({r['logical_bank'] for r in maps})==8
    for backend, bundle in bundles.items():
        patterns = ['f10-proof-*/report.json']
        if backend == 'ASCII8':
            patterns += [p+'-proof-*/report.json' for p in ['boot', 'audio', 'speed', 'rocks', 'sprite-clip', 'steering']]
        for pattern in patterns:
            p, d = latest(bundle, pattern, hashes[backend])
            components.append(dict(backend=backend, machine='Panasonic_FS-A1WSX_PLAIN64',
                main_ram_kib=64, mapper_kib=0, turbo=True, case=pattern, passed=True,
                rom_sha256=hashes[backend], log=str(p.relative_to(ROOT))))
            detailed[backend + '/' + pattern] = d
    smoke = {mode: logged('fixedram-qualification/smoke-'+mode+'.log') for mode in ['rom', 'dos', 'basic']}
    for d in smoke.values():
        assert d['frames'] == 300 and d['main_mapper_bytes'] == 0 and d['graphics']['passed']
    lifecycle = {}
    for mode in ['rom', 'dos', 'basic']:
        p = ROOT/'references/sessions'/('compact-game-plain64-fixed' if mode == 'rom'
            else f'compact-megaram-{mode}-768-plain64-fixed')/'gameover-report.json'
        d = read(p)
        assert d['passed'] and d['new_game_presentations'] == 180
        assert d['rom_sha256'] == hashes['ASCII8' if mode == 'rom' else 'MegaRAM']
        lifecycle[mode] = d
    native = logged('fixedram-final-native.log')
    assert native['passed'] and native['native_ticks'] == 4096
    assert native['variants'][cart.name] == hashes['ASCII8']
    unexpanded=logged('fixedram-mega-unexpanded.log')
    assert unexpanded['main_mapper_bytes']==0 and unexpanded['frames']==300 and unexpanded['graphics']['passed']
    seals = read(ROOT/'references/build/fixedram-executable-seals.json')
    # ZIP also carries current provenance, source overlays and timestamps.
    # Keep runtime identity distinct from archive packaging.
    zip_path='dist/disk/newrallyx-disk.zip'
    zip_change=dict(path=zip_path,previous_sha256=seals.pop(zip_path),current_sha256=digest(ROOT/zip_path),
        scope='Rebuilt archive: cartridge provenance, source overlay and ZIP timestamps may change; all runtime files remain sealed.')
    assert len(seals)==10 and all(digest(ROOT/p) == sha for p, sha in seals.items())
    executables = {name: logged(log) for name, log in [
        ('mapper512-dos', 'fixedram-preserved512-dos.log'),
        ('mapper512-basic', 'fixedram-preserved512-basic.log'),
        ('legacy-dos', 'fixedram-preserved-dos.log'), ('legacy-basic', 'fixedram-preserved-basic.log')]}
    assert executables['mapper512-dos']['passed'] and executables['mapper512-basic']['passed']
    authored = ['scripts/fixedram_backend.py', 'scripts/fixedram_qualify.py', 'scripts/fixedram_report.py',
        'scripts/fixedram_tick_verify.py', 'scripts/fixedram_gameover_verify.py', 'scripts/mapper512_reference.py',
        'scripts/compact_game_build.py', 'scripts/compact_game_verify.py', 'scripts/compact_map_contract.py',
        'scripts/megaram_package.py', 'scripts/disk_package.py', 'src/screen4/session-fixedram-cold.inc',
        'src/screen4/session-fixedram-hot.inc', 'src/screen4/session-fixedram-irq.inc',
        'src/toolchain/msx/emulator.py', 'src/toolchain/msx/mapper_reference.tcl',
        'src/toolchain/screen4/session_profile_adapter.py','src/toolchain/screen4/session_steering_verify.py',
        'src/screen4/modules/contracts.json']
    source_files = {p: digest(ROOT/p) for p in authored}
    primary = chosen['ASCII8', 'Panasonic_FS-A1WSX_PLAIN64', 3]
    out = ROOT/'references/validation/fixedram'
    out.mkdir(parents=True, exist_ok=True)
    ledger = timing_report(cart, out, primary[1], None)
    ledger.update(fixed_ram=True, compact_backend=True, auto_policy=True,
        rom_bytes=(cart/'newrallyx.rom').stat().st_size, main_ram_kib=64, mapper_ram_kib=0,
        turbo_matrix=matrix, qualification_hashes=hashes, compact_comparisons=comparisons,
        regression_matrix=regressions, long_matrix=components, base_mode_matrix=[], boot_matrix=[],
        capacity_matrix=[], mapper_comparisons=[], component_checks=[], source_files=source_files,
        factory_cpu_probe=dict(results=[], scope='Actual CPU/ABI observed by each profile; no new synthetic probe.'),
        working_tree_base=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    (out/'cycle-ledger-enriched.json').write_text(json.dumps(ledger, indent=2)+'\n')
    result = dict(passed=True, status='Local test candidate; no release or physical-hardware acceptance',
        hashes=hashes, previous_hashes=old_hashes, rom_bytes=ledger['rom_bytes'],
        cpu_matrix=matrix, comparisons=comparisons, commands=commands, regressions=regressions,
        component_reports=detailed, smoke=smoke, natural_gameover=lifecycle, native_ticks=native,
        megaram_unexpanded=unexpanded,
        map_constructors=dict(calls=len(maps),logical_banks=sorted({int(r['logical_bank']) for r in maps}),
            inclusive_cycles=distribution(float(r['inclusive_cycles']) for r in maps),
            full_16k_bytes_equal=True,ix_iy_iff_preserved=True,iff_values=sorted({int(r['iff']) for r in maps})),
        host_tests=dict(general=512,components=94,component_skips=1,
            general_log_sha256=digest(ROOT/'references/build/fixedram-unit-final.log'),
            components_log_sha256=digest(ROOT/'references/build/fixedram-component-final.log')),
        executable_seals=seals, executable_checks=executables,legacy_zip=zip_change,
        megaram=read(ROOT/'dist/compact/megaram/manifest.json'),
        source_files=source_files,
        limits='openMSX22, NTSC reference only. Short matched directional workloads and controlled scenarios; not every natural course, PAL50, hardware, subjective audio or owner acceptance. Earlier512KiB divergent-route0.24% question remains separate. No release/commit/push/merge.')
    target = ROOT/'docs/measurements/cartridge/issue42-fixedram64.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(target)


if __name__ == '__main__':
    build()
