#!/usr/bin/env python3
"""Compare isolated original and MSX round preparation using contributor inputs."""
import argparse
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.round_prepare_verify import verify


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--last-round', type=int, choices=range(1,255), default=32)
    parser.add_argument('--bios', type=Path, default=Path('references/msxbios'))
    parser.add_argument('--machine', default='Panasonic_FS-A1WSX')
    parser.add_argument('--mame', default='mame')
    parser.add_argument('--openmsx', default='openmsx')
    verify(Path(__file__).resolve().parents[1], parser.parse_args(argv))


if __name__ == '__main__':
    main()
