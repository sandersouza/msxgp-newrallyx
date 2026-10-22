"""Read-only native scene translation and independent indexed-pixel oracle."""
from PIL import Image

from .hud_contract import native_values
from .native_contract import Snapshot


def radar_from_snapshot(snapshot: Snapshot) -> dict:
    """Read the original nine dot outputs and ten remaining collision flags.

    Coordinates stay in the arcade radar's 64x112 local space. Invalid/unready
    pointers and inactive dot slots are hidden; this never creates game state.
    """
    if not isinstance(snapshot, Snapshot):
        raise ValueError('A complete native snapshot is required')
    video, work, shadow = snapshot.video, snapshot.work, snapshot.shadows
    dots = []
    for offset in range(0x14, 0x1d):
        x = video[0x20+offset] + ((~shadow[offset & 15] & 1) << 8)-224
        y = 157-video[0x820+offset]
        dots.append((x, y) if 0 <= x < 64 and 0 <= y < 112 else None)
    table = int.from_bytes(video[0x992:0x994], 'little')
    flags = []
    for index in range(10):
        at = table-0x8000+2*index
        address = int.from_bytes(video[at:at+2], 'little') if 0x8000 <= table <= 0x8fec else 0
        cell = address-0x9800
        flags.append(((cell & 31)*2, (cell//32)*2)
                     if 0 <= cell < 0x700 and work[cell] in (1, 2, 4) else None)
    return dict(player=dots[0], enemies=tuple(dots[1:]), flags=tuple(flags))


def project_radar(point):
    return (255, 255) if point is None else (2+point[0]*44//64, 2+point[1]*54//112)


def radar_bitmap(snapshot):
    sx, sy = snapshot.shadows[0x130], snapshot.shadows[0x140]
    dots = [((sx+197+x) & 255, (sy+31+y) & 255)
            for point in radar_from_snapshot(snapshot)['enemies'] if point is not None
            for x, y in [project_radar(point)]]
    return ((sx+197) & 254, (sy+31) & 255), dots


def verify_radar_cache(snapshot, vram, page):
    if (not isinstance(snapshot, Snapshot) or len(vram) != 131072
            or type(page) is not int or page not in (0, 1)):
        raise ValueError('Incomplete native radar evidence')
    (ox, oy), dots = radar_bitmap(snapshot)
    differences, first = 0, None
    for y in range(60):
        wy = (oy+y) & 255
        for x in range(50):
            wx = (ox+x) & 255
            wanted = 13 if any((wx-dx) & 255 < 2 and (wy-dy) & 255 < 2 for dx, dy in dots) else 11
            byte = vram[page*32768+wy*128+wx//2]
            actual = (byte >> (0 if wx & 1 else 4)) & 15
            if actual != wanted and {actual, wanted} != {0, 11}:
                differences += 1
                if first is None:
                    first = dict(x=x, y=y, expected=wanted, actual=actual)
    return dict(compared_pixels=3000, different_pixels=differences, first_difference=first)


def scene_from_snapshot(snapshot: Snapshot) -> dict:
    if not isinstance(snapshot, Snapshot):
        raise ValueError('A complete native snapshot is required')
    video, shadows = snapshot.video, snapshot.shadows
    sx, sy = shadows[0x130], shadows[0x140]
    actors = []
    for offset in range(0x1e, 0x13, -2):
        flags, attr = video[offset], video[0x801+offset]
        x = video[offset+1] + ((attr & 0x80) << 1)
        y = 225 - video[0x800+offset]
        actors.append(dict(id=offset, code=flags >> 2, palette=attr & 63,
                           screen_bounds=(x-12, y-6, x+4, y+10),
                           bounds=(x+sx-3, y+sy+16, x+sx+13, y+sy+32),
                           flip_x=bool(flags & 1), flip_y=bool(flags & 2)))
    return dict(tick=snapshot.tick, camera=((sx+9) & 255, (sy+22) & 255),
                flip=bool(shadows[0x183] & 1), actors=tuple(actors),
                hud=native_values(video), tile_codes=video[0x400:0x800],
                tile_attributes=video[0xc00:0x1000],
                foreground_codes=video[:0x400], foreground_attributes=video[0x800:0xc00],
                radar_attributes=shadows[:16])


def _rect(rect):
    if (not isinstance(rect, tuple) or len(rect) != 4
            or any(type(v) is not int for v in rect) or rect[0] >= rect[2] or rect[1] >= rect[3]):
        raise ValueError('Rectangles must have integer, positive half-open bounds')
    return rect


def dirty_regions(previous, current, viewport):
    """Union touching old/new bounds; never discard covered restoration pixels."""
    vx, vy, vx1, vy1 = _rect(viewport)
    result = []
    for rect in previous + current:
        x, y, x1, y1 = _rect(rect)
        candidate = (max(x, vx), max(y, vy), min(x1, vx1), min(y1, vy1))
        if candidate[0] >= candidate[2] or candidate[1] >= candidate[3]:
            continue
        pending = result
        result = []
        while pending:
            old = pending.pop()
            if (candidate[0] <= old[2] and old[0] <= candidate[2]
                    and candidate[1] <= old[3] and old[1] <= candidate[3]):
                candidate = (min(candidate[0], old[0]), min(candidate[1], old[1]),
                             max(candidate[2], old[2]), max(candidate[3], old[3]))
                pending += result
                result = []
            else:
                result.append(old)
        result.append(candidate)
    return tuple(sorted(result))


def tile_pixels(tiles: bytes, lookup: bytes, code: int, attr: int) -> bytes:
    """Decode an opaque 8x8 tile with the arcade's inverted X-flip wiring."""
    if (type(code) is not int or not 0 <= code < len(tiles)//64
            or type(attr) is not int or not 0 <= attr <= 255 or len(lookup) != 256):
        raise ValueError('Invalid native tile descriptor')
    return bytes(lookup[(attr & 63)*4 + tiles[code*64 +
                 (7-y if attr & 128 else y)*8 + (x if attr & 64 else 7-x)]]
                 for y in range(8) for x in range(8))


def compose_scene(world: bytes, width: int, height: int, actors: tuple[dict, ...],
                  camera: tuple[int, int], palette: bytes) -> Image.Image:
    """Fresh toroidal background plus ordered, clipped actors at their original size.

    Actor bounds are already unwrapped world coordinates; transparency is a
    source index (zero), while opaque black can retain index one. The returned
    image has the world dimensions, making restoration checks independent of
    any dirty-region implementation.
    """
    if (type(width) is not int or type(height) is not int or width <= 0 or height <= 0
            or type(world) is not bytes or len(world) != width*height
            or len(palette) != 48 or any(p > 15 for p in world)
            or len(camera) != 2 or any(type(v) is not int for v in camera)):
        raise ValueError('Invalid indexed world, camera or 16-color palette')
    cx, cy = camera
    pixels = bytearray(world[((y+cy) % height)*width + (x+cx) % width]
                       for y in range(height) for x in range(width))
    for actor in actors:
        x, y, x1, y1 = _rect(actor['bounds'])
        aw, ah = x1-x, y1-y
        source = actor['pixels']
        if type(source) is not bytes or len(source) != aw*ah or any(p > 15 for p in source):
            raise ValueError('Invalid indexed actor pixels')
        for dy in range(max(0, y-cy), min(height, y1-cy)):
            sy = dy+cy-y
            if actor.get('flip_y', False):
                sy = ah-1-sy
            for dx in range(max(0, x-cx), min(width, x1-cx)):
                sx = dx+cx-x
                if actor.get('flip_x', False):
                    sx = aw-1-sx
                color = source[sy*aw+sx]
                if color != actor['transparent']:
                    pixels[dy*width+dx] = color
    rgb = bytes(channel for color in pixels for channel in palette[color*3:color*3+3])
    return Image.frombytes('RGB', (width, height), rgb)


def verify_tile_cache(video: bytes, vram: bytes, dirty: bytes, tiles: bytes,
                      lookup: bytes, translation: bytes) -> dict:
    """Check completed clean-page tiles against freshly decoded live game RAM.

    Pending dirty cells are counted explicitly, not called correct. This checks
    the bitmap cache only; it cannot establish complete rendered RGB acceptance.
    """
    if (len(video) != 4096 or len(vram) != 131072 or len(dirty) != 128
            or len(tiles) != 16384 or len(lookup) != 256 or len(translation) != 16):
        raise ValueError('Incomplete native tile-cache evidence')
    compared = mismatches = 0
    first = None
    for index in range(1024):
        if dirty[index//8] & (1 << (index % 8)):
            continue
        compared += 1
        expected = tile_pixels(tiles, lookup, video[0x400+index], video[0xc00+index])
        tx, ty = (index % 32)*8, (index//32)*8
        for y in range(8):
            for x in range(8):
                value = vram[65536 + (ty+y)*128 + (tx+x)//2]
                actual = (value >> (0 if (tx+x) & 1 else 4)) & 15
                wanted = translation[expected[y*8+x]]
                if actual != wanted and {actual, wanted} != {0, 11}:
                    mismatches += 1
                    if first is None:
                        first = dict(tile=index, x=x, y=y, expected=wanted, actual=actual)
    return dict(compared_tiles=compared, pending_tiles=1024-compared,
                different_pixels=mismatches, first_difference=first,
                rendered_rgb_verified=False)


def verify_scene_cache(snapshot: Snapshot, vram: bytes, page: int, tiles: bytes,
                       sprites: bytes, lookup: bytes, translation: bytes, *, radar=False) -> dict:
    """Fresh full visible-scene oracle, with no dirty-cache exclusions.

    Check the prepared bitmap page independently of its atlas, cache tags and
    update history. Raster scanout and HUD sprites require separate evidence.
    """
    if (not isinstance(snapshot, Snapshot) or len(vram) != 131072
            or type(page) is not int or page not in (0, 1)
            or len(tiles) != 16384 or len(sprites) != 16384
            or len(lookup) != 256 or len(translation) != 16):
        raise ValueError('Incomplete native scene-cache evidence')
    ram, shadow = snapshot.video, snapshot.shadows
    sx, sy = shadow[0x130], shadow[0x140]
    width, height = 200, 201
    expected = bytearray(width*height)
    priority = bytearray(width*height)
    for y in range(height):
        wy = (y+sy+22) & 255
        for x in range(width):
            wx = (x+sx+9) & 255
            index = (wy//8)*32 + wx//8
            attr, code = ram[0xc00+index], ram[0x400+index]
            tx = wx & 7 if attr & 64 else 7-(wx & 7)
            ty = 7-(wy & 7) if attr & 128 else wy & 7
            expected[y*width+x] = translation[lookup[(attr & 63)*4+tiles[code*64+ty*8+tx]]]
            priority[y*width+x] = bool(attr & 32)
    # Original first-hit priority is equivalent to drawing the reverse order.
    for offset in range(0x14, 0x20, 2):
        flags, attr = ram[offset], ram[0x801+offset]
        ox = ram[offset+1] + ((attr & 128) << 1)-12
        oy = 225-ram[0x800+offset]-6
        for y in range(max(0, oy), min(height, oy+16)):
            py = 15-(y-oy) if flags & 2 else y-oy
            for x in range(max(0, ox), min(width, ox+16)):
                px = 15-(x-ox) if flags & 1 else x-ox
                color = lookup[(attr & 63)*4+sprites[(flags >> 2)*256+py*16+px]]
                if color and not priority[y*width+x]:
                    expected[y*width+x] = translation[color]
    if radar:
        (rx, ry), dots = radar_bitmap(snapshot)
        for y in range(height):
            wy = (y+sy+22) & 255
            for x in range(width):
                wx = (x+sx+9) & 255
                if (wx-rx) & 255 < 50 and (wy-ry) & 255 < 60:
                    expected[y*width+x] = 13 if any(
                        (wx-dx) & 255 < 2 and (wy-dy) & 255 < 2 for dx, dy in dots) else 11
    differences = 0
    first = None
    for y in range(height):
        wy = (y+sy+22) & 255
        for x in range(width):
            wx = (x+sx+9) & 255
            packed = vram[page*32768+wy*128+wx//2]
            actual = (packed >> (0 if wx & 1 else 4)) & 15
            wanted = expected[y*width+x]
            if actual != wanted and {actual, wanted} != {0, 11}:
                differences += 1
                if first is None:
                    first = dict(x=x, y=y, expected=wanted, actual=actual)
    return dict(compared_pixels=width*height, different_pixels=differences,
                first_difference=first, bitmap_scene_verified=differences == 0,
                rendered_rgb_verified=False)
