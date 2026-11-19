"""Retain compact, exact-program full-game evidence, never native payloads.

Run after mapper512_integrate and the documented emulator matrix. Historical
component reports and the public cartridge timing ledger are not rewritten.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from compact_game_report import distribution


def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bundle=ROOT/'references/build/game-mapper512-integrated'
    manifest=read(bundle/'integration.json');baseline=read(ROOT/'docs/measurements/cartridge/f10-qualified.json')
    for name,info in baseline['artifacts'].items():
        assert digest(ROOT/name)==info['sha256'] and (ROOT/name).stat().st_size==info['bytes'],name
    for name,sha in manifest['runtime_files'].items():assert digest(bundle/name)==sha,name
    for row in manifest['stages']:assert digest(bundle/f"stage-{row['family']}/hot-image.bin")==row['sha256']
    reports=[(p,read(p)) for p in bundle.glob('*/report.json')]

    def select(candidate,round_number,clock='presentation',transition=False):
        matches=[(p,d) for p,d in reports if d['candidate']==candidate and d['native_round']==round_number
                 and d.get('input_clock','presentation')==clock and d['transitions']==transition
                 and not d.get('cold_storage',False)
                 and d['f10']==transition and d['frames']==(240 if transition else 360)]
        p,d=max(matches,key=lambda item:item[0].stat().st_mtime)
        assert d['passed'] and d['graphics']['passed'] and d['reference_rom_sha256']==manifest['reference_rom_sha256']
        assert d['main_ram_kib']==512 and d['cold_epochs']==int(transition)
        if candidate:
            assert d['stage_images']==manifest['stages'] and d['immutable_hot_banks_checked'] and d['cartridge_windows_guarded']
            assert d['observed_irqs']>100 and d['cache_policy_checks']>=d['frames']
            if not transition:assert d['cold_bank_refills']==0
        assert digest(p.parent/'verify.tcl')==d['verification_script_sha256']
        rows=list(csv.DictReader((p.parent/'frames.tsv').open(),delimiter='\t'))
        # Retain timing and state hashes only. Original native/PSG bytes and
        # RAM/VRAM dumps must stay ignored and can be deleted after this report.
        key_fields=['cx','cy','round','enemies','ticks','psg','native']
        frames=[dict(frame=int(r['frame']),work=float(r['work']),period=float(r['period']),
                     state_sha256=hashlib.sha256(json.dumps([r[k] for k in key_fields]).encode()).hexdigest())
                for r in rows if r['active']=='1']
        result={k:v for k,v in d.items() if k not in ('stage_images','path')}
        result.update(input_clock=clock,trace_sha256=digest(p.parent/'frames.tsv'),
                      presented_fps=3579545/d['period']['mean'],active_costs=frames)
        return result

    comparisons=[]
    for clock in ['presentation','native']:
        for n in [5,10,13]:
            control=select(False,n,clock);candidate=select(True,n,clock)
            # Active filtering may omit different frames. Join by presentation
            # index explicitly, never pair rows by shifted filtered positions.
            old={r['frame']:r for r in control['active_costs']}
            pairs=[(old[r['frame']],r) for r in candidate['active_costs']
                   if r['frame'] in old and r['state_sha256']==old[r['frame']]['state_sha256']]
            assert pairs
            matched=dict(count=len(pairs),control=distribution(a['work'] for a,b in pairs),
                         candidate=distribution(b['work'] for a,b in pairs),
                         longer_spans=sum(b['work']-a['work']>.01 for a,b in pairs),
                         max_work_delta=max(b['work']-a['work'] for a,b in pairs),
                         scope='Same presentation index, camera, native actor-state bytes E088..E167, elapsed-tick byte, enemy count and all14 PSG registers; not every native RAM byte or full-course equivalence.')
            assert matched['longer_spans']==0
            comparisons.append(dict(round=n,enemies={5:3,10:5,13:6}[n],input_clock=clock,
                                    control=control,candidate=candidate,matched=matched))
    transitions=[select(True,n,transition=True) for n in [4,8,12,16]]
    for row in transitions:
        assert row['f10'] and row['active_frames']==239
        assert len({s['layout'] for s in row['graphics']['snapshots']})==2
        # Transition means are useful; retain no redundant per-frame ledger
        # for this lifetime/oracle test or unmeasured host I/O duration.
        row.pop('active_costs')
    tests=[]
    for name,count in [('tests',495),('components',94)]:
        log=(ROOT/f'references/build/issue42-integrate-{name}.log').read_text()
        assert re.search(r'Ran '+str(count)+r' tests',log) and '\nOK' in log
        tests.append(dict(suite=name,tests=count,passed=True,skipped=int(name=='components')))
    module_log=ROOT/'references/build/issue42-integrate-module.log'
    assert '"passed": true' in module_log.read_text()
    retained=[]
    for name in ['compact-game','compact-megaram-dos-768','compact-megaram-basic-768','disk-dos-4096','disk-basic-4096']:
        d=read(ROOT/'references/sessions'/name/'report.json')
        if name.startswith('disk-'):assert d['artifact_sha256']==baseline['disk']['disk_image_sha256']
        else:assert d['graphics']['passed'] and d['rom_sha256']==baseline['hashes']['MegaRAM' if 'megaram' in name else 'ASCII8']
        retained.append(dict(case=name,result=d))
    memory=[dict(segments='0',owner='Page3 native state, stack, IRQ, packet dispatcher'),
            dict(segments='1',owner='Main Page0 helpers, cache metadata, navigation, active audio/decor/turbo workers'),
            dict(segments='2..3',owner='Expanded mutable world maps'),dict(segments='4..5',owner='Expanded on/off flag caches'),
            dict(segments='6',owner='Resident full-game code'),dict(segments='7',owner='Original native core'),
            dict(segments='8',owner='PSG worker'),dict(segments='9',owner='Decorations and labels'),
            dict(segments='10',owner='UI/attract; temporary cold raw owner'),dict(segments='11..18',owner='64 packed HUD phase records'),
            dict(segments='19',owner='Current family eight edge records'),dict(segments='20..30',owner='Eleven complete packet-code closures'),
            dict(segments='31',owner='Position-independent ring and current terrain permissions')]
    source_names=['scripts/mapper512_integrate.py','scripts/mapper512_integrated_verify.py','scripts/mapper512_integrated_report.py',
                  'scripts/mapper512_workbook.mjs','scripts/mapper512_backend.py','scripts/compact_transfer.py','scripts/compact_game_build.py',
                  'tests/test_mapper512_integration.py','src/screen4/modules/contracts.json','src/toolchain/screen4/targets.mk']
    report=dict(status='Full-game512KiB RAM-active integration measured; standalone DOS/BASIC edition NOT qualified',
        reference_rom_sha256=manifest['reference_rom_sha256'],program=manifest,memory=memory,
        public_artifacts=baseline['artifacts'],preserved_startup_checks=retained,tests=tests,historical_module_layout_passed=True,
        comparisons=comparisons,f10_family_transitions=transitions,
        static_proofs=dict(ordered_production_packet_references=4384,linked_closure_entries=sum(r['closure_checks'] for r in manifest['stages']),
                          allocation='Declared live masks reject all overlapping source fields, including FF payloads. All32 actual segments are owned; no spare hot segment.'),
        timing=dict(machine='Panasonic_FS-A1WSX_NR512',emulator='openMSX22',cpu='Automatic Panasonic Z80 acceleration scopes; base3.579545MHz, accelerated5.369317MHz',
                    reference_hz=3579545,video='128KiB VRAM, SCREEN4 gameplay, NTSC59.922743Hz; real IRQ and sprite limits, strict VDP callbacks',
                    workload='360 presentations/route, keyboard credit/start/F5 to rounds5/10/13, seed1234 before start; HUD and audio enabled. Independent presentation-clock and native-tick-clock direction schedules.',
                    work='Inclusive GameTurbo_Loop to wait_blank in elapsed guest time x3579545; synchronization excluded. Never R800 instruction cycles.',
                    calls_per_presented_frame=1,self_cycles=None,
                    synchronization='Period includes work, wait and commit. Work excludes wait; period-work is not a measured VBlank/commit breakdown.',
                    remaining_budget='Two-refresh elapsed target approximately119470 reference cycles. No measured drawing/VBlank reserve; do not subtract an assumed5000-cycle reserve as hardware evidence.',
                    limits='Route aggregates differ when cadence changes sampled inputs/native grouping. Native-clock scheduling reduces this mismatch without forcing ticks. Presentation-clock three-enemy route is0.24% slower in FPS; retained explicitly. No universal speedup or complete no-regression qualification.'),
        audio='Original PSG worker stays resident and immutable apart from link operands. All14 PSG registers match in paired samples. No audio waveform/listening or exhaustive event-sequence acceptance.',
        preserved_timing=dict(ledger_sha256=digest(ROOT/'docs/measurements/timing/cycle-ledger.json'),workbook_sha256=digest(ROOT/'docs/cycle-budget.xlsx'),
                              scope='Canonical F10-enabled744KiB cartridge timing remains unchanged. Experimental512KiB results have a separate ledger/workbook.'),
        source_files={n:digest(ROOT/n) for n in source_names},
        decision='Keep public ROM and both disk packages unchanged. Continue independent cold-loader/OS-lifetime work; do not promote or publish this host-assisted integration.',
        limits=['Cartridge/bootstrap plus host-filled cold provider; no standalone512KiB executable.',
                'Hot images are four alternative512KiB layouts with six placeholder work segments, not four runnable ROMs or installed OS reservations.',
                'Cold F5 transitions exercise all four family boundaries but are not naturally earned full-course clears.',
                'OS snapshots, directory, disk I/O, allocator, initial boot atlas and cold scratch peak are unresolved. Ring31 is hot and cannot be counted as a scratch segment.',
                '64KiB cartridge and MegaRAM768KiB remain supported separately;512KiB main-mapper requires no MegaRAM but is not yet delivered.',
                'Broader two-player/attract/restart lifecycle, PAL50, other CPUs, long routes, human audio/perception and physical hardware remain unqualified.',
                'No commit, push, merge or release.'])
    timing=ROOT/'docs/measurements/timing/mapper512-integrated.json'
    timing.write_text(json.dumps(report,indent=2)+'\n')
    summary=json.loads(json.dumps(report))
    for comparison in summary['comparisons']:
        for variant in ['control','candidate']:comparison[variant].pop('active_costs')
    summary['frame_ledger']='docs/measurements/timing/mapper512-integrated.json'
    target=ROOT/'docs/measurements/cartridge/issue42-512-integrated.json'
    target.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(report=str(target.relative_to(ROOT)),native_matched=sum(r['matched']['count'] for r in comparisons if r['input_clock']=='native'),
                          all_matched=sum(r['matched']['count'] for r in comparisons),transitions=len(transitions),status=report['status']),indent=2))


if __name__=='__main__':main()
