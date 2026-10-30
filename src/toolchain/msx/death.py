"""Original static explosion pixels, alignment and non-final-life wait fixture."""
import os
from pathlib import Path
import subprocess
import tempfile

from src.toolchain.graphics.roms import input_records,load_metadata,validate_roms
from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal


def pixels(pairs, assets, encoded):
    """Decode the captured original tile attributes without scaling or recoloring."""
    from .raster_scroll import index_for
    result=[]
    for code,attr in pairs:
        tile=bytearray()
        for y in range(8):
            for x in range(8):
                sx=x if attr&64 else 7-x
                sy=7-y if attr&128 else y
                pen=assets.pixels['tiles'][code*64+sy*8+sx]
                rgb=assets.palette['rgb'][assets.palette['lookup'][(attr&63)*4+pen]]
                tile.append(index_for(encoded,rgb))
        result.append(bytes(tile))
    return result


def verify_capture(path):
    pairs=None
    for index in range(64):
        data=(path/f'effect-{index:02d}.bin').read_bytes()
        if len(data)!=4096:raise ValueError('Incomplete original explosion capture')
        codes=data[0x400:0x800];attrs=data[0xc00:0x1000]
        changed=[i for i,v in enumerate(codes) if v!=0x81]
        if len(changed)!=9 or sorted(codes[i] for i in changed)!=list(range(0xb4,0xbd)):
            raise ValueError('Unexpected original explosion footprint')
        first=codes.index(0xb4);x,y=first%32,first//32
        current=[]
        for dy in range(3):
            for dx in range(3):
                at=((y+dy)%32)*32+(x+dx)%32
                current.append((codes[at],attrs[at]))
        if any(code!=0xb4+i or attr!=0x46 for i,(code,attr) in enumerate(current)):
            raise ValueError('Original explosion tile order/attribute changed')
        # Original source camera phases map to the retained player's world
        # coordinates. Account for its established one-pixel presentation offset.
        wx,wy=396+index%8,1236-index//8
        if (((wx-9)//8*8-x*8)&255)!=24 or (((wy-8)//8*8-y*8)&255)!=80:
            raise ValueError('Original explosion fine-phase alignment changed')
        if pairs is not None and pairs!=current:
            raise ValueError('Original explosion pixels vary unexpectedly by phase')
        pairs=current
    ticks=int((path/'hold-ticks.txt').read_text())
    if ticks!=120:raise ValueError('Unexpected original non-final-life wait threshold')
    return pairs,ticks


def acquire(root,*,mame='mame'):
    source=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    script=root/'src/toolchain/msx/death_capture.lua';cache=root/'assets/arcade/native/death-v1'
    if cache.exists():
        verify_manifest(cache);record=read_json(cache/'capture.json')
        if record['roms']!=source or record['script_sha256']!=digest(script):
            raise ValueError('Original explosion fixture inputs changed')
        return (*verify_capture(cache),cache)
    version=subprocess.check_output([mame,'-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Explosion oracle requires MAME 0.289')
    cache.parent.mkdir(parents=True,exist_ok=True)
    pending=Path(tempfile.mkdtemp(prefix='.death-',dir=cache.parent))
    require_ignored(root,[pending/'capture.json'])
    command=[mame,'nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(script),
        '-cfg_directory',str(pending/'cfg'),'-nvram_directory',str(pending/'nvram'),'-seconds_to_run','60']
    with (pending/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,DEATH_OUTPUT=str(pending)),
                       stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    if not (pending/'complete').is_file():raise ValueError(f'Original explosion probe incomplete: {pending}')
    pairs,ticks=verify_capture(pending)
    if source!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):
        raise ValueError('Source ROMs changed during explosion acquisition')
    json_write(pending/'capture.json',dict(schema_version=1,roms=source,emulator=version,
        script_sha256=digest(script),fine_phases=64,width=24,height=24,hold_ticks=ticks,
        tile_pairs=pairs,world_anchor_bias=[-9,-8],
        scope='Original 1960 drawing and 1929 CP120 loop; isolated RAM harness, test-only return and externally advanced tick counter; not natural gameplay timing'))
    require_ignored(root,[p for p in pending.rglob('*') if p.is_file()]);seal(pending);pending.rename(cache)
    return pairs,ticks,cache
