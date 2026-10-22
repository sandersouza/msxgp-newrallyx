"""Guard the cold-initialization fragment; no captured state is linked."""
import hashlib

from .native_patch import Patch, apply_patches


PROGRAM_SHA256 = 'd6943e556fcd6ffc32bcc1cc4abbec2249c16a2059a3cdc0ba9c942dbb765d4c'


def patch_reset(image: bytes, finalize: int, boundaries: frozenset[int]) -> bytes:
    return apply_patches(image, PROGRAM_SHA256, reset_patches(finalize), boundaries)


def reset_patches(finalize: int) -> tuple[Patch, ...]:
    if type(finalize) is not int or not 0x4000 <= finalize < 0x8000:
        raise ValueError('Reset finalizer must be resident page-1 code')
    return (
        # Retain the original cold RAM initialization. Replace the cabinet
        # interrupt-mode setup with a host-owned transition into game init.
        Patch(0x38cc, 'a14b960855f70e6926a17bbf4b0ed690035927921060ab58ef001f585f92f0ea',
              bytes((0xc3, finalize & 255, finalize >> 8, 0)), 0x38d0),
        # The original checksum includes the deliberately adapted code. ROM
        # revision/integrity is checked against the full SHA-256 before patching.
        # Keep the initialization's success path, including its RAM effects.
        Patch(0x397e, '24a18920807807c8febae511f44fc4763cde03038c20aad2217c89c95d3f1ad3',
              bytes(2), 0x3980),
    )
