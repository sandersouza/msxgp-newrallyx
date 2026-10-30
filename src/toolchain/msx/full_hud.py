"""Full-game HUD display geometry; native counters retain their full width."""
from .display import LEFT_MASK

VISIBLE_SCORE_DIGITS = 7
HIGH_FIELD_X = 24       # Hidden source digit; first visible digit follows HI: at X=32.
SCORE_FIELD_X = 128     # First visible digit follows 1UP: at X=136.
PLAYER_LABEL_X = 104
ROUND_X = 240
CREDIT_LABEL_X = 96
CREDIT_X = 152
HEADER_LEFT = LEFT_MASK

# Authored 16x8 infinity sign, occupying the width of two round digits.
INFINITY_ROWS = (0x0000, 0x381C, 0x6C36, 0xC7E3,
                 0xC7E3, 0x6C36, 0x381C, 0x0000)


def infinity_pixels():
    return bytes(row >> (15-x) & 1 for row in INFINITY_ROWS for x in range(16))


def score_text(value):
    return f'{value % 10**VISIBLE_SCORE_DIGITS:07d}'


def round_text(value):
    return f'{value:02d}' if value <= 99 else '\u221e '


def credit_digit(value):
    return min(value, 9)
