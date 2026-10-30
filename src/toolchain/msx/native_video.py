"""Native renderer resources: all source patterns, no captured game state."""
from pathlib import Path

from src.toolchain.scenes.bundle import load_assets, verify_manifest
from .screen5 import rgb333


def flipped_pens(pixels: bytes, size: int) -> bytes:
    """Four original-size orientations, packed four two-bit pixels per byte."""
    if size not in (8, 16) or len(pixels) % (size*size) or any(p > 3 for p in pixels):
        raise ValueError('Invalid original two-bit pattern data')
    result = bytearray()
    for start in range(0, len(pixels), size*size):
        for flags in range(4):
            oriented = [pixels[start + (size-1-y if flags & 2 else y)*size +
                               (size-1-x if flags & 1 else x)]
                        for y in range(size) for x in range(size)]
            result.extend((oriented[n] << 6) | (oriented[n+1] << 4) |
                          (oriented[n+2] << 2) | oriented[n+3]
                          for n in range(0, len(oriented), 4))
    return bytes(result)


def native_palette(original: dict, hud_palette: bytes):
    """Retain HUD sprite color numbers; reserve zero for bitmap transparency.

    The existing HUD has two spare entries. Move its opaque color zero to 14,
    and use 15 for the original orange absent from the diagnostic first stage.
    Original black index one maps to opaque black 11, independently of zero.
    """
    if len(hud_palette) != 32:
        raise ValueError('A complete 16-entry HUD palette is required')
    palette = bytearray(hud_palette)
    palette[28:30] = palette[:2]
    palette[:2] = b'\0\0'
    r, g, b = rgb333(original['rgb'][4])
    palette[30:32] = bytes(((r << 4) | b, g))
    colors = [(palette[n] >> 4, palette[n+1], palette[n] & 7) for n in range(0, 32, 2)]
    if colors[0] != (0, 0, 0) or colors[11] != (0, 0, 0):
        raise ValueError('Transparent and opaque black entries must both be black')
    translation = bytes(0 if n == 0 else 11 if n == 1 else colors.index(rgb333(rgb))
                        for n, rgb in enumerate(original['rgb'][:16]))
    if len(set(translation)) != 16:
        raise ValueError('Native palette merges distinct source indices')
    # Each table maps a pair of source pens to one SCREEN 5 byte.
    lookup = bytes((translation[original['lookup'][p*4 + (pair >> 2)]] << 4) |
                   translation[original['lookup'][p*4 + (pair & 3)]]
                   for p in range(64) for pair in range(16))
    return bytes(palette), translation, lookup


def black_tables(tiles: bytes, lookup: bytes, translation: bytes):
    if len(tiles) != 16384 or any(p > 3 for p in tiles) or len(lookup) != 256 or len(translation) != 16:
        raise ValueError('Invalid original tile/lookup inventory')
    masks = bytes(sum(1 << pen for pen in set(tiles[n:n+64])) for n in range(0, 16384, 64))
    black = bytes(sum(1 << pen for pen in range(4) if translation[lookup[p*4+pen]] in (0, 11))
                  for p in range(64))
    return masks, black


def borderless_radar(patterns: bytes) -> bytes:
    """Blank the native radar's twelve base cells; live flags remain separate."""
    if len(patterns) != 768:
        raise ValueError('A complete radar base pattern set is required')
    return bytes(len(patterns))


def strip_atlas(program, tiles, lookup, translation):
    """Cache legal maze rows, their phases, and the first two flower sets.

    Derive every byte from ROM graphics/geometry, never a gameplay capture.
    Thirty 24x8 strips occupy unused VRAM lines208..231, below actor patterns
    and above the HUD color table at232. No sprite slots are allocated.
    """
    from .stage_one import cells_from_rom, tile
    from .native_scene import tile_pixels
    if len(program) != 16384:
        raise ValueError('Strip atlas requires the complete original program')
    keys = set()
    for value in set(cells_from_rom(program, 0x30)):
        cells = bytes((value,))*1792
        for y in range(3):
            key = tuple(tile(program, cells, x, y, 0x0d, 0x56) for x in range(3))
            if all(len(set(tile_pixels(tiles, lookup, c, a))) > 1 for c, a in key):
                keys.update(key[n:]+key[:n] for n in range(3))
    ordered = sorted(keys)
    ordered += [tuple((base+y*3+x, 0x51+(base-0x56)//9) for x in range(3))
                for base in (0x56, 0x5f) for y in range(3)]
    if len(ordered) > 30:
        raise ValueError('Strip atlas overlaps HUD VRAM')
    buckets = [[] for _ in range(16)]
    pixels = bytearray()
    for slot, key in enumerate(ordered):
        blocks = [bytes(translation[c] for c in tile_pixels(tiles, lookup, code, attr))
                  for code, attr in key]
        row = bytes(blocks[x//8][y*8+x%8] for y in range(8) for x in range(24))
        pixels.extend((row[n] << 4) | row[n+1] for n in range(0, 192, 2))
        code, attr = key[0]
        buckets[(code ^ attr ^ (attr >> 4)) & 15].append(
            bytes(c for c, a in key)+bytes(a for c, a in key)+
            bytes((slot%10*24, 208+slot//10*8)))
    offsets, records = bytearray(), bytearray()
    for bucket in buckets:
        offsets.extend(len(records).to_bytes(2, 'little'))
        records.append(len(bucket))
        records.extend(b''.join(bucket))
    return bytes(pixels), bytes(offsets), bytes(records), len(ordered)


def plane_masks():
    """Four packed source pens to a mask nibble; pure authored arithmetic."""
    return bytes(sum(8 >> x for x, shift in enumerate((6, 4, 2, 0))
                     if (value >> shift) & 3 in ink)
                 for ink in ({1}, {2}, {3}, {1, 3}, {2, 3}) for value in range(256))


def resources(renderer: Path, assets_path: Path, program: bytes, *, hardware_actors=False):
    verify_manifest(renderer)
    assets = load_assets(assets_path)
    palette, translation, lookup = native_palette(assets.palette, (renderer/'palette.bin').read_bytes())
    import re
    config = (renderer/'config.inc').read_text()
    def bank(name):
        return int(re.search(rf'^{name} EQU (\d+)$', config, re.M)[1])
    hud = (renderer/f'bank-{bank("HUD_BANK")}.bin').read_bytes()[:13824]
    hud = bytes(((14 if value >> 4 == 0 else value >> 4) << 4) |
                (14 if value & 15 == 0 else value & 15) for value in hud)
    tables = bytearray((renderer/f'bank-{bank("HUD_DATA_BANK")}.bin').read_bytes()[:4928])
    tables[4096:4864] = borderless_radar(bytes(tables[4096:4864]))
    strips, strip_offsets, strip_keys, strip_count = strip_atlas(
        program, assets.pixels['tiles'], bytes(assets.palette['lookup']), translation)
    tables.extend(bytes(0x2800-len(tables)))
    tables.extend(strips)
    if hardware_actors:
        expected = {1: (0, 3, 9, 11), 2: (0, 13, 1, 11), 3: (0, 6, 14, 0)}
        if any(tuple(translation[assets.palette['lookup'][p*4+n]] for n in range(4)) != colors
               for p, colors in expected.items()):
            raise ValueError('Unsupported original actor palette')
        tables.extend(bytes(0x3400-len(tables)))
        tables.extend(plane_masks())
    # Strip matching runs with asset-3 in CPU page0. Keep immutable descriptors
    # there rather than consuming scarce resident code space.
    tables.extend(bytes(0x3a00-len(tables)))
    tables.extend(strip_offsets+strip_keys)
    banks = [flipped_pens(assets.pixels['tiles'], 8), flipped_pens(assets.pixels['sprites'], 16),
             hud + lookup, bytes(tables)]
    if any(len(b) > 16384 for b in banks):
        raise ValueError('Native resource bank overflow')
    masks, black = black_tables(assets.pixels['tiles'], bytes(assets.palette['lookup']), translation)
    return {f'video-bank-{n}': b + bytes(16384-len(b)) for n, b in enumerate(banks)}, dict(
        palette=palette, translation=translation, lookup=lookup, lookup_offset=len(hud),
        dots=assets.pixels['dots'], tile_masks=masks, black_masks=black,
        strip_offsets=strip_offsets, strip_keys=strip_keys, strip_count=strip_count)
