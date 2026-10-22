"""Real openMSX proof for the explicitly synthetic stage-3 loader entry."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import csv
from .native_contract import advance_clock

from .build import destination
from .emulator import tcl, reference_machine
from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


def symbols(path):
    return {name: int(value, 16) for name, value in
            re.findall(r'^(\w+): EQU 0x([0-9A-Fa-f]+)', path.read_text(), re.M)}


def analyze_increment(data: bytes) -> int:
    expected = bytearray()
    for ram in (False, True):
        for carry in (0, 1):
            for value in range(256):
                result = (value + 1) & 255
                flags = (result & 0xa8) | carry
                flags |= 0x40 if result == 0 else 0
                flags |= 0x10 if value & 15 == 15 else 0
                flags |= 4 if value == 127 else 0
                readback = result if ram else value
                expected.extend((readback, flags, readback, 0x98 if ram else 0))
    if data != expected:
        mismatch = next((n for n, (a,b) in enumerate(zip(data, expected)) if a != b), min(len(data),len(expected)))
        raise ValueError(f'INC discarded-write flags/readback proof failed at byte {mismatch}')
    return 1024


def analyze_waits(path: Path) -> int:
    with path.open() as stream:
        rows = list(csv.DictReader(stream,delimiter='\t'))
    expected = [dict(case=str(n),ticks=str(t),frames='2',pending=str(p))
                for n,(t,p) in enumerate(((1,1),(4,255),(4,0)))]
    if rows != expected:
        raise ValueError('Incomplete or incorrect logical wait/poll proof')
    return len(rows)


def analyze_schedule(path: Path, state: bytes, frame_cycles: int) -> dict:
    if len(state) != 128:
        raise ValueError('Incomplete scheduling state')
    ticks_long, remainder_long = advance_clock(0,100000*frame_cycles)
    if (int.from_bytes(state[80:84],'little') != remainder_long
            or int.from_bytes(state[84:88],'little') != ticks_long):
        raise ValueError('Assembly long-run clock disagrees with exact cadence')
    with path.open() as stream:
        rows = list(csv.DictReader(stream,delimiter='\t'))
    if len(rows) != 64:
        raise ValueError('Incomplete scheduling gate proof')
    remainder = pending = ticks = 0
    for n,row in enumerate(rows):
        due,remainder = advance_clock(remainder,frame_cycles)
        pending += due
        if n%6 == 0:
            pending -= 1
            ticks += 1
        expected = dict(case=n,gate=n%6,pending=pending,ticks=ticks,remainder=remainder)
        try:
            actual = {k:int(v) for k,v in row.items()}
        except (TypeError,ValueError) as error:
            raise ValueError('Malformed scheduling proof') from error
        if actual != expected:
            raise ValueError(f'Scheduling gate/backlog mismatch at case {n}')
    hardware_ticks, queued = ticks,pending
    with path.with_name('drain.tsv').open() as stream:
        drained = list(csv.DictReader(stream,delimiter='\t'))
    if not drained:
        raise ValueError('Incomplete foreground backlog drain proof')
    since_checkpoint = published = 0
    in_flight = False
    empty_checkpoint = False
    for n,row in enumerate(drained):
        event = row.get('event')
        if event == 'frame':
            due,remainder = advance_clock(remainder,frame_cycles)
            pending += due
        elif event == 'claim' and pending > 0 and not in_flight:
            pending -= 1
            in_flight = True
        elif event == 'publish' and in_flight:
            ticks += 1
            published += 1
            since_checkpoint += 1
            in_flight = False
        elif event == 'checkpoint' and not in_flight:
            if pending == 0 and since_checkpoint == 0:
                empty_checkpoint = True
            since_checkpoint = 0
        else:
            raise ValueError('Unexpected foreground scheduling event')
        try:
            actual = {k:int(v) for k,v in row.items() if k != 'event'}
        except (TypeError,ValueError) as error:
            raise ValueError('Malformed foreground backlog proof') from error
        if actual != dict(case=n,pending=pending,ticks=ticks,remainder=remainder):
            raise ValueError(f'Foreground backlog drain mismatch at case {n}')
    if (pending or in_flight or not empty_checkpoint or drained[-1]['event'] != 'checkpoint'
            or state[70] != 0
            or int.from_bytes(state[48:52],'little') != remainder
            or int.from_bytes(state[64:68],'little') != pending
            or int.from_bytes(state[72:76],'little') != ticks):
        raise ValueError('Final scheduling state differs from observed checkpoints')
    return dict(cases=64,completed_ticks=hardware_ticks,queued_ticks=queued,
                drained_ticks=published,total_ticks=ticks,pending_ticks=pending,remainder=remainder,
                long_run_ticks=ticks_long,long_run_remainder=remainder_long)


def analyze_probe(bundle: Path, output: Path) -> dict:
    result = read_json(output / 'execution.json')
    if (not isinstance(result, dict)
            or any(type(result.get(key)) is not int for key in ('status', 'iterations', 'irqs', 'sp', 'resets'))
            or result.get('status') != 2 or result.get('iterations') != 256
            or result.get('irqs', 0) < 256
            or result.get('resets') != 1):
        raise ValueError('Incomplete loader IRQ/register/stack proof')
    verify_manifest(bundle)
    mode = read_json(bundle / 'build.json').get('mode')
    if mode not in ('loader-probe', 'runtime-probe', 'irq-probe'):
        raise ValueError('Expected an explicit loader-probe bundle')
    syms = symbols(bundle / 'native.sym')
    if result['sp'] != syms.get('NATIVE_STACK'):
        raise ValueError('Host stack was not restored')
    state = (output / 'host-state.bin').read_bytes()
    physical = (output / 'mapper.bin').read_bytes()
    if len(state) != 64 or len(physical) < 131072 or len(physical) % 16384:
        raise ValueError('Incomplete loader memory evidence')
    segments = list(state[8:16])
    if len(set(segments)) != 8 or any(s * 16384 + 16384 > len(physical) for s in segments):
        raise ValueError('Invalid independent mapper segment inventory')
    def segment(role):
        offset = segments[role] * 16384
        return physical[offset:offset + 16384]
    host_offset = syms['NATIVE_STATE'] & 0x3fff
    tag_offset = syms['NATIVE_TAG'] & 0x3fff
    if segment(0)[host_offset:host_offset+64] != state:
        raise ValueError('Host state snapshot does not match physical memory')
    irq_bottom = syms.get('NATIVE_IRQ_BOTTOM', 0xc580) & 0x3fff
    if segment(0)[irq_bottom:irq_bottom+2] != b'\xa5\x5a':
        raise ValueError('Host IRQ stack canary changed')
    program = (bundle / 'native-program.bin').read_bytes()
    resident = (bundle / 'native.rom').read_bytes()[:16384]
    assets = (bundle / 'native-assets.bin').read_bytes()
    if segment(2) != program or segment(1) != resident:
        raise ValueError('Program/resident RAM copy differs from the validated payload')
    for n in range(4):
        if segment(n+4) != assets[n*16384:(n+1)*16384]:
            raise ValueError(f'Asset segment {n} differs from preloaded payload')
    game = bytearray(16384)
    game[0x2200:0x2203] = bytes((255, 255, 0xc3))
    if (segment(3) != game or state[1] or state[36]
            or state[54:56] != bytes((0xa5, 0x5a)) or state[56] != 2
            or segment(0)[tag_offset:tag_offset+2] != state[16:18]):
        raise ValueError('Game restoration, mapping guard or host canary failed')
    visible = (output / 'visible.bin').read_bytes()
    if visible != program + resident + game:
        raise ValueError('Final page-0/page-1/page-2 CPU mapping is incorrect')
    result.update(segments=segments, ram_bytes=len(physical), payloads_verified=True,
                  gameplay=False, reset_policy='machine reset only')
    if mode in ('runtime-probe','irq-probe'):
        result['increment_cases'] = analyze_increment(segment(0)[0x2000:0x3000])
        if type(result.get('game_stack_irqs')) is not int or result['game_stack_irqs'] != 1:
            raise ValueError('Missing original-stack IRQ register proof')
    if mode == 'irq-probe':
        result['wait_cases'] = analyze_waits(output/'waits.tsv')
        extended = (output/'irq-state.bin').read_bytes()
        if extended != segment(0)[host_offset:host_offset+128]:
            raise ValueError('Scheduling state does not match physical host memory')
        result['schedule'] = analyze_schedule(output/'schedule.tsv',extended,
            read_json(bundle/'build.json')['timing']['cpu_cycles'])
    json_write(output / 'verification.json', result)
    return result


def verify_probe(root: Path, rom: Path, output: Path, bios: Path,
                 machine: str = 'Panasonic_FS-A1WSX', openmsx: str = 'openmsx',
                 host_segment: int | None = None, small_memory: bool = False) -> dict:
    """Run the real loader fixture. small_memory tests refusal on stock 64 KB."""
    bundle = rom.parent
    verify_manifest(bundle)
    mode = read_json(bundle / 'build.json').get('mode')
    if mode not in ('loader-probe', 'runtime-probe', 'irq-probe'):
        raise ValueError('Use a sealed loader-probe build')
    if not bios.is_dir():
        raise ValueError('Supply contributor BIOS files')
    output = destination(root, output)
    session = destination(root, output.with_name(output.name + '-session'))
    require_ignored(root, [output / 'session.tcl', output / 'mapper.bin'])
    syms = symbols(bundle / 'native.sym')
    required = ('NATIVE_STATE', 'NATIVE_STACK', 'Native_Primary', 'Native_Boot', 'Native_Reset', 'Native_Status', 'Native_Error', 'Native_Before',
                'Native_After', 'Native_Restored', 'Native_IRQs')
    if any(name not in syms for name in required):
        raise ValueError('Missing loader verification symbols')
    output.mkdir(parents=True)
    session.mkdir(parents=True)
    before = {str(p): digest(p) for p in bios.rglob('*') if p.is_file()}
    lines = [
        'set save_settings_on_exit false', 'set renderer none',
        f'filepool add -path {tcl(bios.resolve())} -types system_rom -position 1',
        f'machine {tcl(machine)}' if small_memory else reference_machine(root, machine),
        'set firmwareswitch off', 'set throttle off', 'set z80_freq 3579545', 'set z80_freq_locked false',
        f'cart {tcl(rom.resolve())} -romtype ASCII16', 'reset',
        f'set out {tcl(output.resolve())}',
        'set iterations 0; set nr_started 0; set nr_booted 0; set nr_resets 0; set nr_game_stack_irqs 0',
        'proc regs {} {set r {}; foreach n {AF BC DE HL IX IY AF2 BC2 DE2 HL2 SP} {lappend r [reg $n]}; return $r}',
        'proc binary {name data} {set f [open [file join $::out $name] wb]; puts -nonewline $f $data; close $f}',
        'proc nr_before {} {if {$::nr_started} {set ::saved_regs [regs]}}',
        'proc nr_after {} {if {!$::nr_started} {return}; if {![info exists ::saved_regs] || [regs] ne $::saved_regs} {puts stderr "Asset mapping/IRQ changed registers or SP: before=$::saved_regs after=[regs] PC=[reg PC]"; exit 2}}',
        'proc nr_restored {} {if {!$::nr_started} {return}; nr_after; incr ::iterations}',
        'proc nr_done {} {',
        ' if {!$::nr_booted} {return}',
        ' if {$::wp_last_value != 2 && $::wp_last_value < 224} {return}',
        ' set status $::wp_last_value',
    ]
    if small_memory:
        lines += [' if {$status != 225} {puts stderr "Small mapper was not rejected"; exit 2}',
                  f' binary refusal.bin [debug read_block memory {syms["NATIVE_STATE"]} 64]',
                  ' puts stderr "PASS: cartridge refused fewer than eight independent segments"; exit 0', '}']
    else:
        lines += [
            ' if {$status != 2} {puts stderr "Loader rejected mapper"; exit 2}',
            f' set slots [debug read_block memory {syms["Native_Primary"]} 5]',
            ' if {!$::nr_resets} {set ::initial_slots $slots; set ::nr_resets 1; set ::nr_started 0; set ::nr_booted 0; set ::iterations 0; set ::nr_game_stack_irqs 0;',
            f'   set ::nr_boot_bp [debug set_bp {syms["Native_Boot"]} {{}} nr_boot]; after time 0 reset; return',
            ' }',
            ' if {$slots ne $::initial_slots} {puts stderr "Machine reset did not restore initial slot state"; exit 2}',
            f' binary host-state.bin [debug read_block memory {syms["NATIVE_STATE"]} 64]',
            f' if {{[info exists ::nr_irq_probe]}} {{binary irq-state.bin [debug read_block memory {syms["NATIVE_STATE"]} 128]}}',
            ' binary mapper.bin [debug read_block {Main RAM} 0 [debug size {Main RAM}]]',
            ' binary visible.bin [debug read_block memory 0 49152]',
            f' set irqs [expr {{[debug read memory {syms["Native_IRQs"]}] + 256*[debug read memory {syms["Native_IRQs"]+1}]}}]',
            ' set f [open [file join $::out execution.json] w]',
            ' puts $f [format {{"status":2,"iterations":%d,"irqs":%d,"sp":%d,"resets":%d,"game_stack_irqs":%d}} $::iterations $irqs [reg SP] $::nr_resets $::nr_game_stack_irqs]',
            ' close $f; exit 0', '}',
        ]
    lines += [
        f'debug set_watchpoint write_mem {syms["Native_Before"]} {{}} nr_before',
        f'debug set_watchpoint write_mem {syms["Native_After"]} {{}} nr_after',
        f'debug set_watchpoint write_mem {syms["Native_Restored"]} {{}} nr_restored',
        f'debug set_watchpoint write_mem {syms["Native_Status"]} {{}} nr_done',
        f'debug set_bp {syms["Native_Reset"]} {{}} {{set ::nr_started 1}}',
        f'debug set_bp {syms["Native_LoaderStart"]} {{}} {{puts stderr "Loader entry: slot=[debug read memory 50434] SP=[reg SP]"}}',
        f'debug set_watchpoint write_mem {syms["Native_RAMSlot"]} {{}} {{if {{$::nr_booted}} {{puts stderr "RAM slot write: value=$::wp_last_value PC=[reg PC]"}}}}',
    ]
    if mode == 'runtime-probe':
        lines += [
            'set nr_game_stack_irqs 0',
            f'debug set_watchpoint write_mem {syms["Native_ProbeBefore"]} {{$::nr_started && $::nr_booted}} {{set ::nr_game_regs [regs]}}',
            f'debug set_watchpoint write_mem {syms["Native_ProbeAfter"]} {{$::nr_started && $::nr_booted}} {{if {{[regs] ne $::nr_game_regs || [reg SP] != 33792}} {{puts stderr "Host IRQ changed original stack/registers"; exit 2}}; incr ::nr_game_stack_irqs}}',
        ]
    if mode == 'irq-probe':
        shutil.copyfile(root/'scripts/msx/native_irq_probe.tcl',output/'irq-probe.tcl')
        lines += ['set nr_irq_probe 1',
                  'set nr_symbols [dict create '+' '.join(f'{k} {v}' for k,v in syms.items())+']',
                  f'set nr_frame_cycles {read_json(bundle/"build.json")["timing"]["cpu_cycles"]}',
                  f'source {tcl(output/"irq-probe.tcl")}']
    lines += ['proc nr_boot {} {', ' set ::nr_booted 1']
    if host_segment is not None:
        if type(host_segment) is not int or not 0 <= host_segment < 8:
            raise ValueError('Synthetic host relocation requires a segment 0..7')
        lines += [
            ' set original [expr {[debug read ioports 255] & 7}]',
            f' debug write_block {{Main RAM}} {host_segment*16384} [debug read_block {{Main RAM}} [expr {{$original*16384}}] 16384]',
            f' debug write ioports 255 {host_segment}',
        ]
    lines += [' debug remove_bp $::nr_boot_bp', '}',
              f'set nr_boot_bp [debug set_bp {syms["Native_Boot"]} {{}} nr_boot]']
    budget = 120 if mode == 'irq-probe' else 45
    lines += [f'after time {budget} {{binary timeout-ram.bin [debug read_block memory 49152 16384]; puts stderr "Loader proof timed out: PC=[reg PC], regs=[regs], status=[debug read memory {syms["Native_Status"]}], slots=[debug read ioports 168], host=[debug read ioports 255]"; exit 2}}']
    (output / 'session.tcl').write_text('if {[catch {\n' + '\n'.join(lines) + '\n} problem]} {puts stderr $problem; exit 2}\n')
    # Keep emulator caches/persistent names (e.g. C-BIOS_MSX2+) out of the strict
    # evidence manifest. Both directories remain local and ignored.
    env = dict(os.environ, OPENMSX_HOME=str(session / 'home'), OPENMSX_USER_DATA=str(session / 'userdata'))
    with (output / 'emulator.log').open('w') as log:
        subprocess.run([openmsx, '-script', str(output / 'session.tcl')], env=env,
                       stdout=log, stderr=subprocess.STDOUT, timeout=120 if mode == 'irq-probe' else 60, check=True)
    if before != {str(p): digest(p) for p in bios.rglob('*') if p.is_file()}:
        raise ValueError('BIOS inventory changed')
    for config in (session / 'userdata/machines').glob('*.xml'):
        shutil.copyfile(config, output / 'reference-machine.xml')
    json_write(output / 'runtime.json', dict(
        openmsx=subprocess.check_output([openmsx, '--version'], text=True).strip(),
        machine=machine, stock_small_mapper=small_memory, relocated_host=host_segment,
        build_manifest_sha256=digest(bundle / 'manifest.json'), bios_sha256=before))
    if small_memory:
        state = (output / 'refusal.bin').read_bytes()
        if len(state) != 64 or state[0] != 0xe1 or not 1 <= state[32] < 8:
            raise ValueError('Missing small-memory refusal evidence')
        result = dict(refused_small_mapper=True, discovered_segments=state[32], gameplay=False)
        json_write(output / 'verification.json', result)
    else:
        result = analyze_probe(bundle, output)
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])
    seal(output)
    verify_manifest(output)
    return result
