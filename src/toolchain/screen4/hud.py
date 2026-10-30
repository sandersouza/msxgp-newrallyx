"""Pure laboratory HUD composition; presentation limits never change game state."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME

from hud_module import FONT,RED_MARKS,CLASSIC_RED_MARKS

WIDTH, HEIGHT = 48, 212
RADAR_TOP, RADAR_BOTTOM = 68, 180
RADAR_POINTS_Y = 70
LIVES_Y, ROUND_Y = 184, 204


def display_values(high_score, score, round_number, lives):
    """Saturate the display, rather than wrapping/truncating decimal digits."""
    cap = lambda value, maximum: max(0, min(int(value), maximum))
    return (f'{cap(high_score,999999):06d}', f'{cap(score,999999):06d}',
            str(cap(round_number,99)), cap(lives,4))


def compose_hud(glyph, life, cells, colors, *, high_score=20000, score=0,
                round_number=1, lives=4, arcade=False, small_round=False,symmetric_gauge=True):
    """Draw native 8x8 glyphs and complete 16x16 padded life masks at 1:1.

    Four cars fit by overlapping transparent source padding only. No opaque
    pixel is clipped, resized, recolored or covered by a neighboring icon.
    """
    if len(life) != 16*16:
        raise ValueError('Require the complete native 16x16 life source')
    shown_high, shown_score, shown_round, shown_lives = display_values(
        high_score,score,round_number,lives)
    pixels = bytearray([colors['black']])*(WIDTH*HEIGHT)

    def text(value, y, color, x=0):
        for i, char in enumerate(value):
            if char == ' ':
                continue
            mask = glyph(char)
            if len(mask) != 64:
                raise ValueError('Require a native 8x8 glyph')
            for gy in range(8):
                for gx in range(8):
                    if mask[gy*8+gx]:
                        pixels[(y+gy)*WIDTH+x+i*8+gx] = colors[color]

    if arcade:
        shown_high=shown_high.lstrip('0').rjust(6) if int(shown_high) else '     0'
        shown_score=shown_score.lstrip('0').rjust(6) if int(shown_score) else '     0'
    text('HI',0,'white'); text(shown_high,8,'red')
    text('1UP',24,'white'); text(shown_score,32,'cyan')
    def small_text(value,y,color,x):
        for i,char in enumerate(value):
            for gy,row in enumerate(FONT[char]):
                for gx in range(4):
                    if row&(8>>gx):pixels[(y+gy)*WIDTH+x+i*5+gx]=colors[color]

    if arcade:
        # New small terminal label; native8x8 score/car artwork is unscaled.
        small_text('FUEL',48,'green',14)
        for x,y in (RED_MARKS if symmetric_gauge else CLASSIC_RED_MARKS):pixels[y*WIDTH+x]=colors['red']
        # Yellow ticks belong to the existing fuel sprites: static mixed
        # red/yellow/black rows would exceed SCREEN4's two-color character row.
    else:text('FUEL',48,'green')
    for y in range(60,64):
        pixels[y*WIDTH:(y+1)*WIDTH] = bytes([colors['yellow']])*WIDTH
    for y in range(RADAR_TOP,RADAR_BOTTOM):
        pixels[y*WIDTH:(y+1)*WIDTH] = bytes([colors['blue']])*WIDTH
    for i, cell in enumerate(cells):
        if cell in (1,2,3,4):
            x, y = 8+i%32, RADAR_POINTS_Y+(i//32)*106//56
            pixels[y*WIDTH+x] = colors['yellow']
    occupied = set()
    for icon in range(shown_lives):
        for y in range(16):
            for x in range(16):
                if life[y*16+x]:
                    px, py = icon*11+x, LIVES_Y+y
                    if not (0<=px<WIDTH and LIVES_Y<=py<ROUND_Y):
                        raise ValueError('Life layout would clip the native drawing')
                    if (px,py) in occupied:
                        raise ValueError('Life drawings overlap opaque source pixels')
                    occupied.add((px,py))
                    pixels[py*WIDTH+px] = colors['yellow']
    if small_round:
        small_text('ROUND',ROUND_Y,'white',0)
        small_text(shown_round,ROUND_Y,'white',WIDTH-(len(shown_round)*5-1))
    else:
        text('RND',ROUND_Y,'white')
        text(shown_round,ROUND_Y,'white',WIDTH-len(shown_round)*8)
    return bytes(pixels)
