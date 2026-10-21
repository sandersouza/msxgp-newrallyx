#!/usr/bin/env python3
"""Generate local-only program analysis and bounded MAME execution evidence."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.graphics.roms import load_metadata, validate_roms, input_records
from scripts.scenes.record import lua_literal, validate_replay
from scripts.scenes.storage import require_ignored, json_write, seal


def program_image(roms, metadata):
    """Apply the inventory's split loads; reject holes, overlap and truncation."""
    image, used = bytearray(0x4000), set()
    for record in metadata['roms']:
        if record['region'] != 'maincpu':
            continue
        data = roms[record['name']]
        for segment in record['loads']:
            first, size = segment['region_offset'], segment['size']
            source = segment['file_offset']
            addresses = set(range(first, first + size))
            if (first < 0 or size <= 0 or first + size > len(image)
                    or source < 0 or source + size > len(data) or used & addresses):
                raise ValueError('Invalid or overlapping program load')
            image[first:first + size] = data[source:source + size]
            used.update(addresses)
    if len(used) != len(image):
        raise ValueError('Program inventory must cover exactly 0000..3fff')
    return bytes(image)


def guarded_hook(image, address, expected_sha256, length, boundaries):
    """Validate a whole-instruction span; this function never patches anything."""
    if (type(address) is not int or type(length) is not int or length <= 0
            or address < 0 or address + length > len(image)
            or address not in boundaries or address + length not in boundaries):
        raise ValueError('Hook must span complete observed instructions')
    if hashlib.sha256(image[address:address + length]).hexdigest() != expected_sha256:
        raise ValueError('Unsupported hook bytes')
    return dict(address=address, length=length, sha256=expected_sha256)


def hook_specs(image):
    specs = json.loads(Path(__file__).with_name('z80_hooks.json').read_text())
    if specs['schema_version']!=1 or specs['set']!='nrallyx':
        raise ValueError('Unsupported hook schema')
    for hook in specs['hooks']:
        start, length = hook['address'], hook['length']
        if hashlib.sha256(image[start:start+length]).hexdigest()!=hook['sha256']:
            raise ValueError(f"Unsupported bytes for {hook['name']}")
    return specs['hooks']


def destination(root, output):
    path = output.absolute()
    allowed = root.resolve() / 'references/analysis'
    if ('..' in path.parts or any(p.is_symlink() for p in [path, *path.parents])
            or not path.is_relative_to(allowed) or path == allowed or path.exists()):
        raise ValueError('Choose a fresh nonsymlink output below references/analysis')
    require_ignored(root, [path / 'program.bin', path / 'manifest.json'])
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
    relative = path.relative_to(root).as_posix().casefold()
    if any(n.casefold() == relative or n.casefold().startswith(relative + '/') for n in tracked if n):
        raise ValueError('Output contains tracked files')
    return path


def generate(root, output, *, capture=False, frames=3200):
    output = destination(root, output)
    metadata = load_metadata()
    inputs = root / 'references/roms/nrallyx'
    roms = validate_roms(inputs, metadata)
    before = input_records(roms)
    image = program_image(roms, metadata)
    hook_specs(image)
    payloads = ['program.bin', 'program.asm', 'linear-index.json', 'disassembler.log',
                'provenance.json', 'manifest.json']
    if capture:
        if type(frames) is not int or not 2402 <= frames <= 3600:
            raise ValueError('Capture frames must be in 2402..3600')
        payloads += ['replay.json', 'config.lua', 'mame.log', 'complete', 'summary.json',
                     'accesses.tsv', 'frames.tsv', 'reset.trace']
        payloads += [f'frame-{f}.trace' for f in (654,756,1015,1860,2300,2400)]
        payloads += [f'state-{f:05d}.bin' for f in range(1799,frames+1)]
        payloads += ['cfg/default.cfg', 'cfg/nrallyx.cfg']
    require_ignored(root, [output/name for name in payloads])
    output.mkdir(parents=True)
    (output / 'program.bin').write_bytes(image)
    result = subprocess.run(['z80dasm', '-a', '-t', '-u', '-g', '0', 'program.bin'],
                            cwd=output, capture_output=True, text=True, check=True)
    (output / 'program.asm').write_text(result.stdout)
    (output / 'disassembler.log').write_text(result.stderr)
    # Linear decoding is exploratory: data and overlapping code need executed PCs.
    annotations = []
    for line in result.stdout.splitlines():
        match = re.search(r';([0-9a-f]{4})\s+((?:[0-9a-f]{2} )*[0-9a-f]{2})', line)
        if match:
            annotations.append(dict(address=int(match[1], 16), text=line.strip()))
    json_write(output / 'linear-index.json', annotations)
    if capture:
        capture_reference(root, output, frames)
        summarize(output, image)
    if input_records(validate_roms(inputs, metadata)) != before:
        raise ValueError('Source ROMs changed')
    json_write(output / 'provenance.json', dict(schema_version=1, inputs=before,
        source=metadata['source'], program_sha256=hashlib.sha256(image).hexdigest(),
        frames=frames if capture else None,
        disassembly='linear sweep; data is not proven code; executed trace is authoritative'))
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])
    seal(output)
    return output


def summarize(output, image):
    """Keep game-derived addresses, disassembly and state evidence local."""
    observed, instructions, trace_counts = set(), {}, {}
    for path in sorted(output.glob('*.trace')):
        hits = Counter()
        for line in path.read_text().splitlines():
            match = re.match(r'^([0-9A-F]{4}): (.*)', line)
            if match:
                address = int(match[1], 16)
                observed.add(address)
                instructions[address] = match[2]
                hits[f'{address:04x}'] += 1
        if not hits:
            raise ValueError(f'Empty execution trace: {path}')
        trace_counts[path.name] = dict(sorted(hits.items()))
    hooks = []
    for spec in hook_specs(image):
        address, length, name = spec['address'], spec['length'], spec['name']
        if address in observed and address + length in observed:
            hook = guarded_hook(image,address,spec['sha256'],length,observed)
            hook.update(name=name, instruction=instructions[address],
                        evidence=[p for p,counts in trace_counts.items() if f'{address:04x}' in counts])
            hooks.append(hook)
    accesses, io_counts, program_writes, reads, writes = 0, Counter(), Counter(), Counter(), Counter()
    exceptional_writes = Counter()
    with (output/'accesses.tsv').open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            count = int(row['count']); accesses += count
            address = int(row['address'],16)
            if row['space']=='io':
                io_counts[f"{row['direction']}:{address:02x}:{row['value']}"] += count
            elif row['direction']=='w':
                region = ('rom' if address<0x4000 else 'video' if 0x8000<=address<=0x8fff
                          else 'work' if 0x9800<=address<=0x9fff else 'hardware' if 0xa000<=address<=0xa187
                          else 'unmapped')
                program_writes[region] += count
                if region in ('rom', 'unmapped'):
                    exceptional_writes[f"{address:04x}@{row['pc_reported']}:{row['value']}"] += count
                if address>=0xa000:
                    writes[f"{address:04x}@{row['pc_reported']}"] += count
            else:
                reads[f"{address:04x}@{row['pc_reported']}"] += count
    if not accesses or not program_writes['video'] or not reads or len(hooks)!=len(hook_specs(image)):
        raise ValueError('Missing memory observation or hook evidence')
    with (output/'frames.tsv').open() as stream:
        frames = list(csv.DictReader(stream, delimiter='\t'))
    transitions = [dict(frame=int(r['frame']), im=int(r['im']), i=r['i'])
        for n,r in enumerate(frames) if n==0 or r['im']!=frames[n-1]['im']]
    json_write(output/'summary.json',dict(schema_version=1, hooks=hooks,
        trace_counts=trace_counts, program_writes=dict(program_writes),
        hardware_reads=dict(sorted(reads.items())), hardware_writes=dict(sorted(writes.items())),
        io=dict(sorted(io_counts.items())), interrupt_transitions=transitions,
        exceptional_writes=dict(sorted(exceptional_writes.items())),
        sampled_sp_range=[min(int(r['sp'],16) for r in frames),max(int(r['sp'],16) for r in frames)],
        access_pc='MAME PC reported during access, often next instruction; not a patch boundary'))


def compare_references(first, second):
    """Compare deterministic evidence, excluding process paths/logs/configuration."""
    names = {'program.bin', 'program.asm', 'linear-index.json', 'provenance.json',
             'accesses.tsv', 'frames.tsv', 'replay.json', 'summary.json'}
    for path in first.iterdir():
        if path.suffix=='.trace' or path.name.startswith('state-'):
            names.add(path.name)
    expected = {p.name for p in second.iterdir() if p.suffix=='.trace' or p.name.startswith('state-')}
    if expected != {n for n in names if n.endswith('.trace') or n.startswith('state-')}:
        raise ValueError('Reference payload inventory differs')
    for name in sorted(names):
        if (first/name).read_bytes() != (second/name).read_bytes():
            raise ValueError(f'Reference replay diverged: {name}')
    return len(names)


def capture_reference(root, output, frames):
    if type(frames) is not int or not 2402 <= frames <= 3600:
        raise ValueError('Capture frames must be in 2402..3600')
    version = subprocess.check_output(['mame', '-help'], text=True).splitlines()[0]
    if not version.startswith('MAME v0.289 '):
        raise ValueError('Requires MAME 0.289')
    replay = validate_replay(json.loads((root / 'scripts/scenes/gameplay-inputs.json').read_text()))
    json_write(output / 'replay.json', replay)
    config = dict(destination=str(output), frames=frames, inputs=replay)
    (output / 'config.lua').write_text('return ' + lua_literal(config) + '\n')
    command = ['mame', 'nrallyx', '-noreadconfig', '-noplugins', '-nocheat',
        '-rompath', str(root / 'references/roms'), '-video', 'none', '-sound', 'none',
        '-nothrottle', '-noautosave', '-noautoframeskip', '-frameskip', '0',
        '-skip_gameinfo', '-debug', '-debugger', 'none', '-autoboot_delay', '0',
        '-autoboot_script', str(root / 'scripts/z80_reference.lua'),
        '-seconds_to_run', str(frames // 50 + 15)]
    for name in ('cfg', 'nvram', 'snapshot', 'state', 'diff'):
        command += [f'-{name}_directory', str(output / name)]
    environment = dict(os.environ, NRALLYX_ANALYSIS_CONFIG=str(output / 'config.lua'))
    with (output / 'mame.log').open('w') as log:
        subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=240)
    if not (output / 'complete').is_file():
        raise ValueError(f'MAME capture incomplete; inspect {output}/mame.log')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--frames', type=int, default=3200)
    parser.add_argument('--compare', type=Path, help='Compare existing output against a second reference')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.compare:
            print(f'{compare_references(args.output,args.compare)} deterministic payloads match')
        else:
            print(generate(root, args.output, capture=args.capture, frames=args.frames))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
