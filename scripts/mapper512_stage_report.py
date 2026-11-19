"""Consolidate cold-stage experiments without promoting unqualified RAM builds."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from mapper512_backend import prepare,pack_record,absolute_programs,flat_windows,suffix_windows,table_layout
from disk_package import compress_bank
from mapper512_rank import ranking_basis


def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def compressed(raw):
    return sum(len(compress_bank(raw[i:i+16384].ljust(16384,b'\xff')))+4 for i in range(0,len(raw),16384))


def main():
    baseline=read(ROOT/'docs/measurements/cartridge/f10-qualified.json')
    for name,info in baseline['artifacts'].items():assert digest(ROOT/name)==info['sha256']
    for name,sha in baseline['source_files'].items():assert digest(ROOT/name)==sha
    bundle=ROOT/'references/build/game-compact-runtime';sha=baseline['hashes']['ASCII8']
    cases,records,packed=prepare();absolute_programs(cases,records)
    results={name:read(ROOT/'references/build/game-mapper512'/('proof-'+name)/'report.json') for name in ['absolute','absolute-flat']}
    for name,data in results.items():
        assert data['passed'] and data['reference_rom_sha256']==sha and data['variant']==name
        assert data['executions']==26304 and data['strict_vram_callbacks']==0
    assert results['absolute-flat']['packet_delta_cycles']['slower']==0
    overlay=read(ROOT/'references/build/game-mapper512-stage/report.json')
    assert overlay['passed'] and overlay['reference_rom_sha256']==sha
    # Metadata-only family specialization. Every retained old live byte has an
    # explicit new location; no padding is inferred from pixel values.
    ranks=b''.join(bytes(record['data'][0x800+layout*256:0x841+layout*256]) for record in records[:64] for layout in range(4))
    assert len(ranks)==16640
    direct_ranking_backing=compressed(ranks)
    ranking_backing=compressed(ranking_basis(records))
    assert ranking_backing==overlay['ranking_basis_lz_bytes']+4
    stage_sources=[]
    for layout in range(4):
        active=list(range(64))+list(range(64+layout*8,72+layout*8))
        staged=[pack_record(records[i],ranking_layout=layout) for i in active]
        live=sum(sum(p[1]) for p in staged)
        assert sum(sum(packed[i][1]) for i in active)-live==12480
        for i,(data,busy,locations) in zip(active,staged):
            for old,new,size in locations:assert data[new:new+size]==records[i]['data'][old:old+size]
            for old,new,size in table_layout(records[i]):
                assert data[new:new+size]==packed[i][0][new:new+size]
        stage_sources.append(dict(layout=layout,active_records=72,fixed_source_segments=9,live_bytes=live,ranking_bytes_reclaimed=12480))
    layout=read(bundle/'layout.json');rom=(ROOT/'dist/newrallyx.rom').read_bytes()
    cold=[];terrain_only=[]
    for bank,page in layout['raw_bank_pages'].items():
        if int(bank) in (0,71,73):continue
        raw=rom[page*8192:page*8192+16384]
        size=compressed(raw);cold.append(dict(logical_bank=int(bank),bytes=size))
        terrain_only.append(compressed(raw[:4096]) if int(bank)==1 else size)
    original=ROOT/'references/build/game';raw=(original/'newrallyx.rom').read_bytes();session=read(original/'session-build.json')
    maps=sum(compressed(raw[b*16384:(b+1)*16384]) for b in session['map_banks'])
    ring=read(original/'ring-refresh.json')['bytes']
    # Full opaque raw owners are retained conservatively. Alternate lifetime
    # removes only bank1's boot-only tail after replay, not its4KiB terrain.
    backing=sum(r['bytes'] for r in cold)+maps+ring+overlay['backing_bytes']+16+ranking_backing+8
    proposed_backing=sum(terrain_only)+maps+ring+overlay['backing_bytes']+16+ranking_backing+8
    allocations=[]
    for mode,linker in [('absolute-suffix',suffix_windows),('absolute-flat',flat_windows)]:
        for family in [None,0,1,2,3]:
            selected=cases if family is None else [c for c in cases if c['record']<64 or (c['record']-64)//8==family]
            windows=linker([c['absolute'] for c in selected]);code=sum(len(w['data']) for w in windows);heads=len(windows)*385
            source_live=max(r['live_bytes'] for r in stage_sources) if family is None else stage_sources[family]['live_bytes']
            # No extra backing is estimated for rebuilding a per-family code
            # graph. Its rows are explicitly incomplete, not fit claims.
            cold_code=overlay['decoder_bytes']+overlay['ranking_code_bytes']
            total=source_live+code+heads+9*16384+backing+cold_code
            proposed_total=source_live+code+heads+9*16384+proposed_backing+cold_code
            allocations.append(dict(variant=mode,layout=family,code_windows=len(windows),code_live_bytes=code,
                helper_bytes=heads,cold_helper_bytes=cold_code,source_live_bytes=source_live,fixed_source_segments=9,work_segments=6,hot_raw_segments=3,
                fixed_physical_bytes=(len(windows)+18)*16384,provisional_live_bytes=total,provisional_margin_512k=524288-total,
                proposed_postboot_lifetime_bytes=proposed_total,proposed_postboot_margin_512k=524288-proposed_total,
                complete_allocation=False,
                missing=['Relinked metadata/bank directory and actual fragment packing','Always-available IRQ/dispatch/decoder and stack lifetimes',
                         'Active UI/decor/terrain permissions cannot be decompressed per frame; their residency is unresolved',
                         'Boot replay versus renderer creation and DOS/BASIC takeover peak',
                         *(['Persistent per-family code reconstruction backing'] if family is not None else [])]))
    tests=[]
    for name,count in [('tests',491),('components',94)]:
        log=(ROOT/f'references/build/issue42-stage-{name}.log').read_text()
        assert re.search(r'Ran '+str(count)+r' tests',log) and '\nOK' in log
        tests.append(dict(suite=name,tests=count,passed=True,skipped=int(name=='components')))
    assert '"passed": true' in (ROOT/'references/build/issue42-stage-module-layout.log').read_text()
    checks=[]
    for name in ['compact-game','compact-game-ram512','compact-megaram-dos-768','compact-megaram-basic-768','disk-dos-4096','disk-basic-4096']:
        data=read(ROOT/'references/sessions'/name/'report.json')
        if name.startswith('disk-'):assert data['artifact_sha256']==baseline['disk']['disk_image_sha256']
        else:
            assert data['frames']==300 and data['graphics']['passed']
            assert data['rom_sha256']==baseline['hashes']['MegaRAM' if 'megaram' in name else 'ASCII8']
        checks.append(dict(case=name,result=data))
    authored=['scripts/mapper512_backend.py','scripts/mapper512_verify.py','scripts/mapper512_stage_verify.py','scripts/mapper512_stage_report.py','scripts/mapper512_rank.py',
              'src/disk/mapper512-stage.asm','src/disk/mapper512-ranking.asm','tests/test_mapper512_backend.py','src/screen4/modules/contracts.json']
    report=dict(status='Cold-stage components qualified; complete512KiB game NOT qualified',reference_rom_sha256=sha,
        owner_constraint='Longer inter-stage preparation is allowed; active gameplay speed and all quality/format requirements remain strict. No release.',
        packet_executions=52608,packet_results=results,cold_overlay=overlay,stage_sources=stage_sources,
        ranking_backing_bytes=ranking_backing,rejected_direct_ranking_backing_bytes=direct_ranking_backing,allocation=allocations,cold_backing=dict(opaque_raw=cold,map_bytes=maps,ring_bytes=ring,
            full_backing_bytes=backing,proposed_boot_tail_discard_backing_bytes=proposed_backing,
            limits='No boot atlas backing after replay in these prospective post-boot counts. Neither post-boot disposal nor reconstruction peak is qualified. Per-family code recipes are excluded and flagged in their rows.'),
        tests=tests,historical_module_layout_passed=True,preserved_startup_checks=checks,default_preserved=dict(artifacts=baseline['artifacts'],symbol_sha256=digest(bundle/'lab.sym'),
            timing_ledger_sha256=digest(ROOT/'docs/measurements/timing/cycle-ledger.json'),timing_workbook_sha256=digest(ROOT/'docs/cycle-budget.xlsx'),
            scope='Byte-identical F10-enabled744KiB ROM and both DOS/BASIC packages. No default runtime source changed. Current active-game timing stays bound to44be6037; new component cycles do not replace it.'),
        component_cycle_ledger=dict(machine='Panasonic_FS-A1WSX_NR512',cpu='Base Z80',cpu_hz=3579545,video='SCREEN4/128KiB VRAM; NTSC59.922743Hz; VDP IRQ generation off',
            reference_rom_sha256=sha,workload='Isolated original packet references and cold overlay/rank fixtures; no active game timing',
            calls_per_presented_frame=None,self_cycles=None,synchronization_waits='None inserted by these fixtures; production IRQ/VDP waits not qualified',
            remaining_gameplay_budget=None,notes='Inclusive packet rows include transfer workers; self costs not separately instrumented. Cold rows include CALL/RET/terminal JP. Never add parent/child costs or interpret them as gameplay FPS.',
            cold_decode_cycles=overlay['transition_cycles'],cold_rank_cycles=overlay['ranking_cycles']),
        source_files={n:digest(ROOT/n) for n in authored},
        decision='Preserve public artifacts. Flat absolute bodies have no added packet cycles, but no full512KiB capacity/performance pass. Suffix bodies add cycles and are not promoted on storage savings. Continue only with measured full-game dispatch/IRQ/native/audio integration; no active decompression or hidden recurring pause.',
        limits='Automated/source and openMSX22 base-Z80/NTSC component evidence. Cartridge-assisted bootstrap, host fixtures and disabled VDP IRQ generation. No physical hardware, PAL50, complete512KiB loader, full-course gameplay or subjective acceptance.')
    target=ROOT/'docs/measurements/cartridge/issue42-stage-overlays.json';target.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(packet_executions=report['packet_executions'],overlay_ms=overlay['transition_ms'],ranking_backing_bytes=ranking_backing,
                         allocations=allocations,status=report['status']),indent=2));return report


if __name__=='__main__':main()
