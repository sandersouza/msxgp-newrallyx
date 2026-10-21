#!/usr/bin/env python3
"""Remove generated builds without touching contributor inputs or local tools."""
import argparse
from pathlib import Path
import shutil
import sys


def clean(root, *, dry_run=False):
    build = root/'references'/'build'
    for path in (build.parent,build):
        if path.is_symlink():
            raise ValueError(f'Refusing to clean through a symlink: {path}')
    if not build.exists():
        return []
    if not build.is_dir():
        raise ValueError(f'Build output is not a directory: {build}')
    entries = sorted(p for p in build.iterdir() if p.name!='.gitkeep')
    if not dry_run:
        for path in entries:
            if path.is_symlink() or not path.is_dir():
                path.unlink()
            else:
                shutil.rmtree(path)
    return entries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',help='List build entries without deleting them')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        entries = clean(root,dry_run=args.dry_run)
    except (ValueError,OSError) as error:
        print(f'Error: {error}',file=sys.stderr)
        return 2
    if args.dry_run:
        for path in entries:
            print(path.relative_to(root))
    verb = 'Would remove' if args.dry_run else 'Removed'
    print(f'{verb} {len(entries)} build entries from references/build/.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
