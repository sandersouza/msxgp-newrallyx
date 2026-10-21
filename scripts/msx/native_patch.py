"""Validate an entire native patch set before returning a patched RAM image."""
from dataclasses import dataclass
import hashlib

from scripts.z80_analysis import guarded_hook


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
    # No writes, even to a private result, until the complete set is accepted.
    result = bytearray(original)
    for patch in patches:
        result[patch.address:patch.address + len(patch.replacement)] = patch.replacement
    return bytes(result)
