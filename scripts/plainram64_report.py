"""Record the mandatory fixed64KiB gate without relabeling failures as passes.

Run compact_game_verify with --ram-kind plain separately for ROM and both
MegaRAM launchers. Reports retain zero physical mapper evidence and distinguish
a correct MegaRAM transfer from subsequent native game compatibility.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()


def observe_overwrite():
    """Read before/after the first map copy, then stop before corrupt return.

    Existing real startup, keyboard and slot state are untouched. No code or
    register mutation; retain only hashes/counts when the report consolidates.
    """
    from compact_game_build import symbols
    s=symbols(ROOT/'references/build/game-compact-runtime/lab.sym')
    text=(ROOT/'references/sessions/compact-game-plain64/verify.tcl').read_text()
    text+=f'''
set ::plain_copy 0
debug set_bp {s['GameSession_CopyMap']} {{!$::plain_copy}} {{
 set ::plain_copy 1;set ::before [debug read_block memory 0 2016]
 set ::target [reg C];set ::fc_before [debug read ioports 252];set ::plain_input_sp [reg SP]
}}
debug set_bp {s['GameSession_RestorePage0']} {{$::plain_copy && [reg SP]==$::plain_input_sp-8}} {{
 set after [debug read_block memory 0 2016]
 set f [open references/build/plain64-overwrite.txt w]
 puts $f "target=$::target fc_before=$::fc_before fc_after=[debug read ioports 252] SP=[reg SP] unchanged=[expr {{$::before eq $after}}]"
 puts $f [binary encode hex $::before];puts $f [binary encode hex $after];close $f
 puts stderr "OBSERVED first map overwrote main Page0 with no mapper";exit
}}
'''
    target=ROOT/'references/build/plain64-overwrite.tcl';target.write_text(text)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='64',NRX_REFERENCE_RAM_KIND='plain',
             OPENMSX_HOME=str(ROOT/'references/build/plain64-overwrite-home'),
             OPENMSX_USER_DATA=str(ROOT/'references/build/plain64-overwrite-data'))
    result=subprocess.run(['openmsx','-script',str(target)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0 and 'OBSERVED first map overwrote' in result.stderr,result.stderr


def report():
    rows=[]
    for name,mode in [('compact-game-plain64','rom'),('compact-megaram-dos-768-plain64','dos'),('compact-megaram-basic-768-plain64','basic')]:
        folder=ROOT/'references/sessions'/name
        config=folder/'userdata/machines/Panasonic_FS-A1WSX_PLAIN64.xml'
        tree=ET.fromstring(config.read_bytes());assert tree.find('.//MemoryMapper') is None
        assert tree.find('MapperReadBackBits') is None
        assert tree.find('.//RAM[@id="Main RAM"]/mem').attrib=={'base':'0x0000','size':'0x10000'}
        log=(folder/'output.log').read_text();assert 'Reference plain RAM: 65536 bytes; RAM mapper: 0 bytes' in log
        good='PASS300 gameplay presentations' in log
        if good:
            result=json.loads((folder/'report.json').read_text());assert result['graphics']['passed'] and result['main_mapper_bytes']==0
        else:
            assert 'TIMEOUT start' in log and 'presents=0' in log
        rows.append(dict(mode=mode,compatible=good,main_ram_kib=64,main_ram_kind='plain',main_mapper_bytes=0,
            megaram_kib=768 if mode!='rom' else None,complete_megaram_image_loaded=mode!='rom' and 'LOADED all compact image bytes' in log,
            observed='300 gameplay presentations and independent graphics pass' if good else 'Title/coin/start reached; game fails before any presentation and returns into boot/title code',
            rom_sha256=sha((folder/'measured.rom').read_bytes()),machine_config_sha256=sha(config.read_bytes()),observer_sha256=sha((folder/'verify.tcl').read_bytes()),log_sha256=sha(log.encode())))
    observe_overwrite()
    record=ROOT/'references/build/plain64-overwrite.txt'
    lines=record.read_text().splitlines();before,after=map(bytes.fromhex,lines[1:3])
    assert len(before)==len(after)==2016 and before!=after
    assert lines[0]=='target=1 fc_before=255 fc_after=255 SP=62318 unchanged=0'
    data=dict(status='Mandatory mapperless64KiB cartridge/MegaRAM gate is not met; release blocked.',
        owner_contract=[dict(format='ROM/cartridge',main_ram='64KiB fixed RAM, no RAM mapper; cartridge bank controller allowed'),
                        dict(format='BIN/COM main-mapper edition',main_ram='Compatible standard RAM mapper with required capacity: current experimental512KiB or legacy4MiB'),
                        dict(format='MegaRAM',main_ram='64KiB fixed RAM, no RAM mapper; compatible MegaRAM with required capacity, current target768KiB')],
        cases=rows,root_cause=dict(source='GameSession_CopyMap in generated modules/mapper/page0.inc; scripts/compact_game_build.py',
            mechanism='Cold constructor writes portFC then uses SP4000/PUSH to fill a16KiB world bank at0000..3FFF. On fixed RAM FC writes do not select another bank, overwriting live Page0 code. Runtime world helpers also assume Page0 bank selection, so removing only that constructor is insufficient.',
            observation=lines[0],inspected_main_code_bytes=len(before),changed_main_code_bytes=sum(a!=b for a,b in zip(before,after)),
            before_sha256=sha(before),after_sha256=sha(after),observer_sha256=sha((ROOT/'references/build/plain64-overwrite.tcl').read_bytes()),
            scope='Read-only breakpoints around the first real cold map construction on the exact supported ROM. No code/state/payload injection.'),
        limits=['Reference openMSX FS-A1WSX-derived fixed64KiB RAM topology with no MemoryMapper device; no physical hardware result.',
                'Previous64KiB mapper successes remain true for that distinct hardware profile; they do not establish fixed-RAM compatibility.',
                'The512KiB diagnostic carrier requires512KiB RAM mapper and is separate from the owner-required cartridge target.',
                'No runtime workaround, relaxed performance/graphics/audio/gameplay requirement or release is introduced.'])
    target=ROOT/'docs/measurements/cartridge/issue42-plain64-gate.json';target.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2));return data


if __name__=='__main__':report()
