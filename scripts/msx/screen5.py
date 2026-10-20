"""Deterministic, non-merging RGB333 conversion and SCREEN 5 nibble packing."""
from collections import Counter
from PIL import Image

WIDTH, HEIGHT = 256, 212
BITMAP_SIZE = WIDTH * HEIGHT // 2
# openMSX 21.0 SDLRasterizer: V9958 maps RGB3 to RGB5, then truncates RGB8.
# Identity color matrix, gamma 1, brightness/contrast 0.
LEVELS = tuple((((v << 2) | (v >> 1)) * 255) // 31 for v in range(8))


def rgb333(color):
    return tuple(min(range(8), key=lambda i: abs(LEVELS[i]-v)) for v in color)


def expand(color):
    return tuple(LEVELS[v] for v in color)


def pack(indices):
    if len(indices) != WIDTH * HEIGHT or any(type(v) is not int or not 0 <= v < 16 for v in indices):
        raise ValueError('SCREEN 5 requires 256x212 indices in 0..15')
    return bytes((indices[i] << 4) | indices[i + 1] for i in range(0, len(indices), 2))


def convert(images):
    if len(images) != 2 or any(im.mode != 'RGB' or im.size != (WIDTH, HEIGHT) for im in images):
        raise ValueError('Supply two RGB 256x212 compact compositions')
    colors = sorted(set().union(*(set(im.get_flattened_data()) for im in images)))
    if len(colors) > 16:
        raise ValueError(f'{len(colors)} source colors exceed 16; explicit palette review required')
    palette = [rgb333(c) for c in colors]
    if len(set(palette)) != len(palette):
        raise ValueError('RGB333 would merge source colors; explicit palette review required')
    table = {color: i for i, color in enumerate(colors)}
    palette += [(0, 0, 0)] * (16 - len(palette))
    encoded = bytes(v for r, g, b in palette for v in ((r << 4) | b, g))
    results = []
    for image in images:
        counts = Counter(image.get_flattened_data())
        indices = [table[c] for c in image.get_flattened_data()]
        preview = Image.new('RGB', image.size)
        preview.putdata([expand(palette[i]) for i in indices])
        squared = sum(count * sum((a-b)**2 for a,b in zip(c, expand(palette[table[c]])))
                      for c,count in counts.items())
        results.append((pack(indices), preview, dict(
            changed_pixels=sum(n for c,n in counts.items() if c != expand(palette[table[c]])),
            max_channel_error=max(abs(a-b) for c in counts for a,b in zip(c,expand(palette[table[c]]))),
            mean_squared_channel_error=squared/(WIDTH*HEIGHT*3))))
    return encoded, results, [dict(source=list(c), index=i, rgb333=list(palette[i]),
                                   converted=list(expand(palette[i]))) for i,c in enumerate(colors)]
