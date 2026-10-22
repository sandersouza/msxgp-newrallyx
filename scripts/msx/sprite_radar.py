"""Transparent sprite radar: native 2x2 markers, reprojected anchors, white frame."""
from scripts.scenes.bundle import load_capture
from scripts.scenes.render import render

X, Y, WIDTH, HEIGHT = 204, 20, 48, 58
BAND = 15  # One spare row permits lossless avoidance of the mode-2 Y=216 sentinel.
CELLS = 12
FRAME_PATTERN = 20
PLAYER_PATTERN, ENEMY_PATTERN = 116, 124


def project(x, y):
    """Move anchors from the arcade's 64x112 radar; keep 2x2 point footprints."""
    return (2+max(0, min(63, x-224))*(WIDTH-4)//64,
            2+max(0, min(111, y-80))*(HEIGHT-4)//112)


def capture_enemy(path, assets):
    """Read the one captured enemy fixture used by a map landmark."""
    frame = render(load_capture(path, assets), assets)
    enemy = next(o for o in frame.objects if o.kind == 'dot' and o.id == 0x15)
    return project(*enemy.rect[:2])


def bitmap(flags):
    pixels = bytearray(WIDTH*HEIGHT)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            # One-pixel chamfered corners, no opaque fill.
            if ((y in (0, HEIGHT-1) and 1 <= x < WIDTH-1)
                    or (x in (0, WIDTH-1) and 1 <= y < HEIGHT-1)):
                pixels[y*WIDTH+x] = 1
    for px, py in flags:
        for y in range(py, py+2):
            for x in range(px, px+2):
                pixels[y*WIDTH+x] = 1
    return bytes(pixels)


def patterns(pixels):
    result = bytearray()
    for shift in (0, 1):
        for band in range(4):
            for column in range(3):
                for half in (0, 8):
                    for y in range(16):
                        source_y = band*BAND+column-2+y-shift
                        result.append(sum((pixels[source_y*WIDTH+column*16+half+bit]
                                           if shift <= y < BAND+shift and 0 <= source_y < HEIGHT else 0) << (7-bit)
                                          for bit in range(8)))
    return bytes(result)


def point_patterns(x, y):
    """CPU-generated marker inside an 8x8 anchor cell, with a shifted variant."""
    return bytes(sum(int(px in (x%8, x%8+1) and row-shift in (y%8, y%8+1)) << (7-bit)
                     for bit, px in enumerate(range(half, half+8)))
                 for shift in (0, 1) for half in (0, 8) for row in range(16))


def attributes(cy, player, enemy):
    scroll = cy-11
    result = bytearray()
    for band in range(4):
        for column in range(3):
            y = (Y+band*BAND+column-2+scroll-1) & 255
            phase = int(y == 216)
            result.extend((y-phase, X+16*column,
                           FRAME_PATTERN+4*(band*3+column+phase*CELLS), 0))
    for point, base in ((player, PLAYER_PATTERN), (enemy, ENEMY_PATTERN)):
        x, py = point
        y = (Y+(py & 248)+scroll-1) & 255
        phase = int(y == 216)
        result.extend((y-phase, X+(x & 248), base+phase*4, 0))
    return bytes(result)


def paint(pixels, flags, player, enemy, white, red, player_color):
    """Screen-coordinate reference independent of sprite packing and VRAM layout."""
    for i, value in enumerate(bitmap(flags)):
        if value:
            y, x = divmod(i, WIDTH)
            pixels[(Y+y)*256+X+x] = white
    # Lower sprite number wins overlaps: player precedes enemy, both follow frame.
    frame = bitmap(flags)
    for point, color in ((enemy, red), (player, player_color)):
        px, py = point
        if px == 255:
            continue
        for y in range(py, py+2):
            for x in range(px, px+2):
                if not frame[y*WIDTH+x]:
                    pixels[(Y+y)*256+X+x] = color
