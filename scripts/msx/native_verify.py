"""Acquire fresh original reset/IRQ evidence before integrating native execution."""
import json
import csv
import os
import re
import hashlib
import shutil
import math
from collections import Counter
from pathlib import Path
import subprocess

from scripts.graphics.roms import load_metadata, validate_roms, input_records
from scripts.scenes.record import lua_literal, validate_replay
from scripts.scenes.storage import require_ignored, json_write, seal
from scripts.scenes.bundle import digest, verify_manifest
from scripts.z80_analysis import destination, program_image
from .build import destination as build_destination
from .emulator import tcl, reference_machine
from .native_probe import symbols
from .native_contract import Snapshot, first_difference, advance_clock
from .native_deadline import analyze_deadline_math, analyze_deadlines


def control_hits(log: str, image: bytes) -> list[dict]:
    """Read execution breakpoints, never infer instructions from memory taps."""
    hits = Counter()
    for line in log.splitlines():
        if not line.startswith('NATIVE_CONTROL '):
            continue
        match = re.fullmatch(r'NATIVE_CONTROL ([0-9A-Fa-f]{4})', line)
        if not match:
            raise ValueError('Malformed control execution marker')
        address = int(match[1], 16)
        if address >= len(image) or image[address] not in (0xf3, 0xfb):
            raise ValueError('Control marker does not identify EI/DI')
        hits[address] += 1
    if not hits:
        raise ValueError('Missing control execution evidence')
    return [dict(address=a, kind='di' if image[a] == 0xf3 else 'ei', count=n)
            for a, n in sorted(hits.items())]


def load_input_levels(reference: Path) -> list[tuple[int,int,int]]:
    with (reference/'boundaries.tsv').open() as stream:
        boundaries = [row for row in csv.DictReader(stream,delimiter='\t') if row['phase']=='pre-game-irq']
    with (reference/'inputs.tsv').open() as stream:
        rows = list(csv.DictReader(stream,delimiter='\t'))
    if len(rows) != len(boundaries) or not rows:
        raise ValueError('Incomplete logical input replay')
    levels = []
    for n,(row,boundary) in enumerate(zip(rows,boundaries)):
        if (row.get('tick') != str(n) or row.get('tick') != boundary['tick']
                or row.get('frame') != boundary['frame']
                or any(not re.fullmatch('[0-9a-f]{2}',row.get(k,'')) for k in ('p1','p2','dip'))):
            raise ValueError('Input levels do not identify the exact pre-IRQ boundary')
        levels.append(tuple(int(row[k],16) for k in ('p1','p2','dip')))
    return levels


def analyze_reference(output: Path) -> dict:
    """Reject partial, misnumbered or phase-shifted fresh-reset evidence."""
    execution = json.loads((output / 'execution.json').read_text())
    if (not isinstance(execution, dict) or type(execution.get('schema_version')) is not int
            or execution['schema_version'] != 1
            or type(execution.get('boot_frame')) is not int
            or not 0 <= execution['boot_frame'] <= 3600
            or type(execution.get('ticks')) is not int or not 1 <= execution['ticks'] <= 3600
            or (output / 'complete').read_text() != 'ok\n'):
        raise ValueError('Incomplete reference execution')
    controls = execution.get('controls')
    if (not isinstance(controls,list) or not controls or any(
            not isinstance(row,dict) or set(row) != {'address','kind','count'}
            or type(row['address']) is not int or not 0 <= row['address'] < 0x4000
            or row['kind'] not in ('ei','di') or type(row['count']) is not int or row['count'] < 1
            for row in controls)
            or [r['address'] for r in controls] != sorted({r['address'] for r in controls})):
        raise ValueError('Missing or malformed reference control execution evidence')
    with (output / 'boundaries.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    tick, previous_time, previous_frame = 0, -1, -1
    foreground, pending, transfer, transfers = False, False, False, 0
    for index, row in enumerate(rows):
        try:
            phase = row['phase']
            number, frame = int(row['tick']), int(row['frame'])
            pc, sp, im, i, iff = (int(row[k], base) for k, base in
                                  (('pc',16), ('sp',16), ('im',10), ('i',16), ('iff1',10)))
            if not re.fullmatch(r'\d+\.\d{3},\d{3},\d{3}', row['time']):
                raise ValueError('Invalid reference timestamp')
            time = int(re.sub(r'[.,]', '', row['time']))
            if (time < previous_time or frame < previous_frame or not 0 <= sp <= 65535
                    or i != 0x3f):
                raise ValueError('Reference CPU/time sequence changed')
            if index == 0:
                valid = (phase == 'initialization-entry' and pc == 3 and number == 0
                         and frame == execution['boot_frame'] and sp == 0x8400 and im == 2 and iff == 0)
            elif phase == 'foreground-entry':
                valid = not foreground and not pending and number == tick and pc == 0xc2c and im == 0 and iff == 1
                foreground = True
            elif phase == 'pre-game-irq':
                valid = not pending and number == tick and pc == 0x1f0 and im == 0 and iff == 0 and 0x8000 <= sp <= 0x8400
                irq_sp = sp
                pending = True
            elif phase == 'game-irq-transfer':
                valid = pending and not transfer and number == tick and pc == 0x75a and im == 0 and iff == 0
                transfer = 1
            elif phase == 'game-irq-collision':
                valid = pending and not transfer and number == tick and pc == 0x3b9 and im == 0 and iff == 0
                transfer = 2
            elif phase == 'post-game-irq-collision':
                valid = pending and transfer == 2 and number == tick+1 and pc == 0x18c1 and sp == irq_sp-12 and im == 0 and iff == 1
                pending = transfer = False
                tick += 1
                transfers += 1
            elif phase == 'post-game-irq-transfer':
                valid = pending and transfer == 1 and number == tick+1 and pc == 0x769 and sp == 0x8400 and im == 0 and iff == 0
                pending = transfer = False
                tick += 1
                transfers += 1
            elif phase == 'post-game-irq':
                valid = pending and not transfer and number == tick + 1 and pc == 0x471 and sp == irq_sp and im == 0 and iff == 1
                pending = False
                tick += 1
            else:
                valid = False
            if not valid:
                raise ValueError(f'Unexpected reference phase/tick/CPU boundary at row {index+2}: {row}')
            previous_time, previous_frame = time, frame
        except (KeyError, TypeError) as error:
            raise ValueError('Malformed reference boundary') from error
    names = {'initialization.bin', 'foreground-entry.bin'} | {
        f'state-{n:05d}.bin' for n in range(1, tick+1)}
    if (pending or not foreground or tick != execution['ticks']
            or {p.name for p in output.glob('*.bin')} != names
            or any((output / name).stat().st_size != 6536 for name in names)):
        raise ValueError('Missing, extra or truncated reference snapshots/boundaries')
    return dict(schema_version=1, ticks=tick, boot_frame=execution['boot_frame'],
                boundaries=len(rows), snapshot_bytes=6536,
                controls=controls, irq_transfers=transfers,
                native_equivalence=False)


def capture_reference(root: Path, output: Path, *, frames: int = 3200, replay_path: Path | None = None) -> Path:
    root = root.resolve()
    output = destination(root, output)
    if type(frames) is not int or not 2402 <= frames <= 3600:
        raise ValueError('Native reference requires 2402..3600 arcade frames to cover coin/start')
    metadata = load_metadata()
    inputs = root / 'references/roms/nrallyx'
    roms = validate_roms(inputs, metadata)
    before = input_records(roms)
    image = program_image(roms, metadata)
    replay = validate_replay(json.loads((replay_path or root / 'scripts/scenes/gameplay-inputs.json').read_text()))
    config = dict(output=str(output), frames=frames, inputs=replay,
                  control_sites=[dict(address=n,kind='di' if b==0xf3 else 'ei')
                                 for n,b in enumerate(image) if b in (0xf3,0xfb)])
    version = subprocess.check_output(['mame', '-help'], text=True).splitlines()[0]
    if not version.startswith('MAME v0.289 '):
        raise ValueError('Requires MAME 0.289')
    require_ignored(root, [output / 'initialization.bin', output / 'execution.json'])
    output.mkdir(parents=True)
    shutil.copyfile(root / 'scripts/msx/native_reference.lua', output / 'acquisition.lua')
    json_write(output / 'provenance.json', dict(schema_version=1, mame=version, inputs=before,
        frames=frames, program_sha256=hashlib.sha256(image).hexdigest(),
        acquisition_sha256=digest(output / 'acquisition.lua'),
        verifier_sha256=digest(Path(__file__))))
    (output / 'config.lua').write_text('return ' + lua_literal(config) + '\n')
    json_write(output / 'replay.json', replay)
    command = ['mame', 'nrallyx', '-noreadconfig', '-noplugins', '-nocheat',
        '-log', '-homepath', str(output),
        '-rompath', str(root / 'references/roms'), '-video', 'none', '-sound', 'none',
        '-nothrottle', '-noautosave', '-noautoframeskip', '-frameskip', '0',
        '-skip_gameinfo', '-debug', '-debugger', 'none', '-autoboot_delay', '0',
        '-autoboot_script', str(output / 'acquisition.lua'),
        '-seconds_to_run', str(frames//50+15)]
    for name in ('cfg', 'nvram', 'snapshot', 'state', 'diff'):
        command += [f'-{name}_directory', str(output / name)]
    env = dict(os.environ, NRALLYX_NATIVE_REFERENCE=str(output / 'config.lua'))
    with (output / 'mame.log').open('w') as log:
        subprocess.run(command, cwd=output, env=env, stdout=log,
                       stderr=subprocess.STDOUT, timeout=240, check=True)
    if (output / 'complete').read_text() != 'ok\n':
        raise ValueError('Reference did not reach original initialization/IRQ boundaries')
    execution = json.loads((output / 'execution.json').read_text())
    execution['controls'] = control_hits((output / 'error.log').read_text(), image)
    json_write(output / 'execution.json', execution)
    json_write(output / 'verification.json', analyze_reference(output))
    if input_records(validate_roms(inputs, metadata)) != before:
        raise ValueError('Contributor ROM inputs changed')
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])
    seal(output)
    verify_manifest(output)
    return output


def verify_reset(root: Path, rom: Path, output: Path, bios: Path, reference: Path,
                 *, machine: str = 'Panasonic_FS-A1WSX', openmsx: str = 'openmsx') -> dict:
    """Stop before original game init; compare all 6536 bytes without exclusions."""
    root = root.resolve()
    bundle = rom.parent
    verify_manifest(bundle)
    verify_manifest(reference)
    analyze_reference(reference)
    report = json.loads((bundle / 'build.json').read_text())
    if report.get('mode') != 'reset-probe' or report.get('reference_manifest_sha256') != digest(reference/'manifest.json'):
        raise ValueError('Expected a reset probe bound to this original acquisition')
    if not bios.is_dir():
        raise ValueError('Supply contributor BIOS files')
    source_inputs = input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    if source_inputs != report.get('inputs'):
        raise ValueError('Contributor ROM inventory differs from the reset build')
    output = build_destination(root, output)
    session = build_destination(root, output.with_name(output.name+'-session'))
    require_ignored(root, [output/'initialization.bin', output/'mapper.bin'])
    syms = symbols(bundle/'native.sym')
    output.mkdir(parents=True)
    session.mkdir(parents=True)
    shutil.copyfile(root/'scripts/msx/native_verify.tcl', output/'acquisition.tcl')
    before = {str(p):digest(p) for p in bios.rglob('*') if p.is_file()}
    lines = ['set save_settings_on_exit false', 'set renderer none',
        f'filepool add -path {tcl(bios.resolve())} -types system_rom -position 1',
        reference_machine(root,machine),
        'set firmwareswitch off', 'set throttle off', 'set z80_freq 3579545', 'set z80_freq_locked false',
        f'cart {tcl(rom.resolve())} -romtype ASCII16', 'reset',
        f'set nr_out {tcl(output)}',
        'set nr_symbols [dict create '+ ' '.join(f'{k} {v}' for k,v in syms.items())+']',
        f'source {tcl(output/"acquisition.tcl")}',
    ]
    (output/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem; exit 2}\n')
    env = dict(os.environ, OPENMSX_HOME=str(session/'home'), OPENMSX_USER_DATA=str(session/'userdata'))
    with (output/'emulator.log').open('w') as log:
        subprocess.run([openmsx,'-script',str(output/'session.tcl')],env=env,stdout=log,
                       stderr=subprocess.STDOUT,timeout=180,check=True)
    if before != {str(p):digest(p) for p in bios.rglob('*') if p.is_file()}:
        raise ValueError('Contributor BIOS inventory changed')
    if input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())) != source_inputs:
        raise ValueError('Contributor ROM inventory changed during reset proof')
    verify_manifest(bundle)
    verify_manifest(reference)
    result = analyze_reset(bundle,output,reference)
    for config in (session/'userdata/machines').glob('*.xml'):
        shutil.copyfile(config,output/'reference-machine.xml')
    json_write(output/'runtime.json',dict(
        openmsx=subprocess.check_output([openmsx,'--version'],text=True).strip(), machine=machine,
        build_manifest_sha256=digest(bundle/'manifest.json'),
        reference_manifest_sha256=digest(reference/'manifest.json'),bios_sha256=before))
    require_ignored(root,[p for p in output.rglob('*') if p.is_file()])
    seal(output)
    verify_manifest(output)
    return result


def analyze_reset(bundle: Path, output: Path, reference: Path) -> dict:
    """Validate the observed reset boundary and compare complete original state."""
    verify_manifest(bundle)
    verify_manifest(reference)
    analyze_reference(reference)
    build = json.loads((bundle/'build.json').read_text())
    if build.get('mode') != 'reset-probe' or build.get('reference_manifest_sha256') != digest(reference/'manifest.json'):
        raise ValueError('Reset evidence is not bound to this reference')
    execution = json.loads((output/'execution.json').read_text())
    if (execution != dict(schema_version=1, pc=3, sp=0x8400, im=2, i=0xd0, iff=0, complete=True)
            or any(type(execution[k]) is not int for k in ('schema_version','pc','sp','im','i','iff'))
            or execution['complete'] is not True
            or (output/'program.bin').read_bytes() != (bundle/'native-program.bin').read_bytes()
            or (output/'resident.bin').read_bytes() != (bundle/'native.rom').read_bytes()[:16384]):
        raise ValueError('Reset CPU boundary or mapped program/resident changed')
    def snapshot(path):
        data = path.read_bytes()
        if len(data) != 6536:
            raise ValueError('Incomplete reset snapshot')
        return Snapshot(0,'initialization-entry',data[:4096],data[4096:6144],data[6144:])
    difference = first_difference(snapshot(reference/'initialization.bin'), snapshot(output/'initialization.bin'))
    result = dict(schema_version=1, phase='initialization-entry', compared_bytes=6536,
                  exclusions=[], first_difference=difference, game_irqs_verified=False)
    json_write(output/'verification.json', result)
    if difference:
        raise ValueError(f'Original reset state diverged: {difference}')
    return result


def analyze_acquisition(bundle: Path, output: Path, reference: Path, count: int) -> dict:
    """Validate a complete raw acquisition; never assert gameplay equivalence."""
    clock = json.loads((output/'clock.json').read_text())
    if (clock != dict(z80_freq=3579545,z80_freq_locked=False)
            or type(clock.get('z80_freq')) is not int or clock.get('z80_freq_locked') is not False):
        raise ValueError('Native acquisition clock is not fixed at standard speed')
    execution = json.loads((output/'execution.json').read_text())
    if (set(execution) != {'schema_version','complete','ticks','stack_min'}
            or any(type(execution[k]) is not int for k in ('schema_version','ticks','stack_min'))
            or execution['schema_version'] != 1 or execution['complete'] is not True
            or execution['ticks'] != count or not 0x8000 <= execution['stack_min'] <= 0x8400):
        raise ValueError('Incomplete native logic acquisition')
    if ((output/'initialization.bin').read_bytes() != (reference/'initialization.bin').read_bytes()
            or (output/'initialization.bin').stat().st_size != 6536):
        raise ValueError('Native initialization state changed')
    for phase in ('initial','final'):
        for name,expected in (('program',(bundle/'native-program.bin').read_bytes()),
                              ('resident',(bundle/'native.rom').read_bytes()[:16384])):
            if len(expected) != 16384 or (output/f'{phase}-{name}.bin').read_bytes() != expected:
                raise ValueError('Native mapped program/resident changed')
    if ({p.name for p in output.glob('state-*.bin')} != {f'state-{n:05d}.bin' for n in range(1,count+1)}
            or any(p.stat().st_size != 6536 for p in output.glob('state-*.bin'))):
        raise ValueError('Incomplete native logic snapshots')
    from .native_compare import native_phases
    if len(native_phases(output/'events.tsv')) != count:
        raise ValueError('Incomplete native event sequence')
    return execution


def analyze_boot_registers(output: Path) -> dict:
    """Verify reference CPU startup values, independently of game RAM snapshots."""
    expected = dict(AF=0x40,BC=0,DE=0,HL=0,IX=0xffff,IY=0xffff,
                    AF2=0,BC2=0,DE2=0,HL2=0)
    actual = json.loads((output/'boot-registers.json').read_text())
    if (not isinstance(actual,dict) or actual != expected
            or any(type(value) is not int for value in actual.values())):
        raise ValueError('Invalid original CPU boot register context')
    return actual


def analyze_function(output: Path) -> dict:
    result = json.loads((output/'function.json').read_text())
    if (not isinstance(result,dict)
            or set(result) != {'cases','complete','compared','reference_cycles','optimized_cycles'}
            or any(type(result[k]) is not int for k in ('cases','reference_cycles','optimized_cycles'))
            or result['cases'] != 131072 or result['complete'] is not True
            or result['compared'] != ['AF','HL','BC','DE']
            or not 0 < result['optimized_cycles'] < result['reference_cycles']):
        raise ValueError('Incomplete or non-improving coordinate differential proof')
    return result


def analyze_presentation_callers(bundle: Path, output: Path) -> dict:
    """Bind complete per-caller timing to actual CALLs in the measured cartridge."""
    syms = symbols(bundle/'native.sym')
    rom = (bundle/'native.rom').read_bytes()
    context = json.loads((output/'presentation-context.json').read_text())
    with (output/'presentation-callers.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    fields = {'caller', 'calls', 'steps', 'skip_cycles', 'step_cycles', 'max_cycles'}
    if not rows:
        raise ValueError('Missing presentation caller timing')
    seen, calls, steps, result = set(), 0, 0, []
    target = syms['Native_PrepareFrame']
    instruction = bytes((0xcd, target & 255, target >> 8))
    for row in rows:
        if set(row) != fields or any(not str(value).isdecimal() for value in row.values()):
            raise ValueError('Invalid presentation caller fields')
        values = {key: int(value) for key, value in row.items()}
        caller = values['caller']
        at = caller-3-0x4000
        if (caller in seen or not 0x4003 <= caller <= 0x8000
                or rom[at:at+3] != instruction
                or not 0 <= values['steps'] <= values['calls']
                or values['calls'] == 0 or values['max_cycles'] == 0
                or (values['step_cycles'] == 0) != (values['steps'] == 0)
                or (values['skip_cycles'] == 0) != (values['steps'] == values['calls'])
                or values['max_cycles'] > values['step_cycles']+values['skip_cycles']):
            raise ValueError('Inconsistent presentation caller timing')
        seen.add(caller)
        calls += values['calls']
        steps += values['steps']
        result.append(values)
    if calls != context['calls'] or steps != context['steps']:
        raise ValueError('Presentation callers disagree with complete context counts')
    return dict(complete=True, calls=calls, steps=steps, callers=result,
                timing='elapsed CPU clocks, including physical IRQ service',
                candidate_manifest_sha256=digest(bundle/'manifest.json'))


def analyze_profile(output: Path, expected) -> dict:
    if (type(expected) not in (tuple,list) or len(expected) != 2
            or any(type(v) is not int for v in expected)
            or not 1 <= expected[0] < expected[1] or expected[1]-expected[0] > 64):
        raise ValueError('Invalid instruction profile window')
    with (output/'profile-window.tsv').open() as stream:
        windows = list(csv.DictReader(stream,delimiter='\t'))
    try:
        if len(windows) != 1 or set(windows[0]) != {'start','end','cycles'}:
            raise ValueError('Incomplete profile window')
        window = {k:int(v) for k,v in windows[0].items()}
        if [window['start'],window['end']] != list(expected) or window['cycles'] <= 0:
            raise ValueError('Wrong profile window')
        with (output/'profile.tsv').open() as stream:
            rows = list(csv.DictReader(stream,delimiter='\t'))
        if not rows or any(set(row) != {'pc','cycles'} for row in rows):
            raise ValueError('Incomplete profile samples')
        samples = [(int(row['pc']),int(row['cycles'])) for row in rows]
        if (len({pc for pc,_ in samples}) != len(samples)
                or any(not 0 <= pc < 65536 or cycles < 0 for pc,cycles in samples)
                or sum(cycles for _,cycles in samples) != window['cycles']):
            raise ValueError('Profile clocks/addresses are inconsistent')
    except (TypeError,ValueError) as error:
        raise ValueError('Invalid instruction profile evidence') from error
    return dict(start=window['start'],end=window['end'],cycles=window['cycles'],pcs=len(samples))


def analyze_fine_math(output: Path, frame_cycles: int) -> dict:
    result = json.loads((output/'fine-math.json').read_text())
    ticks,remainder = advance_clock(0,100000*frame_cycles)
    expected = dict(frames=100000,complete=True,frame_cycles=frame_cycles,
                    ticks=ticks,remainder=remainder)
    if (result != expected or not isinstance(result,dict)
            or any(type(result[k]) is not int for k in ('frames','frame_cycles','ticks','remainder'))
            or result['complete'] is not True):
        raise ValueError('Invalid fine-clock long-run arithmetic proof')
    return result


def analyze_fine_clock(output: Path, frame_cycles: int, count: int) -> dict:
    """Reconcile every physical scanline sample, queue claim and integer clock."""
    if type(frame_cycles) is not int or frame_cycles not in (313*228,262*228):
        raise ValueError('Unsupported fine-clock frame timing')
    quanta = {1:(frame_cycles//228-212)*228*2000,2:128*228*2000,0:84*228*2000}
    with (output/'fine.tsv').open() as stream:
        rows = list(csv.DictReader(stream,delimiter='\t'))
    ticks = remainder = previous_claimed = max_pending = 0
    previous_time = previous_next = None
    max_error = 0.0
    try:
        if not rows:
            raise ValueError('Missing fine-clock samples')
        for row in rows:
            if set(row) != {'claimed','quantum','next','pending','remainder','time'}:
                raise ValueError('Wrong fine-clock sample fields')
            values = {k:int(row[k]) for k in row if k != 'time'}
            time = float(row['time'])
            if (not math.isfinite(time) or time < 0
                    or values['next'] not in quanta or values['quantum'] != quanta[values['next']]
                    or values['remainder'] != remainder
                    or not previous_claimed <= values['claimed'] <= count
                    or not 0 <= values['pending'] <= 0xffffffff
                    or values['claimed']+values['pending'] != ticks):
                raise ValueError('Fine-clock accumulator or queue disagrees with quanta')
            if previous_time is not None:
                error = abs((time-previous_time)*3579545-values['quantum']/2000)
                if (time <= previous_time or values['next'] != (previous_next+1)%3
                        or error > 4096):
                    raise ValueError('Missed or mistimed fine-clock sample')
                max_error = max(max_error,error)
            due,remainder = advance_clock(remainder,values['quantum']//2000)
            ticks += due
            previous_time,previous_next = time,values['next']
            previous_claimed = values['claimed']
            max_pending = max(max_pending,values['pending'])
        final = json.loads((output/'fine-final.json').read_text())
        if (not isinstance(final,dict) or set(final) != {'claimed','pending','remainder'}
                or any(type(v) is not int for v in final.values())
                or final['claimed'] != count or not 0 <= final['pending'] <= 0xffffffff
                or final['claimed']+final['pending'] != ticks or final['remainder'] != remainder):
            raise ValueError('Final fine-clock state disagrees with samples')
    except (KeyError,TypeError,ValueError) as error:
        raise ValueError('Invalid fine-clock execution evidence') from error
    return dict(samples=len(rows),ticks=ticks,remainder=remainder,
                max_pending=max(max_pending,final['pending']),final_pending=final['pending'],
                max_sample_delay_difference_cycles=max_error)


def acquire(root: Path, args) -> Path:
    """Acquire original logic execution; completion alone never proves equality."""
    root = root.resolve()
    bundle,reference = args.rom.parent,args.reference
    verify_manifest(bundle)
    verify_manifest(reference)
    analyze_reference(reference)
    report = json.loads((bundle/'build.json').read_text())
    if (report.get('mode') != 'logic-probe'
            or report.get('reference_manifest_sha256') != digest(reference/'manifest.json')
            or report['timing']['nominal_hz'] != args.hz):
        raise ValueError('Require a logic candidate bound to this reference/refresh')
    levels = load_input_levels(reference)
    count = getattr(args,'ticks',None)
    if count is None:
        count = len(levels)
    if type(count) is not int or not 1 <= count <= len(levels):
        raise ValueError('Invalid logical acquisition length')
    profile = getattr(args,'profile',None)
    if profile is not None and (type(profile) not in (tuple,list) or len(profile) != 2
            or any(type(v) is not int for v in profile)
            or not 1 <= profile[0] < profile[1] <= count or profile[1]-profile[0] > 64):
        raise ValueError('Profile requires an ordered window of at most 64 acquired ticks')
    if not args.bios.is_dir():
        raise ValueError('Supply contributor BIOS files')
    inputs = input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    if inputs != report.get('inputs'):
        raise ValueError('Source ROM inventory differs from candidate')
    output = build_destination(root,args.output)
    session = build_destination(root,output.with_name(output.name+'-session'))
    require_ignored(root,[output/'initialization.bin',output/'state-00001.bin'])
    output.mkdir(parents=True)
    session.mkdir(parents=True)
    shutil.copyfile(root/'scripts/msx/native_acquire.tcl',output/'acquisition.tcl')
    if profile is not None:
        shutil.copyfile(root/'scripts/msx/native_profile.tcl',output/'profile.tcl')
    syms = symbols(bundle/'native.sym')
    before = {str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    (output/'inputs.tcl').write_text('set nr_inputs {'+' '.join('{'+ ' '.join(map(str,row))+'}' for row in levels[:count])+'}\n')
    scanout = getattr(args, 'scanout', False)
    lines = ['set save_settings_on_exit false', 'set sound_driver null',
        *(['set vsync off', 'set renderer SDLGL-PP', 'set pause_on_lost_focus false', 'set pause false',
           'set minframeskip 0', 'set maxframeskip 0', 'set gamma 1', 'set brightness 0',
           'set contrast 0', 'set blur 0', 'set noise 0', 'set scanline 0',
           'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}'] if scanout else ['set renderer none']),
        f'set nr_scanout_enabled {int(scanout)}',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off',
        'set throttle on' if scanout else 'set throttle off', 'set speed 100',
        'set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set nr_out {tcl(output)}',
        f'set nr_target {count}',
        'set nr_entry_spans {'+' '.join('{'+f'{a} {n}'+'}' for a,n in report.get('guarded_entry_spans',[]))+'}',
        'set nr_symbols [dict create '+' '.join(f'{k} {v}' for k,v in syms.items())+']',
        f'source {tcl(output/"inputs.tcl")}',f'source {tcl(output/"acquisition.tcl")}']
    if profile is not None:
        lines += [f'set nr_profile_range {{{profile[0]} {profile[1]}}}',f'source {tcl(output/"profile.tcl")}']
    if getattr(args, 'input_proof', False):
        if not report.get('video_candidate'):
            raise ValueError('Physical input proof requires a video candidate')
        shutil.copyfile(root/'scripts/msx/native_input_probe.tcl',output/'input-probe.tcl')
        lines += [f'source {tcl(output/"input-probe.tcl")}']
    (output/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem; exit 2}\n')
    env = dict(os.environ,OPENMSX_HOME=str(session/'home'),OPENMSX_USER_DATA=str(session/'userdata'))
    with (output/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(output/'session.tcl')],env=env,stdout=log,stderr=subprocess.STDOUT,
                       timeout=300 if scanout else 180,check=True)
    if (before != {str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
            or inputs != input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))):
        raise ValueError('Contributor source/BIOS inventory changed')
    analyze_acquisition(bundle,output,reference,count)
    analyze_boot_registers(output)
    if getattr(args, 'input_proof', False):
        from .native_inputs import analyze_keyboard
        json_write(output/'physical-inputs.json', analyze_keyboard(output/'physical-inputs.tsv'))
    if report.get('function_probe'):
        analyze_function(output)
        if report.get('fine_irq'):
            if report.get('fine_clock') == 'scanline-deadline':
                analyze_deadline_math(output,report['timing']['lines'])
            else:
                analyze_fine_math(output,report['timing']['cpu_cycles'])
    if report.get('fine_irq'):
        fine = (analyze_deadlines(output,report['timing']['lines'],count)
                if report.get('fine_clock') == 'scanline-deadline'
                else analyze_fine_clock(output,report['timing']['cpu_cycles'],count))
        json_write(output/'fine-verification.json',fine)
    if profile is not None:
        json_write(output/'profile.json',analyze_profile(output,profile))
    if report.get('video_candidate'):
        json_write(output/'presentation-costs.json', analyze_presentation_callers(bundle, output))
    verify_manifest(bundle)
    verify_manifest(reference)
    for config in (session/'userdata/machines').glob('*.xml'):
        shutil.copyfile(config,output/'reference-machine.xml')
    json_write(output/'runtime.json',dict(schema_version=1,acquisition_only=True,equivalence=False,
        reference_ticks=len(levels),requested_ticks=count,prefix_only=count!=len(levels),
        profile_range=profile,
        candidate_manifest_sha256=digest(bundle/'manifest.json'),reference_manifest_sha256=digest(reference/'manifest.json'),
        openmsx=subprocess.check_output([args.openmsx,'--version'],text=True).strip(),
        machine=args.machine,bios_sha256=before,inputs=inputs))
    require_ignored(root,[p for p in output.rglob('*') if p.is_file()])
    seal(output)
    verify_manifest(output)
    return output
