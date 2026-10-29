"""Two-color effect conversion, authorized for this experiment on 2026-10-28.

Preserve every tile's dimensions. Keep each row's two most frequent colors;
map other pixels to the nearest retained RGB, matching the reviewed proposal.
This concession applies only to smoke and explosion, not other game assets.
"""
from collections import Counter
from scripts.msx.raster_scroll import palette_rgb


def adapt(tiles, palette):
    rgb = palette_rgb(palette)
    result, changed = [], 0
    for tile in tiles:
        if len(tile) != 64:
            raise ValueError('Effects require complete native 8x8 tiles')
        pixels = bytearray()
        for y in range(8):
            row = tile[y*8:y*8+8]
            kept = [c for c, _ in Counter(row).most_common(2)]
            selected = bytes(c if c in kept else min(kept, key=lambda k:
                sum((a-b)**2 for a, b in zip(rgb[c], rgb[k]))) for c in row)
            changed += sum(a != b for a, b in zip(row, selected))
            pixels.extend(selected)
        result.append(bytes(pixels))
    return result, changed
