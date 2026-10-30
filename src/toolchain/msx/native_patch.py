"""Validate an entire native patch set before returning a patched RAM image."""
from dataclasses import dataclass
import hashlib

from src.toolchain.legacy.z80_analysis import guarded_hook


@dataclass(frozen=True)
class Patch:
    address: int
    expected_sha256: str
    replacement: bytes
    continuation: int


def apply_patches(image: bytes, expected_sha256: str, patches: tuple[Patch, ...],
                  boundaries: frozenset[int]) -> bytes:
    """Require pinned original bytes and evidenced boundaries, never mutate input.

    Boundaries must come from reviewed execution evidence. This function cannot
    establish that a caller-supplied instruction map is truthful or exhaustive.
    Stub destination allocation is validated separately by native_layout.
    """
    if not isinstance(image, (bytes, bytearray)) or len(image) != 0x4000:
        raise ValueError('Native program must contain exactly 16384 bytes')
    original = bytes(image)
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise ValueError('Unsupported complete native program hash')
    if any(type(address) is not int or not 0 <= address <= len(original)
           for address in boundaries):
        raise ValueError('Invalid instruction boundary evidence')
    spans = []
    for patch in patches:
        if not isinstance(patch, Patch):
            raise ValueError('Invalid native patch record')
        if type(patch.replacement) is not bytes or not patch.replacement:
            raise ValueError('Patch replacement must contain immutable bytes')
        length = len(patch.replacement)
        guarded_hook(original, patch.address, patch.expected_sha256, length, boundaries)
        if (type(patch.continuation) is not int
                or not 0 <= patch.continuation < len(original)
                or patch.continuation not in boundaries):
            raise ValueError('Patch continuation must be an evidenced instruction')
        end = patch.address + length
        if any(patch.address < previous_end and previous_start < end
               for previous_start, previous_end in spans):
            raise ValueError('Native patch spans overlap')
        spans.append((patch.address, end))
    # A whole-instruction span is insufficient if another executed instruction
    # branches into its interior. Check direct Z80 control flow at every observed
    # boundary. Replaced source instructions no longer supply incoming edges.
    absolute = {0xc3,0xc2,0xca,0xd2,0xda,0xe2,0xea,0xf2,0xfa,
                0xcd,0xc4,0xcc,0xd4,0xdc,0xe4,0xec,0xf4,0xfc}
    relative = {0x10,0x18,0x20,0x28,0x30,0x38}
    for address in boundaries:
        if address >= len(original) or any(a <= address < b for a, b in spans):
            continue
        opcode = original[address]
        target = None
        if opcode in absolute and address+2 < len(original):
            target = int.from_bytes(original[address+1:address+3], 'little')
        elif opcode in relative and address+1 < len(original):
            offset = original[address+1]
            target = (address+2+(offset if offset < 128 else offset-256)) & 65535
        elif opcode & 0xc7 == 0xc7:
            target = opcode & 0x38
        if target is not None and any(a < target < b for a, b in spans):
            raise ValueError(f'Original control flow enters patch interior: {address:04x}->{target:04x}')
    # No writes, even to a private result, until the complete set is accepted.
    result = bytearray(original)
    for patch in patches:
        result[patch.address:patch.address + len(patch.replacement)] = patch.replacement
    return bytes(result)
