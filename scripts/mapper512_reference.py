"""Keep the existing512KiB experiment pinned to its accepted mapper input.

The corrected default fixed-RAM cartridge is a separate binding. Rebuild the
historical mapper input from contributor assets when absent; never read the
moving default delivery as if its symbols matched this reference bundle.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SHA256='44be6037d05ebf763283f14ef6deb6e4a8bd58b0a25fcc04c693d899c3704f00'


def reference():
    owner=ROOT/'references/build/game-compact-runtime';rom=owner/'newrallyx.rom'
    if not rom.exists():
        from compact_game_build import build
        build(fixed_ram=False)
    if hashlib.sha256(rom.read_bytes()).hexdigest()!=SHA256:
        raise ValueError('512KiB mapper input differs from its sealed reference; do not substitute the current fixed-RAM cartridge')
    return rom
