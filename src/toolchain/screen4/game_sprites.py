"""Exact native car masks and a synthetic oracle for the fixed-HUD adapter.

Call write_assets(output, player_data): player_data is the ignored local
native-player data bank built by src.toolchain.msx.player.build. Its first 1536
bytes contain 12 normal/shifted pairs of two 32-byte mode-2 planes. No
contributor ROM or extracted bytes belong in the repository.

Assembly integration: Init while DI/display-off; provide cy and actor records,
then Prepare -> blanking/DI -> Commit. Preserve R1 16x16 unmagnified, R18=0,
R23=cy low. A new Prepare requires the previous Commit. Interrupt handlers
must preserve a foreground VRAM data pointer if they perform uploads.

Call palette_contract before integration: apply its exact index translation to
all scenery/HUD data and install the returned palette. It preserves every RGB
and validates OR3|9=11black and OR6|10=14black; extracted car masks use those
fixed indices. No palette assumptions should be inferred from a current build.

Actor records are eight signed16 screenX, signed16 screenY, animation0..11,
kind0player/1enemy/255inactive records at c800. Cache c840..c8c1 and scratch
c980..cd6a belong exclusively to this adapter. World pattern VRAM2800..2c7f;
parent HUD pattern IDs144..199 at2c80..2e3f; mode2 colors1800/SAT1a00 with
slots0..13 owned by parent. See game-sprites.inc for source-pixel clipping,
sentinel slot exhaustion and measured synthetic cycle bounds.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from pathlib import Path

ACTORS = 8
FIRST_SLOT = 14
PATTERN_BASE = 0x2800
SET_BYTES = 18 * 32


def native_templates(player_data):
    if len(player_data) < 1536:
        raise ValueError('Need the complete twelve native car facings')
    return b''.join(player_data[i * 128:i * 128 + 64] for i in range(12))


def palette_contract(encoded):
    """Report required source-to-target index permutation; never recolor RGBs."""
    from src.toolchain.msx.player import palette
    remapped, _ = palette(encoded, [], enemy=True)
    old = [encoded[i:i+2] for i in range(0, 32, 2)]
    new = [remapped[i:i+2] for i in range(0, 32, 2)]
    # Duplicate blacks are interchangeable. Preserve exact pair identity for all
    # nonblack colors, and use the same authoritative permutation as player.py.
    _, translated = palette(encoded, [bytes(range(16))], enemy=True)
    if new[11] != b'\0\0' or new[14] != b'\0\0':
        raise ValueError('Both sprite OR indices must encode black')
    return dict(palette=remapped, translation=translated[0],
                translation_required=remapped != encoded,
                source_colors=old, target_colors=new)


def write_assets(output, player_data):
    output = Path(output)
    templates = native_templates(player_data)
    (output / 'game-sprite-templates.bin').write_bytes(templates)
    return dict(template_bytes=len(templates), actors=8, sat_slots=[14, 31],
                pattern_vram=[0x2800, 0x2c7f], hud_pattern_ids=[144, 199],
                ram=[0xc980, 0xcd7f], cache_ram=[0xc840,0xc8c1])


def masked_planes(template, x, y):
    if len(template) != 64:
        raise ValueError('A facing must contain two complete 16x16 planes')
    result = bytearray(64)
    for plane in (0, 32):
        for row in range(16):
            for col in range(16):
                at = plane + (col // 8) * 16 + row
                bit = 128 >> (col % 8)
                if 8 <= x + col < 200 and 0 <= y + row < 212:
                    result[at] |= template[at] & bit
    return bytes(result)


def prepare_reference(templates, actors, cy, active_set=0):
    """Independent byte contract; real VDP enforces eight sprites per scanline.

    Each actor gets two stable slots; one sentinel actor can use the final two
    tail slots. Subsequent sentinel actors are wholly culled for that frame.
    There is no software removal of source pixels to evade scanline limits.
    """
    if len(templates) != 768 or len(actors) != 8 or active_set not in (0, 1):
        raise ValueError('Invalid sprite preparation contract')
    hidden = (cy + 211) & 255
    hidden += hidden == 216
    sat = bytearray(bytes((hidden, 0, 0, 0)) * 18)
    colors = bytearray(288)
    patterns = bytearray(SET_BYTES)
    culled = []
    tail_used = False
    for i, (x, y, animation, kind) in enumerate(actors):
        if kind not in (0, 1) or animation not in range(12):
            continue
        if x < -7 or x >= 200 or y < -15 or y >= 212:
            continue
        sentinel = ((y + cy - 1) & 255) == 216
        if sentinel and tail_used:
            culled.append(i)
            continue
        plane = masked_planes(templates[animation * 64:animation * 64 + 64], x, y)
        ec = 128 if x < 0 else 0
        px = x + 32 if x < 0 else x
        inks = (3, 0x49) if kind == 0 else (6, 0x4a)
        for p in range(2):
            group = i * 2 + p
            source = plane[p * 32:p * 32 + 32]
            main = source
            if sentinel:
                main = b'\0' + source[:15] + b'\0' + source[16:31]
                tail = bytes((source[15],)) + bytes(15) + bytes((source[31],)) + bytes(15)
                patterns[(16+p)*32:(17+p)*32] = tail
                sat[(16+p)*4:(17+p)*4] = bytes(((y+cy+14)&255, px, (active_set*18+16+p)*4, 0))
                colors[(16+p)*16:(17+p)*16] = bytes((inks[p] | ec,)) * 16
            patterns[group*32:(group+1)*32] = main
            sat[group*4:(group+1)*4] = bytes(((y+cy-1-int(sentinel))&255, px, (active_set*18+group)*4, 0))
            colors[group*16:(group+1)*16] = bytes((inks[p] | ec,)) * 16
        tail_used |= sentinel
    return dict(sat=bytes(sat), colors=bytes(colors), patterns=bytes(patterns), culled=culled)
