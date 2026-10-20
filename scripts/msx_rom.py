#!/usr/bin/env python3
"""Build and run the local SCREEN 5 static-scene cartridge."""
import argparse
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.build import build


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build','run','verify'])
    parser.add_argument('--normal',type=Path,default=Path('references/scenes/rom-input/normal'))
    parser.add_argument('--overlap',type=Path,default=Path('references/scenes/rom-input/overlap'))
    parser.add_argument('--output',type=Path,default=Path('references/build/screen5'))
    parser.add_argument('--assembler',type=Path,default=root/'.tools/sjasmplus/1.24.0/sjasmplus')
    parser.add_argument('--machine',default='Panasonic_FS-A1WSX')
    parser.add_argument('--bios',type=Path,default=Path('references/msxbios'))
    parser.add_argument('--rom',type=Path,default=Path('references/build/screen5/static-scene.rom'))
    parser.add_argument('--openmsx',default='openmsx')
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            print(build(root,args.normal,args.overlap,args.output,args.assembler))
        else:
            from scripts.msx.emulator import run
            run(root,args,verify=args.command=='verify')
        return 0
    except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as error:
        print(f'Error: {error}',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
