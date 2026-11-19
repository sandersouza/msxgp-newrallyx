"""Compact sealed cold-I/O and occupied-storage evidence; never original bytes."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from compact_game_report import distribution


def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    cold=ROOT/'references/build/game-mapper512-cold';control=cold.with_name(cold.name+'-per-resource')
    active=ROOT/'references/build/game-mapper512-integrated'
    plans=[read(p/'plan.json') for p in [control,cold]]
    assert plans[0]['records']==plans[1]['records'] and plans[0]['resource_sha256']==plans[1]['resource_sha256']
    assert len(plans[1]['records'])==120
    previous=read(ROOT/'docs/measurements/cartridge/issue42-512-integrated.json')
    assert plans[1]['active_images']==previous['program']['stages']
    frozen=read(ROOT/'docs/measurements/cartridge/f10-qualified.json')
    for n,d in frozen['artifacts'].items():assert digest(ROOT/n)==d['sha256']
    for name,sha in previous['preserved_timing'].items():
        if name=='ledger_sha256':assert digest(ROOT/'docs/measurements/timing/cycle-ledger.json')==sha
        elif name=='workbook_sha256':assert digest(ROOT/'docs/cycle-budget.xlsx')==sha

    def latest(bundle,predicate):
        choices=[(p,read(p)) for p in bundle.glob('*/report.json')]
        p,d=max(((p,d) for p,d in choices if predicate(d)),key=lambda pair:pair[0].stat().st_mtime)
        assert d['passed'];return p,d

    filesystem=[];comparisons=[]
    for mode in ['dos','basic']:
        pairs=[]
        for directory,plan in zip([control,cold],plans):
            p,d=latest(directory,lambda d:d['mode']==mode and not d['negative'] and d['source_bridge_sha256']==plan['bridge']['sha256'] and d.get('filesystem_calls'))
            assert digest(p.parent/'verify.tcl')==d['script_sha256']
            assert d['resource_reads']==120 and d['batch_flushes']==5 and d['masked_span_checks']==5000
            assert d['filesystem_calls']['world_half_checks']==20 and not d['cartridge_attached'] and d['host_payload_injections']==0
            costs=read(p.parent/'cycles.json');flush=read(p.parent/'flush-cycles.json')
            d={k:v for k,v in d.items() if k!='path'}
            d.update(resource_costs=costs,flush_costs=flush,phase_costs=[])
            start=0;j=0
            for i,r in enumerate(plan['records']):
                if r['bank']==2:
                    d['phase_costs'].append(dict(family=r['family'],reads=i-start+1,cycles=sum(costs[start:i+1])+flush[j]))
                    start=i+1;j+=1
            assert abs(sum(r['cycles'] for r in d['phase_costs'])-d['total_cold_cycles'])<.01
            pairs.append(d);filesystem.append(d)
        a,b=pairs
        comparisons.append(dict(mode=mode,control_total=a['total_cold_cycles'],candidate_total=b['total_cold_cycles'],
                                reduction_percent=100*(1-b['total_cold_cycles']/a['total_cold_cycles']),
                                longer_read_spans=sum(y-x>.01 for x,y in zip(a['resource_costs'],b['resource_costs'])),
                                flush_mean_delta=b['batch_flush_cycles']['mean']-a['batch_flush_cycles']['mean']))
        for size,fault in [(512,'missing'),(512,'truncated'),(512,'checksum'),(512,'late'),(64,None),(256,None)]:
            p,d=latest(cold,lambda d:d['mode']==mode and d['ram_kib']==size and d['fault']==fault and d['source_bridge_sha256']==plans[1]['bridge']['sha256'])
            assert digest(p.parent/'verify.tcl')==d['script_sha256'] and d['negative']
            assert d['rejected_hot_data_preserved'] if fault else d['capacity_probe_restored']
            if fault:assert d['resource_reads']==(28 if fault=='late' else 0)
            filesystem.append({k:v for k,v in d.items() if k!='path'})

    live=[];f10=[]
    def active_run(n,candidate,transition=False):
        p,d=latest(active,lambda d:d['candidate']==candidate and d.get('cold_storage',False)==candidate and d['native_round']==n
                   and d['transitions']==transition and d['frames']==(240 if transition else 360)
                   and d.get('input_clock')==('presentation' if transition else 'native'))
        assert d['graphics']['passed'] and d['cold_epochs']==int(transition)
        assert digest(p.parent/'verify.tcl')==d['verification_script_sha256']
        if candidate:
            assert d['stage_images']==plans[1]['active_images'] and d['cartridge_windows_guarded'] and d['immutable_hot_banks_checked']
            assert d['cache_policy_checks']>=d['frames'] and d['observed_irqs']>100
            if not transition:assert d['cold_bank_refills']==0
        return p,{k:v for k,v in d.items() if k not in ('path','stage_images')}
    for n in [5,10,13]:
        rows=[];results=[]
        for candidate in [False,True]:
            p,d=active_run(n,candidate);results.append(d)
            rows.append({r['frame']:r for r in csv.DictReader((p.parent/'frames.tsv').open(),delimiter='\t') if r['active']=='1'})
        keys=['cx','cy','round','enemies','ticks','psg','native'];pairs=[(r,rows[1][i]) for i,r in rows[0].items() if i in rows[1] and all(r[k]==rows[1][i][k] for k in keys)]
        assert pairs and all(float(y['work'])<=float(x['work'])+.01 for x,y in pairs)
        live.append(dict(round=n,control=results[0],occupied=results[1],matching_rows=len(pairs),
                         matched_work=[distribution(float(pair[i]['work']) for pair in pairs) for i in [0,1]],
                         scope='Same presentation/camera/native actor bytes/ticks/enemy count/PSG subset. Occupied storage is a diagnostic host fixture; no disk callback inside the game.'))
    assert sum(d['matching_rows'] for d in live)==465
    for n in [4,8,12,16]:
        _,d=active_run(n,True,True);assert d['f10'] and d['active_frames']==239;f10.append(d)
    tests=[]
    for name,count in [('tests',502),('components',94)]:
        log=(ROOT/f'references/build/issue42-cold-{name}.log').read_text()
        assert re.search(r'Ran '+str(count)+r' tests',log) and '\nOK' in log
        tests.append(dict(suite=name,tests=count,passed=True,skipped=int(name=='components')))
    assert '"passed": true' in (ROOT/'references/build/issue42-cold-module.log').read_text()
    preserved=[]
    for n in ['compact-game','compact-megaram-dos-768','compact-megaram-basic-768','disk-dos-4096','disk-basic-4096']:
        d=read(ROOT/'references/sessions'/n/'report.json')
        if n.startswith('disk-'):assert d['artifact_sha256']==frozen['disk']['disk_image_sha256']
        else:assert d['graphics']['passed'] and d['rom_sha256']==frozen['hashes']['MegaRAM' if 'megaram' in n else 'ASCII8']
        preserved.append(dict(case=n,result=d))
    sources=['scripts/mapper512_integrate.py','scripts/mapper512_integrated_verify.py','scripts/mapper512_cold.py','scripts/mapper512_cold_verify.py',
             'scripts/mapper512_cold_report.py','scripts/mapper512_cold_workbook.mjs','src/disk/mapper512-cold.asm','src/disk/mapper512-cold-loader.asm',
             'tests/test_mapper512_cold.py','tests/test_mapper512_integration.py','src/screen4/modules/contracts.json']
    report=dict(status='Real DOS1/BASIC cold I/O,48KiB scattered storage and active occupied-layout proofs pass; native512KiB boot/callback integration pending',
        plans=plans,filesystem_runs=filesystem,cold_comparisons=comparisons,active_occupied_checks=live,f10_occupied_transitions=f10,tests=tests,
        preserved_artifacts=frozen['artifacts'],preserved_timing=previous['preserved_timing'],preserved_startups=preserved,historical_module_layout_passed=True,
        cycle_ledger=dict(machine='Panasonic_FS-A1WSX_NR512',cpu='Z80 configured3579545Hz; no game acceleration hooks in cold-only runs',
            reference_hz=3579545,video='Cold-only BIOS screen and normal BIOS IRQ; occupied-game SCREEN4 NTSC59.922743Hz, HUD/audio and real sprite limits',
            units='Elapsed guest time x3579545, inclusive hardware/BIOS waits, not instruction-only CPU cycles',
            workload='120 filesystem resources: all four production hot layouts and world pairs plus3->0 wrap; five EndBatch siblings',
            calls_per_presented_frame=None,self_cycles=None,remaining_gameplay_budget=None,
            inclusive='Read and EndBatch are disjoint sibling intervals. Add their costs once; do not add nested decode/BDOS costs. Caller CALL/loop overhead excluded. Read includes RET; EndBatch includes close, OS persistence and map-shadow restoration.',
            synchronization='Cold BIOS/disk waits included; not active-frame waits or VBlank budgeting. Directory-backed virtual floppy, not physical drive timing.'),
        source_files={n:digest(ROOT/n) for n in sources},
        remaining=['Actual native boot including original opening and held-F10 handling without a cartridge',
                   'Replace game cold provider/map callbacks with the filesystem API and correct stopped cache/world lifetimes',
                   'Production game/BIOS VDP IRQ, PSG, input and clock handoff; complete lifecycle and error recovery',
                   'Requalify end-to-end speed/cadence, broader CPU/PAL matrix, hardware and owner acceptance'],
        limits=['No standalone512KiB game is delivered or promoted. Cold executables are ignored diagnostics only.',
                'No-cartridge/no-payload-injection filesystem runs use synthetic game main/Page3 state and a synthetic C0EE lifetime marker, not actual F10 activation.',
                'Occupied active-game runs use real gameplay/IRQs and held F10 but diagnostic host/cartridge startup and cold providers. These are not the same end-to-end run as filesystem tests.',
                'Canonical ROM744KiB/64KiB RAM, MegaRAM768KiB and legacy4MiB executable stay supported separately.',
                'Earlier0.24% slower presentation-clock route remains an unresolved cadence comparison with different trajectories; native-clock occupied runs do not prove every route faster.',
                'DOS2/Nextor allocation and general mapper/slot/hardware compatibility are not qualified. No new release, commit, push or merge.'])
    path=ROOT/'docs/measurements/cartridge/issue42-512-cold-io.json';path.write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'docs/measurements/timing/mapper512-cold-io.json').write_bytes(path.read_bytes())
    print(json.dumps(dict(status=report['status'],filesystem_cases=len(filesystem),active_cases=2*len(live)+len(f10),matched=465,cold_comparisons=comparisons),indent=2))


if __name__=='__main__':main()
