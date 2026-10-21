#!/usr/bin/env python3
"""Build the default development ROM or launch it in an isolated openMSX session."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import destination
from scripts.msx.raster_scroll import build as build_rom
from scripts.msx.emulator import run as run_emulator
from scripts.scenes.storage import require_ignored


ROM = Path('references/build/newrallyx.rom')


def build(root):
    """Keep build evidence and publish the default ROM only after a successful build."""
    output = destination(root, root/'references/build'/f'default-{uuid4().hex}')
    rom = root/ROM
    if rom.is_symlink() or (rom.exists() and not rom.is_file()):
        raise ValueError(f'Default ROM must be a regular file: {rom}')
    pending = output.with_suffix('.rom.tmp')
    require_ignored(root, [rom, pending])
    args = argparse.Namespace(
        output=output, hz=50,
        assets=root/'references/assets/nrallyx',
        captures=root/'references/scenes/review-fixed-v3',
        normal=root/'references/scenes/rom-input/normal',
        overlap=root/'references/scenes/rom-input/overlap',
        assembler=root/'.tools/sjasmplus/1.24.0/sjasmplus',
    )
    built_rom = build_rom(root, args)
    # Keep the sealed bundle unchanged; publish a separate, stable ROM path.
    try:
        shutil.copyfile(built_rom, pending)
        pending.replace(rom)
    finally:
        pending.unlink(missing_ok=True)
    print(f'Default ROM: {rom.relative_to(root)}')


def run(root):
    args = argparse.Namespace(
        rom=root/ROM, output=root/'references/build'/f'run-{uuid4().hex}',
        bios=root/'references/msxbios', machine='Panasonic_FS-A1WSX', openmsx='openmsx',
    )
    run_emulator(root, args)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'run'))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        {'build': build, 'run': run}[args.command](root)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
