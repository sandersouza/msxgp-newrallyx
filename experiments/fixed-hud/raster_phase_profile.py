"""Observe native VDP raster phase at matched PC/SP routine endpoints.

Runs an immutable cartridge snapshot and a keyboard-only route twice, with
and without routine breakpoints. All generated evidence remains ignored.
"""
import csv
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.msx.emulator import reference_machine, tcl
from game_route import setup

HZ = 3579545
BASE = ROOT / 'references/experiments/stage-one-3-enemies'
NAMES = ('Game_Prepare', 'Game_Frame', 'Game_LogicTick', 'GameAudio_Tick',
         'render', 'wait_blank', 'commit', 'clock_irq')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=BASE)
    parser.add_argument('--expected-sha256',help='Optional immutable input guard')
    args=parser.parse_args()
    bundle=args.bundle.resolve()
    expected=hashlib.sha256((bundle/'fixed-hud.rom').read_bytes()).hexdigest()
    if args.expected_sha256:assert expected==args.expected_sha256,'Input ROM hash mismatch'
    out = Path(tempfile.mkdtemp(prefix='raster-phase-', dir=ROOT/'references/experiments'))
    shutil.copyfile(bundle/'fixed-hud.rom', out/'measured.rom')
    shutil.copyfile(bundle/'lab.sym', out/'measured.sym')
    shutil.copyfile(Path(__file__), out/'raster_phase_profile.py')
    assert hashlib.sha256((out/'measured.rom').read_bytes()).hexdigest() == expected
    syms = {n: int(v, 16) for n, v in re.findall(
        r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)', (out/'measured.sym').read_text(), re.M)}
    route = setup(ROOT, out, allow_gameover=True)
    script = f'''
set save_settings_on_exit false
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set renderer none
set firmwareswitch off
set throttle off
set z80_freq {HZ}
set z80_freq_locked true
set limitsprites true
activate_input_layer -blocking raster_phase_profile
cart {tcl(out/'measured.rom')} -romtype ASCII16
reset
set out {tcl(out)}
{route}
proc save {{name}} {{}}
set endpoints [open [file join $out endpoints.tsv] w]
puts $endpoints "presentation\troutine\tduration\tstart_time\tstart_vframe\tstart_vtick\tstart_s2\tend_time\tend_vframe\tend_vtick\tend_s2"
set frames [open [file join $out frames.tsv] w]
puts $frames "presentation\ttime\tvframe\tvtick\tx\ty\tticks\tstate\tdeath\tflags\tr9\tr18\ts2\tactive_start"
set ::frame 0
set ::active 0
set ::stack {{}}
array set ::entries {{}}
array set ::returns {{}}
proc word {{a}} {{expr {{[debug read memory $a]+256*[debug read memory [expr {{$a+1}}]]}}}}
proc stamp {{}} {{list [machine_info time] [machine_info VDP_frame_count] [machine_info VDP_cycle_in_frame] [debug read "VDP status regs" 2]}}
proc leave {{pc}} {{
    while {{[llength $::stack]}} {{
        lassign [lindex $::stack end] name start ret sp owner
        if {{$ret!=$pc || [reg SP]!=$sp+2}} {{return}}
        set end [stamp]
        set duration [expr {{([lindex $end 0]-[lindex $start 0])*{HZ}}}]
        puts $::endpoints "$owner\t$name\t$duration\t[join $start "\\t"]\t[join $end "\\t"]"
        set ::stack [lrange $::stack 0 end-1]
    }}
}}
proc enter {{name}} {{
    if {{!$::active}} {{return}}
    set sp [reg SP]
    set ret [word $sp]
    if {{[llength $::stack]}} {{
        lassign [lindex $::stack end] prev start pr ps owner
        if {{$prev eq $name && $pr==$ret && $ps==$sp}} {{return}}
    }}
    if {{![info exists ::returns($ret)]}} {{set ::returns($ret) [debug set_bp $ret {{}} [list hit $ret]]}}
    lappend ::stack [list $name [stamp] $ret $sp $::frame]
}}
proc hit {{pc}} {{
    if {{[catch {{
        leave $pc
        if {{[info exists ::entries($pc)]}} {{enter $::entries($pc)}}
    }} problem]}} {{puts stderr $problem;exit 2}}
}}
proc next_frame {{}} {{
    if {{[llength $::stack]}} {{puts stderr "Unclosed: $::stack";exit 2}}
    if {{$::active}} {{
        lassign [stamp] time vf vt s2
        puts $::frames "$::frame\t$time\t$vf\t$vt\t[word 0xc000]\t[word 0xc002]\t[debug read memory 0xc026]\t[debug read memory 0xc040]\t[debug read memory 0xc490]\t[debug read memory 0xc50b]\t[debug read {{VDP regs}} 9]\t[debug read {{VDP regs}} 18]\t$s2\t$::active_start"
    }}
    incr ::frame
    if {{$::frame>10000 || $::route_done}} {{close $::frames;close $::endpoints;exit}}
    set ::active [expr {{$::frame>=5}}]
    set ::active_start [expr {{[debug read memory 0xc040]==0 && [debug read memory 0xc490]==0 && [debug read memory 0xc50b]<10}}]
    set ::n $::frame
    route_step
}}
debug set_bp {syms['loop']} {{}} {{next_frame}}
'''
    for name in NAMES:
        script += f'set entries({syms[name]}) {name}\n'
        script += f'set returns({syms[name]}) [debug set_bp {syms[name]} {{}} {{hit {syms[name]}}}]\n'
    script += 'after time 240 {puts stderr "Timed out";exit 2}\n'
    env = dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata'))
    for kind in ('measured', 'control'):
        code = script
        if kind == 'control':
            code = '\n'.join(l for l in script.splitlines() if not l.startswith(('set entries(', 'set returns(')))
            code = code.replace('endpoints.tsv', 'control-endpoints.tsv').replace('frames.tsv', 'control-frames.tsv')
        (out/f'{kind}.tcl').write_text(code)
        with (out/f'{kind}.log').open('w') as log:
            subprocess.run(['openmsx', '-script', str(out/f'{kind}.tcl')], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
    def read(name):
        with (out/name).open() as f:
            return list(csv.DictReader(f, delimiter='\t'))
    frames, control, rows = read('frames.tsv'), read('control-frames.tsv'), read('endpoints.tsv')
    assert len(frames) == len(control)
    state_keys = ('presentation', 'x', 'y', 'ticks', 'state', 'death', 'flags', 'r9', 'r18', 'active_start')
    assert all(all(a[k] == b[k] for k in state_keys) for a, b in zip(frames, control))
    jitter = [abs(float(a['time'])-float(b['time']))*HZ for a,b in zip(frames,control)]
    assert max(jitter) < 5.01, max(jitter)
    assert len({(f['r9'], f['r18']) for f in frames}) == 1
    r9, r18 = int(frames[0]['r9']), int(frames[0]['r18'])
    assert not r9 & 2
    display_line = 3+13+9+(0 if r9 & 128 else 10)+((r18 >> 4)^7)
    lines = 212 if r9 & 128 else 192
    display_start = display_line*1368+202
    blank_start = display_start+lines*1368
    blank_end_next = 262*1368+display_start-1368
    period = 262*1368
    for row in rows:
        for side in ('start','end'):
            vt = int(row[f'{side}_vtick'])
            row[f'{side}_line'] = vt//1368
            row[f'{side}_cpu_cycle_in_line'] = (vt % 1368)/6
            vr = vt < display_start-1368 or vt >= blank_start
            row[f'{side}_vblank'] = vr
            assert vr == bool(int(row[f'{side}_s2']) & 64), row
        start = int(row['start_vtick'])
        end = int(row['end_vtick']) + (int(row['end_vframe'])-int(row['start_vframe']))*period
        row['raster_duration_cycles'] = (end-start)/6
        assert abs(row['raster_duration_cycles']-float(row['duration'])) < .01
        blank = sum(max(0,min(end,k*period+blank_end_next)-max(start,k*period+blank_start))
                    for k in range(-1,math.floor(end/period)+1))
        row['vblank_cycles'] = blank/6
        row['outside_vblank_cycles'] = (end-start-blank)/6
        row['crosses_vblank_boundary'] = blank > 0 and blank < end-start
        row['start_from_previous_blank_edge_cycles'] = ((start-blank_start)%period)/6
        row['end_from_previous_blank_edge_cycles'] = ((end-blank_start)%period)/6
    active_ids = {int(f['presentation']) for f in frames if int(f['active_start'])
                  and int(f['state']) == int(f['death']) == 0 and int(f['flags']) < 10}
    def distribution(values):
        values = sorted(values)
        return dict(min=values[0],mean=statistics.mean(values),p95=values[math.ceil(.95*len(values))-1],max=values[-1])
    def summarize(selected):
        result = {}
        for name in NAMES:
            rs = [r for r in selected if r['routine']==name]
            if not rs:
                continue
            result[name] = dict(calls=len(rs), start_line=distribution([r['start_line'] for r in rs]),
                end_line=distribution([r['end_line'] for r in rs]),
                start_cpu_cycle_in_line=distribution([r['start_cpu_cycle_in_line'] for r in rs]),
                end_cpu_cycle_in_line=distribution([r['end_cpu_cycle_in_line'] for r in rs]),
                duration_cycles=distribution([float(r['duration']) for r in rs]),
                vblank_cycles=distribution([r['vblank_cycles'] for r in rs]),
                outside_vblank_cycles=distribution([r['outside_vblank_cycles'] for r in rs]),
                wholly_inside_vblank=sum(r['outside_vblank_cycles']==0 for r in rs),
                wholly_outside_vblank=sum(r['vblank_cycles']==0 for r in rs),
                crosses_vblank_boundary=sum(r['crosses_vblank_boundary'] for r in rs),
                start_from_blank_edge_cycles=distribution([r['start_from_previous_blank_edge_cycles'] for r in rs]),
                end_from_blank_edge_cycles=distribution([r['end_from_previous_blank_edge_cycles'] for r in rs]))
        return result
    summary = dict(rom_sha256=expected, run_path=str(out), machine='Panasonic_FS-A1WSX_NR128',
        cpu_hz=HZ,emulator=subprocess.check_output(['openmsx','-v'],text=True).strip(),
        limitsprites=True,hud_enabled=True,presentation_intervals=len(frames),active_intervals=len(active_ids),
        calibration=dict(source='openMSX RELEASE_21_0 src/video/VDP.cc and VDP.hh; installed _tas_tools.tcl',
            native_frame_epoch='machine_info VDP_cycle_in_frame, frame begins at VSYNC; no absolute-time modulo',
            vdp_ticks_per_cpu_cycle=6,vdp_ticks_per_line=1368,cpu_cycles_per_line=228,
            lines_per_refresh=262,cycles_per_refresh=59736,refresh_hz=HZ/59736,r9=r9,r18=r18,
            display_line_zero=display_line,display_start_vdp_tick=display_start,
            vblank_start_line=blank_start//1368,vblank_start_cycle_in_line=(blank_start%1368)/6,
            vblank_end_line=((blank_end_next%period)//1368),vblank_end_cycle_in_line=(blank_end_next%1368)/6,
            vblank_cycles=(blank_end_next-blank_start)/6,
            vblank_definition='VDP status2 VR, checked against every endpoint; rising edge equals VSCAN IRQ edge',
            all_endpoint_s2_checks_match=True,all_raster_durations_match_guest_time=True),
        control=dict(frame_states_identical=True,maximum_absolute_boundary_jitter_cycles=max(jitter),
                     final_time_difference_cycles=jitter[-1]),
        method='Matched PC/SP routine entry/return breakpoints; original keyboard-only route until completion/game over; four warmup intervals discarded; native VDP clock snapshots and side-effect-free debug status2 reads',
        limitations='Emulator only; routine endpoint includes descendants/interrupt time. clock_irq excludes hardware entry/vector. VBlank refers to VR, not a guaranteed safe VRAM budget. Line numbers start at physical VSYNC, not visible picture line zero. No actual original ROM or asset data exported.',
        all_routines=summarize(rows),active_routines=summarize([r for r in rows if int(r['presentation']) in active_ids]))
    (out/'endpoints.json').write_text(json.dumps(rows,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(out)
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
