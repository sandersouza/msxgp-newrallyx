"""Publish complete, single-ROM automatic mapper/CPU emulator evidence."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
MACHINES = tuple('Panasonic_FS-A1' + m for m in ('FX', 'WX', 'WSX', 'ST', 'GT')) + ('Sony_HB-F1XV',)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('profile', 'regression', 'long', 'boot', 'capacity', 'factory', 'bundle', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    groups = {name: json.loads(getattr(a, name).read_text())['records']
              for name in ('profile', 'regression', 'long', 'boot', 'capacity')}
    configs = [(m, k) for m in MACHINES for k in (64, 128) if not (m.startswith('Sony') and k == 128)]
    expected = {
        'profile': {(m, k, f'round{r}-{e}enemies') for m, k in configs for r, e in ((5, 3), (10, 5), (13, 6))},
        'regression': {(m, k, c) for m, k in configs for c in ('start', 'integration', 'two-player', 'flags', 'attract', 'radar', 'smoke', 'controls')},
        'long': {(m, k, c) for m in ('Panasonic_FS-A1WSX', 'Panasonic_FS-A1ST') for k in (64, 128)
                 for c in ('steering-smoke', 'boot-skip', 'speed', 'audio', 'sprite-clipping')},
        'boot': {(m, k, 'hardware-check') for m, k in configs
                 if m in ('Panasonic_FS-A1WSX', 'Panasonic_FS-A1ST', 'Panasonic_FS-A1GT', 'Sony_HB-F1XV')},
        'capacity': {('Panasonic_FS-A1WSX', k, 'hardware-check') for k in (256, 512, 1024, 2048, 4096)},
    }
    image = cartridge_path(a.bundle).read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if len(image) > 2 * 1024 * 1024:
        raise ValueError('Cartridge exceeds the mandatory 2MiB limit')
    for name, rows in groups.items():
        identities = [(r['machine'], r['ram_profile_kib'], r['case']) for r in rows]
        if len(set(identities)) != len(rows) or set(identities) != expected[name]:
            raise ValueError(f'Incomplete/duplicate {name} matrix')
        for row in rows:
            if not row['passed'] or row['rom_sha256'] != digest or not row['turbo']:
                raise ValueError('Failed or superseded evidence cannot qualify this cartridge')
            if name in ('profile', 'regression', 'boot', 'capacity'):
                if not row.get('probe_restored') or row.get('selected_profile_kib') != (128 if row['mapper_kib'] >= 128 else 64):
                    raise ValueError('Missing capacity/restoration/cache-tier proof')
    matrix = groups['profile']
    for row in matrix:
        measured = ROOT / row['profile_path'] / 'measured.rom'
        if hashlib.sha256(measured.read_bytes()).hexdigest() != digest:
            raise ValueError('Measured cartridge was replaced')
        with (measured.parent / 'turbo.tsv').open() as file:
            observed = list(csv.DictReader(file, delimiter='\t'))
        if {int(r['kind']) for r in observed} != {row['actual_backend_kind']}:
            raise ValueError('CPU observer and startup capability disagree')
        row['observed_cpu_modes'] = [dict(cpu=cpu, z80_hz=hz, controller=controller)
            for cpu, hz, controller in sorted({(r['cpu'], int(r['z80_hz']), int(r['controller'])) for r in observed})]
    selected = next(r for r in matrix if r['machine'] == 'Panasonic_FS-A1WSX' and r['ram_profile_kib'] == 64 and r['enemy_count'] == 3)
    primary = json.loads((ROOT / selected['ledger']).read_text())
    factory = json.loads(a.factory.read_text())
    if not all(r['returncode'] == 0 for r in factory['results']):
        raise ValueError('Factory CPU qualification is incomplete')
    pairs = []
    for before in matrix:
        if before['selected_profile_kib'] != 64:
            continue
        after = next((r for r in matrix if r['machine'] == before['machine'] and r['case'] == before['case'] and r['selected_profile_kib'] == 128), None)
        if after:
            pairs.append(dict(machine=before['machine'], enemies=before['enemy_count'],
                rom_sha256=digest, low_mapper_kib=before['mapper_kib'], high_mapper_kib=after['mapper_kib'],
                low_fps=before['presented_fps'], high_fps=after['presented_fps'],
                mean_work_reduction_percent=(1-after['work']['mean']/before['work']['mean'])*100,
                p95_work_reduction_percent=(1-after['work']['p95']/before['work']['p95'])*100,
                max_work_reduction_percent=(1-after['work']['max']/before['work']['max'])*100))
    primary.update(auto_policy=True, turbo_matrix=matrix, regression_matrix=groups['regression'],
        long_matrix=groups['long'], boot_matrix=groups['boot'], capacity_matrix=groups['capacity'],
        base_mode_matrix=[], component_checks=[], factory_cpu_probe=factory,
        mapper_comparisons=pairs, paired_comparisons=[], rom_bytes=len(image),
        comparison_limit='Same cartridge/input/population, different available RAM. Timing changes trajectories and active partitions; not matched-state marginal speedups.',
        delivery='Default MAPPER=auto TURBO=1; one cartridge, minimum64KiB mapper RAM. Emulator qualification; user audio/perceptual acceptance pending.',
        physical_hardware='Unavailable, as confirmed by user2026-10-30. No physical-machine qualification.',
        units='Elapsed emulated seconds. Legacy *_cycles are seconds times3579545 reference Hz, never actual R800 instruction cycles.',
        working_tree_base=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        evidence_sources={k: str(v) for k, v in vars(a).items() if k != 'output'})
    primary['authored_source_sha256'] = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in (source_path(name) for name in ('session-auto.inc', 'session-auto-status.inc', 'session_auto.py',
            'session_auto_contract.py', 'session-turbo.inc', 'session_turbo.py', 'session_turbo_contract.py', 'session_profile_adapter.py'))}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(primary, indent=2) + '\n')
    print(a.output)


if __name__ == '__main__':
    main()
