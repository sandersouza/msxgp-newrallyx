"""Reuse the production real-keyboard corner/rollover regression for SCREEN4."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from src.toolchain.msx.emulator import reference_machine,tcl
from src.toolchain.msx.stage_one import acquire,cells_from_rom


def verify(bundle,frames):
    from session_reference import configure
    configure(bundle)
    bundle=Path(bundle).resolve();out=Path(tempfile.mkdtemp(prefix='steering-proof-',dir=bundle))
    rom=(cartridge_path(bundle)).read_bytes();(out/'measured.rom').write_bytes(rom)
    syms={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    program,_=acquire(ROOT)
    board=b''.join(cells_from_rom(program,0x30+i) for i in range(4));(out/'board.bin').write_bytes(board)
    script=(ROOT/'src/toolchain/msx/steering_probe.tcl').read_text()
    seed=int(os.environ.get('NRX_STEERING_SEED','12345'))
    script=script.replace('set seed 12345',f'set seed {seed}')
    script=script.replace('after time 600',f'after time {max(600,round(frames/59.92*2))}')
    script=script.replace('puts stderr "Wall stress timeout"', 'puts stderr "Wall stress timeout PC=[reg PC] SP=[reg SP] CPU=[get_active_cpu] IM=[reg IM] I=[reg I] phase=$::phase n=$::n games=$::games state=[debug read memory 0xc7d0] ready=[debug read memory 0xc7dd]"')
    script=script.replace('source @MAPPER@\nnrallyx_reference_machine "Panasonic_FS-A1WSX"',reference_machine(ROOT,'Panasonic_FS-A1WSX'))
    script=script.replace('set z80_freq_locked false','set z80_freq_locked true')
    # The SCREEN4 loop does not expose the production present-state byte.
    script=script.replace('debug set_watchpoint write_mem 0xc000 {$wp_last_value==2}',
        f'debug set_bp {syms["clock_irq"]} {{[debug read memory 0xc7d0]==0}}')
    script=script.replace('@AFTER_ROCK@',str(syms['Flag_Update']))
    script=script.replace('if {$::n>=1 && $::n<=32}', 'if {0}')
    # Assert priority when the input is actually published, every two refreshes.
    # Flag_Update can reuse an earlier sample and is not an input latch.
    script+='\ndebug set_watchpoint write_mem 0xe3f0 {$::phase eq "game" && $::n>=1 && $::n<=32} {set q [expr {(~$wp_last_value)&60}];if {$q!=$::expected_direction} {puts stderr "Newest keyboard direction lost priority";exit 2};incr ::keys_checked}\n'
    script=script.replace('[string index $::board $a]', '[string index $::board [expr {([debug read memory 0xe28f]&3)*1792+$a}]]')
    script='\n'.join(line for line in script.splitlines() if not line.startswith(('debug set_watchpoint write_mem 0xc03c','debug set_bp @SHOW_SCENE@')))
    for key,value in dict(BIOS=tcl(ROOT/'references/msxbios'),ROM=tcl(out/'measured.rom'),OUTPUT=tcl(out),SMOKE_STRESS='1').items():
        script=script.replace('@'+key+'@',value)
    script=script.replace('$::n>=16000',f'$::n>={frames}')
    from session_turbo_contract import setup as turbo_setup
    script+=turbo_setup(syms,out,io=False)
    from session_auto_contract import setup as auto_setup
    script+=auto_setup(syms,out)
    (out/'steering.tcl').write_text(script)
    with (out/'openmsx.log').open('w') as log:
        run=subprocess.run(['openmsx','-script',str(out/'steering.tcl')],timeout=300,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    complete=out/'summary.tsv'
    report=dict(passed=run.returncode==0 and complete.exists(),requested_active_refreshes=frames,input_seed=seed,rom_sha256=hashlib.sha256(rom).hexdigest(),path=str(out),
        scope='Real keyboard rollover/reversals and Space smoke; no native RAM writes; HUD and sprite limits enabled; native contact cell checked against the selected original maze')
    if complete.exists():
        report['observed']=list(map(int,complete.read_text().split()))
        report['passed'] &= report['observed'][4]>=16
        rows=[list(map(int,line.split())) for line in (out/'movement.tsv').read_text().splitlines()]
        report['distinct_poses_after_refresh5000']=len({tuple(row[4:8]) for row in rows if row[0]>5000})
        if frames>5000:report['passed'] &= report['distinct_poses_after_refresh5000']>=100
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));print((out/'openmsx.log').read_text()[-1000:])
    return 0 if report['passed'] else (run.returncode or 2)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/build/game');p.add_argument('--frames',type=int,default=16000)
    a=p.parse_args();raise SystemExit(verify(a.bundle,a.frames))
