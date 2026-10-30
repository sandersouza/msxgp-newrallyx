"""Exact 1:1 native sprite HUD assets, values and reference preparation.

write_assets(output, glyph, life, palette) uses glyph(char)->64 booleans and
life256 booleans from hud.py/prepare.py's existing local native extraction.
Install the already-permuted palette used by game_sprites.palette_contract;
all active scenery must use the identical index permutation. The HUD introduces
no RGB changes. No original ROM or extracted bytes belong in tracked files.

RAM2000..21bf holds448 pattern bytes;2200..2237 holds14 SAT records;
2240..225b caches14 value/shift keys;2260..22cd is preparation scratch.
22a0..22b4 caches native inputs/camera/validity;22b5 marks SAT publication.
Each native field is decoded only when its source changes; packed keys and
independent scroll compensation preserve exact per-frame pixels and rules.
Init(display-off, DI), Prepare(foreground), Commit(blanking, DI). Prepare must
be committed before preparing again. World sprites use slots14..31. HUD uses
fixed slots0..13, patterns144..199 at2c80..2e3f and colors1800..18df.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from pathlib import Path
from hud_module import FONT,YELLOW_TICKS,CLASSIC_YELLOW_TICKS

XS = (208,224,240,208,224,240,240,208,219,230,241,208,224,240)
YS = (8,8,8,32,32,32,204,184,184,184,184,60,60,60)


def read_score(source,*,arcade=False):
    if len(source) != 8:
        raise ValueError('Need all eight native counter digits')
    ordered = [min(v & 15,9) for v in source[4:8]+source[:4]]
    values=[0x99]*3 if any(ordered[:2]) else [ordered[i]*16+ordered[i+1] for i in (2,4,6)]
    if arcade:
        digits=[v for byte in values for v in (byte>>4,byte&15)]
        for i in range(5):
            if digits[i]:break
            digits[i]=10
        values=[digits[i]*16+digits[i+1] for i in (0,2,4)]
    return values


def display_keys(high, score, native_round, native_lives, fuel,*,arcade=False):
    rnd = min(max(native_round-1,1),99)
    tens,units = divmod(rnd,10)
    lives = min(max(native_lives-1,0),4)
    width = min(fuel,60)*48//60
    return (read_score(high,arcade=arcade)+read_score(score,arcade=arcade)+[(tens or 10)*16+units]+
            [int(i<lives) for i in range(4)]+[min(max(width-(2-i if arcade else i)*16,0),16) for i in range(3)])


def sprite_pattern(pixels):
    return bytes(sum(bool(pixels[y*16+x+b])<<(7-b) for b in range(8))
                 for x in (0,8) for y in range(16))


def write_assets(output, glyph, life, palette):
    from src.toolchain.msx.raster_scroll import index_for
    from game_sprites import palette_contract
    # Validate OR blacks without silently changing the installed palette again.
    if palette_contract(palette)['translation_required']:
        raise ValueError('Pass the already-permuted sprite-compatible palette')
    if len(life) != 256 or any(life[240:]):
        raise ValueError('Complete life icon must have a transparent last row for exact sentinel shift')
    digits = bytearray()
    for char in '0123456789':
        mask = glyph(char)
        if len(mask) != 64:
            raise ValueError('Native glyph must be exactly8x8')
        digits.extend(sum(bool(mask[y*8+x])<<(7-x) for x in range(8)) for y in range(8))
    digits.extend(bytes(8))  # glyph10 is the single-digit round's blank tens.
    life_patterns = sprite_pattern(life)+sprite_pattern(bytes(16)+bytes(life[:240]))
    inks = [index_for(palette,rgb) for rgb in ((255,0,0),(0,151,222),(222,222,222),(255,255,0))]
    if any(v == 0 for v in inks):
        raise ValueError('HUD ink must not use transparent sprite index0')
    colors = bytes(v for ink in ([inks[0]]*3+[inks[1]]*3+[inks[2]]+[inks[3]]*7) for v in [ink]*16)
    output = Path(output)
    (output/'game-hud-digits.bin').write_bytes(digits)
    (output/'game-hud-life.bin').write_bytes(life_patterns)
    (output/'game-hud-colors.bin').write_bytes(colors)
    return dict(digit_bytes=88,life_bytes=64,color_bytes=224,native_round='max(1,E1B0-1), saturated99',fuel_scale='floor(min(E26B,60)*48/60)')


def prepare_reference(digits, life_patterns, keys, cy,*,arcade=False,small_round=False,symmetric_gauge=True):
    if len(digits)!=88 or len(life_patterns)!=64 or len(keys)!=14:
        raise ValueError('Invalid HUD source contract')
    sat, patterns = bytearray(), bytearray()
    hidden = (cy+211)&255
    hidden += hidden==216
    for slot,value in enumerate(keys):
        sy = (cy+(57 if arcade and slot>=11 else YS[slot])-1)&255
        shift = int(sy==216)
        if shift: sy=215
        visible = not (7<=slot<=10 and value==0 or slot>=11 and value==0 and not arcade)
        pattern_id = 172+shift*4 if 7<=slot<11 else 144+slot*4
        sat.extend((sy if visible else hidden,XS[slot],pattern_id,0))
        image = bytearray(256)
        if slot==6 and small_round:
            for code,x0 in ((value>>4,7),(value&15,12)):
                for y,row in enumerate(FONT[' ' if code==10 else str(code)]):
                    for x in range(4):image[(y+shift)*16+x0+x]=bool(row&(8>>x))
            pattern=sprite_pattern(image)
        elif slot<7:
            for col,code in enumerate((value>>4,value&15)):
                for y,row in enumerate(digits[code*8:code*8+8]):
                    for x in range(8): image[(y+shift)*16+col*8+x] = bool(row&(128>>x))
            pattern = sprite_pattern(image)
        elif slot<11:
            pattern = life_patterns[shift*32:(shift+1)*32]
        else:
            for y in range(4):
                for x in range(16-value,16) if arcade else range(value): image[(y+shift+(3 if arcade else 0))*16+x]=1
            if arcade:
                for x in (YELLOW_TICKS if symmetric_gauge else CLASSIC_YELLOW_TICKS):
                    if (slot-11)*16<=x<(slot-10)*16:image[(1+shift)*16+x-(slot-11)*16]=1
            pattern = sprite_pattern(image)
        patterns.extend(pattern)
    return bytes(sat),bytes(patterns)


def write_local_assets(output, palette, *, root=None):
    """Read the same contributor-local glyph and life masks as prepare.py."""
    from src.toolchain.scenes.bundle import load_assets
    from src.toolchain.msx.inputs import load_huds, background_zero
    from src.toolchain.msx.raster_scroll import index_for
    root = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    assets = load_assets(root/'assets/arcade/nrallyx')
    original, huds, _ = load_huds(root/'assets/arcade/scenes/normal',root/'assets/arcade/scenes/overlap')
    original, huds = background_zero(original,huds)
    yellow = index_for(original,(255,255,0))
    def glyph(char):
        tile = assets.pixels['tiles'][int(char)*64:(int(char)+1)*64]
        return bytes(bool(assets.palette['lookup'][38*4+p]) for p in tile)
    life = bytes(huds[0][(180+y)*56+x]==yellow for y in range(16) for x in range(16))
    return write_assets(output,glyph,life,palette)
