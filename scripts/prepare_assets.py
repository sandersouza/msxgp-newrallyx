#!/usr/bin/env python3
"""Prepare missing arcade inputs; used automatically by make build/run."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('all','graphics','scenes','native'),default='all')
    args=parser.parse_args(argv)
    try:
        from src.toolchain.graphics.prepare import prepare
        prepare(ROOT,args.stage)
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
        print(f'Asset preparation failed: {error}\n'
              'Place the unpacked original nrallyx ROM set in references/roms/nrallyx/.\n'
              'Run make environment for tools. See docs/building.md for filenames and recovery.',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
