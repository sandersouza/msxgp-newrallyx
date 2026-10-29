"""Live first-stage emulator checks; retain guest traces and complete frames."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.msx.emulator import reference_machine,tcl,scanout_recording_tcl
BASE=ROOT/'references/experiments/stage-one'


def symbols():
    return {n:int(v,16) for n,v in re.findall(r'^([\w.]+): EQU 0x([0-9a-fA-F]+)',
            (BASE/'lab.sym').read_text(),re.M)}


def run(frames=180,scenario='natural',headless=False,bundle=None):
    global BASE
    if bundle is not None:
        BASE=Path(bundle).resolve()
    syms=symbols()
    out=Path(tempfile.mkdtemp(prefix=scenario+'-',dir=BASE))
    shutil.copyfile(BASE/'fixed-hud.rom',out/'measured.rom')
    resources=json.loads((BASE/'game-resources.json').read_text())
    multi=resources['banks']['GAME_TEST_ENEMIES']
    route_setup=''
    if scenario=='route':
        from game_route import setup
        route_setup=setup(ROOT,out,allow_gameover=bool(multi))
    script=f'''
set save_settings_on_exit false
{'set renderer none' if headless else ''}
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
set throttle off
set z80_freq 3579545
set z80_freq_locked true
set limitsprites true
if {{!$limitsprites}} {{error "Hardware sprite limit was not enabled"}}
set gamma 1.0
set brightness 0
set contrast 0
set color_matrix {{{{1 0 0}} {{0 1 0}} {{0 0 1}}}}
set scanline 0
set blur 0
set noise 0
set minframeskip 0
set maxframeskip 0
activate_input_layer -blocking first_stage_verification
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
{'' if headless else scanout_recording_tcl(out,syms['boot'])}
set out {tcl(out)}
set n 0
set route_done 0
set psg_writes 0
set in_commit 0
set commit_outside_vblank_writes 0
set commit_end_outside_vblank 0
set commit_log [open [file join $out commit.tsv] w]
puts $commit_log "frame\tcycles\tstart_vblank\tend_vblank"
set first_time 0
set last_time 0
set log [open [file join $out frames.tsv] w]
puts $log "frame\ttime\tcx\tcy\tnative_ticks\tflags\tscore\tfuel\tlives\tdeath\tstate\tenemies\tsmoke\telapsed"
proc word {{a}} {{expr {{[debug read memory $a]+256*[debug read memory [expr {{$a+1}}]]}}}}
proc save {{name}} {{
    if {{{0 if headless else 1}}} {{screenshot -raw -size auto [file join $::out $name.png]}}
    set f [open [file join $::out $name.ram] wb];puts -nonewline $f [debug read_block memory 0 65536];close $f
    set f [open [file join $::out $name.vram] wb];puts -nonewline $f [debug read_block VRAM 0 131072];close $f
}}
set VDP.too_fast_vram_access_callback {{
    if {{[debug read memory 0xc00c]==1}} {{puts stderr "VRAM timing violation at [reg PC]";exit 2}}
}}
debug set_watchpoint write_io 0xa1 {{[debug read memory 0xc00c]==1}} {{incr ::psg_writes}}
{route_setup}
debug set_bp {syms['commit']} {{[debug read memory 0xc00c]==1}} {{
    set ::in_commit 1
    set ::commit_start [machine_info time]
    set ::commit_start_blank [expr {{([debug read {{VDP status regs}} 2]&64)!=0}}]
}}
debug set_bp {syms['frame_done']} {{}} {{
    if {{$::in_commit}} {{
        set end_blank [expr {{([debug read {{VDP status regs}} 2]&64)!=0}}]
        if {{!$end_blank}} {{incr ::commit_end_outside_vblank}}
        puts $::commit_log "$::n\t[expr {{([machine_info time]-$::commit_start)*3579545}}]\t$::commit_start_blank\t$end_blank"
    }}
    set ::in_commit 0
}}
debug set_watchpoint write_io 0x98 {{$::in_commit}} {{
    if {{!([debug read {{VDP status regs}} 2]&64)}} {{incr ::commit_outside_vblank_writes}}
}}
proc boundary {{}} {{
    incr ::n
    if {{$::n==1}} {{set ::first_time [machine_info time]}}
    set ::last_time [machine_info time]
    keymatrixup 8 255
    if {{$::n<48}} {{keymatrixdown 8 32}} elseif {{$::n<96}} {{keymatrixdown 8 128}} elseif {{$::n<144}} {{keymatrixdown 8 64}} else {{keymatrixdown 8 16}}
    if {{{tcl(scenario)} eq "smoke" && $::n>=10 && $::n<60}} {{keymatrixdown 8 1}}
    if {{{tcl(scenario)} eq "heavy" && $::n==1}} {{debug write memory 0xe24e 7}}
    if {{{tcl(scenario)} eq "route"}} {{route_step}}
    puts $::log "$::n\t[machine_info time]\t[word 0xc000]\t[word 0xc002]\t[word 0xc440]\t[debug read memory 0xc50b]\t[word 0xe0a0]\t[debug read memory 0xe26b]\t[debug read memory 0xe00f]\t[debug read memory 0xc490]\t[debug read memory 0xc040]\t[debug read memory 0xe24e]\t[word 0xc711]\t[debug read memory 0xc026]"
    if {{$::n in {{2 30 90 {frames}}}}} {{save frame-$::n}}
    if {{$::n>={frames} || ({tcl(scenario)} eq "route" && $::route_done)}} {{
        close $::log
        close $::commit_log
        set f [open [file join $::out result.json] w]
        puts $f [format {{{{"frames":%d,"seconds":%.9f,"psg_writes":%d,"pc":%d,"commit_outside_vblank_writes":%d,"commit_end_outside_vblank":%d}}}} $::n [expr {{$::last_time-$::first_time}}] $::psg_writes [reg PC] $::commit_outside_vblank_writes $::commit_end_outside_vblank]
        close $f;exit
    }}
}}
debug set_bp {syms['loop']} {{}} {{boundary}}
after time {300 if scenario=="route" else 60} {{puts stderr "Gameplay timed out at PC=[reg PC] SP=[reg SP]";save timeout;exit 2}}
'''
    (out/'verify.tcl').write_text(script)
    env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata'))
    with (out/'openmsx.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'verify.tcl')],env=env,
            stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    result=json.loads((out/'result.json').read_text())
    assert result['commit_outside_vblank_writes']==0, 'Sprite/HUD publication wrote outside VBlank'
    assert result['commit_end_outside_vblank']==0, 'Presentation commit exceeded VBlank'
    result.update(scenario=scenario,rom_sha256=hashlib.sha256((out/'measured.rom').read_bytes()).hexdigest(),
                  headless=headless,cpu_hz=3579545,machine='Panasonic_FS-A1WSX',hardware_sprite_limit=True,
                  presented_fps=(result['frames']-1)/result['seconds'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    from game_analyze import analyze
    validation=analyze(out,BASE)
    if scenario=='route':
        completed=any(s['state']==2 and s['flags']==10 for s in validation['snapshots'])
        gameover=any(s['state']==1 for s in validation['snapshots'])
        assert completed or (multi and gameover), 'Route did not reach completion or native multi-enemy game over'
        result.update(stage_completed=completed,native_game_over=gameover)
    result['validated_snapshots']=len(validation['snapshots'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(out)
    print(json.dumps(result,indent=2))
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=int,default=180)
    parser.add_argument('--scenario',choices=('natural','smoke','heavy','route'),default='natural')
    parser.add_argument('--headless',action='store_true',help='Retain RAM/VRAM contracts without opening a video window')
    parser.add_argument('--bundle',type=Path,help='Built gameplay cartridge/resource directory')
    args=parser.parse_args()
    run(args.frames,args.scenario,args.headless,args.bundle)
