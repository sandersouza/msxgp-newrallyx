"""Layouts and resistor network from the pinned MAME reference (see nrallyx.json)."""


def _layout(width, height, count, planes, xs, ys, stride):
    return dict(width=width, height=height, count=count, planes=planes,
                x_offsets=xs, y_offsets=ys, stride_bits=stride)


LAYOUTS = {
    'tiles': _layout(8, 8, 256, [0, 4], [64,65,66,67,0,1,2,3],
                     [8*y for y in range(8)], 128),
    'sprites': _layout(16, 16, 64, [0, 4],
                       [64,65,66,67,128,129,130,131,192,193,194,195,0,1,2,3],
                       [8*y for y in range(8)] + [8*y for y in range(32,40)], 512),
    'dots': _layout(4, 4, 8, [6, 7], [0,8,16,24], [0,32,64,96], 128),
}


def decode_graphics(gfx1: bytes, gfx2: bytes) -> dict[str, bytes]:
    if len(gfx1) != 4096 or len(gfx2) != 256:
        raise ValueError('Expected gfx1 size 4096 and gfx2 size 256')
    result = {}
    for name, layout in LAYOUTS.items():
        source = gfx2 if name == 'dots' else gfx1
        pixels = bytearray()
        for code in range(layout['count']):
            for y in layout['y_offsets']:
                for x in layout['x_offsets']:
                    value = 0
                    for plane, offset in enumerate(layout['planes']):
                        bit = code * layout['stride_bits'] + y + x + offset
                        if source[bit // 8] & (0x80 >> (bit % 8)):
                            value |= 2 >> plane
                    pixels.append(value)
        result[name] = bytes(pixels)
    return result


def flip_pixels(pixels: bytes, width: int, height: int,
                flip_x: bool, flip_y: bool) -> bytes:
    if width <= 0 or height <= 0 or len(pixels) != width * height:
        raise ValueError('Pixel count does not match positive dimensions')
    return bytes(pixels[(height-1-y if flip_y else y)*width +
                        (width-1-x if flip_x else x)]
                 for y in range(height) for x in range(width))


def _resistor_weights(resistors, pull_down):
    # MAME uses 1e12 ohms for absent pull resistors, then global autoscaling.
    result = []
    for index, resistor in enumerate(resistors):
        low = (1 / pull_down if pull_down else 1e-12)
        low += sum(1 / other for i, other in enumerate(resistors) if i != index)
        high = 1e-12 + 1 / resistor
        result.append(255 * high / (low + high))
    return result


def decode_palette(palette_prom: bytes, lookup_prom: bytes) -> dict:
    if len(palette_prom) != 32 or len(lookup_prom) != 256:
        raise ValueError('Expected palette PROM size 32 and lookup PROM size 256')
    rg = _resistor_weights([1000,470,220], 0)
    blue = _resistor_weights([470,220], 1000)
    scale = 255 / max(sum(rg), sum(blue))
    rg, blue = [[x * scale for x in weights] for weights in (rg, blue)]

    def channel(value, offset, weights):
        return int(sum(w * ((value >> (offset+i)) & 1)
                       for i, w in enumerate(weights)) + 0.5)

    rgb = [[channel(v, 0, rg), channel(v, 3, rg), channel(v, 6, blue)]
           for v in palette_prom]
    lookup = [v & 15 for v in lookup_prom]
    variants = [lookup[i:i+4] for i in range(0,256,4)]
    return dict(raw_palette=list(palette_prom), raw_lookup=list(lookup_prom),
                rgb=rgb, lookup=lookup, variants=variants,
                sprite_alpha=[[0 if pen == 0 else 255 for pen in row] for row in variants],
                dot_indices=[16,17,18,19], dot_alpha=[255,255,255,0],
                transparency={'tiles': 'opaque', 'sprites': 'indirect index 0',
                              'dots': 'source pen 3; isolated preview only'})


def graphics_metadata() -> dict:
    groups = {}
    for name, layout in LAYOUTS.items():
        columns = 16 if name == 'tiles' else 8
        width, height = layout['width'], layout['height']
        groups[name] = dict(layout, atlas_columns=columns,
            atlas_size=[columns*width, ((layout['count']+columns-1)//columns)*height],
            slots=[dict(id=i, x=(i % columns)*width, y=(i // columns)*height)
                   for i in range(layout['count'])])
    return dict(schema_version=1, groups=groups,
                encoding='uint8 source pen; graphic ID, row, column; top-left origin',
                canonical_orientation='unflipped MAME graphics viewer orientation',
                flips={'tiles': 'flip X = NOT attr bit 6; flip Y = attr bit 7',
                       'sprites': 'flip X = sprite byte bit 0; flip Y = bit 1',
                       'dots': 'unflipped; runtime code = ((radarattr & 14) >> 1) XOR 7'})
