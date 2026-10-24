"""Acquire the original attract cast and retain every source pixel at 1:1."""
import os
import subprocess
from PIL import Image
from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal
from .screen5 import expand,rgb333


def acquire(root):
    out=root/'references/attract/native-v1'
    script=root/'scripts/msx/attract_inventory.lua'
    roms=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Attract acquisition requires MAME 0.289')
    if out.exists():
        verify_manifest(out);info=read_json(out/'capture.json')
        if info['roms']!=roms or info['script_sha256']!=digest(script):
            raise ValueError('Attract acquisition inputs changed; use a fresh evidence directory')
        return out
    require_ignored(root,[out/'capture.json']);out.mkdir(parents=True)
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat',
        '-rompath',str(root/'references/roms'),'-video','none','-sound','none','-nothrottle',
        '-noautosave','-noautoframeskip','-frameskip','0','-skip_gameinfo','-debug','-debugger','none',
        '-autoboot_delay','0','-autoboot_script',str(script),
        '-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','90']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,check=True,timeout=120,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,ATTRACT_OUTPUT=str(out)))
    if not (out/'complete').is_file():raise ValueError('Incomplete original attract acquisition')
    # This pinned frame contains the complete cast before the source demo starts.
    with Image.open(out/'frame-1440.png') as im:
        if im.size!=(288,224):raise ValueError('Unexpected source attract dimensions')
    json_write(out/'capture.json',dict(roms=roms,emulator=version,script_sha256=digest(script),
        cast_frame=1440,demo_frame=int((out/'complete').read_text()),
        scope='Unmodified original boot/title/cast and first attract gameplay boundary; no inputs or guest-state writes.'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    return out


def cast(root,palette):
    source=acquire(root)
    colors=[expand((palette[i]>>4,palette[i+1],palette[i]&7)) for i in range(0,32,2)]
    with Image.open(source/'frame-1440.png') as im:
        rgb=im.convert('RGB')
        # The lower twelve rows and the detached arcade HUD are empty scenery
        # or independently adapted HUD content. No cast drawing is rescaled.
        image=rgb.crop((0,0,224,212))
        indexed=bytes(colors.index(expand(rgb333(pixel))) for pixel in image.getdata())
    background=indexed[0]
    result=bytearray([background])*(256*212)
    for y in range(212):result[y*256+16:y*256+240]=indexed[y*224:(y+1)*224]
    return result,background
