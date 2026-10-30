"""Execute synthetic dirty-name queues and the real ring uploader in openMSX."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys

HERE = RUNTIME
ROOT = HERE.parents[1]
MARK_BYTES = 514
POST_BYTES = 2567


def cases():
    result = []
    def add(marks, col=0, row=0, back=0, seen=None, label='single'):
        result.append(dict(marks=tuple(marks), col=col, row=row, back=back,
                           seen=tuple(seen or (col, row, col, row)), label=label))
    for index in range(1024):
        add((index,), (0, 7, 31, 127, 255)[index % 5],
            (0, 7, 31, 128, 255)[(index//5) % 5], index & 1)
    for mask in range(1, 256):
        add((5*32+8+bit for bit in range(8) if mask & (1 << bit)),
            label='all-byte-masks')
    for count in (0, 1, 23, 24, 127, 128):
        indices = [group*8+(group & 7) for group in range(count)]
        add(indices, 31, 31, 0, label=f'{count}-groups')
        add(list(reversed(indices))*2, 7, 255, 1,
            label=f'{count}-groups-duplicates')
    add(list(range(1024))*2, 31, 31, 1, label='1024-cells-duplicated')
    for back in (0, 1):
        for col, row in ((0, 0), (31, 31), (127, 255)):
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (-1, -1), (2, 0), (0, 2)):
                prior = ((col-dx) & 255, (row-dy) & 255)*2
                add((5*32+8, 31*32+31, 0), col, row, back, prior,
                    label='camera-transitions')
        add((5*32+8,), 7, 31, back, (255, 0, 7, 31),
            label='first-plane-unseen')
        add((5*32+8,), 7, 31, back, (7, 31, 255, 0),
            label='second-plane-unseen')
        add((), 7, 31, back, (255, 0, 255, 0), label='unseen-empty')
    return result


def queued(marks):
    bits = bytearray(128)
    order = []
    for index in marks:
        group, bit = divmod(index, 8)
        if not bits[group]:
            order.append(group)
        bits[group] |= 1 << bit
    queue = bytes(order)+bytes(128-len(order))
    return bytes(bits), queue, len(order)


def fixture(case, index):
    world = bytes((i*37+(i//32)*11+index*17) & 255 for i in range(1024))
    old = bytearray(world)
    for cell in set(case['marks']):
        old[cell] ^= 0x7f
    names = bytes(0xe0+(row+col) % 16 for row in range(32) for col in range(32))
    return world, bytes(old)*2, names


def visible(cell, col, row):
    return 1 <= ((cell % 32-col) & 31) < 24 and ((cell//32-row) & 31) < 28


def oracle_phase(case, world, vram, names, seen, selected, pending):
    """Independent physical-write oracle, including ring/HUD ownership."""
    vram = bytearray(vram)
    seen = list(seen)
    count = len(pending)
    covered = bool(count and (count >= 24 or seen[selected*2] == 255))
    if covered:
        seen[selected*2] = 255
    planned = bytes(seen)+bytes((255 if covered else 0,))
    col, row = case['col'], case['row']
    dx, dy = (col-seen[selected*2]) & 255, (row-seen[selected*2+1]) & 255
    full = seen[selected*2] == 255 or dx not in (0, 1, 255) or dy not in (0, 1, 255)
    ring_writes = 0
    def write(cell, value):
        nonlocal ring_writes
        vram[selected*1024+cell] = value
        ring_writes += 1
    if full:
        for cell, value in enumerate(world):
            write(cell, value)
    else:
        if dx:
            x = (col+(1 if dx == 255 else 23)) & 31
            for y in range(32):
                cell = y*32+x
                write(cell, world[cell])
        if dy:
            y = (row+(0 if dy == 255 else 31)) & 31
            for x in range(32):
                cell = y*32+x
                write(cell, world[cell])
    seen[selected*2:selected*2+2] = (col, row)
    for relative_row in range(28):
        physical_row = ((row+relative_row) & 31)*32
        write(physical_row+(col & 31), names[relative_row*32])
        for x in range(24, 32):
            write(physical_row+((col+x) & 31), names[relative_row*32+x])
    dirty_writes = 0
    if not covered:
        for group, mask in pending.items():
            for bit in range(8):
                cell = group*8+bit
                if mask & (1 << bit) and visible(cell, col, row):
                    vram[selected*1024+cell] = world[cell]
                    dirty_writes += 1
    return bytes(vram), bytes(seen), planned, ring_writes, dirty_writes


def source():
    lab = (HERE/'lab.asm').read_text()
    definitions = lab[lab.index('cx EQU '):lab.index('    ORG $4000')]
    io = lab[lab.index('address:\n'):lab.index('palette:\n')]
    dirty = (HERE/'game-dirty.inc').read_text()
    dirty = re.sub(r'(GameDirty_Bits EQU )\$2600', r'\g<1>$d000', dirty)
    dirty = re.sub(r'(GameDirty_Queues EQU )\$2700', r'\g<1>$d100', dirty)
    return ''' OUTPUT "probe.rom"
 MACRO reg number,value
 ld a,value
 out ($99),a
 ld a,$80+number
 out ($99),a
 ENDM
'''+definitions+'''Probe_MarkCount EQU $e100
Probe_MarkValues EQU $e200
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 reg 1,$02
 reg 0,4
 reg 8,$2a
 reg 9,$82
main:
 jp main
Probe_RunMarks:
 ld bc,(Probe_MarkCount)
 ld a,b
 or c
 ret z
 ld ix,Probe_MarkValues
.loop:
 ld l,(ix+0)
 ld h,(ix+1)
 inc ix
 inc ix
 call GameDirty_Mark
Probe_AfterMark:
 dec bc
 ld a,b
 or c
 jr nz,Probe_RunMarks.loop
 ret
Probe_Run:
 call Probe_RunMarks
Probe_AfterMarks:
Probe_RunPhase:
 call GameDirty_Plan
Probe_AfterPlan:
 call Ring_UploadNames
Probe_AfterRing:
 call GameDirty_Upload
Probe_AfterUpload:
 jp main
Probe_Baseline:
 call Ring_UploadNames
Probe_AfterBaseline:
 jp main
'''+dirty+(HERE/'game-ring.inc').read_text()+io+'''
Probe_End:
 ASSERT $ < $8000
 defs $8000-$,$ff
'''


def stats(values):
    ordered = sorted(values)
    return dict(calls=len(values), mean=statistics.mean(values),
                p99=ordered[(len(values)*99+99)//100-1], maximum=max(values))


def verify(bios, out=None):
    sys.path.insert(0, str(ROOT))
    from src.toolchain.msx.emulator import reference_machine, tcl
    out = Path(out or ROOT/'outputs/fixed-hud/dirty-synthetic').resolve()
    out.mkdir(parents=True, exist_ok=True)
    inputs, packed, offsets = cases(), bytearray(), []
    for index, case in enumerate(inputs):
        world, vram, names = fixture(case, index)
        offsets.append(len(packed))
        packed.extend(world+vram+names+
                      bytes((case['col'], case['row'], case['back']))+
                      bytes(case['seen'])+len(case['marks']).to_bytes(2, 'little'))
        for cell in case['marks']:
            packed.extend((0xd800+cell).to_bytes(2, 'little'))
    (out/'cases.bin').write_bytes(packed)
    (out/'probe.asm').write_text(source())
    assembled = subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),
                                '--nologo', '--sym=probe.sym', 'probe.asm'],
                               cwd=out, capture_output=True, text=True)
    if assembled.returncode:
        raise AssertionError(assembled.stdout+assembled.stderr)
    syms = {n: int(v, 16) for n, v in re.findall(
        r'^([\w.]+): EQU 0x([0-9a-fA-F]+)', (out/'probe.sym').read_text(), re.M)}
    lines = ['set save_settings_on_exit false', 'set renderer none',
             'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'),
             'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(out/"probe.rom")} -romtype Normal', 'reset', f'set out {tcl(out)}',
             'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
             f'set offsets [list {" ".join(map(str, offsets))}]',
             'foreach name {markers actual planned baseline} {set $name [open [file join $out $name.bin] wb]}',
             'set timing [open [file join $out cycles.txt] w];set marktiming [open [file join $out mark-cycles.txt] w];set basetiming [open [file join $out baseline-cycles.txt] w]',
             'set index 0;set started 0;set stage idle',
             'proc invoke {target} {reg SP 0xf380;reg PC $target}',
             'proc issue {} {',
             f' if {{$::index=={len(inputs)}}} {{foreach name {{markers actual planned baseline timing marktiming basetiming}} {{close [set ::$name]}};exit 0;return}}',
             ' set at [lindex $::offsets $::index];set ::phase 0',
             ' set ::world [string range $::data $at [expr {$at+1023}]]',
             ' set ::oldvram [string range $::data [expr {$at+1024}] [expr {$at+3071}]]',
             ' debug write_block memory 0xd800 $::world;debug write_block VRAM 0x2000 $::oldvram',
             ' debug write_block memory 0xc400 [string range $::data [expr {$at+3072}] [expr {$at+4095}]]',
             ' binary scan [string range $::data [expr {$at+4096}] [expr {$at+4102}]] cu* p',
             ' set ::col [lindex $p 0];set ::row [lindex $p 1];set ::firstback [lindex $p 2]',
             ' debug write memory 0xc009 $::col;debug write memory 0xc008 $::row;debug write memory 0xc006 $::firstback',
             ' debug write_block memory 0xc018 [string range $::data [expr {$at+4099}] [expr {$at+4102}]]',
             ' debug write_block memory 0xe100 [string range $::data [expr {$at+4103}] [expr {$at+4104}]]',
             ' binary scan [string range $::data [expr {$at+4103}] [expr {$at+4104}]] su count',
             ' debug write_block memory 0xe200 [string range $::data [expr {$at+4105}] [expr {$at+4104+2*$count}]]',
             ' debug write_block memory 0xd000 [string repeat "\0" 512];debug write_block memory 0xc096 "\0\0"',
             ' debug write memory 0xc099 165;debug write memory 0xcfff 165;debug write memory 0xd200 165',
             ' set ptrs "";for {set y 0} {$y<28} {incr y} {',
             '  set base [expr {0x2000+(($::row+$y)&31)*32}];append ptrs [binary format s* [list [expr {$base+($::col&31)}] [expr {$base+(($::col+24)&31)}]]]',
             ' };debug write_block memory 0xce00 $ptrs',
             ' reg AF 0x7393;reg DE 0x7a69;reg IY 0x9a89',
             f' invoke {syms["Probe_Run"]}', '}',
             f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
             f'debug set_bp {syms["GameDirty_Mark"]} {{$::started}} {{set ::mark_at [machine_info time];set ::regs [list [reg AF] [reg BC] [reg DE] [reg HL] [reg IX] [reg IY]]}}',
             f'debug set_bp {syms["Probe_AfterMark"]} {{$::started}} {{',
             ' if {$::regs ne [list [reg AF] [reg BC] [reg DE] [reg HL] [reg IX] [reg IY]]} {error "Mark clobbered caller registers"}',
             ' puts $::marktiming [list $::index [expr {round(([machine_info time]-$::mark_at)*3579545)}]]', '}',
             f'debug set_bp {syms["Probe_AfterMarks"]} {{$::started}} {{',
             ' foreach {address length} {0xc096 2 0xd000 256 0xd100 256} {puts -nonewline $::markers [debug read_block memory $address $length]}', '}',
             f'debug set_bp {syms["GameDirty_Plan"]} {{$::started}} {{set ::plan_at [machine_info time]}}',
             f'debug set_bp {syms["Probe_AfterPlan"]} {{$::started}} {{',
             ' set ::plan_cycles [expr {round(([machine_info time]-$::plan_at)*3579545)}]',
             ' puts -nonewline $::planned [debug read_block memory 0xc018 4];puts -nonewline $::planned [debug read_block memory 0xc099 1]', '}',
             f'debug set_bp {syms["Ring_UploadNames"]} {{$::started}} {{set ::ring_at [machine_info time];set ::stage ring;set ::ring_writes 0}}',
             f'debug set_bp {syms["Probe_AfterRing"]} {{$::started}} {{',
             ' set ::ring_cycles [expr {round(([machine_info time]-$::ring_at)*3579545)}];set ::before_dirty [debug read_block VRAM 0x2000 2048]', '}',
             f'debug set_bp {syms["GameDirty_Upload"]} {{$::started}} {{set ::dirty_at [machine_info time];set ::stage dirty;set ::dirty_writes 0}}',
             f'debug set_bp {syms["Probe_AfterUpload"]} {{$::started}} {{',
             ' set cycles [expr {round(([machine_info time]-$::dirty_at)*3579545)}];set ::stage idle',
             ' if {[debug read memory 0xc099]!=0 && ($::dirty_writes || $::before_dirty ne [debug read_block VRAM 0x2000 2048])} {error "Covered dirty upload still wrote VRAM"}',
             ' foreach address {0xcfff 0xd200} {if {[debug read memory $address]!=165} {error "Dirty scratch crossed allocation"}}',
             ' if {[debug read_block memory 0xd800 1024] ne $::world} {error "Dirty helper changed native world IDs"}',
             ' foreach {address length} {0xc096 2 0xd000 256 0xd100 256 0xc018 4 0xc099 1} {puts -nonewline $::actual [debug read_block memory $address $length]}',
             ' puts -nonewline $::actual [debug read_block VRAM 0x2000 2048]',
             ' puts $::timing [list $::index $::phase $::plan_cycles $::ring_cycles $cycles $::ring_writes $::dirty_writes]',
             ' if {$::phase==0} {',
             '  set ::phase 1;debug write memory 0xc006 [expr {1-$::firstback}]',
             f'  invoke {syms["Probe_RunPhase"]}',
             ' } else {',
             '  set ::basephase 0;debug write_block VRAM 0x2000 $::oldvram;debug write memory 0xc006 $::firstback;debug write memory [expr {0xc018+2*$::firstback}] 255',
             f'  invoke {syms["Probe_Baseline"]}',
             ' }', '}',
             f'debug set_bp {syms["Probe_AfterBaseline"]} {{$::started}} {{',
             ' set ::stage idle;puts $::basetiming [list $::index $::basephase [expr {round(([machine_info time]-$::ring_at)*3579545)}]]',
             ' puts -nonewline $::baseline [debug read_block VRAM 0x2000 2048]',
             ' if {$::basephase==0} {',
             '  set ::basephase 1;debug write memory 0xc006 [expr {1-$::firstback}];debug write memory [expr {0xc018+2*(1-$::firstback)}] 255',
             f'  invoke {syms["Probe_Baseline"]}',
             ' } else {incr ::index;issue}', '}',
             'debug set_watchpoint write_io 0x98 {$::started && $::stage ne "idle"} {if {$::stage eq "dirty"} {incr ::dirty_writes} else {incr ::ring_writes}}',
             'after time 600 {puts stderr "Dirty probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+
                                  '\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=180,
                       env=dict(os.environ, OPENMSX_HOME=str(out/'home'),
                                OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'actual.bin').read_bytes()
    markers = (out/'markers.bin').read_bytes()
    planned = (out/'planned.bin').read_bytes()
    baseline = (out/'baseline.bin').read_bytes()
    assert len(actual) == len(inputs)*2*POST_BYTES
    assert len(markers) == len(inputs)*MARK_BYTES
    assert len(planned) == len(inputs)*2*5
    assert len(baseline) == len(inputs)*2*2048
    timing = [list(map(int, line.split())) for line in (out/'cycles.txt').read_text().splitlines()]
    mark_cycles = [list(map(int, line.split())) for line in (out/'mark-cycles.txt').read_text().splitlines()]
    base_cycles = [list(map(int, line.split())) for line in (out/'baseline-cycles.txt').read_text().splitlines()]
    for index, case in enumerate(inputs):
        bits, queue, count = queued(case['marks'])
        marker_expected = bytes((count, count))+bits*2+queue*2
        if markers[index*MARK_BYTES:(index+1)*MARK_BYTES] != marker_expected:
            raise AssertionError(f'Mark bitsets/queue differs: case={index} {case["label"]}')
        world, vram, names = fixture(case, index)
        seen = bytes(case['seen'])
        lengths, bitplanes = [count, count], [bits, bits]
        pending = {i: mask for i, mask in enumerate(bits) if mask}
        for phase in (0, 1):
            selected = case['back'] ^ phase
            vram, seen, plan, ring_writes, dirty_writes = oracle_phase(
                case, world, vram, names, seen, selected, pending)
            slot = index*2+phase
            if planned[slot*5:slot*5+5] != plan:
                raise AssertionError(f'Plan differs: case={index} phase={phase}')
            lengths[selected], bitplanes[selected] = 0, bytes(128)
            expected = bytes(lengths)+b''.join(bitplanes)+queue*2+seen+plan[-1:]+vram
            record = actual[slot*POST_BYTES:(slot+1)*POST_BYTES]
            if record != expected:
                at = next(i for i, (a, b) in enumerate(zip(record, expected)) if a != b)
                raise AssertionError(f'Queue/VRAM differs: case={index} phase={phase} label={case["label"]} offset={at} actual={record[at]} expected={expected[at]}')
            if timing[slot][5:] != [ring_writes, dirty_writes]:
                raise AssertionError(f'VRAM write count differs: case={index} phase={phase}')
            full = baseline[slot*2048:(slot+1)*2048]
            # The full baseline also refreshes hidden rows; compare the complete
            # visible physical 32-column rows on every buffer already presented.
            for plane in ({case['back']} if phase == 0 else {0, 1}):
                for y in range(28):
                    start = plane*1024+((case['row']+y) & 31)*32
                    if record[519+start:519+start+32] != full[start:start+32]:
                        raise AssertionError(f'Full-ring baseline differs: case={index} phase={phase}')
    report = dict(cases=len(inputs), phases=len(inputs)*2, marker_calls=len(mark_cycles),
                  cpu_hz=3579545, machine='Panasonic_FS-A1WSX_NR128', video_hz_nominal=60,
                  synchronization_waits=0, hardware_sprite_limits=True,
                  rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(),
                  dirty_source_sha256=hashlib.sha256((HERE/'game-dirty.inc').read_bytes()).hexdigest(),
                  ring_source_sha256=hashlib.sha256((HERE/'game-ring.inc').read_bytes()).hexdigest(),
                  scope='Synthetic IDs/names; actual assembled markers, planner, dirty uploader and Ring_UploadNames. Inclusive entry-to-return emulated CPU cycles include memory/IO waits; no IRQ, synchronization, native simulation or other HUD/art preparation. Ring_UploadNames includes its fixed name overlays. Caller CALL excluded.',
                  exact_comparison='Both marker bitsets and FIFO group queues; register preservation; Plan seen/Covered; selected-only clearing; both physical VRAM name tables against independent oracle; visible names against actual full-ring uploader; exact OUT98 count and zero covered writes; world IDs unchanged.',
                  limitations='Probe bitsets/queues relocated to D000/D100 to isolate Page0 mapping; no continuous gameplay/scanout or physical hardware validation.',
                  workloads={})
    for label in sorted({c['label'] for c in inputs}):
        ids = {i for i, c in enumerate(inputs) if c['label'] == label}
        rows = [r for r in timing if r[0] in ids]
        values = {name: stats([r[column] for r in rows])
                  for column, name in ((2, 'GameDirty_Plan'), (3, 'Ring_UploadNames'),
                                       (4, 'GameDirty_Upload'), (5, 'ring_data_writes'),
                                       (6, 'dirty_data_writes'))}
        marks = [r[1] for r in mark_cycles if r[0] in ids]
        if marks:
            values['GameDirty_Mark'] = stats(marks)
        values['baseline_full_Ring_UploadNames'] = stats([r[2] for r in base_cycles if r[0] in ids])
        report['workloads'][label] = values
    (out/'cycle-ledger.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bios', type=Path, default=ROOT/'references/msxbios')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.bios, args.out), indent=2))
