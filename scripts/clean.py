#!/usr/bin/env python3
"""Remove generated builds without touching contributor inputs or local tools."""
import argparse
from pathlib import Path
import shutil
import sys


GENERATED_ROOTS = ('build','cache','sessions','validation','baselines','archive','analysis',
                   'experiments','disassembly','mame-validation','mame-state','screenshots',
                   'stage-one-research','scenes','stage-one','exports','attract','probe','mame-source')


def clean(root, *, dry_run=False):
    root=Path(root)
    references=root/'references'
    for path in (references,references/'build'):
        if path.is_symlink():raise ValueError(f'Refusing to clean through a symlink: {path}')
    entries=[references/name for name in GENERATED_ROOTS if (references/name).exists() or (references/name).is_symlink()]
    if references.exists():entries += [p for p in references.iterdir() if p.name.startswith('issue')]
    entries += [root/name for name in ('outputs',) if (root/name).exists()]
    entries=[p for p in entries if p.is_symlink() or not p.is_dir() or any(c.name!='.gitkeep' for c in p.iterdir())]
    tracked=set()
    if (root/'.git').exists():
        import subprocess
        tracked={root/name for name in subprocess.check_output(['git','ls-files','references'],cwd=root,text=True).splitlines()}
    def remove(path):
        if path.name=='.gitkeep' or path in tracked:return
        if any(p.is_relative_to(path) for p in tracked):
            if path.is_dir() and not path.is_symlink():
                for child in list(path.iterdir()):remove(child)
            return
        if path.is_symlink() or not path.is_dir():path.unlink(missing_ok=True)
        else:
            # Repository placeholders are retained, but binary evidence is not.
            if any(path.rglob('.gitkeep')):
                for child in list(path.iterdir()):remove(child)
            else:shutil.rmtree(path)
    if not dry_run:
        for path in entries:remove(path)
    return sorted(entries)


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
    print(f'{verb} {len(entries)} generated artifact roots; source inputs and documented results are preserved.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
