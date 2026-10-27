#!/usr/bin/env python3
"""Inventory original New Rally-X round preparation from local contributor ROMs."""
import argparse
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.round_inventory import run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path, default=Path('references/assets/nrallyx'))
    parser.add_argument('--last-round', type=int, choices=range(1, 255), default=32)
    parser.add_argument('--mame', default='mame')
    args = parser.parse_args(argv)
    run(Path(__file__).resolve().parents[1], args)


if __name__ == '__main__':
    main()
