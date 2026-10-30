"""Original rock placement fixture; immutable scenery only, no runtime collision."""
import os
from pathlib import Path
import subprocess
import tempfile

from src.toolchain.graphics.roms import load_metadata, validate_roms, input_records
from src.toolchain.scenes.bundle import digest, read_json, verify_manifest
from src.toolchain.scenes.storage import json_write, require_ignored, seal
from . import stage_one


def cells_from_placement(base_cells, video):
    """Accept original cell pointers only; never invent placements or overwrite flags."""
    if len(base_cells) != 1792 or len(video) != 4096:
        raise ValueError('Incomplete rock placement inputs')
    count = video[0x251]
    table = int.from_bytes(video[0x996:0x998], 'little')
    if count != 2 or video[0x28f] != 0x30 or not 0x8000 <= table <= 0x9000-count*2:
        raise ValueError('Unexpected original rock placement configuration')
    cells = bytearray(base_cells)
    positions = []
    for index in range(count):
        at = table-0x8000+index*2
        address = int.from_bytes(video[at:at+2], 'little')
        cell = address-0x9800
        if not 0 <= cell < len(cells) or cells[cell] != 0:
            raise ValueError('Rock pointer overlaps a wall/object or leaves the board')
        cells[cell] = 3
        positions.append(dict(cell_x=cell%32, cell_y=cell//32,
                              world_origin=[24+cell%32*24, 24+cell//32*24]))
    return bytes(cells), positions


def verify_capture(program, base, path):
    video = (path/'placement-video.bin').read_bytes()
    if (path/'base-work.bin').read_bytes()[:1792] != base:
        raise ValueError('Rock acquisition does not match the baseline first-stage board')
    cells, positions = cells_from_placement(base, video)
    if (path/'work.bin').read_bytes()[:1792] != cells:
        raise ValueError('Rock board differs from original cell pointers')
    display = (path/'video.bin').read_bytes()
    checked = 0
    for cy in (-1,9,19,29,39,49,59):
        for cx in (-1,9,19,29):
            window = (path/f'window-{cx}-{cy}.bin').read_bytes()
            if len(window) != 4096:
                raise ValueError('Truncated original rock redraw')
            for y in range(32):
                for x in range(32):
                    wanted = stage_one.tile(program,cells,cx*3+x,cy*3+y,display[0x2b1],display[0x2d6])
                    at = y*32+x
                    if (window[0x400+at],window[0xc00+at]) != wanted:
                        raise ValueError('Rock bitmap selector differs from original Z80 redraw')
                    checked += 1
    return cells, positions, checked


def acquire(root, program, base, *, mame='mame'):
    source = input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    script = root/'src/toolchain/msx/rocks_capture.lua'
    cache = root/'assets/arcade/native/rocks-v1'
    if cache.exists():
        verify_manifest(cache)
        record = read_json(cache/'capture.json')
        if record['roms'] != source or record['script_sha256'] != digest(script):
            raise ValueError('Rock acquisition inputs changed; use a fresh fixture cache')
        return (*verify_capture(program,base,cache),cache)
    version = subprocess.check_output([mame,'-version'],text=True).strip()
    if not version.startswith('0.289 '):
        raise ValueError('Rock acquisition requires pinned MAME 0.289')
    require_ignored(root,[cache/'video.bin'])
    cache.parent.mkdir(parents=True,exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix='.rocks-',dir=cache.parent))
    env = dict(os.environ,ROCKS_OUTPUT=str(pending.resolve()))
    command = [mame,'nrallyx','-noreadconfig','-noplugins','-nocheat',
        '-rompath',str(root/'references/roms'),'-video','none','-sound','none',
        '-nothrottle','-noautosave','-noautoframeskip','-frameskip','0','-skip_gameinfo',
        '-autoboot_delay','0','-autoboot_script',str(script),
        '-cfg_directory',str(pending/'cfg'),'-nvram_directory',str(pending/'nvram'),'-seconds_to_run','60']
    with (pending/'mame.log').open('w') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    if not (pending/'complete').is_file():
        raise ValueError(f'Original rock fixture did not complete: {pending}/mame.log')
    cells,positions,checked = verify_capture(program,base,pending)
    if source != input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):
        raise ValueError('Contributor ROM inventory changed during rock acquisition')
    json_write(pending/'capture.json',dict(schema_version=1,roms=source,emulator=version,
        script_sha256=digest(script),internal_parameter_round=3,rock_count=2,
        positions=positions,native_tiles_checked=checked,
        scope='Isolated original parameter/placement routines; first-stage board with only rock cells added; original redraw oracle'))
    require_ignored(root,[p for p in pending.rglob('*') if p.is_file()])
    seal(pending);pending.rename(cache)
    return cells,positions,checked,cache
