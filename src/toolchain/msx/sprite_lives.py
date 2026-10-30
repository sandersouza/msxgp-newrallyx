"""One original outlined car and one dynamically defined original-font digit."""
X, NUMBER_X, Y, SPLIT = 220, 238, 194, 176
CAR_PATTERN, COUNT_PATTERN = 156, 172
FIRST_SLOT = 14  # Fuel has already passed when these slots become the footer.


def digit_masks(assets):
    lookup, tiles = assets.palette['lookup'], assets.pixels['tiles']
    return bytes(sum(int(lookup[38*4+tiles[n*64+y*8+x]] != 0) << (7-x)
                     for x in range(8)) for n in range(10) for y in range(8))


def digit_bitmap(digits, value):
    if len(digits) != 80 or value not in range(10):
        raise ValueError('Life counter requires ten native 8x8 glyphs and a digit 0..9')
    return bytes(int(3 <= y < 11 and x < 8 and digits[value*8+y-3] & (128 >> x) != 0)
                 for y in range(16) for x in range(16))


def attributes(cy):
    y = (Y+cy-11-1) & 255
    phase = int(y == 216)
    return bytes(v for x,p in ((X,CAR_PATTERN+phase*8), (X,CAR_PATTERN+4+phase*8),
                               (NUMBER_X,COUNT_PATTERN+phase*4)) for v in (y-phase,x,p,0))


def paint(pixels, life, outline, digits, value, yellow, black, white):
    for y in range(16):
        for x in range(16):
            if outline[y*16+x]:
                pixels[(Y+y)*256+X+x] = yellow if life[y*16+x] else black
    mask = digit_bitmap(digits, value)
    for y in range(16):
        for x in range(16):
            if mask[y*16+x]:
                pixels[(Y+y)*256+NUMBER_X+x] = white
