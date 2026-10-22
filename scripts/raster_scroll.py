#!/usr/bin/env python3
"""Build, run or verify the full-screen hardware-scroll diagnostic."""
import argparse
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.raster_scroll import build
from scripts.msx.emulator import run


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'run', 'verify', 'verify-hud', 'verify-player', 'verify-hud-cost'))
    parser.add_argument('--output', type=Path, required=True, help='Fresh output directory')
    parser.add_argument('--rom', type=Path, default=Path('references/build/newrallyx.rom'))
    parser.add_argument('--normal', type=Path, default=Path('references/scenes/rom-input/normal'))
    parser.add_argument('--overlap', type=Path, default=Path('references/scenes/rom-input/overlap'))
    parser.add_argument('--assets', type=Path, default=Path('references/assets/nrallyx'))
    parser.add_argument('--captures', type=Path, default=Path('references/scenes/review-fixed-v3'))
    parser.add_argument('--hz', type=int, choices=(50, 60), default=50)
    parser.add_argument('--assembler', type=Path, default=root/'.tools/sjasmplus/1.24.0/sjasmplus')
    parser.add_argument('--bios', type=Path, default=Path('references/msxbios'))
    parser.add_argument('--machine', default='Panasonic_FS-A1WSX')
    parser.add_argument('--openmsx', default='openmsx')
    parser.add_argument('--headless', action='store_true', help='Verify player RAM/timing without a display or RGB captures')
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify-hud-cost':
            from scripts.msx.hud_verify import measure_attributes
            measure_attributes(root,args)
        elif args.command == 'verify-player':
            from scripts.msx.player_verify import verify
            verify(root,args)
        elif args.command == 'verify-hud':
            from scripts.msx.hud_verify import verify
            verify(root,args)
        elif args.command == 'verify':
            from scripts.msx.raster_verify import verify
            verify(root, args)
        else:
            (build if args.command == 'build' else run)(root, args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
