"""Cartridge inventory and size-gated publication; metadata contains no ROM data.

Duplicate banks and fill-like tails are investigation candidates. Neither proves
that bytes are unreachable or can be removed without changing bank consumers.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

BANK_BYTES = 16384
PREFERRED_BYTES = 2 * 1024 * 1024
# The2MiB cartridge class is a hard limit, including optional turbo builds.
MAXIMUM_BYTES = PREFERRED_BYTES


def capacity_report(data):
    """Validate the programmed ASCII16 image before replacing any ROM."""
    size = len(data)
    if not size or size % BANK_BYTES:
        raise ValueError('Cartridge image must contain complete 16 KiB banks')
    if size > MAXIMUM_BYTES:
        raise ValueError(f'Cartridge image is {size} bytes; maximum is {MAXIMUM_BYTES}')
    return dict(bytes=size,bank_count=size//BANK_BYTES,mapper='ASCII16',
                sha256=hashlib.sha256(data).hexdigest(),preferred_bytes=PREFERRED_BYTES,
                maximum_bytes=MAXIMUM_BYTES,within_preferred=size<=PREFERRED_BYTES,
                preferred_headroom_bytes=PREFERRED_BYTES-size,
                maximum_headroom_bytes=MAXIMUM_BYTES-size)


def publish_rom(data, target, *, report_path=None):
    """Gate size before touching the last good artifact; replace atomically."""
    # Validate before creating a temporary file: a failed size/alignment gate
    # must leave both the last working ROM and its published report untouched.
    report = capacity_report(data)
    target = Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.'+target.name+'-',dir=target.parent,delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary,target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    if report_path is not None:
        Path(report_path).write_text(json.dumps(report,indent=2)+'\n')
    return report


def inventory(data, *, bank_bytes=BANK_BYTES):
    if not isinstance(bank_bytes, int) or isinstance(bank_bytes, bool) or bank_bytes <= 0:
        raise ValueError('bank_bytes must be a positive integer')
    groups = defaultdict(list)
    banks = []
    for number, offset in enumerate(range(0, len(data), bank_bytes)):
        block = data[offset:offset+bank_bytes]
        sha = hashlib.sha256(block).hexdigest()
        if len(block) == bank_bytes:
            groups[sha].append(number)
        banks.append(dict(number=number, offset=offset, bytes=len(block), sha256=sha,
                          ff_tail_bytes=len(block)-len(block.rstrip(b'\xff')),
                          zero_tail_bytes=len(block)-len(block.rstrip(b'\0')),
                          complete=len(block) == bank_bytes))
    duplicates = [dict(sha256=sha, canonical=ids[0], duplicates=ids[1:])
                  for sha, ids in groups.items() if len(ids) > 1]
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                bank_bytes=bank_bytes, bank_count=len(banks),
                complete_bank_count=len(data)//bank_bytes,
                partial_last_bank_bytes=len(data)%bank_bytes,
                preferred_bytes=PREFERRED_BYTES, maximum_bytes=MAXIMUM_BYTES,
                within_preferred=len(data)<=PREFERRED_BYTES,
                within_maximum=len(data)<=MAXIMUM_BYTES,
                maximum_headroom_bytes=MAXIMUM_BYTES-len(data),
                reduction_needed_for_preferred_bytes=max(0,len(data)-PREFERRED_BYTES),
                accounted_bytes=sum(b['bytes'] for b in banks),
                duplicate_complete_bank_bytes=sum(len(d['duplicates'])*bank_bytes for d in duplicates),
                ff_tail_candidate_bytes=sum(b['ff_tail_bytes'] for b in banks),
                zero_tail_candidate_bytes=sum(b['zero_tail_bytes'] for b in banks),
                duplicate_groups=duplicates, banks=banks,
                limitations='Bank hashes/counts only. Fill-like tails may be addressed data or fixed reservations, not reclaimable padding. Duplicate-bank savings require validated reference remapping; no storage or runtime change is made.')


def bundle_tags(bundle, count):
    tags = defaultdict(set)
    if not bundle:
        return tags
    for filename in ('game-resources.json', 'session-build.json'):
        path = bundle/filename
        if not path.exists():
            continue
        metadata = json.loads(path.read_text())
        for name, number in metadata.get('banks', {}).items():
            if name.endswith('_BANK') and isinstance(number, int) and 0 <= number < count:
                tags[number].add(name)
        for name in ('terrain_banks', 'map_banks', 'edge_banks'):
            for number in metadata.get(name, []):
                if 0 <= number < count:
                    tags[number].add(name)
    return tags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, help='Optional generated metadata directory')
    parser.add_argument('--build-command', help='Recorded build command; this tool does not execute it')
    args = parser.parse_args()
    rom = args.rom.resolve()
    report = inventory(rom.read_bytes())
    tags = bundle_tags(args.bundle, report['bank_count'])
    for bank in report['banks']:
        bank['metadata_tags'] = sorted(tags[bank['number']])
    report['provenance'] = dict(
        rom=str(rom), recorded_build_command=args.build_command,
        checkout=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        working_tree=subprocess.check_output(['git','status','--porcelain=v1'],text=True).splitlines(),
        metadata_directory=str(args.bundle.resolve()) if args.bundle else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in (
        'bytes','sha256','bank_count','maximum_headroom_bytes',
        'reduction_needed_for_preferred_bytes','duplicate_complete_bank_bytes',
        'ff_tail_candidate_bytes','zero_tail_candidate_bytes')},indent=2))


if __name__ == '__main__':
    main()
