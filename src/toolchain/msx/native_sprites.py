"""Feasibility model for original actors in the sprite slots released by #24.

This does not enable a cartridge renderer. It compiles source pixels, including
priority/clipping, and refuses frames exceeding the actual mode-2 constraints.
"""
from .native_scene import actors_from_snapshot, radar_bitmap, radar_visible

# Patterns0..179 belong to the HUD, including its reserved-Y variants.
ACTOR_PATTERN_BASE = 180
ACTOR_PATTERN_VRAM = 0x1f800+ACTOR_PATTERN_BASE*8
ACTOR_PATTERN_BANKS = ((0, 4, 8, 12, 16, 180, 184, 188, 192, 196, 200, 204),
                       tuple(range(208, 256, 4)))


def published_actors(hud, vram, page):
    """Read the actual pending SAT/colors and uploaded pattern-bank payload."""
    count = hud[0x175]
    if page not in (0, 1) or count > 12 or hud[0x144+count*4] != 216:
        raise ValueError('Invalid hardware actor SAT publication')
    attrs = hud[0x144:0x144+count*4]
    if tuple(attrs[2::4]) != ACTOR_PATTERN_BANKS[page][:count] or any(attrs[3::4]):
        raise ValueError('Hardware actors overlap reserved HUD pattern slots')
    colors = hud[0x180:0x180+min(count, 8)*16]+hud[0x240:0x240+max(0, count-8)*16]
    patterns = b''.join(vram[0x1f800+pattern*8:0x1f800+pattern*8+32] for pattern in attrs[2::4])
    return dict(supported=True, slots=count, attributes=attrs, colors=colors, patterns=patterns)


def planes(pixels):
    """Encode exact indexed pixels in two OR planes when possible, else layers."""
    if len(pixels) != 256 or any(not 0 <= c < 16 for c in pixels):
        raise ValueError('An original-size indexed actor is required')
    colors = sorted(set(pixels)-{0})
    if len(colors) > 3:
        return None
    specs = [(c, {c}) for c in colors]
    if len(colors) == 3:
        for a in colors:
            for b in colors:
                if a != b and (a | b) in set(colors)-{a, b}:
                    specs = [(a, {a, a | b}), (b | 64, {b, a | b})]
                    break
            if len(specs) == 2:
                break
    output = []
    for color, ink in specs:
        # VDP 16x16 layout: sixteen left rows followed by sixteen right rows.
        pattern = bytes(sum(128 >> x for x in range(8)
                            if pixels[y*16+half*8+x] in ink)
                        for half in range(2) for y in range(16))
        output.append((pattern, bytes((color,))*16))
    return output


def compile_actors(snapshot, sprites, lookup, translation, hud, *, hud_enabled=True):
    """Compile a frozen frame without allocating sprites or changing game RAM.

    Slots17..29 leave a terminator at30. Any unsupported palette, reserved Y,
    total-slot overflow or line congestion requires the existing bitmap path.
    """
    if len(sprites) != 16384 or len(lookup) != 256 or len(translation) != 16 or len(hud) != 1140:
        raise ValueError('Incomplete actor/HUD resources')
    scene = actors_from_snapshot(snapshot)
    sx, sy = snapshot.shadows[0x130], snapshot.shadows[0x140]
    scroll = hud[0x1c]
    radar, _ = radar_bitmap(snapshot)
    visible_radar = hud_enabled and radar_visible(snapshot)
    attrs, patterns, colors, actors = bytearray(), bytearray(), bytearray(), []
    for actor in scene:
        x0, y0, _, _ = actor['screen_bounds']
        pixels = bytearray(256)
        for y in range(16):
            for x in range(16):
                dx, dy = x0+x, y0+y
                if not (0 <= dx < 200 and 0 <= dy < 201):
                    continue
                wx, wy = (sx+9+dx) & 255, (sy+22+dy) & 255
                if visible_radar and (wx-radar[0]) & 255 < 50 and (wy-radar[1]) & 255 < 60:
                    continue
                tile = (wy//8)*32+wx//8
                if snapshot.video[0xc00+tile] & 32:
                    continue
                px = 15-x if actor['flip_x'] else x
                py = 15-y if actor['flip_y'] else y
                pen = sprites[actor['code']*256+py*16+px]
                color = lookup[actor['palette']*4+pen]
                # Source transparency is original color index zero, not pen zero.
                pixels[y*16+x] = translation[color] if color else 0
        encoded = planes(pixels)
        if encoded is None:
            return dict(supported=False, reason='four opaque colors')
        if not encoded:
            continue
        ax, ay = x0+8, (y0+11+scroll-1) & 255
        if ay == 216:
            return dict(supported=False, reason='reserved terminator Y')
        ec = 128 if ax < 0 else 0
        ax += 32 if ec else 0
        for pattern, color in encoded:
            slot = len(attrs)//4
            if slot >= 13:
                return dict(supported=False, reason='thirteen actor slots exceeded')
            attrs.extend((ay, ax, ACTOR_PATTERN_BASE+slot*4, 0))
            patterns.extend(pattern)
            colors.extend(c | ec for c in color)
        actors.append(dict(id=actor['id'], x=x0+8, y=y0+11,
                           pixels=bytes(pixels), planes=len(encoded)))
    peak = 0
    for y in range(11, 212):
        base = hud[0x100:0x144]
        if y >= 176:
            base = base[:56]+hud[0x290:0x29c]
        count = 0
        for at in range(0, len(base), 4):
            ay = base[at]
            if ay == 216:
                break
            count += ((y+scroll)-(ay+1)) & 255 < 16
        count += sum(((y+scroll)-(attrs[at]+1)) & 255 < 16
                     for at in range(0, len(attrs), 4))
        peak = max(peak, count)
    if peak > 8:
        return dict(supported=False, reason='eight sprites per line exceeded', peak=peak)
    return dict(supported=True, attributes=bytes(attrs), patterns=bytes(patterns),
                colors=bytes(colors), slots=len(attrs)//4, peak=peak, actors=actors)
