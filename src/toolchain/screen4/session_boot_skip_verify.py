"""Exercise real keyboard-matrix skip edges and held-key consumption in openMSX."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from src.toolchain.msx.emulator import reference_machine,tcl

def verify(bundle):
    from session_reference import configure
    configure(bundle)
    bundle=Path(bundle).resolve();out=Path(tempfile.mkdtemp(prefix='boot-skip-proof-',dir=bundle))
    shutil.copyfile(cartridge_path(bundle),out/'measured.rom')
    s={n:int(v,16) for n,v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)',(bundle/'lab.sym').read_text())}
    cases=[(r,1,.02) for r in range(11)]+[(0,32,5.0),(7,128,11.1),(0,2,.5)]
    code=f'''set save_settings_on_exit false
set renderer SDLGL-PP
set sound_driver null
set throttle off
set minframeskip 0
set maxframeskip 0
set vsync off
set z80_freq 3579545
set z80_freq_locked true
set limitsprites true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
activate_input_layer -blocking boot_skip_proof
set cases {{{' '.join('{%d %d %.2f}'%c for c in cases)}}}
set index 0;set armed 0;set injected 0;set done 0
set log [open {tcl(out/'cases.tsv')} w]
proc inject {{}} {{
 lassign [lindex $::cases $::index] row mask delay
 set ::injected [machine_info time]
 keymatrixdown $row $mask
}}
proc next_case {{}} {{
 if {{[debug read memory {s['GameSession_BootKeyGate']}] || [debug read memory {s['Full_UIEdges']}] || [debug read memory {s['Full_UIHeld']}]}} {{error "Skip key not released cleanly"}}
 incr ::index
 if {{$::index==[llength $::cases]}} {{close $::log;exit 0}}
 set ::armed 0;set ::injected 0;set ::done 0
 reset
}}
proc release {{}} {{
 if {{[debug read memory {s['Full_UIHeld']}] || [debug read memory {s['Full_UIEdges']}] || [debug read memory {s['Session_Credits']}]}} {{error "Held skip key leaked into title input"}}
 lassign [lindex $::cases $::index] row mask delay
 keymatrixup $row $mask
 after time .1 next_case
}}
debug set_bp {s['GameSession_BootShow']} {{!$::armed}} {{
 set ::armed 1
 after time [lindex [lindex $::cases $::index] 2] inject
}}
debug set_bp {s['GameSession_BootShow.done']} {{$::armed && !$::done}} {{
 if {{!$::injected}} {{error "Boot ended before injection"}}
 set latency [expr {{[machine_info time]-$::injected}}]
 if {{$latency>.04 || ![debug read memory {s['GameSession_BootSkip']}]}} {{error "Skip missed or too late: $latency"}}
 foreach r {{8 9 10}} {{if {{[debug read {{PSG regs}} $r]}} {{error "Skip retained PSG sound"}}}}
 if {{[debug read {{VDP regs}} 15]}} {{error "VDP status selector not restored"}}
 puts $::log "$::index $latency";flush $::log
 set ::done 1
}}
debug set_bp {s['GameSession_UI']} {{$::done==1}} {{
 set ::done 2
 after time 1.2 release
}}
set VDP.too_fast_vram_access_callback {{error "Boot skip VRAM timing violation"}}
after time 140 {{puts stderr "Boot skip timeout case=$::index PC=[reg PC]";exit 3}}
'''
    (out/'probe.tcl').write_text('if {[catch {\n'+code+'\n} e]} {puts stderr $::errorInfo;exit 2}\n')
    with (out/'openmsx.log').open('w') as log:
        run=subprocess.run(['openmsx','-script',str(out/'probe.tcl')],timeout=150,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    assert run.returncode==0,(out,(out/'openmsx.log').read_text()[-1800:])
    rows=[line.split() for line in (out/'cases.tsv').read_text().splitlines()]
    assert len(rows)==len(cases)
    result=dict(passed=True,rom_sha256=hashlib.sha256((out/'measured.rom').read_bytes()).hexdigest(),cases=len(rows),
        max_skip_latency_ms=max(float(row[1]) for row in rows)*1000,path=str(out),
        scope='All11 keyboard rows, initial fill, moving RAM test, final matrix, held coin/start/Return keys; title key consumption, release, PSG silence, VDP status selector and access timing. Real keymatrix input, no guest-state writes.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/build/game');a=p.parse_args();verify(a.bundle)
