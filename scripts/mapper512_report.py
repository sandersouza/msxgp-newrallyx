"""Consolidate512KiB component evidence without changing default timing/artifacts."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from disk_package import compress_bank


def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def compressed_size(raw):
    """Reference cold-stream estimate, including4-byte bank length/checksum headers."""
    return sum(len(compress_bank(raw[i:i+16384].ljust(16384,b'\xff')))+4 for i in range(0,len(raw),16384))


def main():
    baseline=read(ROOT/'docs/measurements/cartridge/issue42-768-qualified.json')
    for name,expected in baseline['artifacts'].items():assert digest(ROOT/name)==expected['sha256']
    assert all(digest(ROOT/name)==expected for name,expected in baseline['source_files'].items())
    directory=ROOT/'references/build/game-mapper512'
    allocation=read(directory/'analysis.json')
    reports={v:read(directory/('proof-'+v)/'report.json') for v in ('compact','hoisted')}
    for v,d in reports.items():
        assert d['passed'] and d['main_ram_kib']==512 and d['packet_references']==4384 and d['executions']==26304 and d['strict_vram_callbacks']==0
        assert d['reference_rom_sha256']==baseline['hashes']['ASCII8'] and d['variant']==v
    bundle=ROOT/'references/build/game-compact-runtime';rom=(ROOT/'dist/newrallyx.rom').read_bytes();layout=read(bundle/'layout.json')
    raw_owners=[]
    for bank,page in layout['raw_bank_pages'].items():
        if int(bank) in (0,71,73):continue
        raw=rom[page*8192:page*8192+16384]
        raw_owners.append(dict(logical_bank=int(bank),expanded_bytes=16384,reference_lz_bytes=compressed_size(raw),sha256=hashlib.sha256(raw).hexdigest()))
    source=ROOT/'references/build/game';original=(source/'newrallyx.rom').read_bytes();session=read(source/'session-build.json')
    maps=[]
    for bank in session['map_banks']:
        raw=original[bank*16384:(bank+1)*16384]
        maps.append(dict(logical_bank=bank,expanded_bytes=16384,reference_lz_bytes=compressed_size(raw),sha256=hashlib.sha256(raw).hexdigest()))
    page,address=layout['atlas_table'];at=page*8192+address-0xa000;pointer_table=rom[at:at+layout['atlas']['pointer_bytes']]
    tiles=set()
    for i in range(0,len(pointer_table),3):
        page=pointer_table[i];a=int.from_bytes(pointer_table[i+1:i+3],'little');at=page*8192+a-0xa000;tag=rom[at]
        size=33 if tag==255 else 1 if tag>=192 else 9 if tag&64 else 17
        tiles.add(rom[at:at+size])
    assert sum(map(len,tiles))==layout['atlas']['tile_bytes']
    commands=[]
    for index in range(71):
        page,a=layout['boot_pointers'][str(index)];at=page*8192+a-0x8000;size=2+2*int.from_bytes(rom[at:at+2],'little');commands.append(rom[at:at+size])
    assert sum(map(len,commands))==layout['atlas']['command_bytes']
    luts=(bundle/'assembly/compact-atlas-luts.bin').read_bytes()
    atlas=b''.join(sorted(tiles))+pointer_table+luts+b''.join(commands)
    cold=dict(raw_owner_reference_bytes=sum(x['reference_lz_bytes'] for x in raw_owners),
        expanded_map_reference_bytes=sum(x['reference_lz_bytes'] for x in maps),atlas_reference_lz_bytes=compressed_size(atlas),atlas_bytes=len(atlas),
        ring_worker_bytes=1934,raw_owners=raw_owners,maps=maps,
        limits='Reference bytes/compressor, not a linked512KiB cold format or a minimum-size proof. Raw72/74 are treated as cold; restart must cache its8 bytes. Bootstrap/decode/IRQ/metadata adaptation and overlapping lifetimes are unimplemented.')
    cold['reference_bytes']=sum(cold[k] for k in ('raw_owner_reference_bytes','expanded_map_reference_bytes','atlas_reference_lz_bytes','ring_worker_bytes'))
    budgets=[]
    for variant in ('compact','hoisted'):
        a=allocation[variant+'_suffix'];n=a['code_windows']
        workers=n*(385+(a['header_workers']*24 if variant=='compact' else 0))
        live=160041+a['code_live_bytes']+workers+3*16384
        for work in (4,6):
            total=live+work*16384+cold['reference_bytes']
            budgets.append(dict(variant=variant,work_segments=work,cache_policy='Existing64KiB tier' if work==4 else 'Current expanded tier selected on512KiB',
                provisional_bytes_including_reference_cold=total,margin_512k=524288-total,
                fixed_segment_bytes=(12+n+3+work)*16384,live_source_code_worker_and_hot_owner_bytes=live,
                limits='Optimistic pooling into every declared source/code hole; excludes new dispatch/IRQ/decode/directory/staging overhead and does not establish feasible initialization lifetimes.'))
    tests=[]
    for kind,count in [('tests',486),('components',94)]:
        log=(ROOT/f'references/build/issue42-512-{kind}.log').read_text()
        assert re.search(r'Ran '+str(count)+r' tests',log) and '\nOK' in log
        tests.append(dict(suite=kind,passed=True,tests=count,skipped=1 if kind=='components' else 0))
    preserved=[]
    for name in ('compact-game','compact-game-ram512','compact-megaram-dos-768','compact-megaram-basic-768','disk-dos-4096','disk-basic-4096'):
        d=read(ROOT/'references/sessions'/name/'report.json')
        if name.startswith('disk-'):assert d['artifact_sha256']==baseline['disk_manifest']['disk_image_sha256']
        else:
            assert d['frames']==300 and d['graphics']['passed']
            assert d['rom_sha256']==baseline['hashes']['MegaRAM' if 'megaram' in name else 'ASCII8']
        preserved.append(dict(case=name,result=d))
    ram=(ROOT/'references/sessions/compact-game-ram512/final.ram').read_bytes()
    p3=int(re.search(r'p3=(\d+)',(directory/'proof-hoisted/output.log').read_text())[1])
    segments=list(ram[0xc0d0:0xc0d4])+[ram[0xc0f7],p3]
    assert ram[0x7e2]==1 and len(set(segments))==6
    cache=dict(expanded=True,work_segments=segments,count=6,scope='Read-only unchanged-ROM512KiB startup snapshot; Page3 mapper identity also observed at packet bootstrap.')
    assert '"passed": true' in (ROOT/'references/build/issue42-512-module-layout.log').read_text()
    authored=['scripts/mapper512_backend.py','scripts/mapper512_verify.py','scripts/mapper512_report.py','tests/test_mapper512_backend.py','src/screen4/modules/contracts.json']
    result=dict(status='Experimental component backend; complete512KiB executable not delivered or qualified',
        reference_rom_sha256=baseline['hashes']['ASCII8'],configuration=dict(machine='Panasonic_FS-A1WSX_NR512',ram_kib=512,video='SCREEN4 display on,128KiB VRAM, real VDP timing',cpu_hz=3579545,
            emulator=subprocess.check_output(['openmsx','-v'],text=True).strip(),vdp_irq_generation=False,calls_per_presented_frame='Not measured: isolated fixtures, not gameplay FPS'),
        allocation=allocation,execution=reports,cold_reference=cold,provisional_ram_budgets=budgets,tests=tests,current_expanded_cache=cache,
        preserved_startup_checks=preserved,module_layout_passed=True,
        default_preserved=dict(artifacts=baseline['artifacts'],source_files_verified=len(baseline['source_files']),
            symbol_sha256=digest(bundle/'lab.sym'),timing_ledger_sha256=digest(ROOT/'docs/measurements/timing/cycle-ledger.json'),
            timing_workbook_sha256=digest(ROOT/'docs/cycle-budget.xlsx'),scope='Byte-identical744KiB public ROM, both disk packages and default source implementation. Existing whole-game evidence remains bound to its original hash; no512KiB whole-game/audio claim.'),
        source_files={name:digest(ROOT/name) for name in authored},
        decision='Do not promote either512KiB prototype. Preserve744KiB/768KiB as the stable fallback. The owner requested no release yet; current component failures do not establish that all512KiB designs are impossible or trigger a merge/release.')
    target=ROOT/'docs/measurements/cartridge/issue42-512-backend.json';target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],budgets=budgets,cold_reference_bytes=cold['reference_bytes'],default_unchanged=True),indent=2));return result


if __name__=='__main__':main()
