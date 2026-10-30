#!/usr/bin/env python3
"""Restore missing historical outputs from local Git objects.

No network access, ROM downloads, or overwriting of existing files. Fresh probe
evidence should instead be generated with the driver named in the manifest.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def restore(root, entries, *, check=False):
    counts = dict(matching=0, missing=0, different=0, restored=0)
    for entry in entries:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or len(relative.parts) < 2 or relative.parts[0] != 'outputs':
            raise ValueError(f'Invalid probe path: {relative}')
        path = root/relative
        if not path.resolve().is_relative_to((root/'outputs').resolve()):
            raise ValueError(f'Probe path escapes outputs: {relative}')
        if path.exists():
            matches = path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
            counts['matching' if matches else 'different'] += 1
            continue
        if check:
            counts['missing'] += 1
            continue
        data = subprocess.check_output(['git', 'cat-file', 'blob', entry['git_blob']], cwd=root)
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f'Historical payload digest mismatch: {relative}')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        counts['restored'] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check without writing')
    parser.add_argument('--group', help='Only this outputs/fixed-hud subdirectory, e.g. radar-synthetic')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'docs/retired-artifacts.json').read_text())
    entries = [f for f in manifest['files'] if not args.group or
               (len(Path(f['path']).parts) > 2 and Path(f['path']).parts[2] == args.group)]
    if not entries:
        parser.error('No matching probe group')
    result = restore(ROOT, entries, check=args.check)
    print(json.dumps(result, sort_keys=True))
    return int(bool(result['missing'] or result['different']))


if __name__ == '__main__':
    raise SystemExit(main())
