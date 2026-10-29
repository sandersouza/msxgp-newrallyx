"""Checked sound-only address adaptation; original code/data stays in references.

The sound overlay executes at its original Page0 code/table addresses. Only
its state and hardware destinations move. This avoids relocating song pointers
or mixing the original sound workspace with the existing presentation code.
"""
import re
import subprocess


ENTRY = 0x2580
CODE = ((0x2580, 0x2afd), (0x2b17, 0x2b3c))
STATE = 0x3800
REGISTERS = 0x3a00
BANG = 0x3a20


def map_address(value):
    if 0x8a00 <= value < 0x8c00:
        return STATE + value - 0x8a00
    if 0x8000 <= value < 0x8a00 or 0x8c00 <= value < 0x9000:
        return value + 0x6000
    if 0xa100 <= value < 0xa120:
        return REGISTERS + value - 0xa100
    if value in (0xa180, 0xa182):
        return BANG + int(value == 0xa182)
    if 0xa000 <= value < 0xa200:
        raise ValueError(f'Unexpected sound hardware address {value:04x}')
    return value


def relocate(program, instructions, *, complete=True):
    if len(program) != 16384:
        raise ValueError('Expected one validated 16 KB original program')
    image = bytearray(program)
    visited = set()
    changes = []
    for at, raw, text in instructions:
        if not any(start <= at and at + len(raw) <= end for start, end in CODE):
            raise ValueError('Sound instruction outside the selected code ranges')
        span = set(range(at, at + len(raw)))
        if not raw or span & visited or program[at:at+len(raw)] != raw:
            raise ValueError('Overlapping or mismatched sound instruction bytes')
        visited.update(span)
        if text.startswith(('defb', 'defw')):
            raise ValueError('Undecoded data in sound code range')
        if text.startswith(('call ', 'jp ')) and len(raw) == 3:
            target = int.from_bytes(raw[-2:], 'little')
            if not any(start <= target < end for start, end in CODE):
                raise ValueError(f'Sound control flow leaves selected code: {target:04x}')
        if len(raw) < 3 or not text.startswith('ld ') or re.search(r'\((?:ix|iy)(?:[+-]|\))', text):
            continue
        value = int.from_bytes(raw[-2:], 'little')
        mapped = map_address(value)
        if mapped != value:
            image[at+len(raw)-2:at+len(raw)] = mapped.to_bytes(2, 'little')
            changes.append(dict(address=at, original=value, target=mapped))
    if complete and visited != {at for start, end in CODE for at in range(start, end)}:
        raise ValueError('Incomplete sound code coverage')
    image[STATE:0x3b00] = bytes(0x300)
    return bytes(image), changes


def build(program, out):
    instructions = []
    for start, end in CODE:
        path = out / f'audio-code-{start:04x}.bin'
        path.write_bytes(program[start:end])
        listing = subprocess.check_output(['z80dasm', '-a', '-t', '-g', str(start), str(path)],
                                          text=True, stderr=subprocess.DEVNULL)
        (out / f'audio-code-{start:04x}.asm').write_text(listing)
        for line in listing.splitlines():
            match = re.search(r';([0-9a-f]{4})\s+((?:[0-9a-f]{2}\s+)+)', line)
            if match:
                instructions.append((int(match[1], 16), bytes.fromhex(match[2]), line.split(';', 1)[0].strip()))
    image, changes = relocate(program, instructions)
    (out/'audio-overlay.bin').write_bytes(image)
    return image, changes
