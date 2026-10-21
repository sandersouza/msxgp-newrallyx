"""Reconstruct the original first-stage tilemap from contributor ROMs and native RAM.

Only algorithms and addresses live here. ROM tables, captured RAM, tilemaps and
rendered pixels remain in ignored references/ directories.
"""
import os
from pathlib import Path
import subprocess
import tempfile
from scripts.graphics.roms import load_metadata, validate_roms, input_records
from scripts.extract_graphics import _region
from scripts.scenes.bundle import digest, verify_manifest, read_json
from scripts.scenes.storage import require_ignored, seal, json_write

CELL_COLUMNS, CELL_ROWS = 32, 56
BORDER = 24
WIDTH, HEIGHT = 768+2*BORDER, 1344+2*BORDER
TILE_COLUMNS, TILE_ROWS = WIDTH//8, HEIGHT//8
STRIDE = 128  # Four rows of 128 packed tiles fit an ASCII16 bank.
START = (264, 1032)
LANDMARKS = (START, (0, 0), (WIDTH-240, 0), (0, HEIGHT-201), (WIDTH-240, HEIGHT-201))


def cells_from_rom(program, page):
    def wall(x, y):
        return not (0 <= x < 32 and 0 <= y < 56) or bool(
            program[page*256+y*4+x//8] & (128 >> (x%8)))
    cells = bytearray(32*56)
    for y in range(56):
        for x in range(32):
            if wall(x, y):
                value = 0
                for i, mask in enumerate(program[0x2531:0x253a]):
                    if wall(x+i%3-1, y+i//3-1):
                        value |= mask
                cells[y*32+x] = value or 0x87
    return bytes(cells)


def tile(program, cells, tx, ty, wall_color, flower):
    """Equivalent to the native tile selector; coordinates precede border padding."""
    x, sx = divmod(tx, 3)
    y, sy = divmod(ty, 3)
    sub = sy*3+sx
    if not (0 <= x < 32 and 0 <= y < 56):
        return flower+sub, 0x51+max(0, (flower-0x56)//9)
    value = cells[y*32+x]
    if value & 0xf8:
        record = program[0x2505+sub*4:0x2509+sub*4]
        index = sum(bit for bit, mask in zip((4,2,1),record[1:]) if value & mask)
        return program[0x2529+index], wall_color | record[0]
    packed = program[0x2552+value*9+sub]
    return 0x80 | (packed & 31), (packed & 0xc0) | (0x15+bool(packed & 32))


def acquire(root, *, mame='mame'):
    """Replay a clean original game and cross-check every tile with its Z80 renderer."""
    roms = validate_roms(root/'references/roms/nrallyx', load_metadata())
    program = _region(roms, load_metadata(), 'maincpu', 16384)
    source = input_records(roms)
    cache = root/'references/stage-one/native-v1'
    script = root/'scripts/msx/stage_one_capture.lua'
    if cache.exists():
        verify_manifest(cache)
        capture = read_json(cache/'capture.json')
        if (capture['roms'] != source or capture['script_sha256'] != digest(script)
                or not capture['emulator'].startswith('0.289 ')):
            raise ValueError('Stage-one cache has different inputs/tooling; move it aside and rebuild')
        return program, cache
    version = subprocess.check_output([mame, '-version'],text=True).strip()
    if not version.startswith('0.289 '):
        raise ValueError('Native stage acquisition requires the pinned MAME 0.289')
    require_ignored(root, [cache/'video.bin'])
    cache.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix='.native-v1-',dir=cache.parent))
    env = dict(os.environ, STAGE_ONE_OUTPUT=str(pending.resolve()))
    command = [mame, 'nrallyx', '-noreadconfig', '-noplugins', '-nocheat',
        '-rompath', str(root/'references/roms'), '-video', 'none', '-sound', 'none',
        '-nothrottle', '-noautosave', '-noautoframeskip', '-frameskip', '0',
        '-skip_gameinfo', '-autoboot_delay', '0', '-autoboot_script', str(script),
        '-cfg_directory', str(pending/'cfg'), '-nvram_directory', str(pending/'nvram'),
        '-seconds_to_run', '60']
    with (pending/'mame.log').open('w') as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=90)
    if not (pending/'complete').is_file():
        raise ValueError(f'Native stage acquisition did not finish: {pending}/mame.log')
    json_write(pending/'capture.json', dict(schema_version=1, roms=source,
        emulator=version,
        input=dict(coin=[1800,1804], start=[1860,1864], snapshot=2200),
        renderer_check='Original Z80 full-window redraw in isolated diagnostic RAM harness',
        script_sha256=digest(script)))
    reconstruct(program, pending)
    require_ignored(root, [p for p in pending.rglob('*') if p.is_file()])
    seal(pending)
    pending.rename(cache)
    return program, cache


def reconstruct(program, cache):
    video, work = (cache/'video.bin').read_bytes(), (cache/'work.bin').read_bytes()
    if len(video)!=4096 or len(work)!=2048 or video[0x28f]!=0x30:
        raise ValueError('Expected first-stage native RAM')
    cells = work[:1792]
    layout = cells_from_rom(program, video[0x28f])
    if any((layout[i] != 0 if c in (1,2,3,4) else c != layout[i])
           for i,c in enumerate(cells)):
        raise ValueError('Captured first-stage geometry differs from the original layout')
    if cells.count(1)!=8 or cells.count(4)!=1 or cells.count(2)!=1:
        raise ValueError('Expected untouched first stage: eight flags, special flag and lucky flag')
    wall_color, flower = video[0x2b1], video[0x2d6]
    checked = 0
    for cy in (-1,9,19,29,39,49,59):
        for cx in (-1,9,19,29):
            native = (cache/f'window-{cx}-{cy}.bin').read_bytes()
            for y in range(32):
                for x in range(32):
                    code, attr = tile(program,cells,cx*3+x,cy*3+y,wall_color,flower)
                    i = y*32+x
                    if (native[0x400+i],native[0xc00+i]) != (code,attr):
                        raise ValueError(f'Native tile mismatch: {cx*3+x},{cy*3+y}')
                    checked += 1
    pairs = [tile(program,cells,x-3,y-3,wall_color,flower)
             for y in range(TILE_ROWS) for x in range(TILE_COLUMNS)]
    return cells, pairs, checked


def bitmap(pairs, assets, encoded):
    from .raster_scroll import index_for
    result = bytearray(WIDTH*HEIGHT)
    indices = {}
    for rgb in assets.palette['rgb']:
        try:
            indices[tuple(rgb)] = index_for(encoded,rgb)
        except ValueError:
            pass
    for i, (code, attr) in enumerate(pairs):
        bx, by = i%TILE_COLUMNS*8, i//TILE_COLUMNS*8
        for y in range(8):
            for x in range(8):
                sx = x if attr & 64 else 7-x
                sy = 7-y if attr & 128 else y
                pen = assets.pixels['tiles'][code*64+sy*8+sx]
                rgb = assets.palette['rgb'][assets.palette['lookup'][(attr&63)*4+pen]]
                result[(by+y)*WIDTH+bx+x] = indices[tuple(rgb)]
    return bytes(result)


def tile_banks(world):
    from .screen5 import packed
    data = bytearray(STRIDE*TILE_ROWS*32)
    # Four tile rows per bank, laid out as contiguous 1024-pixel scanlines.
    # Column loads still address 8x8 tiles; row streaming uses contiguous bursts.
    for y in range(HEIGHT):
        data[y*512:y*512+WIDTH//2]=packed(world[y*WIDTH:(y+1)*WIDTH])
    data.extend(bytes((-len(data))%16384))
    return [bytes(data[i:i+16384]) for i in range(0,len(data),16384)]
