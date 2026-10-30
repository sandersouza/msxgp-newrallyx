"""Measure guest-time routine costs without modifying the lab ROM.

Return breakpoints match both PC and SP, including tail calls and interrupts.
Inclusive time contains descendants; self time subtracts tracked descendants.
Neither is an instruction-table estimate or host wall-clock measurement.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import csv
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.toolchain.msx.emulator import reference_machine, tcl

BASE = ROOT / 'references/experiments/fixed-hud'
HZ = 3579545
ROUTINES = {
    'input': 'Keyboard / elapsed-tick camera movement',
    'render': 'Complete back-buffer preparation',
    'wait_blank': 'Synchronization wait (includes HALT)',
    'commit': 'Atomic VDP register publication',
    'Ring_Prepare': 'World ring update',
    'Ring_LoadColumns': 'Incoming world columns',
    'Ring_LoadRun': 'World ID lookup run',
    'Ring_UploadNames': 'Name table delta / cold refill',
    'Ring_UploadColumn': 'Column VRAM upload',
    'Ring_UploadRow': 'Row VRAM upload',
    'boundaries': 'Right-edge name selection',
    'left_names': 'Wrapped HUD guard name stores',
    'radar': 'Camera-center radar marker',
    'hud_upload': 'HUD phase packet upload',
    'address': 'VDP VRAM address setup',
    'upload': 'General VRAM transfer',
    'clock_irq': 'VBlank ISR body (entry latency excluded)',
    'HUD_NameStores': 'Compiled HUD name stores',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--movement', action='store_true',
                        help='Separate horizontal/vertical normal/Shift routes and tile crossings')
    args = parser.parse_args()
    segments = [('warmup', 4, 0, 0),
                ('horizontal_normal_right', 64, 128, 0),
                ('horizontal_normal_left', 64, 16, 0),
                ('vertical_normal_up', 64, 32, 0),
                ('vertical_normal_down', 64, 64, 0),
                ('horizontal_shift_right', 48, 128, 1),
                ('horizontal_shift_left', 48, 16, 1),
                ('vertical_shift_up', 48, 32, 1),
                ('vertical_shift_down', 48, 64, 1),
                ('idle', 32, 0, 0)]
    last_frame = sum(s[1] for s in segments) if args.movement else 312
    expected_frames = last_frame-4
    route = []
    limit = 0
    for name, length, mask, shift in segments:
        limit += length
        route.append(f'if {{$::frame<={limit}}} {{set ::command {name};'
                     f'keymatrixdown 8 {mask};keymatrixdown 6 {shift};return}}')
    route_tcl = '\n'.join(route)
    out = Path(tempfile.mkdtemp(prefix='profile-', dir=BASE))
    syms = {n: int(v, 16) for n, v in re.findall(
        r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)', (BASE / 'lab.sym').read_text(), re.M)}
    syms['HUD_NameStores'] = 0xa300
    script = f'''
set save_settings_on_exit false
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
set throttle off
set z80_freq {HZ}
set z80_freq_locked true
cart {tcl(BASE/'fixed-hud.rom')} -romtype ASCII16
reset
set out {tcl(out)}
set calls [open [file join $out calls.tsv] w]
puts $calls "frame\troutine\tinclusive_cycles\tself_cycles\ttop_level"
set frames [open [file join $out frames.tsv] w]
puts $frames "frame\tcycles\tcx\tcy\telapsed_ticks\tstart_x\tstart_y\tcommand\tspeed"
set active 0
set frame 0
set stack {{}}
array set returns {{}}
array set entries {{}}
proc word {{a}} {{expr {{[debug read memory $a]+256*[debug read memory [expr {{$a+1}}]]}}}}
proc cycle {{}} {{expr {{[machine_info time]*{HZ}}}}}
proc leave {{pc}} {{
    while {{[llength $::stack]}} {{
        lassign [lindex $::stack end] name start child ret sp owner
        if {{$ret!=$pc || [reg SP]!=$sp+2}} {{return}}
        set duration [expr {{[cycle]-$start}}]
        set self [expr {{$duration-$child}}]
        if {{$self < -0.1}} {{error "Negative self time for $name"}}
        puts $::calls "$owner\t$name\t$duration\t$self\t[expr {{[llength $::stack]==1}}]"
        set ::stack [lrange $::stack 0 end-1]
        if {{[llength $::stack]}} {{
            set parent [lindex $::stack end]
            lset parent 2 [expr {{[lindex $parent 2]+$duration}}]
            lset ::stack end $parent
        }}
    }}
}}
proc enter {{name}} {{
    if {{!$::active}} {{return}}
    set sp [reg SP]
    set ret [word $sp]
    # An IRQ can arrive before the instruction at an entry breakpoint runs.
    # The resumed PC must not create a second copy of that routine entry.
    if {{[llength $::stack]}} {{
        lassign [lindex $::stack end] prev start child pr ps owner
        if {{$prev eq $name && $pr==$ret && $ps==$sp}} {{return}}
    }}
    # A tail-call shares its caller's return address and SP. Both are closed
    # at the same return breakpoint, innermost first.
    if {{![info exists ::returns($ret)]}} {{
        set ::returns($ret) [debug set_bp $ret {{}} [list hit $ret]]
    }}
    lappend ::stack [list $name [cycle] 0 $ret $sp $::frame]
}}
proc hit {{pc}} {{
    # A return PC can also be a routine entry (notably after an IRQ).
    # One dispatcher guarantees return processing precedes entry processing.
    if {{[catch {{
        leave $pc
        if {{[info exists ::entries($pc)]}} {{enter $::entries($pc)}}
    }} problem]}} {{puts stderr $problem;exit 2}}
}}
proc next_frame {{}} {{
    if {{$::active}} {{
        if {{[llength $::stack]}} {{puts stderr "Unclosed routine at frame boundary: $::stack";exit 2}}
        puts $::frames "$::frame\t[expr {{[cycle]-$::start}}]\t[word 0xc000]\t[word 0xc002]\t[debug read memory 0xc026]\t$::start_x\t$::start_y\t$::command\t[debug read memory 0xc00a]"
    }}
    incr ::frame
    if {{$::frame>{last_frame}}} {{close $::calls;close $::frames;exit}}
    set ::active [expr {{$::frame>=5}}]
    set ::start [cycle]
    set ::start_x [word 0xc000]
    set ::start_y [word 0xc002]
    set ::command continuous
    keymatrixup 8 255
    keymatrixup 6 1
    if {{{int(args.movement)}}} {{{route_tcl}}}
    if {{$::frame<48}} {{keymatrixdown 8 192}} elseif {{$::frame<96}} {{keymatrixdown 8 48}} elseif {{$::frame<160}} {{keymatrixdown 8 128;keymatrixdown 6 1}} elseif {{$::frame<224}} {{keymatrixdown 8 64;keymatrixdown 6 1}} elseif {{$::frame<260}} {{keymatrixdown 8 16;keymatrixdown 6 1}} elseif {{$::frame<292}} {{keymatrixdown 8 32;keymatrixdown 6 1}}
}}
debug set_bp {syms['loop']} {{}} {{next_frame}}
'''
    for name in ROUTINES:
        script += f'set entries({syms[name]}) {name}\n'
        script += f'set returns({syms[name]}) [debug set_bp {syms[name]} {{}} {{hit {syms[name]}}}]\n'
    script += 'after time 30 {puts stderr "Profiling timed out";exit 2}\n'
    (out / 'profile.tcl').write_text(script)
    env = dict(os.environ, OPENMSX_HOME=str(out / 'home'), OPENMSX_USER_DATA=str(out / 'userdata'))
    with (out / 'openmsx.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out / 'profile.tcl')], env=env,
                       stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
    with (out / 'calls.tsv').open() as f:
        calls = list(csv.DictReader(f, delimiter='\t'))
    with (out / 'frames.tsv').open() as f:
        frames = list(csv.DictReader(f, delimiter='\t'))
    assert len(frames) == expected_frames, len(frames)
    # A second run retains only frame-boundary observation and the same keys.
    # Compare guest state, total elapsed time and boundary jitter. openMSX can
    # shift HALT/IRQ observation boundaries by one five-cycle M1 interval.
    control = '\n'.join(line for line in script.splitlines()
                        if not line.startswith(('set entries(', 'set returns(')))
    control = control.replace('calls.tsv', 'control-calls.tsv').replace(
        'frames.tsv', 'control-frames.tsv')
    (out/'control.tcl').write_text(control)
    with (out/'control.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'control.tcl')], env=env,
                       stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
    with (out/'control-frames.tsv').open() as f:
        control_frames = list(csv.DictReader(f, delimiter='\t'))
    assert len(frames) == len(control_frames)
    for measured, plain in zip(frames, control_frames):
        assert all(measured[k] == plain[k] for k in measured if k != 'cycles')
        assert abs(float(measured['cycles'])-float(plain['cycles'])) < 5.01
    assert abs(sum(float(r['cycles']) for r in frames)-sum(
        float(r['cycles']) for r in control_frames)) < .01
    stats = []
    for name, purpose in ROUTINES.items():
        rows = [r for r in calls if r['routine'] == name]
        assert rows, f'Unexercised routine: {name}'
        a = sorted(float(r['inclusive_cycles']) for r in rows)
        b = [float(r['self_cycles']) for r in rows]
        stats.append(dict(name=name, purpose=purpose, calls=len(rows),
                          calls_per_frame=len(rows)/len(frames), min=min(a),
                          mean=statistics.mean(a), p95=a[math.ceil(.95*len(a))-1],
                          max=max(a), self_mean=statistics.mean(b), self_total=sum(b)))
    frame_data = []
    for row in frames:
        n = int(row['frame'])
        owned = [r for r in calls if int(r['frame']) == n]
        phases = {name: sum(float(r['inclusive_cycles']) for r in owned
                           if r['routine'] == name)
                  for name in ('input', 'render', 'wait_blank', 'commit')}
        total = float(row['cycles'])
        residual = total - sum(phases.values())
        # Loop CALLs and bookkeeping remain outside routine-entry/return spans.
        assert 0 <= residual < 500, (n, residual)
        # An ISR can run between phase calls. Its body is already a tracked
        # top-level span; only its entry/vector and loop instructions remain
        # untracked. Do not add that ISR body again when reconciling self time.
        outside_hooks=sum(float(r['inclusive_cycles']) for r in owned
            if int(r.get('top_level',0)) and r['routine'] not in phases)
        untracked=residual-outside_hooks
        assert 0<=untracked<500,(n,untracked)
        self_total = sum(float(r['self_cycles']) for r in owned)
        assert abs(self_total + untracked - total) < .1, (n, self_total, total)
        assert all(sum(r['routine'] == name for r in owned) == 1 for name in phases)
        frame_data.append(dict(frame=n, cycles=total, cx=int(row['cx']), cy=int(row['cy']),
                               elapsed_ticks=int(row['elapsed_ticks']), **phases,
                               start_x=int(row['start_x']), start_y=int(row['start_y']),
                               command=row['command'], speed=int(row['speed']),
                               loop_overhead=residual, standalone_hook_cycles=outside_hooks, untracked_loop_overhead=untracked,
                               work=phases['input']+phases['render']+phases['commit']+residual))
        current = frame_data[-1]
        current['dx'] = current['cx']-current['start_x']
        current['dy'] = current['cy']-current['start_y']
        current['phase_x'] = current['cx'] % 8
        current['phase_y'] = current['cy'] % 8
        current['tile_crossing'] = (current['cx']//8 != current['start_x']//8
                                    or current['cy']//8 != current['start_y']//8)
        for name in ('Ring_Prepare', 'hud_upload', 'Ring_UploadNames',
                     'Ring_LoadColumns', 'Ring_UploadColumn', 'Ring_UploadRow'):
            spans = [r for r in owned if r['routine'] == name]
            current[name+'_cycles'] = sum(float(r['inclusive_cycles']) for r in spans)
            current[name+'_calls'] = len(spans)
    groups = []
    phase_groups = []
    if args.movement:
        for r in frame_data:
            if r['command'] == 'idle':
                assert r['dx'] == r['dy'] == 0
            else:
                axis = 'dx' if r['command'].startswith('horizontal') else 'dy'
                other = 'dy' if axis == 'dx' else 'dx'
                sign = 1 if r['command'].endswith(('right', 'down')) else -1
                assert r[axis] == sign*r['speed']*r['elapsed_ticks'], r
                assert r[other] == 0, r  # No clamped or diagonal samples.
        for axis in ('horizontal', 'vertical'):
            for speed in ('normal', 'shift'):
                for crossing in (False, True):
                    rows = [r for r in frame_data if r['command'].startswith(axis+'_'+speed)
                            and r['tile_crossing'] == crossing]
                    assert len(rows) >= 8, (axis, speed, crossing, len(rows))
                    work = sorted(r['work'] for r in rows)
                    groups.append(dict(axis=axis, speed=speed,
                        transition='tile crossing' if crossing else 'fine only', samples=len(rows),
                        mean=statistics.mean(work), p95=work[math.ceil(.95*len(work))-1],
                        max=max(work), interval_mean=statistics.mean(r['cycles'] for r in rows),
                        over_draw=sum(r['work']>59736 for r in rows),
                        over_two_refreshes=sum(r['work']>119472 for r in rows),
                        **{name:statistics.mean(r[name+'_cycles'] for r in rows)
                           for name in ('Ring_Prepare','hud_upload','Ring_UploadNames')}))
        # Every measured axis must cover all eight fine positions at normal speed.
        for axis, key in (('horizontal','phase_x'),('vertical','phase_y')):
            assert {r[key] for r in frame_data if r['command'].startswith(axis+'_normal')} == set(range(8))
            for phase in range(8):
                rows = [r for r in frame_data if r['command'].startswith(axis+'_normal')
                        and r[key] == phase]
                phase_groups.append(dict(axis=axis, phase=phase, samples=len(rows),
                    mean=statistics.mean(r['work'] for r in rows),
                    max=max(r['work'] for r in rows),
                    crossings=sum(r['tile_crossing'] for r in rows)))
        idle = [r for r in frame_data if r['command'] == 'idle']
        groups.append(dict(axis='idle', speed='none', transition='stationary', samples=len(idle),
            mean=statistics.mean(r['work'] for r in idle), p95=sorted(r['work'] for r in idle)[math.ceil(.95*len(idle))-1],
            max=max(r['work'] for r in idle), interval_mean=statistics.mean(r['cycles'] for r in idle),
            over_draw=sum(r['work']>59736 for r in idle), over_two_refreshes=sum(r['work']>119472 for r in idle),
            **{name:statistics.mean(r[name+'_cycles'] for r in idle)
               for name in ('Ring_Prepare','hud_upload','Ring_UploadNames')}))
    metadata = dict(cpu_hz=HZ, video_hz_nominal=50, cycles_per_refresh=313*228,
                    layout=json.loads((BASE/'prepare.json').read_text())['geometry'],
                    measured_frames=len(frames), rom_sha256=hashlib.sha256(
                        (BASE/'fixed-hud.rom').read_bytes()).hexdigest(),
                    machine=re.search(r'Reference RAM mapper: (\d+) bytes; machine: (\S+)',(out/'openmsx.log').read_text()).group(2),
                    mapper_ram_kib=int(re.search(r'Reference RAM mapper: (\d+) bytes; machine: (\S+)',(out/'openmsx.log').read_text()).group(1))//1024,
                    workload=('isolated horizontal/vertical routes, both directions, normal/Shift and idle'
                              if args.movement else 'continuous keys, 1/2 px per tick; frames 5..312'),
                    control_check=f'{len(frames)} camera/tick states match a run without routine breakpoints; total duration matches within 0.01 cycle; per-frame observation jitter <=5 cycles',
                    emulator=subprocess.check_output(['openmsx','-v'],text=True).strip(),
                    method='Guest emulated seconds * CPU Hz; entry to matched PC/SP return; tracked descendants subtracted for self time',
                    limitations='Free-camera laboratory; no game logic, enemies, collisions or flag hook. ISR body excludes hardware interrupt entry/vector latency. HALT included only in wait_blank; no physical hardware validation.',
                    run_path=str(out), routines=stats, frames=frame_data,
                    movement_groups=groups, phase_groups=phase_groups)
    (out/'summary.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (BASE/'last-profile.txt').write_text(str(out)+'\n')
    print(out)
    print(json.dumps(dict(frames=len(frames), calls=len(calls),
                         work_mean_ms=statistics.mean(r['work'] for r in frame_data)*1000/HZ,
                         work_max_ms=max(r['work'] for r in frame_data)*1000/HZ)))


if __name__ == '__main__':
    main()
