#!/usr/bin/env python3
"""Extract original nrallyx graphics; never downloads or modifies input ROMs."""
import argparse
from pathlib import Path
import sys

if __package__:
    from .graphics.roms import input_records, load_metadata, validate_roms
    from .graphics.decode import decode_graphics, decode_palette, graphics_metadata
else:
    from graphics.roms import input_records, load_metadata, validate_roms
    from graphics.decode import decode_graphics, decode_palette, graphics_metadata

REPO_ROOT = Path(__file__).resolve().parents[1]


def _path(value):
    if not value.strip():
        raise argparse.ArgumentTypeError('Path must not be empty')
    return Path(value)


def _region(roms, metadata, region, size):
    buffer = bytearray(size)
    for entry in metadata['roms']:
        if entry['region'] == region:
            for load in entry['loads']:
                start, count = load['region_offset'], load['size']
                offset = load['file_offset']
                if start < 0 or start+count > size or offset+count > len(roms[entry['name']]):
                    raise ValueError(f'Invalid load metadata for {entry["name"]}')
                buffer[start:start+count] = roms[entry['name']][offset:offset+count]
    return bytes(buffer)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(
        'Extract the unpacked nrallyx set pinned to MAME 0.289. '
        'Requires Python 3.14 and Pillow 13.0.0. Generated data must stay '
        'strictly below this repository\'s ignored references/assets/.'))
    parser.add_argument('--input', required=True, type=_path, help='Contributor-supplied unpacked ROM directory')
    parser.add_argument('--output', required=True, type=_path, help='New directory below references/assets/')
    parser.add_argument('--overwrite', action='store_true',
                        help='Replace only an unchanged complete extraction; unknown or modified output is preserved')
    args = parser.parse_args(argv)
    try:
        if sys.version_info[:2] != (3,14):
            raise ValueError('Use Python 3.14, preferably .venv/bin/python; see docs/setup.md')
        if __package__:
            from .graphics.export import publish_output, write_payload, PILLOW_VERSION
        else:
            from graphics.export import publish_output, write_payload, PILLOW_VERSION
        if PILLOW_VERSION != '13.0.0':
            raise ValueError('Install Pillow 13.0.0 using .venv/bin/python -m pip install -r requirements.txt')
        metadata = load_metadata()
        buffers = validate_roms(args.input, metadata)
        pixels = decode_graphics(_region(buffers, metadata, 'gfx1', 4096),
                                 _region(buffers, metadata, 'gfx2', 256))
        proms = _region(buffers, metadata, 'proms', 352)
        palette = decode_palette(proms[:32], proms[32:288])
        manifest = publish_output(REPO_ROOT, args.input, args.output, args.overwrite,
            lambda staging: write_payload(staging, pixels, palette, graphics_metadata(),
                                          input_records(buffers), metadata['source']))
        print(f'Extracted {len(manifest["outputs"])} payload files plus manifest into {args.output}')
        return 0
    except ImportError as error:
        print(f'Extraction failed: {error}. Install dependencies with '
              '.venv/bin/python -m pip install -r requirements.txt', file=sys.stderr)
        return 1
    except (ValueError, OSError) as error:
        print(f'Extraction failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
