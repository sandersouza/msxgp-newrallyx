"""Publish only complete, ROM-bound emulator matrices; retain elapsed-time units."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import csv
import re

ROOT=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--matrix',type=Path,required=True)
    p.add_argument('--regression',type=Path,required=True)
    p.add_argument('--long',type=Path,required=True)
    p.add_argument('--factory',type=Path,required=True)
    p.add_argument('--base-mode',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    matrix=json.loads(a.matrix.read_text())['records']
    regression=json.loads(a.regression.read_text())['records']
    long=json.loads(a.long.read_text())['records']
    factory=json.loads(a.factory.read_text())
    base_mode=json.loads(a.base_mode.read_text())['records']
    if len(matrix)!=66 or len(regression)!=88 or len(long)!=40 or len(base_mode)!=11:
        raise ValueError('Incomplete five-model/control, two-RAM-profile evidence matrix')
    if not all(r['passed'] for r in matrix+regression+long+base_mode) or not all(r['returncode']==0 for r in factory['results']):
        raise ValueError('Failed or unavailable cases cannot be published as qualification')
    selected=next(r for r in matrix if r['machine']=='Panasonic_FS-A1WSX' and r['ram_profile_kib']==64 and r['turbo'] and r['enemy_count']==3)
    primary=json.loads((ROOT/selected['ledger']).read_text())
    for row in matrix:
        measured=ROOT/row['profile_path']/'measured.rom'
        if hashlib.sha256(measured.read_bytes()).hexdigest()!=row['rom_sha256']:
            raise ValueError('Measured image changed')
        if row['turbo']:
            with (ROOT/row['profile_path']/'turbo.tsv').open() as file:
                observed=list(csv.DictReader(file,delimiter='\t'))
            kinds={int(r['kind']) for r in observed}
            if len(kinds)!=1:raise ValueError('Missing/inconsistent observed backend')
            row['actual_backend_kind']=kinds.pop()
            row['observed_cpu_modes']=[dict(cpu=cpu,z80_hz=hz,controller=controller) for cpu,hz,controller in
                sorted({(r['cpu'],int(r['z80_hz']),int(r['controller'])) for r in observed})]
            if row['actual_backend_kind']==0:row['cpu_policy']='Base Z80 fallback; original foreground loop'
        else:
            row['actual_backend_kind']=0
    for row in base_mode:
        candidates=list((ROOT/row['log']).parent.glob('session-start-*/base-cpu.tsv'))
        if not candidates:raise ValueError('Missing observed base-machine CPU state')
        source=max(candidates,key=lambda f:f.stat().st_mtime)
        with source.open() as file:observed=list(csv.DictReader(file,delimiter='\t'))
        if not observed or any(r['cpu']!='z80' or r['z80_hz']!='3579545' for r in observed):
            raise ValueError('Base-machine CPU state was not qualified')
        row['cpu_state_evidence']=str(source.relative_to(ROOT))
        row['observed_cpu_modes']=sorted({r['cpu']+':'+r['z80_hz'] for r in observed})
    for row in matrix+regression+long+base_mode:
        bundle=ROOT/'references/experiments'/('full-session'+('-turbo' if row['turbo'] else '')+('-64k' if row['ram_profile_kib']==64 else ''))
        if hashlib.sha256((cartridge_path(bundle)).read_bytes()).hexdigest()!=row['rom_sha256']:
            raise ValueError('Superseded cartridge evidence cannot qualify the current build')
    pairs=[]
    for row in matrix:
        if not row['turbo']:continue
        before=next(r for r in matrix if not r['turbo'] and all(r[k]==row[k] for k in ('machine','ram_profile_kib','case')))
        pairs.append(dict(machine=row['machine'],ram_profile_kib=row['ram_profile_kib'],enemies=row['enemy_count'],
            base_rom_sha256=before['rom_sha256'],turbo_rom_sha256=row['rom_sha256'],
            base_active_frames=before['active_frames'],turbo_active_frames=row['active_frames'],
            mean_work_reduction_percent=(1-row['work']['mean']/before['work']['mean'])*100,
            p95_work_reduction_percent=(1-row['work']['p95']/before['work']['p95'])*100,
            max_work_reduction_percent=(1-row['work']['max']/before['work']['max'])*100,
            base_fps=before['presented_fps'],turbo_fps=row['presented_fps'],
            base_late_fraction=before['late_frames']/before['active_frames'],turbo_late_fraction=row['late_frames']/row['active_frames']))
    components={}
    for ram in (64,128):
        bundle=ROOT/'references/experiments'/('full-session-turbo'+('-64k' if ram==64 else ''))
        expected=hashlib.sha256((cartridge_path(bundle)).read_bytes()).hexdigest()
        for kind,pattern in (('motion','motion-predicate-*/report.json'),('rocks','rocks-proof-*/report.json')):
            for source in bundle.glob(pattern):
                value=json.loads(source.read_text())
                if value.get('rom_sha256')!=expected or not value.get('passed'):continue
                found=re.search(r'Reference RAM mapper: \d+ bytes; machine: (\S+)',(source.parent/'openmsx.log').read_text())
                if not found:continue
                key=(kind,ram,found[1])
                if key not in components or source.stat().st_mtime>components[key][0]:
                    components[key]=(source.stat().st_mtime,value|dict(kind=kind,machine=found[1],ram_profile_kib=ram,
                        source=str(source.relative_to(ROOT)),cpu_mode='Base Z80; controlled fixture outside accelerated scopes',cpu_hz=3579545))
    if len(components)!=8:raise ValueError('Missing controlled motion/rock components for both representative CPUs/RAM profiles')
    primary.update(turbo_matrix=matrix,regression_matrix=regression,long_matrix=long,base_mode_matrix=base_mode,factory_cpu_probe=factory,
        component_checks=[value for _,value in components.values()],
        paired_comparisons=pairs,comparison_limit='Same machine/input/population; timing changes trajectories and active partitions. This is a workload comparison, not a matched-state marginal speedup.',
        working_tree_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        rom_bytes=selected['rom_bytes'],delivery='Opt-in TURBO=1; emulator qualification only; user audio/perceptual acceptance pending.',
        physical_hardware='Unavailable, as confirmed by user2026-10-30. No physical-machine qualification.',
        units='Elapsed emulated seconds. Legacy *_cycles fields are seconds times3579545 reference Hz, including mixed-clock waits; never actual R800 instruction cycles.',
        rejected_evidence='Pre-IM2-restoration turboR runs and unguarded Page0 breakpoint aliases are retained privately and excluded.',
        evidence_sources={k:str(v) for k,v in vars(a).items() if k!='output'})
    primary['authored_source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
        for f in (source_path('session-turbo.inc'),source_path('session_turbo.py'),source_path('session_turbo_contract.py'),source_path('session_profile_adapter.py'))}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(primary,indent=2)+'\n')
    print(a.output)


if __name__=='__main__':
    main()
