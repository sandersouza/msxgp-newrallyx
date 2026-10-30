"""Run paired native workloads or graphics/rules checks on isolated machine bundles."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import csv

ROOT=Path(__file__).resolve().parents[3]
MACHINES=tuple('Panasonic_FS-A1'+m for m in ('FX','WX','WSX','ST','GT'))+('Sony_HB-F1XV',)
WORKLOADS=((5,3),(10,5),(13,6))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--machine',choices=MACHINES,action='append')
    p.add_argument('--ram',type=int,choices=(64,128,256,512,1024,2048,4096),action='append')
    p.add_argument('--kind',choices=('profile','regression','long','boot'),default='profile')
    p.add_argument('--bundle',type=Path,help='One automatic cartridge for every requested machine/RAM configuration')
    p.add_argument('--frames',type=int,default=360)
    p.add_argument('--turbo',type=int,choices=(0,1),help='Restrict to one CPU-build policy')
    p.add_argument('--case',action='append',help='Restrict to named cases')
    p.add_argument('--reuse',type=Path,help='Reuse only passed cases with the exact current cartridge hash')
    args=p.parse_args()
    if args.bundle and args.turbo is None:p.error('--bundle requires explicit --turbo0/1')
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'references'):
        p.error('Outputs must stay in ignored references/')
    output.mkdir(parents=True,exist_ok=False)
    records=[]
    retained=json.loads(args.reuse.read_text())['records'] if args.reuse else []
    for machine in args.machine or MACHINES:
        for ram in args.ram or (64,128):
            if machine.startswith('Sony') and ram==128:
                continue  # Stock control has64KiB; no invented RAM expansion.
            for turbo in ((args.turbo,) if args.turbo is not None else (0,1) if args.kind in ('profile','long') else (1,)):
                source=ROOT/'references/experiments'/('full-session'+('-turbo' if turbo else '')+('-64k' if ram==64 else ''))
                if args.bundle:
                    source=args.bundle.resolve()
                    if bool(json.loads((source/'session-build.json').read_text()).get('turbo',False))!=bool(turbo):
                        p.error('Requested turbo policy differs from the supplied cartridge')
                bundle=output/machine/str(ram)/str(turbo)
                bundle.mkdir(parents=True)
                for item in source.iterdir():
                    if item.is_file() and item.name not in ('last-profile.txt',):
                        (bundle/item.name).symlink_to(item.resolve())
                env=dict(os.environ,NRX_REFERENCE_MACHINE=machine,NRX_REFERENCE_RAM_KIB=str(ram))
                if args.kind=='profile':
                    cases=[(f'round{r}-{e}enemies', ['session_profile.py'],dict(NRX_PROFILE_ROUND=str(r),NRX_PROFILE_ENEMIES=str(e),NRX_PROFILE_FRAMES=str(args.frames))) for r,e in WORKLOADS]
                elif args.kind=='regression':
                    cases=[(s,['session_verify.py','--headless','--scenario',s,'--contracts'],{}) for s in ('start','integration','two-player','flags','attract','radar','smoke','controls')]
                elif args.kind=='long':
                    cases=[('steering-smoke',['session_steering_verify.py','--frames','16000'],{}),('boot-skip',['session_boot_skip_verify.py'],{}),('speed',['session_speed_verify.py'],{}),('audio',['session_audio_verify.py'],{}),('sprite-clipping',['session_sprite_verify.py'],{})]
                else:
                    cases=[('hardware-check',['session_boot_verify.py'],{})]
                for name,command,extra in cases:
                    if args.case and name not in args.case:continue
                    record=dict(machine=machine,ram_profile_kib=ram,turbo=bool(turbo),case=name,
                                rom_sha256=hashlib.sha256((cartridge_path(bundle)).read_bytes()).hexdigest(),
                                rom_bytes=(cartridge_path(bundle)).stat().st_size)
                    log=bundle/(name+'.log')
                    match=next((r for r in retained if r.get('passed') and all(r.get(k)==record[k] for k in ('machine','ram_profile_kib','turbo','case','rom_sha256'))),None)
                    if match:
                        records.append(match|dict(reused_from=str(args.reuse)))
                        (output/'result.json').write_text(json.dumps(dict(kind=args.kind,records=records),indent=2)+'\n')
                        print(json.dumps(dict(machine=machine,ram=ram,case=name,reused=True)),flush=True)
                        continue
                    try:
                        with log.open('w') as file:
                            run=subprocess.run([sys.executable,'-B',str(Path(__file__).parent/command[0]),*command[1:],'--bundle',str(bundle)],env=env|extra,cwd=ROOT,stdout=file,stderr=subprocess.STDOUT,timeout=420 if args.kind=='long' else 240)
                        record['passed']=run.returncode==0
                        record['log']=str(log.relative_to(ROOT))
                        if not record['passed']:
                            record['error']=log.read_text()[-1600:]
                        elif args.kind=='profile':
                            profile=Path((bundle/'last-profile.txt').read_text().strip())
                            from session_report import report
                            ledger=report(bundle,bundle/(name+'-ledger'),profile=profile)
                            data=json.loads((bundle/(name+'-ledger')/'cycle-ledger.json').read_text())
                            record.update({k:data[k] for k in ('work','interval','active_frames','active_seconds','presented_fps','late_frames','cadence','native_round','enemy_count','routines','timing_units','cpu_policy')})
                            record['profile_path']=str(profile.relative_to(ROOT))
                            record['ledger']=str((bundle/(name+'-ledger')/'cycle-ledger.json').relative_to(ROOT))
                        if record['passed'] and args.bundle:
                            mode_files=list(bundle.glob('*/mapper-auto.tsv'))
                            if mode_files:
                                mode_file=max(mode_files,key=lambda f:f.stat().st_mtime)
                                with mode_file.open() as file:mode=list(csv.DictReader(file,delimiter='\t'))[-1]
                                record.update(mapper_kib=int(mode['mapper_kib']),selected_profile_kib=int(mode['profile_kib']),actual_backend_kind=int(mode['turbo_kind']),probe_restored=mode['probe_restored']=='1',mode_evidence=str(mode_file.relative_to(ROOT)))
                    except Exception as error:
                        record.update(passed=False,error=str(error))
                    records.append(record)
                    (output/'result.json').write_text(json.dumps(dict(kind=args.kind,records=records),indent=2)+'\n')
                    print(json.dumps({k:record[k] for k in ('machine','ram_profile_kib','turbo','case','passed')}),flush=True)
    return int(any(not row['passed'] for row in records))


if __name__=='__main__':
    raise SystemExit(main())
