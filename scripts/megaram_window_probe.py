"""Synthetic MegaRAM bank/write-mode test, not a game acceptance test."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.toolchain.msx.emulator import reference_machine,tcl


def extension_setup(out, size, name):
    """Build a private extension from the running emulator's system data."""
    extensions=out/'userdata/extensions'
    extensions.mkdir(parents=True,exist_ok=True)
    return f'''set stream [open [file join $::env(OPENMSX_SYSTEM_DATA) extensions MegaRAM.xml] r]
set definition [read $stream];close $stream
if {{[string first {{<size>512</size>}} $definition]<0}} {{error "Unsupported MegaRAM extension schema"}}
set definition [string map [list {{<size>512</size>}} {{<size>{size}</size>}} {{primary slot="any"}} {{primary slot="1"}}] $definition]
set stream [open {tcl(extensions/(name+'.xml'))} w];puts $stream $definition;close $stream
ext {name}
'''


def run(size=1024):
    out=ROOT/'references/build/game-issue41-megaram'
    out.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo',
        '--sym=probe.sym',str(ROOT/'tests/fixtures/issue41-megaram-smoke.asm')],cwd=out,check=True,capture_output=True)
    syms={n:int(v,16) for n,v in re.findall(r'(?m)^(\w+): EQU 0x([\da-fA-F]+)',(out/'probe.sym').read_text())}
    script=f'''set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
{extension_setup(out,size,'MegaRAM_1MB_probe')}
reset
set started 0
debug set_bp {syms['Passed']} {{$::started}} {{puts stderr "PASS: independent MegaRAM banks0/64/127; write mode and mapping mode";exit}}
debug set_bp {syms['Failed']} {{$::started}} {{puts stderr "FAIL: MegaRAM banks alias or write/read differs";exit 2}}
after time 10 {{set ::started 1;debug write_block memory 0xc100 [binary format H* {(out/'probe.bin').read_bytes().hex()}];reg PC 0xc100}}
after time 20 {{puts stderr "TIMEOUT";exit 3}}
'''
    (out/'probe.tcl').write_text(script)
    env=dict(os.environ,NRX_REFERENCE_RAM_KIB='64',OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    result=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],env=env,capture_output=True,text=True,timeout=45)
    if size==512:
        assert result.returncode==2 and 'FAIL:' in result.stderr,result.stderr
        print('Negative control passed:512KiB aliases bank64 onto bank0.')
        return
    assert result.returncode==0 and 'PASS:' in result.stderr,result.stderr
    report=dict(system_mapper_kib=64,megaram_kib=1024,banks_checked=[0,42,64,127],
        lower_and_upper_8k_windows_independent=True,negative_512k_control=True,
        passed=True,scope='Synthetic emulator I/O and bank independence only; not a game loader, physical hardware, or timing qualification',
        source_reference='https://github.com/openMSX/openMSX/blob/master/src/memory/MSXMegaRam.cc')
    (ROOT/'docs/measurements/cartridge/issue41-megaram-probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print(result.stderr[-1200:])


if __name__=='__main__':
    run(512)
    run(1024)
