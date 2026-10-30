"""Build local SCREEN 4 inputs; retain canonical original inputs under ignored assets/arcade/."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from PIL import Image
from src.toolchain.scenes.bundle import load_assets
from src.toolchain.msx.inputs import load_huds, background_zero
from src.toolchain.msx import stage_one, tilemap
from src.toolchain.msx.raster_scroll import palette_rgb, index_for
from edge import SCENE_WIDTH, EDGE_WIDTH
from hud import compose_hud, display_values

OUT = ROOT / 'references/experiments/fixed-hud'
SPLIT = SCENE_WIDTH


def encode_tile(pixels):
    """Reject color loss: adaptation belongs to the explicit scenery codec only."""
    pattern, colors = bytearray(), bytearray()
    for y in range(8):
        row = pixels[y*8:y*8+8]
        unique = sorted(set(row))
        if len(unique) > 2:
            raise ValueError(f'HUD row needs {len(unique)} colors: {list(row)}')
        bg, fg = unique[0], unique[-1]
        pattern.append(sum((p == fg) << (7-x) for x, p in enumerate(row)))
        colors.append(fg*16+bg)
    return bytes(pattern), bytes(colors)


def shifted_hud(hud, fx, fy, blank):
    """Inverse scroll in pattern space, including a guard cell on every edge."""
    width, height = 56, 256
    pixels = bytearray([blank])*(width*height)
    for y in range(height):
        for x in range(width):
            hx, hy = x-fx, (y-fy) % 256
            if 0 <= hx < 48 and hy < 212:
                pixels[y*width+x] = hud[hy*48+hx]
    names, dictionary, patterns, colors = bytearray(), {}, bytearray(), bytearray()
    for ty in range(32):
        for tx in range(7):
            tile = bytes(pixels[(ty*8+y)*width+tx*8+x] for y in range(8) for x in range(8))
            key = encode_tile(tile)
            if key not in dictionary:
                dictionary[key] = len(dictionary)
                patterns.extend(key[0]); colors.extend(key[1])
            names.append(dictionary[key])
    # Decode independently, then undo the compensation and compare every HUD pixel.
    decoded = bytearray(width*height)
    for ty in range(32):
        for tx in range(7):
            at = names[ty*7+tx]*8
            for y in range(8):
                p, c = patterns[at+y], colors[at+y]
                for x in range(8):
                    decoded[(ty*8+y)*width+tx*8+x] = c >> 4 if p & (128 >> x) else c & 15
    assert all(decoded[((y+fy)%256)*width+x+fx] == hud[y*48+x]
               for y in range(212) for x in range(48))
    return bytes(names), bytes(patterns), bytes(colors), len(dictionary)


def prepare(*, high_score=20000, score=0, round_number=1, lives=4, arcade=False, small_round=False,symmetric_gauge=True):
    OUT.mkdir(parents=True, exist_ok=True)
    from src.toolchain.graphics.canonical import promote
    assets = load_assets(promote(ROOT))
    palette, huds, _ = load_huds(ROOT/'assets/arcade/scenes/normal',
                              ROOT/'assets/arcade/scenes/overlap')
    palette, huds = background_zero(palette, huds)
    program, capture = stage_one.acquire(ROOT)
    cells, pairs, checked = stage_one.reconstruct(program, capture)
    original = stage_one.bitmap(pairs, assets, palette)
    terrain = tilemap.encode(original, palette)
    (OUT/'palette.bin').write_bytes(palette)
    padded = bytearray(b''.join(terrain['banks']))
    for ty in range(256):
        for tx in range(128):
            if ty >= 174 or tx >= 102:
                padded[ty*128+tx] = padded[(ty%3)*128+tx%3]
    (OUT/'map.bin').write_bytes(padded)
    (OUT/'terrain-patterns.bin').write_bytes(terrain['patterns'][:2048])
    (OUT/'terrain-colors.bin').write_bytes(terrain['colors'][:2048])
    rgb = palette_rgb(palette)
    image = Image.new('RGB', (stage_one.WIDTH, stage_one.HEIGHT))
    image.putdata([rgb[c] for c in terrain['world']]); image.save(OUT/'maze.png')
    black = index_for(palette, (0,0,0))
    white = index_for(palette, (222,222,222))
    yellow = index_for(palette, (255,255,0))
    blue = index_for(palette, (0,0,151))
    red = index_for(palette, (255,0,0))
    cyan = index_for(palette, (0,151,222))
    green = index_for(palette, (0,106,0))
    def glyph(char):
        code = int(char) if char.isdigit() else ord(char)
        tile = assets.pixels['tiles'][code*64:(code+1)*64]
        return bytes(bool(assets.palette['lookup'][38*4+p]) for p in tile)
    life = bytes(huds[0][(180+y)*56+x] == yellow for y in range(16) for x in range(16))
    hud = compose_hud(glyph,life,cells,
                      dict(black=black,white=white,yellow=yellow,blue=blue,
                           red=red,cyan=cyan,green=green),
                      high_score=high_score,score=score,round_number=round_number,lives=lives,arcade=arcade,small_round=small_round,symmetric_gauge=symmetric_gauge)
    (OUT/'hud.bin').write_bytes(hud)
    preview = Image.new('RGB',(256,212))
    cx,cy = stage_one.START
    view = bytearray(terrain['world'][(cy+y)*stage_one.WIDTH+cx+x]
                 if x<SPLIT else black if x<208 else hud[y*48+x-208]
                 for y in range(212) for x in range(256))
    for y in range(212): view[y*256:y*256+8]=bytes([black])*8
    for y in range(212):
        for x in range(SPLIT-EDGE_WIDTH,SPLIT):
            tile_x=(cx+x)//8*8
            at=(cy+y)*stage_one.WIDTH+tile_x
            view[y*256+x]=Counter(terrain['world'][at:at+8]).most_common(1)[0][0]
    preview.putdata([rgb[c] for c in view]); preview.save(OUT/'layout.png')
    counts=[]
    for fy in range(8):
        for fx in range(8):
            names, patterns, colors, count = shifted_hud(hud, fx, fy, black)
            (OUT/f'hud-{fy*8+fx:02d}.bin').write_bytes(names+patterns+colors)
            counts.append(count)
    report = dict(status='offline compensation verified; ROM runtime pending',
                  geometry=dict(screen=[256,212],split=SPLIT,hud_width=256-SPLIT,
                                hud_percent=(256-SPLIT)/256*100, left_mask_required=8,
                                radar_top=68,radar_bottom=180,lives_y=184,round_y=204,
                                round_label='ROUND' if small_round else 'RND',round_alignment='right',
                                scene_edge_simplification_pixels=EDGE_WIDTH,
                                horizontal_fine='R26/R27 with fixed eight-pixel left mask'),
                  native_tiles_checked=checked, scenery_tiles=terrain['tiles'],
                  changed_scenery_pixels=terrain['changed_pixels'], total_scenery_pixels=len(original),
                  hud_phases_checked=64, hud_unique_tiles=dict(min=min(counts),max=max(counts)),
                  display_values=dict(zip(('high_score','score','round','lives'),
                      display_values(high_score,score,round_number,lives))),
                  input_values=dict(high_score=high_score,score=score,round=round_number,lives=lives),
                  hud_pattern_color_upload_bytes=dict(min=min(counts)*16,max=max(counts)*16),
                  source='Contributor ROMs and validated native-v1 MAME acquisition',
                  notes=['No asset resizing.', 'Scenery two-color reduction authorized for this experiment only.',
                         '56-pixel HUD includes an eight-pixel left inset and 48 usable pixels; six-digit scores and 48-pixel fuel/radar panels.',
                         'Fixed eight-pixel left mask authorized for this experiment only; original glyphs stay 8x8.',
                         'The final seven scenery pixels use a phase-independent dominant source-tile-row color.',
                         'Offline compensation is not evidence of raster stability or frame cost.'])
    (OUT/'prepare.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__': prepare()
