"""Keep compact exact-artifact lifecycle results; raw emulator data is disposable."""
import csv
import hashlib
import json
from pathlib import Path
import struct
from compact_game_build import symbols
from compact_game_report import distribution
from disk_package import decompress_bank

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'references/build/game-mapper512-game'
DOCS=ROOT/'docs/measurements'
sha=lambda data:hashlib.sha256(data).hexdigest()


def build():
    plan=json.loads((BASE/'plan.json').read_text())
    reports=[]
    for p in BASE.glob('*/lifecycle-report.json'):
        d=json.loads(p.read_text())
        if d['resource_sha256']==plan['resource_sha256'] and d['bridge_sha256']==plan['bridge_sha256']:reports.append((p,d))
    cases=[(m,'completion',n,n==2) for m in ['dos','basic'] for n in [2,3,4,7,8,11,12,15,16]]
    cases += [(m,'gameover',2,False) for m in ['dos','basic','rom512']]
    cases += [('rom512','completion',2,True),('rom512','completion',3,False)]
    matrix=[]
    for mode,scenario,n,reset in cases:
        matches=[(p,d) for p,d in reports if (d['mode'],d['scenario'],d['native_round'],d['reset_check'])==(mode,scenario,n,reset)]
        assert matches,('Missing lifecycle case',mode,scenario,n,reset)
        p,d=max(matches,key=lambda item:item[0].stat().st_mtime_ns)
        assert d['graphics']['passed'] and d['opening']['passed']
        event={e['event']:e for e in d['lifecycle']}
        if scenario=='completion':
            wait=event['fuel_bonus']['seconds']-event['settlement']['seconds']
            assert 1.65<wait<2.0 and event['next_stage']['flags']==0
            assert event['settlement']['fuel']==event['fuel_bonus']['fuel']>0
            assert event['next_stage']['fuel']==15360
            assert not event['fuel_bonus']['music']&32 and event['settlement']['score']==event['fuel_bonus']['score']
            assert event['native_next_round']['fuel']==0
        else:
            assert event['game_over']['music']&4
            assert event['title_after_game_over']['music']==0
        matrix.append({k:d[k] for k in ['mode','scenario','native_round','f10','reset_check','active_frames','immutable_live_bytes_checked','verification_script_sha256','lifecycle_sha256','diagnostic_contact_writes','lifecycle']})
        matrix[-1].update(graphics_snapshots=len(d['graphics']['snapshots']),opening_states=d['opening']['frames'],
                          opening_cadence_error_max=d['opening']['publication_tick_error_max'],
                          opening_pixels_sha256=sha(''.join(d['opening']['frame_sha256']).encode()))
        if mode=='rom512':matrix[-1]['carrier_sha256']=d['carrier_sha256']
    # Compare complete decoded resources with the previous exact package. Its
    # original directory is retained inside COM, rather than assuming current
    # stream offsets fit an older compressed file.
    old_hash='f9251378356627f321524aef423cec272d24240de4fc49b0801556e712296414'
    control=ROOT/'references/build/game-mapper512-lifecycle-control/files/NRX512.DAT'
    sources=list(BASE.glob('*/files/NRX512.DAT'))+([control] if control.exists() else [])
    source=next(p for p in sources if sha(p.read_bytes())==old_hash)
    old=source.read_bytes();bridge=(source.parent/'NRX512.COM').read_bytes()[-11756:]
    assert sha(bridge)=='40fc063fa685ec34538f064895015bbfa5c33b741d0444bdb5b17f80462e76d5'
    s=symbols(BASE/'mapper512-cold.asm.sym');raw=(BASE/'files/NRX512.DAT').read_bytes();changes=[]
    for i,r in enumerate(plan['records']):
        bank,length,checksum,at=struct.unpack_from('<BHHI',bridge,s['Cold_Resources']-0x5000+i*9)
        assert bank==r['bank'];before=decompress_bank(old[at:at+length]);assert sum(before)&65535==checksum
        after=decompress_bank(raw[r['offset']:r['offset']+r['compressed']])
        offsets=[j for j,(a,b) in enumerate(zip(before,after)) if a!=b]
        if offsets:changes.append(dict(resource=i,kind=r['kind'],bank=bank,changed_bytes=len(offsets),offsets=offsets))
    assert {(r['kind'],r['bank']) for r in changes}=={('hot',6),('boot',153)}
    helper=symbols(ROOT/'references/build/game-mapper512-game-runtime/lab.sym')['Mapper512_ResumeVideo']-0x4000
    hot=next(r for r in changes if r['kind']=='hot');assert hot['offsets']==list(range(helper,helper+13))
    assert next(r for r in changes if r['kind']=='boot')['changed_bytes']==5
    current_symbols=symbols(ROOT/'references/build/game-mapper512-game-runtime/lab.sym')
    control_symbols=ROOT/'references/build/game-mapper512-lifecycle-control-runtime/lab.sym'
    previous_symbols=symbols(control_symbols if control_symbols.exists() else ROOT/'references/build/game-mapper512-sync-baseline-runtime/lab.sym')
    assert all(current_symbols[k]==v for k,v in previous_symbols.items())
    # All production renderer, source, native and sound resources are identical.
    # The only new resident bytes fill old FF tail padding for a cold-only call.
    performance=[];prior=json.loads((DOCS/'timing/mapper512-audio-sync.json').read_text())
    for mode in ['dos','basic']:
        for n in [5,10,13]:
            matches=[]
            for p in BASE.glob('*/report.json'):
                d=json.loads(p.read_text())
                if d.get('resource_sha256')==plan['resource_sha256'] and d.get('frames')==360 and d.get('profile_audio') and d.get('mode')==mode and d['native_round']==n:matches.append((p,d))
            p,d=max(matches,key=lambda item:item[0].stat().st_mtime_ns)
            rows=list(csv.DictReader((p.parent/'frames.tsv').open(),delimiter='\t'));active=[r for r in rows if r['active']=='1']
            control=next(v['candidate'] for v in prior['performance'] if v['mode']==mode and v['round']==n)
            item={k:d[k] for k in ['mode','native_round','frames','active_frames','work','period','verification_script_sha256']}
            item.update(enemies=sorted({int(r['enemies']) for r in active}),presented_fps=3579545/d['period']['mean'],
                audio_calls_per_present=distribution(float(r['audio_calls']) for r in active),
                audio_inclusive=distribution(float(r['audio_cost']) for r in active),
                audio_without_irq=distribution(float(r['audio_cost'])-float(r['audio_irq_cost']) for r in active),
                irq_inclusive=distribution(float(r['irq_cost']) for r in active),
                work_without_audio_irq=distribution(float(r['work'])-float(r['audio_cost'])-float(r['irq_cost'])+float(r['audio_irq_cost']) for r in active),
                work_budget_remaining=distribution(119472-float(r['work']) for r in active),
                publish_tail_and_wait=distribution(float(r['period'])-float(r['work']) for r in active),
                trace_sha256=sha((p.parent/'frames.tsv').read_bytes()),
                historical_work_delta={k:d['work'][k]-control['work'][k] for k in ['mean','p95','max']})
            performance.append(item)
    pcm=[]
    runtime=ROOT/'references/build/game-mapper512-game-runtime'
    for mode in ['dos','basic']:
        matches=[]
        for p in runtime.glob('audio-proof-*/report.json'):
            d=json.loads(p.read_text())
            if d.get('mode')==mode and d.get('resource_sha256')==plan['resource_sha256']:matches.append((p,d))
        p,d=max(matches,key=lambda item:item[0].stat().st_mtime_ns);assert d['passed']
        pcm.append(dict(mode=mode,passed=True,report_sha256=sha(p.read_bytes()),scope=d['scope']))
    seals=[]
    for path,wanted in [('dist/newrallyx.rom','44be6037d05ebf763283f14ef6deb6e4a8bd58b0a25fcc04c693d899c3704f00'),
                         ('dist/compact/megaram/newrallyx-megaram.zip','ed50647304f1d647f1161a85f36f487129506cd76e3abdcecb8122ebf2c8768d'),
                         ('dist/disk/newrallyx-disk.zip','fca5d77ade0bc83156e37279c8968f6108e762ccb128f651c8e54741d3668428'),
                         ('docs/cycle-budget.xlsx','c19093e1953486e3b30108fceae49f2507381a2330668df77aa313befdb5d7cd')]:
        data=(ROOT/path).read_bytes();assert sha(data)==wanted;seals.append(dict(path=path,bytes=len(data),sha256=wanted))
    carrier=json.loads((ROOT/'dist/experimental/mapper512/manifest.json').read_text())
    assert sha((ROOT/carrier['rom']).read_bytes())==carrier['rom_sha256']
    assert all(r.get('carrier_sha256',carrier['rom_sha256'])==carrier['rom_sha256'] for r in matrix)
    rom_runs=[]
    for p in BASE.glob('rom512-r13-f101-*/report.json'):
        d=json.loads(p.read_text())
        if d.get('carrier_sha256')==carrier['rom_sha256'] and d.get('transitions') and d['frames']==360:rom_runs.append((p,d))
    p,rom_run=max(rom_runs,key=lambda item:item[0].stat().st_mtime_ns)
    test_rom=dict(passed=True,frames=rom_run['frames'],round=rom_run['native_round'],transitions=rom_run['transitions'],
        graphics=rom_run['graphics']['passed'],opening=rom_run['opening']['passed'],immutable_live_bytes_checked=rom_run['immutable_live_bytes_checked'],
        observer_sha256=rom_run['verification_script_sha256'],carrier_sha256=rom_run['carrier_sha256'],scope='Actual carrier path, boot and real F5 advances through all four cold families to round13, then13->14. Distinct from natural ten-flag completion.')
    preservation=[]
    for name in ['compact-game','compact-megaram-dos-768','compact-megaram-basic-768','disk-dos-4096','disk-basic-4096']:
        p=ROOT/'references/sessions'/name/'report.json';d=json.loads(p.read_text())
        if 'graphics' in d:assert d['graphics']['passed']
        preservation.append(dict(case=name,report_sha256=sha(p.read_bytes()),observed={k:v for k,v in d.items() if k!='graphics'},
                                 graphics_passed=d.get('graphics',{}).get('passed'),scope='Fresh supported-format regression/smoke observer; retains its own original scope, not512KiB qualification.'))
    result=dict(status='Experimental lifecycle continuation;23 cases pass, no release or unconditional performance promotion.',
        candidate={k:plan[k] for k in ['resource_bytes','resource_sha256','bridge_bytes','bridge_sha256','files']},
        carrier=carrier,matrix=matrix,test_rom=test_rom,resource_delta=changes,existing_symbol_values_preserved=len(previous_symbols),performance=performance,pcm=pcm,seals=seals,preservation=preservation,
        cycle_ledger=dict(cpu_hz=3579545,refresh_hz=59.922743,two_refresh_budget_cycles=119472,
            workload='Six360-presentation native-clock keyboard routes, rounds5/10/13 with3/5/6 enemies, HUD/sound and real sprite limits, actual512KiB DOS1/BASIC boot.',
            method='Main-loop entry to wait_blank: inclusive work once per presented frame. Matched SP/PC sound returns and IRQ spans separate overlap; subtract shared audio IRQ only once. Publish tail/wait is not a pure synchronization wait. No parent/child inclusive addition.',
            vblank='Full refresh, two-refresh presentation budget and VBlank are distinct. Usable VBlank remains unmeasured;5000-cycle reserve is a planning assumption.'),
        limits=['No physical hardware, PAL50 or subjective listening acceptance.',
                'Completion uses ten controlled two-byte cell-contact probes, not a full keyboard course; all following native settlement/bonus/challenge/cold transitions execute without injected code or state forcing.',
                'Diagnostic ASCII8 ROM requires512KiB main mapper and replaces only cold resource transport. Actual DOS1/BASIC matrix runs have no cartridge and perform real filesystem reads; DOS2/Nextor unqualified.',
                'All preexisting active instructions/native/audio/source resources are unchanged. Historical aggregate cost deltas include unchanged/slower cases and are not a matched trajectory speedup or proof that the prior0.24percent route concern is closed.',
                'Canonical744KiB ROM remains64KiB-compatible; no512KiB-cartridge-on64KiB claim. MegaRAM and legacy executables remain byte-identical.'])
    text=json.dumps(result,indent=2)+'\n'
    for p in [DOCS/'cartridge/issue42-512-lifecycle.json',DOCS/'timing/mapper512-lifecycle.json']:p.write_text(text)
    print(json.dumps(dict(cases=len(matrix),graphics_snapshots=sum(r['graphics_snapshots'] for r in matrix),candidate=result['candidate'],rom=carrier['rom_sha256'],changed_resources=changes),indent=2));return result


if __name__=='__main__':build()
