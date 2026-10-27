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
from . import full_hud
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
    if 'left_header' in image.info:
        result.paste(image.info['left_header'],(32+DISPLAY_SHIFT,14))
    return result


def index_for(encoded, source):
    rgb = expand(rgb333(source))
    return palette_rgb(encoded).index(rgb)


def header(assets, encoded, score=0, high=20000, player=1, *, background=None, full_game=False, round_=1):
    """Use all 32 original 8x8 cells, with inline values and no scaled glyphs."""
    if player not in (1,2):
        raise ValueError('Player label must be 1 or 2')
    black = index_for(encoded, (0, 0, 0))
    white = index_for(encoded, (222, 222, 222))
    red = index_for(encoded, (255, 0, 0))
    cyan = index_for(encoded, (0, 151, 222))
    parts = [(' ', black), ('HISCORE:', white), (f'{high:06d}', red), (' '*7, black),
             (f'{player}UP:', white), (f'{score:06d}', cyan)]
    if full_game:
        from .full_hud import score_text,round_text
        parts=[(' ',black),('HI:',white),(score_text(high),red),('  ',black),
               (f'{player}UP:',white),(score_text(score),cyan),('    R:',white),
               (round_text(round_),white)]
    if sum(len(text) for text, _ in parts) != 32:
        raise ValueError('Scoreboard values must fit one 32-cell line')
    result = bytearray([black if background is None else background]) * (256*8)
    column = 0
    for text, color in parts:
        for char in text:
            if char == '\u221e':
                from .full_hud import infinity_pixels
                mask=infinity_pixels()
                for y in range(8):
                    for x in range(16):
                        if mask[y*16+x]:result[y*256+column*8+x]=color
                column+=1  # The following reserved blank owns the other half.
                continue
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


def player_label_patterns(assets, palette, *, background=None,full_game=False):
    """Extract the original 1/2 glyph at the current label position."""
    from .full_hud import PLAYER_LABEL_X as FULL_PLAYER_LABEL_X
    return b''.join(packed(bytes(line[y*256+(FULL_PLAYER_LABEL_X if full_game else PLAYER_LABEL_X)+x]
                                  for y in range(8) for x in range(8)))
                    for player in (1, 2) for line in [header(assets, palette, player=player,background=background,full_game=full_game)])


def sprite_pattern(mask, shift=0):
    if shift and any(mask[-16:]):
        raise ValueError('Sentinel-avoidance shift would clip sprite pixels')
    return bytes(sum((mask[(y-shift)*16+x+bit] if y >= shift else 0) << (7-bit)
                     for bit in range(8)) for x in (0, 8) for y in range(16))


def sprite_attributes(cy, lives=2, points=None, footer=False,*,cells_only=False,bitmap_radar=False,separate_player=False):
    overlay = radar.attributes(cy, points['player'], points['enemy']) if points else b''
    if cells_only:overlay=overlay[:48]
    if bitmap_radar:
        hidden=(cy-11+211)&255
        overlay=bytes((hidden+int(hidden==216),0,116,0))
    result = overlay
    if separate_player:
        hidden=(cy-11+211)&255
        result=bytes((hidden+int(hidden==216),0,0,0))+result
    if footer:
        result += life_counter.attributes(cy)
    elif points:
        attrs=bytearray(fuel.attributes(cy))
        if bitmap_radar:
            for i in range(0,len(attrs),4):attrs[i]=(attrs[i]+80-radar.HEIGHT)&255
        result += attrs
    return result + bytes([216])


def compose(world, hud, life, palette, cx=0, cy=0, lives=2, points=None, player_color=None,
            fuel_level=None, life_digits=None, *, width=256, fuel_pixels=None, actors=(),actor_top=BODY_TOP,
            radar_back_points=(),life_outline=True,fuel_color=None):
    """Independent screen-coordinate oracle; no hardware-page/address calculations."""
    black, yellow = index_for(palette, (0, 0, 0)), index_for(palette, (255, 255, 0))
    pixels = bytearray([black]) * (256*212)
    pixels[:256*HUD_HEIGHT] = hud
    for y in range(BODY_TOP, 212):
        for x in range(LEFT_MASK, 256-RIGHT_MASK):
            pixels[y*256+x] = world[(y-BODY_TOP+cy)*width+x-LEFT_MASK+cx]
    if points:
        for px,py in radar_back_points:
            if px==255:continue
            for y in range(py,py+2):
                for x in range(px,px+2):
                    pixels[(radar.Y+y)*256+radar.X+x]=index_for(palette,(255,0,0))
    for actor,ax,ay in actors:
        for y in range(16):
            for x in range(16):
                color=actor[y*16+x]
                if color and LEFT_MASK<=ax+x<256 and actor_top<=ay+y<212:
                    pixels[(ay+y)*256+ax+x]=color
    if life_digits is not None:
        life_counter.paint(pixels, life, outlined_life(life) if life_outline else life, life_digits, lives, yellow, black,
                           index_for(palette, (222, 222, 222)))
    if points:
        white, red = index_for(palette, (222, 222, 222)), index_for(palette, (255, 0, 0))
        if points.get('cells_only'):
            from .radar_cells import paint
            paint(pixels,points['flags'],points['player'],[points['enemy'],*points.get('extra_enemies',())],
                  white,red,black,(cy-BODY_TOP)&255,square=points.get('square',True),cells=points.get('published_cells'))
            if points.get('separate_player_visible'):
                px,py=points['separate_player']
                for y in range(py,py+2):
                        for x in range(px,px+2):pixels[(radar.Y+y)*256+radar.X+x]=points['separate_player_color']
        else:
            radar.paint(pixels, points['flags'], points['player'], points['enemy'], white, red,
                        white if player_color is None else player_color,border=points.get('border',True),square=points.get('square',False),
                        enemies=points.get('extra_enemies',()))
    if fuel_level is not None:
        fuel_pixels = fuel.LEVELS[fuel_level]
    if fuel_pixels is not None:
        fuel.paint_pixels(pixels, fuel_pixels, index_for(palette, (222, 222, 222)), yellow if fuel_color is None else fuel_color)
    image = Image.new('RGB', (256, 212))
    colors = palette_rgb(palette)
    image.putdata([colors[index] for index in pixels])
    framed = Image.new('RGB', image.size, colors[black])
    framed.paste(image, (DISPLAY_SHIFT, 0))
    if DISPLAY_SHIFT<0:framed.info['left_header']=image.crop((0,0,-DISPLAY_SHIFT,8))
    return framed


def build(root, args):
    output = destination(root, args.output)
    hud_enabled = not getattr(args, 'no_hud', False)
    stage = getattr(args, 'stage', 0)
    full_game=bool(getattr(args,'full_game',False))
    if full_game and (stage!=12 or not hud_enabled):
        raise ValueError('Full-game development requires stage12 and the complete HUD')
    tile_mode=bool(getattr(args,'tile_mode',False))
    if tile_mode and stage not in (0,1):
        raise ValueError('SCREEN 4 prototype isolates the stage00/01 driving fixture')
    player_blitter=bool(getattr(args,'player_blitter',False))
    fast_player=bool(player_blitter and stage==9)
    bitmap_radar=bool(getattr(args,'radar_blitter',False))
    outline_flicker=bool(getattr(args,'outline_flicker',False))
    flicker=bool(getattr(args,'sprite_flicker',False) or outline_flicker)
    if outline_flicker and not hud_enabled:raise ValueError('Outline experiment retains the full HUD')
    if tile_mode and (player_blitter or bitmap_radar or flicker):
        raise ValueError('SCREEN 4 fixture uses the established sprite player/HUD')
    if bitmap_radar and (not hud_enabled or flicker):
        raise ValueError('Bitmap radar requires HUD enabled without sprite flicker')
    if player_blitter and stage not in (0,1,9):
        raise ValueError('Player blitter supports stages00/01 and the stage09 gameplay integration')
    if player_blitter and flicker:
        raise ValueError('Integrate the bitmap player before combining sprite priority rotation')
    cells_only=stage>=9 and not getattr(args,'separate_radar_points',False) and not flicker and not bitmap_radar
    radar_player=bool(cells_only and hud_enabled and not getattr(args,'enemy_logic_only',False) and getattr(args,'enemies',None)!=0)
    fuel_slot=12+radar_player if cells_only else FUEL_SLOT
    player_slot=15+radar_player if cells_only else PLAYER_SLOT
    hud_slots=15+radar_player if cells_only else HUD_SPRITES
    if bitmap_radar:fuel_slot,player_slot,hud_slots=1,4,4
    fuel_y=radar.Y+80+4 if bitmap_radar else fuel.Y
    base_slots=hud_slots+2
    if type(stage) is not int or stage not in range(13):
        raise ValueError('Choose implemented incremental stage 0 through 12')
    enemy_count=getattr(args,'enemies',None)
    if enemy_count is None:enemy_count=7 if full_game else 2 if flicker else 1 if stage>=8 else 0
    flicker_stress=bool(getattr(args,'flicker_stress',False))
    if flicker_stress and (not flicker or not hud_enabled):raise ValueError('Flicker HUD-overlap stress fixture requires sprite flicker and HUD')
    if enemy_count not in (range(8) if full_game else range(4)) or enemy_count and stage<8 or enemy_count>1 and stage<9:
        raise ValueError('Stage 08 supports one enemy; stage 09 supports up to three enemies')
    if bitmap_radar and enemy_count>1:
        raise ValueError('Bitmap radar experiment currently tracks one enemy')
    enemy_render=bool(enemy_count and not getattr(args,'enemy_logic_only',False))
    smoke_runtime=stage>=10
    from .inputs import native_clock
    logic_hz=getattr(args,'logic_hz',None)
    if logic_hz is not None and not smoke_runtime:
        raise ValueError('Slower logic diagnostics require stage10/11')
    clock=native_clock(args.hz,logic_hz)
    if full_game and args.hz==60:
        frame=video_timing(args.hz)['frame_seconds']
        clock=dict(clock,tick_seconds=frame,rate=0,base_ticks_per_refresh=1,
            speed_ratio=.0165/frame,adapted=True,mode='One logical tick per physical NTSC refresh')
    smoke_component=bool(getattr(args,'smoke_component',False) or smoke_runtime)
    completion_component=bool(getattr(args,'completion_component',False) or stage>=11)
    round_preparation=bool(getattr(args,'round_component',False) or full_game)
    if round_preparation and stage!=12:
        raise ValueError('Round preparation component requires the approved stage12 baseline')
    if completion_component and not smoke_runtime:
        raise ValueError('Completion component requires the stage10 gameplay reference')
    if smoke_component and (stage not in (9,10,11,12) or enemy_count!=1 and not full_game):
        raise ValueError('Smoke component proof starts from the stage09 one-enemy reference')
    if smoke_runtime and (not hud_enabled or not cells_only or player_blitter or bitmap_radar or flicker or tile_mode):
        raise ValueError('Smoke integration requires the accepted complete sprite player/radar and enabled HUD')
    if fast_player and (not hud_enabled or not cells_only or not enemy_render or bitmap_radar):
        raise ValueError('Stage09 bitmap player integration requires the compact sprite HUD and rendered enemies')
    enemy_contact=bool(enemy_render and not getattr(args,'enemy_render_only',False))
    enemy_planes=getattr(args,'enemy_planes',None) or 2
    if full_game and (enemy_count!=7 or enemy_planes!=2 or not enemy_contact or
                      getattr(args,'simple_maze',False) or getattr(args,'radar_quantum',1)!=1):
        raise ValueError('Full gameplay requires seven native actor slots, complete cars, contact, original scenery and exact radar coordinates')
    if enemy_planes not in (1,2) or enemy_count==1 and enemy_planes!=2:
        raise ValueError('The one-enemy reference keeps two planes; population diagnostics allow one or two')
    if flicker and (stage!=9 or enemy_count!=2 or not enemy_render or enemy_planes!=2):
        raise ValueError('Sprite flicker diagnostic requires stage09, two rendered enemies and two color planes')
    if enemy_count==3 and (not cells_only or not hud_enabled or player_blitter or enemy_planes!=2 or not enemy_render):
        raise ValueError('Three enemies require the normal sprite player/radar, complete car colors and enabled HUD')
    extra_radar=int(enemy_count>1 and enemy_render and hud_enabled and (not cells_only or enemy_count==3))
    bare_sat=bool(stage>=9 and enemy_count>=2 and not hud_enabled and cells_only)
    if bare_sat:
        fuel_slot,player_slot,hud_slots,base_slots=0,0,0,2
    tile_strips=bool(getattr(args,'tile_strips',False) or stage>=10)
    if tile_strips and not (stage==9 and enemy_count>=2 or smoke_runtime):
        raise ValueError('Tile strips require stage09 population or stage10 smoke')
    marker_quantum=getattr(args,'radar_quantum',1)
    if marker_quantum not in (1,2) or marker_quantum!=1 and not (tile_strips and cells_only and hud_enabled):
        raise ValueError('Radar quantization requires the stage09 compact HUD strip diagnostic')
    static_life=bool(cells_only and hud_enabled and enemy_count>=2 and not tile_strips)
    simple_maze=bool(getattr(args,'simple_maze',False))
    if simple_maze and not (stage==9 and enemy_count>=2 or smoke_runtime):
        raise ValueError('Simple maze requires stage09 population or stage10/11 smoke')
    cache_columns=48 if full_game else 48 if stage>=10 else 40 if stage>=9 else 48 if stage>=4 else 64
    cache_guard=8 if full_game else 8 if stage>=10 else 4 if stage>=9 else 8 if stage>=4 else 16
    if getattr(args,'cache_columns',None):
        cache_columns=args.cache_columns
        if cache_columns in (36,40) and stage<9:raise ValueError('The 40-column cache is a stage09 experiment')
        cache_guard=2 if cache_columns==36 else 4 if cache_columns==40 else 8 if cache_columns==48 else 16
    require_ignored(root, [output/'raster-scroll.rom'])
    palette, huds, colors, scenes = sources(args)
    from . import player as driver
    palette,huds=driver.palette(palette,huds,enemy=enemy_render)
    if full_game:
        from .round_scenery import complete_palette
        palette=complete_palette(palette)
        huds=[bytes(data).translate(bytes(11 if i==15 else i for i in range(256))) for data in huds]
    assets = load_assets(args.assets)
    from . import stage_one
    program, native = stage_one.acquire(root)
    cells, pairs, checked = stage_one.reconstruct(program, native)
    rock_reference = None
    rock_positions = []
    rock_checked = 0
    if 1 <= stage <= 10:
        from . import rocks
        cells,rock_positions,rock_checked,rock_reference = rocks.acquire(root,program,cells)
        source_video = (native/'video.bin').read_bytes()
        pairs = [stage_one.tile(program,cells,x-3,y-3,source_video[0x2b1],source_video[0x2d6])
                 for y in range(stage_one.TILE_ROWS) for x in range(stage_one.TILE_COLUMNS)]
    stage_world = stage_one.bitmap(pairs, assets, palette)
    tile_data=None
    if tile_mode:
        from .tilemap import encode
        before=stage_world
        tile_data=encode(stage_world,palette)
        stage_world=tile_data['world']
        tile_data['source_world_sha256']=__import__('hashlib').sha256(before).hexdigest()
    scenery_style=None
    if simple_maze:
        source=index_for(palette,(0,0,151));target=index_for(palette,(255,0,151))
        protected=[(24+i%32*24,24+i//32*24,24,24)
                   for i,kind in enumerate(cells) if kind in (1,2,3,4)]
        original_world=stage_world
        stage_world=driver.merge_scenery_color(stage_world,source,target,protected)
        scenery_style=dict(mode='merge-blue-wall-outline',source_index=source,target_index=target,
            protected_objects=len(protected),changed_pixels=sum(a!=b for a,b in zip(original_world,stage_world)),
            source_world_sha256=__import__('hashlib').sha256(original_world).hexdigest(),
            dimensions_unchanged=True,collision_world_unchanged=True)
    yellow = index_for(palette, (255, 255, 0))
    black = index_for(palette, (0, 0, 0))
    header_background=black
    radar_border=True
    radar_square=stage>=8
    life = bytes(huds[0][(180+y)*56+x] == yellow for y in range(16) for x in range(16))
    patterns = bytes(128)  # Preserve established radar/fuel pattern indices.
    patterns += bytes(32)  # Retain subsequent pattern IDs; no mask pattern/SAT.
    flags = [(2+(i%32*24+36)*44//stage_one.WIDTH,
              2+(i//32*24+36)*54//stage_one.HEIGHT)
             for i,c in enumerate(cells) if c in (1,2,4)]
    points = [dict(flags=flags,border=radar_border,square=radar_square, player=[2+(x+VIEWPORT_HALF)*44//stage_one.WIDTH,
                                       2+(y+100)*54//stage_one.HEIGHT],
                   enemy=radar.capture_enemy(scene['path'], assets))
              for scene,(x,y) in zip(scenes,stage_one.LANDMARKS)]
    patterns += bytes(12*64+128)  # Two phases for the frame and two dynamic point sprites.
    patterns += fuel.icon_patterns()+fuel.gauge_patterns(0)
    patterns += b''.join(sprite_pattern(mask, phase) for phase in (0,1)
                         for mask in (life, outlined_life(life)))+bytes(64)
    digits = life_counter.digit_masks(assets)
    states = [header(assets, palette, i*5000, max(20000, i*5000),background=header_background) for i in range(32)]
    output.mkdir(parents=True)
    (output/'rock-cells.bin').write_bytes(b''.join((0x9800+p['cell_y']*32+p['cell_x']).to_bytes(2,'little')
        for p in rock_positions))
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
        native_manifest=digest(native/'manifest.json'),
        rock_fixture=(dict(original_parameter_round=3, positions=rock_positions,
                           native_tiles_checked=rock_checked,
                           manifest_sha256=digest(rock_reference/'manifest.json')) if rock_reference else None)))
    hud_bank = len(banks)+1
    # A single font bank supports every six-digit score, not 32 fixed values.
    pair_fonts = bytearray()
    for color in (index_for(palette,(0,151,222)), index_for(palette,(255,0,0))):
        for value in range(100):
            pair = bytearray([header_background])*(16*8)
            for column,digit in enumerate((value//10,value%10)):
                glyph=assets.pixels['tiles'][digit*64:(digit+1)*64]
                for y in range(8):
                    for x in range(8):
                        if assets.palette['lookup'][38*4+glyph[y*8+x]]:
                            pair[y*16+column*8+x]=color
            pair_fonts.extend(packed(pair))
    data = (packed(header(assets,palette,high=0,background=header_background,full_game=full_game)) if hud_enabled else bytes([black*17])*1024)+pair_fonts
    data += bytes(16384-len(data))
    if tile_strips:
        if any(data[0x3f00:0x3fc0]):raise ValueError('Demo digits overlap HUD fonts')
        data=bytearray(data)
        data[0x3f00:0x3fc0]=bytes(int(c) for i in range(32) for c in f'{i*5000:06d}')
    banks.append(bytes(data))
    resources = b''.join(fuel.gauge_patterns(i) for i in range(31))
    resources += bytes(4096-len(resources))
    resources += radar.patterns(radar.bitmap([],border=radar_border,square=radar_square))
    resources += player_label_patterns(assets, palette,background=header_background,full_game=full_game)
    banks.append(resources+bytes(16384-len(resources)))
    player_bank=len(banks)+1
    banks.extend(driver.build(output,program,(native/'video.bin').read_bytes(),assets,rock_collision=stage>=2,scoring=stage>=5,fuel=stage>=6,lives=stage>=7,enemies=bool(enemy_count),enemy_count=enemy_count,smoke=smoke_component,smoke_notify=smoke_runtime,parameters=completion_component,round_preparation=round_preparation,full_game=full_game))
    smoke_tiles=[]
    if smoke_runtime:
        from .smoke import eligibility
        cleared=bytes(0 if c in (1,2,4) else c for c in cells)
        video=(native/'video.bin').read_bytes()
        clear_pairs=[stage_one.tile(program,cleared,x-3,y-3,video[0x2b1],video[0x2d6])
            for y in range(stage_one.TILE_ROWS) for x in range(stage_one.TILE_COLUMNS)]
        permission=eligibility(pairs,clear_pairs)
        data=bytearray(banks[player_bank])
        if any(data[0x700:0x700+len(permission)]) or 0x700+len(permission)>0x2000:
            raise ValueError('Smoke permission map overlaps player resources')
        data[0x700:0x700+len(permission)]=permission;banks[player_bank]=bytes(data)
        (output/'smoke-permission.bin').write_bytes(permission)
        from .death import pixels as original_pixels
        if program[0xfeb:0xfed]!=bytes((0x3e,0xbd)) or program[0xff3:0xff5]!=bytes((0x36,0x45)):
            raise ValueError('Original smoke tile sequence changed')
        smoke_tiles=original_pixels([(program[0xfec]+i,program[0xff4]) for i in range(9)],assets,palette)
    if outline_flicker:
        from .outline_flicker import resources,order
        masks,row_colors=resources((output/'player-pixels.bin').read_bytes())
        data=bytearray(banks[player_bank]);data[:len(masks)]=masks
        if any(data[0x1800:0x1800+len(row_colors)*2]):raise ValueError('Outline color table overlaps player resources')
        data[0x1800:0x1800+len(row_colors)]=row_colors
        enemy_colors=bytes((v&32)|(6 if v&15==3 else 10) for v in row_colors)
        data[0x1800+len(row_colors):0x1800+2*len(row_colors)]=enemy_colors
        banks[player_bank]=bytes(data)
        (output/'outline-colors.bin').write_bytes(row_colors+enemy_colors)
        (output/'outline-orders.bin').write_bytes(bytes(i for p in range(4) for i in order(p)))
    if player_blitter or bitmap_radar:
        pixels=(output/'player-pixels.bin').read_bytes()
        player_atlas=bytes(v for y in range(16) for frame in range(12)
            for v in packed(pixels[frame*256+y*16:frame*256+y*16+16]))
        data=bytearray(banks[player_bank])
        if any(data[0x800:0x800+len(player_atlas)]):raise ValueError('Player blitter source overlaps bank resources')
        if player_blitter:data[0x800:0x800+len(player_atlas)]=player_atlas
        if fast_player:
            from .player_blitter import opaque_atlas
            fast_atlas=opaque_atlas(pixels,0)
            if any(data[0xe00:0xe00+len(fast_atlas)]):raise ValueError('Opaque player atlas overlaps bank resources')
            data[0xe00:0xe00+len(fast_atlas)]=fast_atlas
        if bitmap_radar:
            blue=index_for(palette,(0,0,151));white=index_for(palette,(222,222,222))
            image=bytearray([blue])*(48*80)
            for x,y in flags:
                y=2+(y-2)*76//54
                for row in range(2):image[(y+row)*48+x:(y+row)*48+x+2]=bytes([white])*2
            radar_data=packed(image)
            # A second byte-aligned phase permits HMMM at odd destination X.
            shifted=packed(bytes(v for y in range(80) for v in ([blue]+list(image[y*48:y*48+48])+[blue])))
            radar_sources=radar_data+shifted
            if any(data[0xe00:0xe00+len(radar_sources)]):raise ValueError('Bitmap radar source overlaps bank data')
            data[0xe00:0xe00+len(radar_sources)]=radar_sources
            (output/'radar-bitmap.bin').write_bytes(radar_data)
            (output/'radar-bitmap-y.bin').write_bytes(bytes(255 if y==255 else min(78,2+max(0,y-2)*76//54) for y in range(256)))
        banks[player_bank]=bytes(data)
    death_reference=None
    death_tiles=[]
    death_ticks=0
    flag_records=[]
    empty_tiles=[]
    if stage>=3:
        from . import death
        death_pairs,death_ticks,death_reference=death.acquire(root)
        death_tiles=death.pixels(death_pairs,assets,palette)
    if stage>=4:
        from . import flags as collection
        flag_records=collection.records((native/'video.bin').read_bytes(),cells)
        empty_pairs=[stage_one.tile(program,bytes(1792),x,y,0,0) for y in range(3) for x in range(3)]
        empty_tiles=death.pixels(empty_pairs,assets,palette)
        if len(set(empty_tiles))!=1:raise ValueError('Original empty flag cell is not a uniform tile')
        empty_tiles=empty_tiles[:1]
        if fast_player and set(empty_tiles[0])!={0}:
            raise ValueError('Opaque player requires the certified original color-zero road')
    solid_runs=bool(stage>=9 and (enemy_count>=2 or fast_player or smoke_runtime))
    source_xy=solid_runs
    grouped_rows=tuple(range(0,len(death_tiles),3))+tuple(len(death_tiles)+len(empty_tiles)+i for i in range(0,len(smoke_tiles),3)) if stage>=11 or simple_maze else ()
    atlas,ids,atlas_count,extra_ids=driver.atlas_with_tiles(stage_world,death_tiles+empty_tiles+smoke_tiles,force_source_xy=source_xy,grouped_rows=grouped_rows)
    source_xy=bool(source_xy or atlas_count>32)
    death_ids=extra_ids[:len(death_tiles)]
    if stage>=6:
        for i in range(0,9,3):
            if death_ids[i]%32>29 or death_ids[i:i+3]!=list(range(death_ids[i],death_ids[i]+3)):
                raise ValueError('Original explosion row is not contiguous in its command atlas')
    empty_id=extra_ids[len(death_tiles)] if empty_tiles else 0
    if smoke_runtime:
        smoke_ids=extra_ids[len(death_tiles)+len(empty_tiles):]
        for i in range(0,9,3):
            if smoke_ids[i]%32>29 or smoke_ids[i:i+3]!=list(range(smoke_ids[i],smoke_ids[i]+3)):
                raise ValueError('Original smoke row is not contiguous in its command atlas')
        (output/'smoke-sources.bin').write_bytes(bytes(v for i in smoke_ids for v in ((i%32)*8,16+i//32*8)))
        flowers=ids[0]
        flower_sources=[]
        for y in range(3):
            row=[tuple(flowers[y*256+x*2:y*256+x*2+2]) for x in range(3)]
            if any(v!=(row[0][0]+x*8,row[0][1]) for x,v in enumerate(row)) or row[0][0]>232:
                raise ValueError('Original flower row is not contiguous in its command atlas')
            flower_sources.extend(row[0])
        (output/'flower-sources.bin').write_bytes(bytes(flower_sources))
        (output/'smoke-pixels.bin').write_bytes(b''.join(smoke_tiles))
    flag_row=0
    if enemy_render:
        # Three copies of the original empty tile occupy spare atlas slots.
        # One 24x8 command replaces three individual collected-flag copies.
        flag_row=atlas_count
        if flag_row%32>29:flag_row+=32-flag_row%32
        if flag_row+3>len(atlas)//32:raise ValueError('No spare atlas row for collected-flag brush')
        atlas=bytearray(atlas)
        for y in range(8):
            at=(flag_row//32*8+y)*128+flag_row%32*4
            atlas[at:at+12]=packed(empty_tiles[0][y*8:y*8+8])*3
        atlas=bytes(atlas)
    if smoke_runtime and not tile_strips:
        if len(atlas)!=2048 or flag_row+3>61:
            raise ValueError('Vertical flower strips overlap the command atlas')
        atlas=bytearray(atlas)+bytes(2048)
        for phase in range(3):
            for y in range(24):
                at=(8+y)*128+(232+phase*8)//2
                pixels=stage_world[y*stage_one.WIDTH+phase*8:y*stage_one.WIDTH+phase*8+8]
                atlas[at:at+4]=packed(pixels)
        atlas=bytes(atlas)
    if smoke_runtime:
        (output/'flower-vertical-sources.bin').write_bytes(bytes(v for phase in range(3) for v in (232+phase*8,24)))
    if stage>=4:ids=collection.encode_owners(ids,flag_records)
    if solid_runs:
        ids=driver.uniform_source_tags(atlas,ids)
    if tile_strips:
        from .tile_strips import candidates
        ids=candidates(ids)
    (output/'flag-records.bin').write_bytes(b''.join(f['address'].to_bytes(2,'little')+
        bytes((f['kind'],f['hud_slot'],f['tile_x'],f['tile_y'])) for f in flag_records))
    json_write(output/'flags.json',dict(records=flag_records,empty_tile=empty_id,
        ownership_encoding='source-X bit 0 marker; source-Y high nibble slot+1' if stage>=4 else None))
    (output/'death-sources.bin').write_bytes(bytes(v for i in death_ids for v in ((i%32)*8,16+i//32*8)))
    (output/'death-pixels.bin').write_bytes(b''.join(death_tiles))
    (output/'stage-atlas.bin').write_bytes(atlas)
    if stage>=8:
        if len(atlas)>4096:raise ValueError('Command atlas exceeds spare player data-bank space')
        data=bytearray(banks[player_bank])
        if any(data[0x3000:]):raise ValueError('Player data-bank atlas region is not empty')
        data[0x3000:0x3000+len(atlas)]=atlas
        banks[player_bank]=bytes(data)
    enemy_mask_bank=0
    enemy_pair_bank=0
    if enemy_render:
        # Twelve facings x sixteen left clips x two mode-2 planes, 12 KiB.
        # Precompute this exact masking operation outside the raster deadline.
        enemy_mask_bank=len(banks)+1
        masks=banks[player_bank][:1536]
        def enemy_masks(index):
            result=masks[index*128:index*128+64]
            return bytes(a|b for a,b in zip(result[:32],result[32:]))+bytes(32) if enemy_planes==1 else result
        clipper=driver.projected_masks if full_game else driver.clipped_masks
        clipped=b''.join(clipper(enemy_masks(index),clip)
                         for index in range(12) for clip in range(16))
        dot_patterns=b''.join(sprite_pattern(bytes(int(x<=px<x+2 and y<=py<y+2)
                            for py in range(16) for px in range(16)),shift)
                       for y in range(8) for x in range(8) for shift in (0,1))
        if len(clipped)!=12288 or len(dot_patterns)!=4096:raise ValueError('Enemy mask/radar bank layout changed')
        banks.append(clipped+dot_patterns)
        if enemy_count>1 and not cells_only:
            enemy_pair_bank=len(banks)+1
            for diagonal in range(2):
                patterns_pair=bytearray()
                for dy in range(16):
                    for dx in range(16):
                        if dx>=15 or dy>=14:
                            patterns_pair.extend(bytes(64))  # guarded, unreachable table entries
                            continue
                        dots=((0,dy),(dx,0)) if diagonal else ((0,0),(dx,dy))
                        mask=bytes(int(any(ax<=x<ax+2 and ay<=y<ay+2 for ax,ay in dots))
                                   for y in range(16) for x in range(16))
                        patterns_pair.extend(b''.join(sprite_pattern(mask,phase) for phase in (0,1)))
                if len(patterns_pair)!=16384:raise ValueError('Paired radar table layout changed')
                banks.append(bytes(patterns_pair))
    radar_cache_bank=0
    radar_sat_bank=0
    if cells_only:
        from .radar_cells import dirty_table,base_variants
        radar_cache_bank=len(banks)+1
        variants,offsets=base_variants(flags,border=radar_border,square=radar_square)
        (output/'radar-cell-flag-offsets.bin').write_bytes(offsets)
        table=dirty_table()+variants
        banks.append(table+bytes(16384-len(table)))
        radar_sat_bank=len(banks)+1
        coordinate_table=b''.join(sprite_attributes((scroll+11)&255,
            points=dict(player=[2,2],enemy=[2,2]),cells_only=True,separate_player=radar_player)[:hud_slots*4] for scroll in range(256))
        if len(coordinate_table)!=hud_slots*4*256:raise ValueError('Compact coordinate-table size changed')
        (output/'radar-coordinates.bin').write_bytes(coordinate_table)
        banks.append(coordinate_table+bytes(16384-len(coordinate_table)))
    player_road_bank=0
    if fast_player:
        from .player_blitter import road_tiles
        player_road_bank=len(banks)+1
        road=road_tiles(stage_world,0,flags=flag_records)
        (output/'player-road-tiles.bin').write_bytes(road)
        banks.extend((road[:16384],road[16384:]))
    tile_data_bank=0
    if tile_mode:
        tile_data_bank=len(banks)+1
        banks.append(tile_data['patterns']+tile_data['colors'])
        ids=tile_data['banks']
        (output/'tile-patterns.bin').write_bytes(tile_data['patterns'])
        (output/'tile-colors.bin').write_bytes(tile_data['colors'])
    id_bank=len(banks)+1
    banks.extend(ids)
    strip_info=None;strip_h_bank=strip_v_bank=0;strip_div3_addr=0
    if tile_strips:
        from .tile_strips import encode
        strips=encode(stage_world)
        if smoke_runtime:
            (output/'flower-vertical-sources.bin').write_bytes(strips['vertical']['table'][:6])
        strip_h_bank=len(banks)+1
        htable=bytearray(strips['horizontal']['table'])
        data_offset=0x1800
        hdata=strips['horizontal']['pixels'];vdata=strips['vertical']['pixels']
        div_offset=data_offset+len(hdata)+len(vdata)
        if div_offset+256>16384:
            raise ValueError('Strip graphics exceed spare horizontal-lookup bank space')
        htable[16384+data_offset:16384+data_offset+len(hdata)]=hdata
        voffset=data_offset+len(hdata)
        htable[16384+voffset:16384+voffset+len(vdata)]=vdata
        htable[16384+div_offset:16384+div_offset+256]=bytes(i//3 for i in range(256))
        strip_div3_addr=0x8000+div_offset
        banks.extend((bytes(htable[:16384]),bytes(htable[16384:])))
        strip_v_bank=len(banks)+1;banks.append(strips['vertical']['table'])
        init=[]
        for axis,offset in (('horizontal',data_offset),('vertical',voffset)):
            data=strips[axis];dest=data['vram']
            (output/f'strip-{axis}.bin').write_bytes(data['pixels'])
            init.extend((f'    ld a,{strip_h_bank+1}', '    ld ($7000),a',
                f'    vdp_write 14,{dest//16384}',f'    ld a,{dest%16384&255}',
                '    out ($99),a',f'    ld a,{64+(dest%16384>>8)}','    out ($99),a',
                f'    ld hl,${0x8000+offset:04x}',f'    ld de,{len(data["pixels"])}','    call upload'))
        init.extend(('    ld a,PLAYER_DATA_BANK','    ld ($7000),a','    ret'))
        (output/'strip-init.inc').write_text('\n'.join(init)+'\n')
        (output/'strip-div3.bin').write_bytes(bytes(i//3 for i in range(256)))
        strip_info=dict(horizontal_unique=strips['horizontal']['unique'],vertical_unique=strips['vertical']['unique'],
            vram_bytes=len(hdata)+len(vdata),horizontal_lookup_bank=strip_h_bank,vertical_lookup_bank=strip_v_bank,
            source_pixels_unchanged=True,maximum_tiles_per_command=3)
    if full_game:
        from .full_round_build import package,cold_source
        full_profile=package(root,output,banks,program,assets,palette,death_tiles,smoke_tiles)
        x,y=full_profile['sources']['empty'][:2]
        flag_row=(y-16)//8*32+x//8
        (output/'full-div3-small.bin').write_bytes(bytes(i//3 for i in range(32)))
        (output/'full-load.inc').write_text(cold_source(root))
    json_write(output/'stage-atlas.json',dict(tiles=atlas_count,vram=0x10800,id_bank=id_bank,
        bytes=len(atlas),rows=len(atlas)//128,
        world_tile_address_encoding=('source-xy-solid-tags' if solid_runs else 'source-xy') if source_xy else 'index8',
        world_address_banks=len(ids)))
    (output/'player-radar-x.bin').write_bytes(bytes(2+(i*8+4)*44//stage_one.WIDTH for i in range(102)))
    (output/'player-radar-y.bin').write_bytes(bytes(2+(i*8+4)*54//stage_one.HEIGHT for i in range(174)))
    (output/'hud-states.bin').write_bytes(b''.join(packed(state) for state in states))
    (output/'life.bin').write_bytes(life)
    (output/'life-digits.bin').write_bytes(digits)
    (output/'sprite-patterns.bin').write_bytes(patterns)
    (output/'radar-patterns.bin').write_bytes(radar.patterns(radar.bitmap([],border=radar_border,square=radar_square)))
    (output/'radar-enemies.bin').write_bytes(bytes(v for p in points for v in p['enemy']))
    (output/'hud-fuel-scale.bin').write_bytes(bytes(min(i,54)*30//54 for i in range(55 if stage>=12 else 256)))
    (output/'hud-project-x.bin').write_bytes(bytes(2+x*44//64 for x in range(64)))
    (output/'hud-project-y.bin').write_bytes(bytes(2+y*54//112 for y in range(112)))
    (output/'hud-demo-flags.bin').write_bytes(bytes(v for point in flags for v in point))
    (output/'hud-demo-digits.bin').write_bytes(bytes(int(c) for i in range(32) for c in f'{i*5000:06d}'))
    json_write(output/'radar.json', dict(x=radar.X, y=radar.Y, width=radar.WIDTH,
                                      height=radar.HEIGHT, scenes=points))
    white = index_for(palette, (222, 222, 222))
    red = index_for(palette, (255, 0, 0))
    sprite_colors = bytes([white | 0x20])*(16*12)
    if radar_player:sprite_colors=bytes([black|0x20])*16+sprite_colors
    if not cells_only:sprite_colors+=bytes([white|0x20])*16+bytes([red|0x20])*16
    sprite_colors += b''.join(bytes([c | 0x20])*16 for c in (white, yellow, yellow))
    if not player_blitter:sprite_colors += bytes([3|0x20])*16+bytes([9|0x60])*16
    if bitmap_radar:sprite_colors=sprite_colors[14*16:]
    if bitmap_radar:
        sprite_colors=bytes([white|0x20])*16+sprite_colors
        patterns=patterns[:116*8]+radar.point_patterns(0,0)+patterns[124*8:]
        (output/'sprite-patterns.bin').write_bytes(patterns)
    if enemy_render:
        sprite_colors+=(bytes([6|0x20])*16+(bytes([10|0x60])*16 if enemy_planes==2 else b''))*enemy_count
        if extra_radar:sprite_colors+=bytes([red|0x20])*16
    if bare_sat:sprite_colors=sprite_colors[15*16:]
    (output/'sprite-colors.bin').write_bytes(sprite_colors)
    if stage>=9:
        initial=patterns+radar.patterns(radar.bitmap([],border=radar_border,square=radar_square))
        data=bytearray(banks[hud_bank])
        if any(data[0x1800:0x1800+len(initial)]):raise ValueError('HUD initialization resources overlap')
        data[0x1800:0x1800+len(initial)]=initial
        banks[hud_bank]=bytes(data)
    (output/'sprite-attributes.bin').write_bytes(bytes([216]) if bare_sat else sprite_attributes(0, points=dict(player=[2,2],enemy=[2,2]),cells_only=cells_only,bitmap_radar=bitmap_radar,separate_player=radar_player))
    (output/'palette.bin').write_bytes(palette)
    radar_projection_bank=0
    if enemy_count>=3 or smoke_runtime:
        radar_projection_bank=len(banks)+1
        projection=(output/'stage-radar-x.bin').read_bytes()+(output/'stage-radar-y.bin').read_bytes()
        banks.append(projection+bytes(16384-len(projection)))
    session_image_bank=session_bank=0
    if stage>=12:
        from .session import resources
        session_image_bank=len(banks)+1;session_bank=session_image_bank+1
        first,second=resources(assets,black,white,full_game=full_game,root=root,palette=palette)
        banks.extend((first,second))
    if full_game:
        from .full_enemy import validate_extension_space
        validate_extension_space(banks[player_bank-1])
        if any(banks[hud_bank-1][0x3600:0x3f00]):
            raise ValueError('Compact HUD writer overlaps font-bank resources')
    terrain_bank=0
    if full_game:
        terrain_bank=len(banks)+1
        banks.append(bytes([255])*16384)
    for n, bank in enumerate(banks, 1):
        (output/f'bank-{n}.bin').write_bytes(bank)
    size = 16384*(1 << len(banks).bit_length())
    (output/'config.inc').write_text(
        ('    DEFINE HUD_ENEMY_METER 1\n' if enemy_render else '')+
        ('    DEFINE HUD_COLLECTION_METER 1\n' if stage>=4 else '')+
        ('    DEFINE HUD_SCORING_METER 1\n' if stage>=5 else '')+
        ('    DEFINE HUD_FUEL_METER 1\n' if stage>=6 else '')+
        f'TILE_MODE EQU {int(tile_mode)}\nTILE_DATA_BANK EQU {tile_data_bank}\nMAZE_R0 EQU {4 if tile_mode else 6}\nMAZE_R2 EQU {0x28 if tile_mode else 0x3f}\n'
        f'HUD_WORK_BASE EQU $c000\nHUD_API_BASE EQU $c300\nHUD_ENABLED EQU {int(hud_enabled)}\n'
        f'HUD_ALERTS EQU {int(stage>=12)}\nRADAR_SPECIAL_FLAG_OFFSET EQU {18 if full_game else next((f["hud_slot"]*2 for f in flag_records if f["kind"]==2),0)}\n'
        f'COMPLETION_COMPONENT EQU {int(completion_component)}\n'
        f'COMPLETION_RUNTIME EQU {int(stage>=11)}\n'
        f'SESSION_RUNTIME EQU {int(stage>=12)}\nSESSION_IMAGE_BANK EQU {session_image_bank}\nSESSION_BANK EQU {session_bank}\n'
        f'VDP_R9 EQU {video_timing(args.hz)["vdp_r9"]}\nBLACK EQU {black}\n'
        f'HUD_BANK EQU {hud_bank}\nHUD_DATA_BANK EQU {hud_bank+1}\nBODY_TOP EQU {BODY_TOP}\nLIFE_Y EQU {LIFE_Y}\n'
        f'PLAYER_BANK EQU {player_bank}\nPLAYER_DATA_BANK EQU {player_bank+1}\n'
        f'STAGE_ID_BANK EQU {id_bank}\nSTAGE_RADAR_BANK EQU {radar_projection_bank}\n'
        f'STAGE_ATLAS_TILES EQU {atlas_count}\nSTAGE_SOURCE_XY EQU {int(source_xy)}\nSTAGE_ATLAS_BYTES EQU {len(atlas)}\n'
        f'STAGE_BANKED_ATLAS EQU {int(stage>=8)}\nENEMY_COUNT EQU {enemy_count}\n'
        f'ENEMY_RENDER EQU {int(enemy_render)}\n'
        f'ENEMY_CONTACT EQU {int(enemy_contact)}\n'
        f'ENEMY_MASK_BANK EQU {enemy_mask_bank}\n'
        f'ENEMY_PAIR_BANK EQU {enemy_pair_bank}\nENEMY_PAIR_RADAR EQU {int(enemy_count>1 and enemy_render and not cells_only)}\n'
        f'RADAR_CELLS_ONLY EQU {int(cells_only)}\nRADAR_CACHE_BANK EQU {radar_cache_bank}\n'
        f'RADAR_PLAYER_SPRITE EQU {int(radar_player)}\nRADAR_MAP_SLOT EQU {int(radar_player)}\nRADAR_PLAYER_PATTERN EQU {240 if full_game else 180 if player_blitter else 232 if enemy_count>1 else 240}\n'
        f'RADAR_SAT_BANK EQU {radar_sat_bank}\n'
        f'PLAYER_BLITTER EQU {int(player_blitter)}\n'
        f'PLAYER_FAST_BLITTER EQU {int(fast_player)}\nPLAYER_ROAD_BANK EQU {player_road_bank}\n'
        f'RADAR_BLITTER EQU {int(bitmap_radar)}\n'
        f'SPRITE_FLICKER EQU {int(flicker)}\nFLICKER_SLOTS EQU {24 if hud_enabled else 23}\n'
        f'OUTLINE_FLICKER EQU {int(outline_flicker)}\n'
        f'FLICKER_STRESS EQU {int(flicker_stress)}\n'
        f'RADAR_BLUE EQU {index_for(palette,(0,0,151))}\n'
        f'RASTER_GUARD EQU {int(enemy_render or player_blitter or tile_mode)}\nStage_GuardClosed EQU ${0xc67c if full_game else 0xc5e8:04x}\n'
        f'STAGE_GUARD_LINE EQU {(202 if fast_player or smoke_runtime else 140 if tile_strips and hud_enabled and cells_only else 196 if bare_sat or simple_maze or tile_strips else 202) if stage>=9 else 196}\n'
        f'STAGE_SOLID_RUN_TILES EQU {8 if full_game or simple_maze else 4}\n'
        f'STAGE_SOLID_RUNS EQU {int(solid_runs)}\n'
        f'RADAR_MARKER_QUANTUM EQU {marker_quantum}\nSTAGE_TILE_STRIPS EQU {int(tile_strips)}\nSTRIP_H_BANK EQU {strip_h_bank}\nSTRIP_V_BANK EQU {strip_v_bank}\n'
        f'STRIP_DIV3_ADDR EQU ${strip_div3_addr:04x}\n'
        f'FLAG_ROW_X EQU {flag_row%32*8}\nFLAG_ROW_Y EQU {16+flag_row//32*8}\n'
        f'STAGE_CACHE_COLUMNS EQU {cache_columns}\nSTAGE_CACHE_GUARD EQU {cache_guard}\n'
        f'STAGE_CACHE_TOP_GUARD EQU 3\n'
        f'FULL_TERRAIN_BANK EQU {terrain_bank}\nINCREMENTAL_STAGE EQU {stage}\nFULL_GAME EQU {int(full_game)}\nROCK_COUNT EQU {len(rock_positions)}\n'
        f'SMOKE_RUNTIME EQU {int(smoke_runtime)}\n'
        f'DEATH_HOLD_TICKS EQU {death_ticks}\n'
        f'FLAG_EMPTY_X EQU {(empty_id%32)*8}\nFLAG_EMPTY_Y EQU {16+empty_id//32*8}\n'
        f'PLAYER_RATE EQU {clock["rate"]}\n'
        f'FULL_CLOCK_BASE EQU {clock.get("base_ticks_per_refresh",1)}\n'
        f'LIFE_X0 EQU {LIFE_X[0]}\nLIFE_X1 EQU {LIFE_X[1]}\nMASK_SPRITES EQU {len(MASK_ROWS)}\n'
        f'VIEWPORT_WIDTH EQU {VIEWPORT_WIDTH}\nVIEWPORT_HALF EQU {VIEWPORT_HALF}\n'
        f'HORIZONTAL_ADJUST EQU {HORIZONTAL_ADJUST}\nPLAYER_X EQU {PLAYER_X}\n'
        f'PLAYER_LABEL_X EQU {full_hud.PLAYER_LABEL_X if full_game else PLAYER_LABEL_X}\nSCORE_X EQU {full_hud.SCORE_FIELD_X if full_game else SCORE_X}\n'
        f'HIGH_X EQU {full_hud.HIGH_FIELD_X if full_game else 72}\nHUD_DIGITS EQU {8 if full_game else 6}\n'
        f'ROUND_X EQU {full_hud.ROUND_X}\nCREDIT_X EQU {full_hud.CREDIT_X}\n'
        f'FUEL_SLOT EQU {fuel_slot}\nPLAYER_SLOT EQU {player_slot}\n'
        f'HUD_STATIC_LIFE EQU {int(static_life)}\n'
        f'FUEL_COLORS EQU $f400+{fuel_slot}*16\nFUEL_ATTRIBUTES EQU $f600+{fuel_slot}*4\n'
        f'PLAYER_COLORS EQU $f400+12*16\n'
        f'SAT_BYTES EQU {hud_slots*4+1}\nPATTERN_BYTES EQU {len(patterns)}\n'
        f'SPRITE_COLOR_BYTES EQU {len(sprite_colors)}\nWHITE EQU {white}\nRED EQU {red}\n'
        f'RADAR_X EQU {radar.X}\nRADAR_Y EQU {radar.Y}\n'
        f'YELLOW EQU {yellow}\nFUEL_Y EQU {fuel_y}\nLIFE_SPLIT EQU {LIFE_SPLIT}\n')
    if full_game:
        from .enemy_navigation import original_maps
        (output/'full-navigation.bin').write_bytes(original_maps(program))
    (output/'payload.inc').write_text(''.join(
        (f'    INCBIN "bank-{n}.bin",0,$3600\n    DISP $b600\n    INCLUDE "full-hud-number.inc"\n    ASSERT $ <= $bf00\n    defs $bf00-$,$ff\n    ENT\n    INCBIN "bank-{n}.bin",$3f00,$100\n' if full_game and n==hud_bank else
         f'    INCBIN "bank-{n}.bin",0,$3800\n    DISP $b800\n    INCLUDE "session.inc"\n    ASSERT $ <= $c000\n    defs $c000-$,$ff\n    ENT\n' if n==session_bank else
         '    DISP $1000\nFull_CacheEngineStart:\n    INCLUDE "full-terrain-engine.inc"\nFull_CacheEngineEnd:\n    ENT\n    defs $1000-(Full_CacheEngineEnd-Full_CacheEngineStart),$ff\n    DISP $ea00\nFull_PresentStart:\n    INCLUDE "full-presentation.inc"\nFull_PresentEnd:\n    ASSERT $ <= $ec00\n    ENT\n    defs $1000-(Full_PresentEnd-Full_PresentStart),$ff\n    INCBIN "full-navigation.bin"\n' if full_game and n==terrain_bank else
         f'    INCBIN "bank-{n}.bin",0,$2800\n    INCLUDE "full-load.inc"\n    defs $400-(Full_LoadEnd-Full_LoadStart)-(Full_EnemyHotEnd-Full_EnemyHotStart)-(Full_RadarIRQEnd-Full_RadarIRQStart),$ff\n    DISP $ac00\n    INCLUDE "round-objects.inc"\n    ASSERT $ <= $ae00\n    defs $ae00-$,$ff\n    ENT\n    DISP $ae00\n    INCLUDE "full-round-native.inc"\n    ASSERT $ <= $b000\n    defs $b000-$,$ff\n    ENT\n    INCBIN "bank-{n}.bin",$3000,$500\n    DISP $b500\n    INCLUDE "full-native-motion.inc"\n    ASSERT $ <= $b600\n    defs $b600-$,$ff\n    ENT\n    DISP $b600\n    INCLUDE "full-native-ai.inc"\n    ASSERT $ <= $bf00\n    defs $bf00-$,$ff\n    ENT\n    INCBIN "bank-{n}.bin",$3f00,$100\n' if full_game and n==player_bank else
         f'    INCBIN "bank-{n}.bin",0,$2c00\n    DISP $ac00\n    INCLUDE "round-objects.inc"\n    ASSERT $ <= $ae00\n    defs $ae00-$,$ff\n    ENT\n    INCBIN "bank-{n}.bin",$2e00,$1200\n' if round_preparation and n==player_bank else
         f'    INCBIN "bank-{n}.bin"\n') for n in range(1, len(banks)+1))
                                      + f'    defs {size}-$+16384,$ff\n')
    with (output/'config.inc').open('a') as config:
        config.write(f'STAGE_WIDTH EQU {stage_one.WIDTH}\n'
            f'STAGE_HEIGHT EQU {stage_one.HEIGHT}\nSTAGE_COLUMNS EQU {stage_one.TILE_COLUMNS}\n'
            f'STAGE_ROWS EQU {stage_one.TILE_ROWS}\n')
    shutil.copyfile(root/'src/stage-one-stream.inc', output/'stage-one-stream.inc')
    if round_preparation:
        shutil.copyfile(root/'src/round-objects.inc', output/'round-objects.inc')
    if full_game:
        for name in ('full-radar-motion.inc','full-hud-number.inc','full-round-native.inc','full-msx-enemies.inc','full-presentation.inc','full-sprite-cache.inc','full-main.inc','full-native-ai.inc','full-native-motion.inc','full-wide-native.inc','full-enemy-far-native.inc','full-terrain-cache.inc','full-terrain-engine.inc','full-wide-strips.inc','full-round-runtime.inc'):
            shutil.copyfile(root/'src'/name,output/name)
    shutil.copyfile(root/'src/player.inc',output/'player.inc')
    if smoke_runtime:shutil.copyfile(root/'src/smoke.inc',output/'smoke.inc')
    if completion_component:shutil.copyfile(root/'src/completion.inc',output/'completion.inc')
    if stage>=12:
        for name in ('session.inc','session-loader.inc','full-session.inc'):shutil.copyfile(root/'src'/name,output/name)
    if player_blitter or bitmap_radar:shutil.copyfile(root/'src/bitmap-player.inc',output/'bitmap-player.inc')
    if bitmap_radar:shutil.copyfile(root/'src/bitmap-radar.inc',output/'bitmap-radar.inc')
    if flicker:shutil.copyfile(root/'src/sprite-flicker.inc',output/'sprite-flicker.inc')
    if outline_flicker:shutil.copyfile(root/'src/outline-flicker.inc',output/'outline-flicker.inc')
    if tile_mode:shutil.copyfile(root/'src/tilemap.inc',output/'tilemap.inc')
    if stage>=9:shutil.copyfile(root/'src/sprite-upload.inc',output/'sprite-upload.inc')
    shutil.copyfile(root/'src/rock-collision.inc',output/'rock-collision.inc')
    shutil.copyfile(root/'src/death.inc',output/'death.inc')
    shutil.copyfile(root/'src/flags.inc',output/'flags.inc')
    shutil.copyfile(root/'src/score.inc',output/'score.inc')
    shutil.copyfile(root/'src/fuel.inc',output/'fuel.inc')
    shutil.copyfile(root/'src/lives.inc',output/'lives.inc')
    if tile_strips:shutil.copyfile(root/'src/tile-strips.inc',output/'tile-strips.inc')
    from .enemy_population import assembly as enemy_assembly
    if full_game:
        from .full_enemy import assembly as full_enemy_assembly,registration_table
        (output/'full-registration.bin').write_bytes(registration_table())
        resident,native_prepare=full_enemy_assembly((root/'src/enemy.inc').read_text())
        (output/'enemy.inc').write_text(resident)
        (output/'full-enemy-prepare.inc').write_text(native_prepare)
        shutil.copyfile(root/'src/full-enemy-loop.inc',output/'full-enemy-loop.inc')
    else:
        (output/'enemy.inc').write_text(enemy_assembly((root/'src/enemy.inc').read_text(),enemy_count,enemy_planes,compact=cells_only,player_slot=player_slot,radar_player=radar_player and not player_blitter,player_blitter=player_blitter)
                                  if enemy_render else (root/'src/enemy.inc').read_text())
    if cells_only:shutil.copyfile(root/'src/radar-cells.inc',output/'radar-cells.inc')
    if enemy_count>1 and enemy_render and not cells_only:
        shutil.copyfile(root/'src/enemy-radar-pair.inc',output/'enemy-radar-pair.inc')
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
    memory_layout=None
    if full_game:
        from .full_memory import layout
        from .hud_verify import symbols
        memory_layout=layout(symbols(output/'raster-scroll.sym'))
        json_write(output/'full-memory.json',memory_layout)
    json_write(output/'build.json', dict(schema_version=1, experiment='full-screen-hardware-raster',
        step_pixels=1, strip_border_flowers=False, timing=video_timing(args.hz),
        incremental_stage=stage, hud_enabled=hud_enabled, full_arcade_loop=False,
        native_clock=(dict(clock,basis='Elapsed physical VBlank counter',maximum_ticks_per_loop=3,
            maximum_pending_ticks=12,maximum_elapsed_refreshes=8) if full_game else clock),
        hardware_cpu_clock=(dict(controller='Factory Panasonic switched device 8, port 0x41',
            detection='ID complement 0xF7 and turbo-available bit2 clear',
            pure_cpu_hz=5369318,vdp_io_hz=3579545,
            fallback='Unsupported machines retain their standard CPU clock',
            emulator='z80_freq_locked true follows machine-selected frequency; false overrides it') if full_game else None),
        terrain_ownership=(dict(mapper_code=[0x1000,0x2000],tile_tags=[0x2000,0x3000],
            segment='Page3 segment XOR 1, temporarily mapped into page0',
            cell_prefetch_pixels=[24,24],source_pixels_unchanged=True,
            viewport_gate='Every newly exposed row/column must own its exact world coordinates',
            native_smoke_rows=[0xd160,0xd180],
            vertical_presentation=dict(maximum_pixels_per_packet=8,latched_scroll=0xd2cc,
                frame_origin_addresses=[0xe3f2,0xe3f4],
                policy='Independent ownership-checked axes, at most eight pixels from this packet origin',
                player_sat='Complete pair published by the maze IRQ against its actual R23',
                initialized=0xd2cd,ownership='Both planned and latched views, including mixed corner columns')) if full_game else None),
        full_game=full_game,full_memory=memory_layout,
        full_hud_layout=(dict(header_left=full_hud.HEADER_LEFT,visible_score_digits=7,native_score_digits=8,
            source_sha256={p:digest(root/p) for p in ('scripts/msx/full_hud.py','src/full-hud-number.inc')},
            score_policy='Lowest seven native digits; scoring and record state unchanged',
            high_digits_x=full_hud.HIGH_FIELD_X+8,score_digits_x=full_hud.SCORE_FIELD_X+8,
            player_label_x=full_hud.PLAYER_LABEL_X,round_x=full_hud.ROUND_X,
            round_digits=2,round_overflow='16x8 infinity symbol above 99',
            credit_x=full_hud.CREDIT_X,credit_digits=1,credit_display_maximum=9) if full_game else None),
        session=(dict(state_address=0xc7d0,credits_address=0xc7d2,ready_address=0xc7dd,image_bank=session_image_bank,code_bank=session_bank,keys='5 credit, 1 one-player start'+(', 2 two-player start' if full_game else '')+'; arrows/joystick1 steering, Space/Ctrl/triggerA smoke, P pause, Home reset'+('; F5 advance one round (debug)' if full_game else ''),
            debug_advance=(dict(key='F5',row=7,mask=2,held_address=0xdfcb,
                behavior='One original next-round preparation per press; unpause, keep score/lives/credits, no completion award; human gameplay only') if full_game else None),
            direction_gate='Four-way, newest direction edge wins; simultaneous edges choose one direction',
            direction_state_addresses=[0xc7de,0xc7df],
            wall_protection=dict(rollover_refreshes=8,counter_address=0xc7e6,snapshot_address=0xd200,
                signed_corner_threshold=8,
                scope='After multi-key input or near an inside corner, reject a wall-center position while retaining steering, fuel, score, enemies and native clocks'),
            initial_state=1,game_over_state=2,completed_state=3,high_score_preserved=True,
            source_sha256={p:digest(root/p) for p in ('src/session.inc','src/session-loader.inc','scripts/msx/session.py')},
            source_font_scale='1:1 original 8x8',next_round_enabled=full_game,
            player_capacity=2 if full_game else 1,attract_demo=full_game,
            attract_wait_refreshes=900 if full_game else None) if stage>=12 else None),
        cache_backpressure=(dict(held_refresh_counter=0xc71d,vertical_debt_tiles=None if full_game else 2,
            horizontal_debt_tiles=None if full_game else cache_guard-1,
            scope=('Hold the camera/native advance only for an incomplete newly exposed edge; retain bounded elapsed-time debt' if full_game else 'Hold all native simulation clocks for one refresh while hidden cache jobs recover; preserve original pixels and rules')) if smoke_runtime else None),
        completion_component=(dict(runtime_enabled=stage>=11,source_entry=0x1fa9,
            source_sha256=digest(root/'src/completion.inc'),scope='Original remaining-fuel conversion, normal/challenge progression and session transitions' if full_game else 'Initial normal round, original remaining-fuel conversion and explicit session transitions' if stage>=12 else 'Initial normal-round remaining-fuel conversion and explicit stopped segment; credit/start/game-over presentation pending' if stage>=11 else 'Isolated remaining-fuel converter; round completion and start/game-over not yet integrated') if completion_component else None),
        parameter_component=(dict(runtime_enabled=stage>=11,source_entry=0x1b1f,
            table_pointer=int.from_bytes((native/'video.bin').read_bytes()[0x2d2:0x2d4],'little')+0x8000,
            round_limit=(native/'video.bin').read_bytes()[0x2d8],
            scope='Original initial/post-flag/per-life parameter dispatch' if stage>=11 else 'Isolated original post-flag movement/population parameter dispatch; runtime not enabled') if completion_component else None),
        round_completion=(dict(state_address=0xc724,settle_ticks=61,
            final_state=3,next_round_enabled=full_game,credit_start_enabled=stage>=12,
            scope='Original fuel award and dynamic normal/challenge rounds' if full_game else 'Original remaining-fuel award; initial-round session screens' if stage>=12 else 'Original remaining-fuel award, explicit stopped initial-round segment; menu/credit/start pending') if stage>=11 else None),
        smoke_component=(dict(runtime_enabled=smoke_runtime,activation=0x0f64,expiry=0x0185,
            source_sha256={p:digest(root/p) for p in ('src/smoke.inc','scripts/msx/smoke.py','scripts/msx/player.py')},
            keyboard='Ctrl, active-low original input bit 1' if smoke_runtime else None,
            additional_sprite_slots=0,
            code_buffer=0xe400,attribute_buffer=0xec00,
            published_state_address=0xd300 if smoke_runtime else None,
            publication_counts_address=0xdb00 if smoke_runtime else None,
            scope='Selected original smoke rules with bounded bitmap adapter' if smoke_runtime else 'Linked selected original logic for isolated proof; keyboard smoke and bitmap publication not yet integrated') if smoke_component else None),
        allow_sprite_overflow=bool(stage>=9 and not flicker and not player_blitter and not bitmap_radar),
        scenery_style=scenery_style,
        tile_strips=strip_info,
        player_blitter=player_blitter,
        player_fast_blitter=fast_player,player_road_bank=player_road_bank,
        flag_display_state_address=0xc534 if fast_player or smoke_runtime else None,
        flag_presentation_latency_refreshes=1 if fast_player or smoke_runtime else 0,
        radar_blitter=bitmap_radar,
        outline_flicker=outline_flicker,
        outline_body_adaptation='One majority original body color per row; original black ink independent, no CC' if outline_flicker else None,
        sprite_flicker=(dict(mode='Independent body-first cars; alternate outlines/radar' if outline_flicker else 'Alternate canonical priority / two complete enemy pairs in radar slots6..9, displaced cells in slots19..22',
                            phases=4 if outline_flicker else 2,phase_address=0xc7ca if outline_flicker else 0xc7c0,source_sha256=digest(root/'src/sprite-flicker.inc'),
                            front_table_address=0xc7c1 if outline_flicker else None,
                            table_offsets=[0,0x800] if outline_flicker else None,
                            stationary_stress_fixture=flicker_stress,
                            hardware_sprite_limit_enabled=True,allocation_unchanged=True,
                            scope='Priority rotation experiment; overloaded scanlines intentionally lose lower-priority pixels') if flicker else None),
        hud_style=dict(header_background=header_background,radar_border=False if bitmap_radar else radar_border,radar_square=radar_square,radar_background='blue' if bitmap_radar else 'transparent',additional_sprite_slots=0,
                       life_outline=not static_life,static_fuel_life_colors=static_life,
                       fuel_low_threshold_units=6 if stage>=12 else None,
                       fuel_color_state_address=0xc39b if stage>=12 else None,
                       fuel_publication=dict(payload_address=0xd180,ready_address=0xc39d,
                            byte_count=128,phase='VBlank',maximum_ready_latency_refreshes=1) if stage>=12 else None,
                       radar_special_flag_blink_ticks=32 if stage>=12 else None,
                       radar_special_flag_slot=next((f['hud_slot'] for f in flag_records if f['kind']==2),None) if stage>=12 else None,
                       header_irq_reservation_line=0 if full_game else 1 if stage>=12 else 3 if stage>=9 else 7,
                       score_digits=8 if full_game else 6,round_digits=3 if full_game else 0,
                       radar_bitmap_size=[48,80] if bitmap_radar else None,
                       radar_background_index=index_for(palette,(0,0,151)) if bitmap_radar else None,
                       radar_marker_state_address=0xcf60 if cells_only and hud_enabled else None,
                       radar_flag_state_address=0xcfa8 if cells_only and hud_enabled else None,
                       radar_dirty_state_address=0xcf08 if cells_only and hud_enabled else None,
                       radar_ready_state_address=0xcf12 if cells_only and hud_enabled else None,
                       radar_cells_per_refresh=1 if cells_only else None,
                       coordinates_direct_rom=bool(cells_only),
                       radar_presentation_latency_refreshes=1 if cells_only else None,
                       radar_upload_after_line=80 if cells_only and hud_enabled else None,
                       radar_pending_refresh_limit=16 if cells_only else None,
                       radar_coordinate_lookup_bank=radar_sat_bank if cells_only else None,
                       radar_marker_quantum=marker_quantum,
                       radar_player_sprite=bool(radar_player or bitmap_radar),radar_player_slot=0 if radar_player or bitmap_radar else None,
                       radar_player_pattern=240 if full_game else 116 if bitmap_radar else 180 if player_blitter else 232 if enemy_count>1 else 240,
                       radar_player_blink_ticks=8 if radar_player or bitmap_radar else None,
                       radar_player_blink_colors=['white','black'] if radar_player or bitmap_radar else None,
                       radar_bitmap_copy='HMMM even/odd phases; exact one-pixel edge repair, save-under' if bitmap_radar else None,
                       radar_map_first_slot=None if bitmap_radar else int(radar_player),
                       radar_cells_only=cells_only,radar_row_recoloring='Red enemies recolor white flags/frame on affected sprite rows; independent player alternates white/black above the map' if radar_player else 'Black player overrides red enemies overrides white flags/frame on affected sprite rows' if cells_only else None),
        tile_mode=(dict(mode='SCREEN 4',tiles=tile_data['tiles'],changed_pixels=tile_data['changed_pixels'],
                        total_pixels=len(stage_world),source_world_sha256=tile_data['source_world_sha256'],
                        patterns_vram=0,colors_vram=0x4000,name_tables_vram=[0x2000,0xa000],
                        sprite_slots_added=0,dimensions_unchanged=True) if tile_mode else None),
        enemy_count=enemy_count,enemy_rendered=enemy_render,enemy_contact_applies_death=enemy_contact,atlas_banked=stage>=8,
        full_enemy_presentation=(dict(records=0xce20,record_bytes=32,capacity=7,
            edge_projection='zero-EC shifted exact negative-X masks',
            shared_mask_cache=dict(slots=12,maximum_front_replacements=2,unused_slot_preload=True),
            access='Direct IX-indexed records; no shared actor scratch copies',
            sat='Visible complete pairs in original actor order, one trailing terminator',
            unchanged_attributes='Skip only identical attributes at the same destination',
            source_registration='World viewport for all seven descriptors; seven independent radar anchors',
            publication='Complete deferred mask/color/SAT packet no sooner than two VBlanks; late packets may shift phase, with one coherent scroll snapshot',
            radar_coordinates='Maze IRQ after R23 latch; player dot, twelve body sprites, three shared fuel slots and the complete player pair',
            actor_cpu_clock='Factory turbo for pure descriptor/cache/RAM work; base clock for ordinary VDP transfers',
            hardware_sprite_limit_enabled=True) if full_game else None),
        rock_collision=stage>=2, rock_sprite_slots=0,
        cache_columns=cache_columns,cache_horizontal_guard_tiles=cache_guard,
        cache_solid_runs=solid_runs,
        cache_solid_run_tiles=8 if full_game or simple_maze else 4,
        radar_work_phase='adaptive post-cache tail (140/196), next-refresh publication' if tile_strips and hud_enabled and cells_only and not smoke_runtime else None,
        gameplay_systems=['player movement', 'steering', 'wall collision', 'player animation']+
                         (['static original rock bitmap fixture'] if rock_positions else [])+
                         (['rock contact events'] if stage >= 2 else [])+
                         (['bitmap explosion and logical death hold'] if stage >= 3 else [])+
                         (['persistent flag collection'] if stage>=4 else [])+
                         (['original flag points, digit carry and high score'] if stage>=5 else [])+
                         (['original decimal fuel consumption, empty deceleration and bounded lucky conversion'] if stage>=6 else [])+
                         (['original single-player life loss, same-round restart and stopped zero-life run'] if stage>=7 else [])+
                         (['original enemy initialization/fractional kinematics/facing; MSX 30 Hz pursuit/motion and 60 Hz world contact'] if full_game else ['selected original enemy initialization, motion, facing, AI and virtual visibility'] if enemy_count else [])+
                         (['original enemy silhouettes and live radar' if enemy_planes==1 else 'exact enemy sprite masks and live radar'] if enemy_render else [])+
                         (['original enemy contact through explosion/lives'] if enemy_contact else [])+
                         (['original keyboard smoke, fuel charge, bitmap clouds and enemy stun/recovery'] if smoke_runtime else [])+
                         (['original post-flag difficulty and remaining-fuel completion bonus'] if stage>=11 else [])+
                         (['four original dynamic maps and original flag/rock placements','normal/challenge progression','alternating two-player boards','original cast and autonomous attract demonstration'] if full_game else []),
        msx_enemy_navigation=(dict(entry=0xb600,source_sha256=digest(root/'src/full-msx-enemies.inc'),
            decisions='New cell centres only; reciprocal wall exits, actor-dependent axis priority, no reverse outside dead ends',
            motion_hz=1/(2*video_timing(args.hz)['frame_seconds']) if args.hz==60 else None,
            motion_divisor=2,player_motion_divisor=2,player_speed_cap_pixels=2,enemy_speed_cap_pixels=1.875,
            continuous='Player/enemy fractional movement and spatial queries every other native tick with doubled delta; original lower near/far speeds; smoke immunity in native tick units; timers and startup/spin recovery every native tick',
            navigation_mapper=[0x3000,0x3700],decision_cells=[0xd2a8,0xd2b6],
            contact='Inclusive ten-pixel world rectangle; normal startup actors use fourteen pixels for the complete silhouette. Challenge remains ten; signed fine offsets may span two coarse cells; all seven actors, no virtual OAM dependency') if full_game else None),
        full_presentation_timing=(dict(target_hz=1/(2*video_timing(args.hz)['frame_seconds']),
            publication_clock=dict(minimum_refreshes=2,last_tick_address=0xdfcc,
                valid_address=0xdfcd,first_packet='Odd VBlank; late packets may shift phase'),
            logic_hz=1/video_timing(args.hz)['frame_seconds'] if args.hz==60 else 1/.0165,
            scope='User-approved stable half-refresh presentation; original art/HUD and real sprite limits retained',
            packet_mapper=[0,0x384],code=[0xea00,0xec00],
            readiness='After visible repairs and complete car preparation; score and bitmap HUD maintenance follow',
            interrupt_mapping='VBlank preserves actual interrupted Page0 primary/secondary slot and mapper segment',
            prefetch='Bounded foreground work plus hidden copies during idle body intervals; exact contiguous cell fragments at physical seams') if full_game else None),
        death=(dict(hold_ticks=death_ticks,anchor_bias=[-9,-8],width=24,height=24,
                    display_state_address=0xc49a if stage>=9 else 0xc490,
                    presentation_latency_refreshes=1 if stage>=9 else 0,
                    sprite_slots=0,manifest_sha256=digest(death_reference/'manifest.json'),
                    completion=('same-round restart or stopped zero-life run; final hold 96 ticks' if stage>=7 else
                                'restore terrain and wait for diagnostic Home; lives/restart deferred to stage 07'))
               if death_reference else None),
        hud_values=(('live score/high score/fuel/lives and player/flag radar; enemy fixture' if stage>=7 else
                     'live score/high score/fuel and player/flag radar; life/enemy fixtures' if stage>=6 else
                     'live score/high score and player/flag radar; fuel/life/enemy fixtures' if stage>=5 else
                     'live player/flag radar; score/fuel/life/enemy fixtures' if stage>=4 else 'diagnostic fixtures')
                    if hud_enabled else 'disabled'),
        scoring=(dict(adapter='Exact hundred-point carry groups; original high-score/bonus-life checks at reachable boundaries',
                      original_increment=0x2119,original_checks=0x2064,lucky_fuel_conversion='bounded tick adapter' if stage>=6 else 'pending stage 06',
                      publication='After dirty terrain; scoring reserves remaining guard work for that refresh') if stage>=5 else None),
        geometry=dict(width=256, height=212, header_height=HUD_HEIGHT, separator=[8, BODY_TOP],
                      maze=[LEFT_MASK, BODY_TOP, 256-RIGHT_MASK, 212], left_mask=LEFT_MASK,
                      right_mask=RIGHT_MASK, header=[LEFT_MASK, 0, 256, HUD_HEIGHT],
                      horizontal_adjust=HORIZONTAL_ADJUST, display_shift=DISPLAY_SHIFT,
                      framed_maze=[4, BODY_TOP, 252, 212]),
        sprites=dict(size=[16, 16], life_y=LIFE_Y, life_x=list(LIFE_X), layers_per_life=1 if static_life else 2,
                     player_forbidden_y_bias=-1 if (stage>=9 or tile_mode) and not player_blitter else 0,
                     life_size=[16,16], life_magnification=1, life_split=LIFE_SPLIT,
                     life_counter_slots=0 if bare_sat else 2 if static_life else 3, life_reuses_fuel_slots=[] if bare_sat else list(range(fuel_slot,fuel_slot+3)),
                     maximum_lives=9, margin_slots=0, radar_slots=1 if bitmap_radar else 0 if bare_sat else 12+radar_player+extra_radar if cells_only else 14+extra_radar,
                     hud_slots=hud_slots+extra_radar,
                     player_slots=0 if player_blitter else 2, player_first_slot=player_slot,enemy_slots=enemy_planes*enemy_count if enemy_render else 0,
                     extra_enemy_radar_slots=extra_radar,
                     total_slots=base_slots-2*player_blitter+enemy_planes*enemy_count*enemy_render+extra_radar,
                     free_slots=32-base_slots+2*player_blitter-enemy_planes*enemy_count*enemy_render-extra_radar,
                     black=black, yellow=yellow, white=white, red=red), colors=colors, size=size,
        scenes=[dict(number=s['number'], world_origin=stage_one.LANDMARKS[i])
                for i,s in enumerate(scenes)],
        inputs=dict(assets=digest(args.assets/'manifest.json'),
                    rock_fixture=digest(rock_reference/'manifest.json') if rock_reference else None,
                    captures=[digest(s['path']/'manifest.json') for s in scenes],
                    hud=[digest(p/'manifest.json') for p in (args.normal, args.overlap)]),
        source_sha256={p:digest(root/p) for p in ('src/raster-scroll.asm', 'scripts/msx/raster_scroll.py',
                       'scripts/msx/inputs.py', 'scripts/msx/display.py', 'scripts/msx/sprite_radar.py', 'scripts/msx/player.py','src/player.inc',
                       'scripts/msx/sprite_fuel.py', 'scripts/msx/sprite_lives.py',
                       'src/stage-one-stream.inc', 'src/hud.inc', 'src/hud-api.inc', 'src/hud-demo.inc', 'src/hud-native.inc', 'src/hud-state.inc', 'src/hud-assets.inc', 'src/hud-raster.inc', 'scripts/msx/stage_one.py',
                       'scripts/msx/stage_one_capture.lua')}, rom_sha256=digest(rom),
        rock_source_sha256={p:digest(root/p) for p in ('scripts/msx/rocks.py','scripts/msx/rocks_capture.lua','src/rock-collision.inc')} if stage >= 1 else None,
        death_source_sha256={p:digest(root/p) for p in ('scripts/msx/death.py','scripts/msx/death_capture.lua','src/death.inc')} if stage>=3 else None,
        flag_source_sha256={p:digest(root/p) for p in ('scripts/msx/flags.py','src/flags.inc')} if stage>=4 else None,
        score_source_sha256={p:digest(root/p) for p in ('src/score.inc',)} if stage>=5 else None,
        fuel_rules=(dict(source_sha256=digest(root/'src/fuel.inc'),consumption=0x1ecc,decrement=0x1f13,
                         empty_deceleration=0x0482,clock='Fresh counter zero; consume before increment each 16.5 ms logical tick',
                         lucky='Original round-dependent HALT/chunk cadence; saved fuel restored; last flag excluded',
                         scope='Selected original logic without full arcade IRQ/foreground; original post-flag parameter dispatch active' if stage>=11 else 'No full arcade IRQ or foreground; post-flag difficulty parameter update deferred') if stage>=6 else None),
        life_rules=(dict(source_sha256=digest(root/'src/lives.inc'),decrement=0x18da,refill_prefix=0x08e7,
                         nonfinal_ticks=120,final_ticks=96,hud='Remaining count minus current car, presentation cap nine',
                         persistence='Score, high score, award bits and collected flags retained; current-life flag ordinal resets',
                         restart='Bounded scene reload, fresh active fuel clock; explicit game-over session screen' if stage>=12 else 'Bounded scene reload, fresh active fuel clock; game-over presentation pending') if stage>=7 else None),
        enemy_logic=(dict(source_sha256=digest(root/'src/enemy.inc'),count=enemy_count,ai=0xb600 if full_game else 0x0cd6,
                         initializer=0x0ab5,virtual_slots=6,registration=None if full_game else 0x15bd,contact=0xb603 if full_game else 0x038a,
                         rendered=enemy_render,contact_applied=enemy_contact,
                         sprite_planes=enemy_planes,
                         paired_radar=enemy_count>1 and enemy_render and not cells_only,
                         generator_sha256=digest(root/('scripts/msx/full_enemy.py' if full_game else 'scripts/msx/enemy_population.py')) if enemy_count>1 else None,
                         radar_pair_source_sha256=digest(root/'src/enemy-radar-pair.inc') if enemy_count>1 and enemy_render and not cells_only else None,
                         color_adaptation='One red silhouette retaining every opaque source pixel' if enemy_planes==1 else None,
                         palette=dict(body=6,window=10,black=14) if enemy_render else None,
                         sentinel_bias='One presentation pixel upward only at forbidden SAT Y=216' if enemy_render else None,
                         guard_deadline_scanline=(202 if full_game else 204 if stage>=9 else 196) if enemy_render else None,
                         sprite_body_top=12 if enemy_render else None,
                         score_publication=('After actor/camera packet readiness' if full_game else 'Pending flag score retained across a two-tick driving refresh or after footer; paused/dead states can drain') if enemy_render else None,
                         scope='Original initialization and fractional integrator; authored MSX pursuit/contact, half-rate enemy movement and complete exact masks' if full_game else 'Selected original routines; exact masks/visibility with declared MSX presentation adapter' if enemy_render else
                         'Logic-only diagnostic; car rendering and applying contact to death not enabled') if enemy_count else None),
        fuel=dict(rectangle=[fuel.X, fuel_y, fuel.X+fuel.WIDTH, fuel_y+fuel.HEIGHT],
                  slots=[] if bare_sat else list(range(fuel_slot,fuel_slot+3)), levels=list(fuel.LEVELS)),
        scope='Incremental selected-original gameplay; enabled systems listed explicitly; full arcade foreground/IRQ absent'))
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])
    seal(output)
    print(f'{size} bytes, {len(banks)+1} banks: {rom}')
    return rom
