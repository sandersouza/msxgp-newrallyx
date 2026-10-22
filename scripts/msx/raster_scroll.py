"""V9958 scrolling with a fixed scoreboard, radar/fuel and outlined-car life counter."""
import shutil
import subprocess

from PIL import Image
from .build import destination
from .screen5 import packed
from .screen5 import expand, rgb333
from .inputs import sources, video_timing
from . import sprite_radar as radar
from . import sprite_fuel as fuel
from . import sprite_lives as life_counter
from scripts.scenes.bundle import digest, load_assets
from scripts.scenes.storage import json_write, require_ignored, seal
from .display import (LEFT_MASK, VIEWPORT_WIDTH, VIEWPORT_HALF, HORIZONTAL_ADJUST,
                      DISPLAY_SHIFT, PLAYER_X, FUEL_SLOT, PLAYER_SLOT, HUD_SPRITES, TOTAL_SPRITES,
                      PLAYER_LABEL_X, SCORE_X)

HUD_HEIGHT = 8
BODY_TOP = 11
RIGHT_MASK = 0
MASK_ROWS = ()
LIFE_Y = life_counter.Y
LIFE_X = (life_counter.X, life_counter.NUMBER_X)
LIFE_SPLIT = life_counter.SPLIT
LIFE_PATTERN = life_counter.CAR_PATTERN


def palette_rgb(encoded):
    return [expand((encoded[i] >> 4, encoded[i+1], encoded[i] & 7))
            for i in range(0, 32, 2)]


def bordered(image, palette):
    """Include the complete 320x240 raw frame, rather than cropping overscan."""
    if image.size != (256, 212):
        raise ValueError('Expected a complete 256x212 display oracle')
    result = Image.new('RGB', (320, 240), palette_rgb(palette)[index_for(palette, (0, 0, 0))])
    result.paste(image, (32, 14))
    return result


def index_for(encoded, source):
    rgb = expand(rgb333(source))
    return palette_rgb(encoded).index(rgb)


def header(assets, encoded, score=0, high=20000, player=1):
    """Use all 32 original 8x8 cells, with inline values and no scaled glyphs."""
    if player not in (1,2):
        raise ValueError('Player label must be 1 or 2')
    black = index_for(encoded, (0, 0, 0))
    white = index_for(encoded, (222, 222, 222))
    red = index_for(encoded, (255, 0, 0))
    cyan = index_for(encoded, (0, 151, 222))
    parts = [(' ', black), ('HISCORE:', white), (f'{high:06d}', red), (' '*7, black),
             (f'{player}UP:', white), (f'{score:06d}', cyan)]
    if sum(len(text) for text, _ in parts) != 32:
        raise ValueError('Scoreboard values must fit one 32-cell line')
    result = bytearray([black]) * (256*8)
    column = 0
    for text, color in parts:
        for char in text:
            if char != ' ':
                code = int(char) if char.isdigit() else ord(char)
                glyph = assets.pixels['tiles'][code*64:(code+1)*64]
                for y in range(8):
                    for x in range(8):
                        if assets.palette['lookup'][38*4+glyph[y*8+x]] != 0:
                            result[y*256+column*8+x] = color
            column += 1
    return bytes(result)


def outlined_life(mask):
    """Preserve the source silhouette and add a one-pixel, eight-neighbor outline."""
    if len(mask) != 256:
        raise ValueError('Life icon must retain its 16x16 source dimensions')
    if any(mask[y*16+x] for y in range(16) for x in range(16)
           if x in (0, 15) or y in (0, 15)):
        raise ValueError('Source life icon needs padding for an unclipped outline')
    return bytes(any(mask[ny*16+nx] for ny in range(max(0, y-1), min(16, y+2))
                     for nx in range(max(0, x-1), min(16, x+2)))
                 for y in range(16) for x in range(16))


def player_label_patterns(assets, palette):
    """Extract the original 1/2 glyph at the current label position."""
    return b''.join(packed(bytes(line[y*256+PLAYER_LABEL_X+x]
                                  for y in range(8) for x in range(8)))
                    for player in (1, 2) for line in [header(assets, palette, player=player)])


def sprite_pattern(mask, shift=0):
    if shift and any(mask[-16:]):
        raise ValueError('Sentinel-avoidance shift would clip sprite pixels')
    return bytes(sum((mask[(y-shift)*16+x+bit] if y >= shift else 0) << (7-bit)
                     for bit in range(8)) for x in (0, 8) for y in range(16))


def sprite_attributes(cy, lives=2, points=None, footer=False):
    overlay = radar.attributes(cy, points['player'], points['enemy']) if points else b''
    result = overlay
    if footer:
        result += life_counter.attributes(cy)
    elif points:
        result += fuel.attributes(cy)
    return result + bytes([216])


def compose(world, hud, life, palette, cx=0, cy=0, lives=2, points=None, player_color=None,
            fuel_level=None, life_digits=None, *, width=256, fuel_pixels=None):
    """Independent screen-coordinate oracle; no hardware-page/address calculations."""
    black, yellow = index_for(palette, (0, 0, 0)), index_for(palette, (255, 255, 0))
    pixels = bytearray([black]) * (256*212)
    pixels[:256*HUD_HEIGHT] = hud
    for y in range(BODY_TOP, 212):
        for x in range(LEFT_MASK, 256-RIGHT_MASK):
            pixels[y*256+x] = world[(y-BODY_TOP+cy)*width+x-LEFT_MASK+cx]
    if life_digits is not None:
        life_counter.paint(pixels, life, outlined_life(life), life_digits, lives, yellow, black,
                           index_for(palette, (222, 222, 222)))
    if points:
        white, red = index_for(palette, (222, 222, 222)), index_for(palette, (255, 0, 0))
        radar.paint(pixels, points['flags'], points['player'], points['enemy'], white, red,
                    white if player_color is None else player_color)
    if fuel_level is not None:
        fuel_pixels = fuel.LEVELS[fuel_level]
    if fuel_pixels is not None:
        fuel.paint_pixels(pixels, fuel_pixels, index_for(palette, (222, 222, 222)), yellow)
    image = Image.new('RGB', (256, 212))
    colors = palette_rgb(palette)
    image.putdata([colors[index] for index in pixels])
    framed = Image.new('RGB', image.size, colors[black])
    framed.paste(image, (DISPLAY_SHIFT, 0))
    return framed


def build(root, args):
    output = destination(root, args.output)
    require_ignored(root, [output/'raster-scroll.rom'])
    palette, huds, colors, scenes = sources(args)
    from . import player as driver
    palette,huds=driver.palette(palette,huds)
    assets = load_assets(args.assets)
    from . import stage_one
    program, native = stage_one.acquire(root)
    cells, pairs, checked = stage_one.reconstruct(program, native)
    stage_world = stage_one.bitmap(pairs, assets, palette)
    yellow = index_for(palette, (255, 255, 0))
    black = index_for(palette, (0, 0, 0))
    life = bytes(huds[0][(180+y)*56+x] == yellow for y in range(16) for x in range(16))
    patterns = bytes(128)  # Preserve established radar/fuel pattern indices.
    patterns += bytes(32)  # Retain subsequent pattern IDs; no mask pattern/SAT.
    flags = [(2+(i%32*24+36)*44//stage_one.WIDTH,
              2+(i//32*24+36)*54//stage_one.HEIGHT)
             for i,c in enumerate(cells) if c in (1,2,4)]
    points = [dict(flags=flags, player=[2+(x+VIEWPORT_HALF)*44//stage_one.WIDTH,
                                       2+(y+100)*54//stage_one.HEIGHT],
                   enemy=radar.capture_enemy(scene['path'], assets))
              for scene,(x,y) in zip(scenes,stage_one.LANDMARKS)]
    patterns += bytes(12*64+128)  # Two phases for the frame and two dynamic point sprites.
    patterns += fuel.icon_patterns()+fuel.gauge_patterns(0)
    patterns += b''.join(sprite_pattern(mask, phase) for phase in (0,1)
                         for mask in (life, outlined_life(life)))+bytes(64)
    digits = life_counter.digit_masks(assets)
    states = [header(assets, palette, i*5000, max(20000, i*5000)) for i in range(32)]
    output.mkdir(parents=True)
    banks = stage_one.tile_banks(stage_world)
    (output/'stage-world.bin').write_bytes(stage_world)
    (output/'stage-radar-x.bin').write_bytes(bytes(2+(x+VIEWPORT_HALF)*44//stage_one.WIDTH
        for x in range(stage_one.WIDTH-VIEWPORT_WIDTH+1)))
    (output/'stage-radar-y.bin').write_bytes(bytes(2+(y+100)*54//stage_one.HEIGHT
        for y in range(stage_one.HEIGHT-201+1)))
    (output/'stage-tilemap.bin').write_bytes(bytes(v for pair in pairs for v in pair))
    (output/'stage-landmarks.bin').write_bytes(b''.join(v.to_bytes(2,'little')
        for point in stage_one.LANDMARKS for v in point))
    image = Image.new('RGB',(stage_one.WIDTH,stage_one.HEIGHT))
    rgb_palette = palette_rgb(palette)
    image.putdata([rgb_palette[p] for p in stage_world])
    image.save(output/'stage-one.png')
    json_write(output/'stage-one.json', dict(width=stage_one.WIDTH,height=stage_one.HEIGHT,
        maze=[24,24,792,1368], border=24, source_origin=[-24,-24],
        landmarks=stage_one.LANDMARKS, native_tiles_checked=checked,
        cells=1792, flags=cells.count(1), special_flags=cells.count(2),
        lucky_flags=cells.count(4), rocks=cells.count(3),
        native_manifest=digest(native/'manifest.json')))
    hud_bank = len(banks)+1
    # A single font bank supports every six-digit score, not 32 fixed values.
    pair_fonts = bytearray()
    for color in (index_for(palette,(0,151,222)), index_for(palette,(255,0,0))):
        for value in range(100):
            pair = bytearray([black])*(16*8)
            for column,digit in enumerate((value//10,value%10)):
                glyph=assets.pixels['tiles'][digit*64:(digit+1)*64]
                for y in range(8):
                    for x in range(8):
                        if assets.palette['lookup'][38*4+glyph[y*8+x]]:
                            pair[y*16+column*8+x]=color
            pair_fonts.extend(packed(pair))
    data = packed(header(assets,palette,high=0))+pair_fonts
    data += bytes(16384-len(data))
    banks.append(bytes(data))
    resources = b''.join(fuel.gauge_patterns(i) for i in range(31))
    resources += bytes(4096-len(resources))
    resources += radar.patterns(radar.bitmap([]))
    resources += player_label_patterns(assets, palette)
    banks.append(resources+bytes(16384-len(resources)))
    player_bank=len(banks)+1
    banks.extend(driver.build(output,program,(native/'video.bin').read_bytes(),assets))
    atlas,ids,atlas_count=driver.atlas(stage_world)
    (output/'stage-atlas.bin').write_bytes(atlas)
    id_bank=len(banks)+1
    banks.extend(ids)
    json_write(output/'stage-atlas.json',dict(tiles=atlas_count,vram=0x10800,id_bank=id_bank))
    (output/'player-radar-x.bin').write_bytes(bytes(2+(i*8+4)*44//stage_one.WIDTH for i in range(102)))
    (output/'player-radar-y.bin').write_bytes(bytes(2+(i*8+4)*54//stage_one.HEIGHT for i in range(174)))
    (output/'hud-states.bin').write_bytes(b''.join(packed(state) for state in states))
    (output/'life.bin').write_bytes(life)
    (output/'life-digits.bin').write_bytes(digits)
    (output/'sprite-patterns.bin').write_bytes(patterns)
    (output/'radar-patterns.bin').write_bytes(radar.patterns(radar.bitmap([])))
    (output/'radar-enemies.bin').write_bytes(bytes(v for p in points for v in p['enemy']))
    (output/'hud-fuel-scale.bin').write_bytes(bytes(min(i,54)*30//54 for i in range(256)))
    (output/'hud-project-x.bin').write_bytes(bytes(2+x*44//64 for x in range(64)))
    (output/'hud-project-y.bin').write_bytes(bytes(2+y*54//112 for y in range(112)))
    (output/'hud-demo-flags.bin').write_bytes(bytes(v for point in flags for v in point))
    (output/'hud-demo-digits.bin').write_bytes(bytes(int(c) for i in range(32) for c in f'{i*5000:06d}'))
    json_write(output/'radar.json', dict(x=radar.X, y=radar.Y, width=radar.WIDTH,
                                      height=radar.HEIGHT, scenes=points))
    white = index_for(palette, (222, 222, 222))
    red = index_for(palette, (255, 0, 0))
    sprite_colors = bytes([white | 0x20])*(16*13) + bytes([red | 0x20])*16
    sprite_colors += b''.join(bytes([c | 0x20])*16 for c in (white, yellow, yellow))
    sprite_colors += bytes([3|0x20])*16+bytes([9|0x60])*16
    (output/'sprite-colors.bin').write_bytes(sprite_colors)
    (output/'sprite-attributes.bin').write_bytes(sprite_attributes(0, points=dict(player=[2,2],enemy=[2,2])))
    (output/'palette.bin').write_bytes(palette)
    for n, bank in enumerate(banks, 1):
        (output/f'bank-{n}.bin').write_bytes(bank)
    size = 16384*(1 << len(banks).bit_length())
    (output/'config.inc').write_text(
        f'HUD_WORK_BASE EQU $c000\nHUD_API_BASE EQU $c300\n'
        f'VDP_R9 EQU {video_timing(args.hz)["vdp_r9"]}\nBLACK EQU {black}\n'
        f'HUD_BANK EQU {hud_bank}\nHUD_DATA_BANK EQU {hud_bank+1}\nBODY_TOP EQU {BODY_TOP}\nLIFE_Y EQU {LIFE_Y}\n'
        f'PLAYER_BANK EQU {player_bank}\nPLAYER_DATA_BANK EQU {player_bank+1}\n'
        f'STAGE_ID_BANK EQU {id_bank}\n'
        f'PLAYER_RATE EQU {round((video_timing(args.hz)["frame_seconds"]/.0165-1)*65536)}\n'
        f'LIFE_X0 EQU {LIFE_X[0]}\nLIFE_X1 EQU {LIFE_X[1]}\nMASK_SPRITES EQU {len(MASK_ROWS)}\n'
        f'VIEWPORT_WIDTH EQU {VIEWPORT_WIDTH}\nVIEWPORT_HALF EQU {VIEWPORT_HALF}\n'
        f'HORIZONTAL_ADJUST EQU {HORIZONTAL_ADJUST}\nPLAYER_X EQU {PLAYER_X}\n'
        f'PLAYER_LABEL_X EQU {PLAYER_LABEL_X}\nSCORE_X EQU {SCORE_X}\n'
        f'FUEL_SLOT EQU {FUEL_SLOT}\nPLAYER_SLOT EQU {PLAYER_SLOT}\n'
        f'FUEL_COLORS EQU $f400+{FUEL_SLOT}*16\nFUEL_ATTRIBUTES EQU $f600+{FUEL_SLOT}*4\n'
        f'PLAYER_COLORS EQU $f400+12*16\n'
        f'SAT_BYTES EQU {HUD_SPRITES*4+1}\nPATTERN_BYTES EQU {len(patterns)}\n'
        f'SPRITE_COLOR_BYTES EQU {len(sprite_colors)}\nWHITE EQU {white}\n'
        f'RADAR_X EQU {radar.X}\nRADAR_Y EQU {radar.Y}\n'
        f'YELLOW EQU {yellow}\nFUEL_Y EQU {fuel.Y}\nLIFE_SPLIT EQU {LIFE_SPLIT}\n')
    (output/'payload.inc').write_text(''.join(f'    INCBIN "bank-{n}.bin"\n' for n in range(1, len(banks)+1))
                                      + f'    defs {size}-$+16384,$ff\n')
    with (output/'config.inc').open('a') as config:
        config.write(f'STAGE_WIDTH EQU {stage_one.WIDTH}\n'
            f'STAGE_HEIGHT EQU {stage_one.HEIGHT}\nSTAGE_COLUMNS EQU {stage_one.TILE_COLUMNS}\n'
            f'STAGE_ROWS EQU {stage_one.TILE_ROWS}\n')
    shutil.copyfile(root/'src/stage-one-stream.inc', output/'stage-one-stream.inc')
    shutil.copyfile(root/'src/player.inc',output/'player.inc')
    (output/'stage-flower-phase.bin').write_bytes(bytes((i-256 if i>=224 else i)%3 for i in range(256)))
    for name in ('hud.inc','hud-api.inc','hud-demo.inc','hud-native.inc','hud-state.inc','hud-assets.inc','hud-raster.inc'):
        shutil.copyfile(root/'src'/name,output/name)
    shutil.copyfile(root/'src/raster-scroll.asm', output/'raster-scroll.asm')
    result = subprocess.run([str(args.assembler.resolve()), '--nologo', '--sym=raster-scroll.sym',
                             '--lst=raster-scroll.lst', 'raster-scroll.asm'], cwd=output,
                            capture_output=True, text=True)
    (output/'assembly.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError(f'Raster cartridge assembly failed: {result.stdout}{result.stderr}')
    rom = output/'raster-scroll.rom'
    if rom.stat().st_size != size:
        raise ValueError('Unexpected raster cartridge size')
    json_write(output/'build.json', dict(schema_version=1, experiment='full-screen-hardware-raster',
        step_pixels=1, strip_border_flowers=False, timing=video_timing(args.hz),
        geometry=dict(width=256, height=212, header_height=HUD_HEIGHT, separator=[8, BODY_TOP],
                      maze=[LEFT_MASK, BODY_TOP, 256-RIGHT_MASK, 212], left_mask=LEFT_MASK,
                      right_mask=RIGHT_MASK, header=[LEFT_MASK, 0, 256, HUD_HEIGHT],
                      horizontal_adjust=HORIZONTAL_ADJUST, display_shift=DISPLAY_SHIFT,
                      framed_maze=[4, BODY_TOP, 252, 212]),
        sprites=dict(size=[16, 16], life_y=LIFE_Y, life_x=list(LIFE_X), layers_per_life=2,
                     life_size=[16,16], life_magnification=1, life_split=LIFE_SPLIT,
                     life_counter_slots=3, life_reuses_fuel_slots=list(range(FUEL_SLOT,FUEL_SLOT+3)),
                     maximum_lives=9, margin_slots=0, radar_slots=14, hud_slots=HUD_SPRITES,
                     player_slots=2, player_first_slot=PLAYER_SLOT, total_slots=TOTAL_SPRITES, free_slots=32-TOTAL_SPRITES,
                     black=black, yellow=yellow, white=white, red=red), colors=colors, size=size,
        scenes=[dict(number=s['number'], world_origin=stage_one.LANDMARKS[i])
                for i,s in enumerate(scenes)],
        inputs=dict(assets=digest(args.assets/'manifest.json'),
                    captures=[digest(s['path']/'manifest.json') for s in scenes],
                    hud=[digest(p/'manifest.json') for p in (args.normal, args.overlap)]),
        source_sha256={p:digest(root/p) for p in ('src/raster-scroll.asm', 'scripts/msx/raster_scroll.py',
                       'scripts/msx/inputs.py', 'scripts/msx/display.py', 'scripts/msx/sprite_radar.py', 'scripts/msx/player.py','src/player.inc',
                       'scripts/msx/sprite_fuel.py', 'scripts/msx/sprite_lives.py',
                       'src/stage-one-stream.inc', 'src/hud.inc', 'src/hud-api.inc', 'src/hud-demo.inc', 'src/hud-native.inc', 'src/hud-state.inc', 'src/hud-assets.inc', 'src/hud-raster.inc', 'scripts/msx/stage_one.py',
                       'scripts/msx/stage_one_capture.lua')}, rom_sha256=digest(rom),
        fuel=dict(rectangle=[fuel.X, fuel.Y, fuel.X+fuel.WIDTH, fuel.Y+fuel.HEIGHT],
                  slots=list(range(FUEL_SLOT,FUEL_SLOT+3)), levels=list(fuel.LEVELS)),
        scope='Original player movement, steering and walls with sprite HUD; enemy AI and remaining gameplay rules pending'))
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])
    seal(output)
    print(f'{size} bytes, {len(banks)+1} banks: {rom}')
    return rom
