"""Native renderer resources: all source patterns, no captured game state."""
from pathlib import Path

from scripts.scenes.bundle import load_assets, verify_manifest
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


def resources(renderer: Path, assets_path: Path):
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
    tables = (renderer/f'bank-{bank("HUD_DATA_BANK")}.bin').read_bytes()[:4928]
    banks = [flipped_pens(assets.pixels['tiles'], 8), flipped_pens(assets.pixels['sprites'], 16),
             hud + lookup, tables]
    if any(len(b) > 16384 for b in banks):
        raise ValueError('Native resource bank overflow')
    masks, black = black_tables(assets.pixels['tiles'], bytes(assets.palette['lookup']), translation)
    return {f'video-bank-{n}': b + bytes(16384-len(b)) for n, b in enumerate(banks)}, dict(
        palette=palette, translation=translation, lookup=lookup, lookup_offset=len(hud),
        dots=assets.pixels['dots'], tile_masks=masks, black_masks=black)
