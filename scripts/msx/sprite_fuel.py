"""Authored white pump and yellow dynamic gauge, aligned to the sprite radar."""
from . import sprite_radar as radar

X, Y, WIDTH, HEIGHT = radar.X, radar.Y+radar.HEIGHT+4, radar.WIDTH, 16
ICON_PATTERN, BAR_PATTERN = 132, 140
LEVELS = (30, 22, 15, 7, 0)
PUMP = (
    '............',
    '.######.....',
    '.#....#.##..',
    '.#....#..##.',
    '.######...#.',
    '.######...#.',
    '.######...#.',
    '.######.#.#.',
    '.######.#.#.',
    '.######.###.',
    '.######.....',
    '.######.....',
    '########....',
    '............',
    '............',
    '............',
)


def icon():
    return bytes(int(x < 12 and PUMP[y][x] == '#') for y in range(16) for x in range(16))


def pattern(mask, width, column=0, shift=0):
    if any(mask[(15*width):]):
        raise ValueError('Fuel pattern needs one empty bottom row for sentinel avoidance')
    return bytes(sum((mask[(y-shift)*width+column+half+bit] if y >= shift else 0) << (7-bit)
                     for bit in range(8)) for half in (0, 8) for y in range(16))


def icon_patterns():
    return b''.join(pattern(icon(), 16, shift=phase) for phase in (0, 1))


def attributes(cy):
    y = (Y+cy-11-1) & 255
    phase = int(y == 216)
    return bytes(v for x, p in ((X, ICON_PATTERN+phase*4),
                               (X+16, BAR_PATTERN+phase*8),
                               (X+32, BAR_PATTERN+4+phase*8)) for v in (y-phase,x,p,0))


def gauge_patterns(pixels):
    """Reusable 0..30-pixel fill, independent of the keyboard's five fixtures."""
    if not 0 <= pixels <= 30:
        raise ValueError('Fuel fill must be 0..30 pixels')
    mask = bytes(int(y in (3,10) or (4 <= y <= 9 and
                     (x in (0,31) or 1 <= x <= pixels)))
                 for y in range(16) for x in range(32))
    return b''.join(pattern(mask,32,column,phase) for phase in (0,1) for column in (0,16))


def paint_pixels(pixels, amount, white, yellow):
    """Screen-coordinate oracle for every gauge amount, independent of sprite packing."""
    pump=icon()
    for y in range(16):
        for x in range(16):
            if pump[y*16+x]:pixels[(Y+y)*256+X+x]=white
    for y in range(16):
        for x in range(32):
            if y in (3,10) or (4<=y<=9 and (x in (0,31) or 1<=x<=amount)):
                pixels[(Y+y)*256+X+16+x]=yellow
