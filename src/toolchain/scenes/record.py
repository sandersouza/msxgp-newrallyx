"""Run the installed MAME with contributor ROMs and frame-scheduled inputs."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image
from src.toolchain.graphics.roms import load_metadata, validate_roms, input_records
from .bundle import load_assets, load_capture, verify_manifest
from .storage import json_write, seal, safe_destination, publish_bundle, require_ignored

INPUTS = {'Coin 1','1 Player Start','P1 Up','P1 Down','P1 Left','P1 Right','P1 Button 1'}
CASE_PAYLOADS = ['capture.json','video.bin','radar-attributes.bin','reference.png','manifest.json']


def check_acquisition_paths(root, work, frames):
    names=['run.json','run.lua','mame.log','failure.txt','cfg/default.cfg','cfg/nrallyx.cfg']
    names += [f'frame-{frame:05d}/{name}' for frame in frames for name in CASE_PAYLOADS+['complete']]
    require_ignored(root,[work/name for name in names])


def lua_literal(value):
    if isinstance(value,str):
        return json.dumps(value,ensure_ascii=False)
    if type(value) is int:
        return str(value)
    if isinstance(value,list):
        return '{'+','.join(lua_literal(v) for v in value)+'}'
    if isinstance(value,dict):
        return '{'+','.join('['+lua_literal(k)+']='+lua_literal(v) for k,v in value.items())+'}'
    raise ValueError('Unsupported Lua configuration value')


def validate_replay(events):
    if not isinstance(events,list):
        raise ValueError('Replay must be a JSON array')
    previous = 0
    for event in events:
        if (not isinstance(event,dict) or set(event) != {'frame','field','value'}
                or type(event['frame']) is not int or event['frame'] < max(1,previous)
                or event['field'] not in INPUTS or type(event['value']) is not int
                or event['value'] not in (0,1)):
            raise ValueError('Invalid replay: require ordered frame, field and binary value')
        previous = event['frame']
    return events


def finalize_case(case, assets):
    marker = case/'complete'
    if not marker.is_file() or marker.read_text().strip() != 'ok':
        raise ValueError(f'MAME did not complete capture: {case}')
    marker.unlink()
    with Image.open(case/'reference.png') as image:
        image.convert('RGB').save(case/'reference.png', optimize=False, compress_level=9)
    seal(case)
    load_capture(case, assets)


def capture_gameplay(root: Path, assets: Path, output: Path, replay: Path, frames: list[int], *, overwrite=False) -> None:
    from .bundle import read_json
    root = root.resolve()
    output = safe_destination(root, output, overwrite=overwrite)
    loaded = load_assets(assets)
    events = validate_replay(read_json(replay))
    if (not frames or any(type(f) is not int or f <= 1 for f in frames)
            or sorted(set(frames)) != frames or frames[-1] > 36000):
        raise ValueError('Frames must be unique ascending integers in 2..36000')
    payloads=['replay.json']+[f'frame-{frame:05d}/{name}' for frame in frames for name in CASE_PAYLOADS]
    if output.exists():
        verify_manifest(output,set(payloads))
    version = subprocess.run(['mame','-help'],capture_output=True,text=True,check=True).stdout.splitlines()[0]
    if not version.startswith('MAME v0.289 '):
        raise ValueError('Gameplay capture requires MAME 0.289')
    rompath = root/'references/roms/nrallyx'
    metadata = load_metadata()
    before = input_records(validate_roms(rompath, metadata))
    if before != loaded.manifest['inputs']:
        raise ValueError('Source ROMs differ from asset provenance')
    output.parent.mkdir(parents=True,exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='.acquisition-',dir=output.parent))
    check_acquisition_paths(root,work,frames)
    require_ignored(root,[output/name for name in payloads+['manifest.json']])
    for frame in frames:
        (work/f'frame-{frame:05d}').mkdir()
    config = dict(destination=str(work), frames=frames, inputs=events,
        source=metadata['source'], roms=before, assets_sha256=loaded.sha256)
    json_write(work/'run.json',config)
    header = dict(schema_version=1,set='nrallyx',emulator='0.289',source=metadata['source'],
        roms=before,assets_sha256=loaded.sha256,visible=[0,16,288,240],
        phase='vblank-rising-before-irq',shadow_factor=0.6,
        acquisition='fresh configuration; observed writes; soft reset; frame-scheduled input')
    lua_config = dict(destination=str(work),frames=frames,inputs=events,
                      header=json.dumps(header,sort_keys=True)[:-1])
    (work/'run.lua').write_text('return '+lua_literal(lua_config)+'\n')
    environment = dict(os.environ, NRALLYX_CAPTURE_CONFIG=str(work/'run.lua'))
    command = ['mame','nrallyx','-noreadconfig','-noplugins','-nocheat',
        '-rompath',str(rompath.parent),'-video','none',
        '-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/scenes/capture.lua'),
        '-snapview','native','-snapsize','288x224','-nosnapbilinear',
        '-brightness','1','-contrast','1','-gamma','1',
        '-seconds_to_run',str(frames[-1]//50+15)]
    for option in ('cfg','nvram','snapshot','state','diff'):
        command += [f'-{option}_directory',str(work/option)]
    try:
        with (work/'mame.log').open('w') as log:
            result = subprocess.run(command, env=environment, stdout=log,
                                    stderr=subprocess.STDOUT,text=True, timeout=180)
        if result.returncode:
            raise ValueError(f'MAME exited {result.returncode}')
        require_ignored(root,[p for p in work.rglob('*') if p.is_file()])
        for frame in frames:
            finalize_case(work/f'frame-{frame:05d}',loaded)
        after = input_records(validate_roms(rompath,metadata))
        if after != before:
            raise ValueError('Source ROM hashes changed')
        def writer(stage):
            for frame in frames:
                name=f'frame-{frame:05d}'
                shutil.copytree(work/name,stage/name)
            # No absolute acquisition paths in the published metadata.
            json_write(stage/'replay.json',dict(frames=frames,inputs=events))
        publish_bundle(root,output,writer,payloads=payloads,overwrite=overwrite)
        # Successful acquisition is sealed above; do not retain duplicate raw work.
        shutil.rmtree(work)
    except (OSError,subprocess.SubprocessError,ValueError) as error:
        raise ValueError(f'{error}; acquisition evidence retained at {work}') from error
