"""Strict offline replay comparison; acquisition completion is not equivalence."""
import csv
import json
import math
from itertools import zip_longest
from pathlib import Path

from .native_contract import Snapshot, first_difference
from .native_verify import (analyze_reference, analyze_acquisition, load_input_levels,
                            analyze_boot_registers, analyze_fine_clock)
from .native_reset import PROGRAM_SHA256
from .native_deadline import analyze_deadlines
from src.toolchain.scenes.bundle import digest, verify_manifest
from src.toolchain.scenes.storage import json_write, seal, require_ignored
from src.toolchain.legacy.z80_analysis import destination


def snapshot(path: Path, tick: int, phase: str) -> Snapshot:
    data = path.read_bytes()
    return Snapshot(tick,phase,data[:4096],data[4096:6144],data[6144:])


def compare_series(expected, actual, exclusions=()) -> dict:
    exclusions = tuple(exclusions)
    first = None
    different = count = 0
    for n,(left,right) in enumerate(zip_longest(expected,actual)):
        if (not isinstance(left,Snapshot) or not isinstance(right,Snapshot)
                or left.tick != n or right.tick != n
                or (n == 0 and left.phase != 'initialization-entry')
                or (n > 0 and left.phase not in ('post-game-irq','post-game-irq-transfer','post-game-irq-collision'))):
            raise ValueError('Incomplete or misnumbered replay snapshots')
        difference = first_difference(left,right,exclusions)
        count += 1
        if difference:
            different += 1
            if first is None:
                first = difference
    if count < 2:
        raise ValueError('Replay requires reset and completed game IRQ snapshots')
    return dict(schema_version=1,state_equivalence=first is None,
                compared_snapshots=count,snapshot_bytes=6536,
                different_snapshots=different,first_difference=first,
                exclusions=[vars(item) for item in exclusions])


def native_phases(path: Path, expected: tuple[str,...] | None = None) -> tuple[str,...]:
    with path.open() as stream:
        rows = list(csv.DictReader(stream,delimiter='\t'))
    fields = {'tick','phase','pc','sp','pending','cycles','time'}
    if expected is None:
        expected = tuple(row.get('phase') for row in rows[1::2])
    if any(phase not in ('post-game-irq','post-game-irq-transfer','post-game-irq-collision') for phase in expected):
        raise ValueError('Unknown native publication phase')
    if len(rows) != 2*len(expected):
        raise ValueError('Incomplete native IRQ boundary sequence')
    previous_time = -1
    phases = []
    try:
        for n,phase in enumerate(expected):
            pre,post = rows[2*n:2*n+2]
            if set(pre) != fields or set(post) != fields:
                raise ValueError('Wrong native IRQ boundary fields')
            a = {k:int(pre[k]) for k in fields-{'phase','time'}}
            b = {k:int(post[k]) for k in fields-{'phase','time'}}
            begin,end = float(pre['time']),float(post['time'])
            if (not math.isfinite(begin) or not math.isfinite(end)
                    or not previous_time <= begin < end
                    or pre['phase'] != 'pre-game-irq' or post['phase'] != phase
                    or a['tick'] != n or b['tick'] != n+1 or a['pc'] != 0x1f0
                    or not 0x4000 <= b['pc'] < 0x8000 or a['cycles'] != 0
                    or abs(round((end-begin)*3579545)-b['cycles']) > 1
                    or not 0x8000 <= a['sp'] <= 0x8400
                    or b['sp'] != (0x8400 if phase == 'post-game-irq-transfer' else
                                    a['sp']-12 if phase == 'post-game-irq-collision' else a['sp'])
                    or any(not 0 <= row['pending'] <= 0xffffffff for row in (a,b))):
                raise ValueError('Native IRQ tick/phase/SP/time changed')
            phases.append(phase)
            previous_time = end
    except (KeyError,TypeError,ValueError) as error:
        raise ValueError('Invalid native IRQ boundary evidence') from error
    return tuple(phases)


def compare_acquisition(root: Path, bundle: Path, capture: Path, reference: Path, output: Path) -> dict:
    """Write sealed diagnostics and raise on any complete-byte divergence."""
    for path in (bundle,capture,reference):
        verify_manifest(path)
    source = analyze_reference(reference)
    count = source['ticks']
    build = json.loads((bundle/'build.json').read_text())
    runtime = json.loads((capture/'runtime.json').read_text())
    provenance = json.loads((reference/'provenance.json').read_text())
    if (build.get('mode') != 'logic-probe' or runtime.get('acquisition_only') is not True
            or runtime.get('equivalence') is not False or runtime.get('prefix_only') is not False
            or type(runtime.get('requested_ticks')) is not int or runtime['requested_ticks'] != count
            or type(runtime.get('reference_ticks')) is not int or runtime['reference_ticks'] != count
            or runtime.get('candidate_manifest_sha256') != digest(bundle/'manifest.json')
            or runtime.get('reference_manifest_sha256') != digest(reference/'manifest.json')
            or build.get('reference_manifest_sha256') != digest(reference/'manifest.json')
            or build.get('source_program_sha256') != PROGRAM_SHA256
            or provenance.get('program_sha256') != PROGRAM_SHA256
            or build.get('program_sha256') != digest(bundle/'native-program.bin')
            or not build.get('inputs') or build['inputs'] != runtime.get('inputs')
            or build['inputs'] != provenance.get('inputs')):
        raise ValueError('Unbound or incomplete replay/source identity')
    levels = load_input_levels(reference)
    script = 'set nr_inputs {'+' '.join('{'+ ' '.join(map(str,row))+'}' for row in levels)+'}\n'
    if (capture/'inputs.tcl').read_text() != script:
        raise ValueError('Native replay levels differ from the reference')
    analyze_acquisition(bundle,capture,reference,count)
    analyze_boot_registers(capture)
    if build.get('fine_irq'):
        if build.get('fine_clock') == 'scanline-deadline':
            analyze_deadlines(capture,build['timing']['lines'],count)
        else:
            analyze_fine_clock(capture,build['timing']['cpu_cycles'],count)
    with (reference/'boundaries.tsv').open() as stream:
        phases = tuple(row['phase'] for row in csv.DictReader(stream,delimiter='\t')
                       if row['phase'].startswith('post-game-irq'))
    native_phases(capture/'events.tsv',phases)
    def states(folder):
        yield snapshot(folder/'initialization.bin',0,'initialization-entry')
        for n,phase in enumerate(phases,1):
            yield snapshot(folder/f'state-{n:05d}.bin',n,phase)
    report = compare_series(states(reference),states(capture))
    report.update(candidate_manifest_sha256=digest(bundle/'manifest.json'),
                  capture_manifest_sha256=digest(capture/'manifest.json'),
                  reference_manifest_sha256=digest(reference/'manifest.json'))
    output = destination(root.resolve(),output)
    require_ignored(root,[output/'comparison.json'])
    output.mkdir(parents=True)
    json_write(output/'comparison.json',report)
    seal(output)
    verify_manifest(output)
    if not report['state_equivalence']:
        raise ValueError(f"Native state diverged: {report['first_difference']}; report: {output}")
    return report
