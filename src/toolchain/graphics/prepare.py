"""Rebuild missing canonical inputs from contributor ROMs before any linker runs.

Stages are deliberately ordered: validated pixels -> capture/reconstruction ->
native state. Existing bundles are verified, never silently overwritten. This
module changes host preparation only; no new code is added to the MSX runtime.
"""
from pathlib import Path

from .canonical import promote
from .roms import load_metadata, validate_roms, input_records
from src.toolchain.scenes.bundle import load_assets, load_capture, verify_manifest

FRAMES = (2200, 2410, 2411, 2760, 2761)


def graphics(root):
    """Require exact contributor ROM checksums even when extracted inputs exist."""
    from scripts.extract_graphics import main as extract
    source=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    target=promote(root)
    if not target.exists():
        print('Preparing arcade graphics from references/roms/nrallyx...',flush=True)
        if extract(['--input',str(root/'references/roms/nrallyx'),'--output',str(target)]):
            raise ValueError('Graphics extraction failed; see the error above')
    assets=load_assets(target)
    if assets.manifest['inputs']!=source:
        raise ValueError('Arcade assets differ from the supplied ROMs; preserve/move the old bundle before regenerating')
    return assets


def scenes(root, assets):
    """Capture five deterministic arcade frames, then reconstruct both HUD inputs."""
    from scripts.arcade_scene import main as scene
    from src.toolchain.msx.inputs import load_huds
    target=root/'assets/arcade/scenes'
    captures=target/'captures'
    common=['--root',str(root),'--assets',str(root/'assets/arcade/nrallyx')]
    if not captures.exists():
        print('Preparing arcade captures with MAME (first build only)...',flush=True)
        if scene(['capture',*common,'--output',str(captures),'--replay',str(root/'src/toolchain/scenes/gameplay-inputs.json')]):
            raise ValueError('Arcade capture failed; see the error above')
    verify_manifest(captures)
    for frame in FRAMES:load_capture(captures/f'frame-{frame:05d}',assets)
    for name,frame in (('normal',2200),('overlap',2760)):
        output=target/name
        if not output.exists():
            print(f'Preparing {name} reconstruction...',flush=True)
            if scene(['analyze',*common,'--capture',str(captures/f'frame-{frame:05d}'),'--output',str(output)]):
                raise ValueError(f'Arcade {name} reconstruction failed; see the error above')
    load_huds(target/'normal',target/'overlap')


def native(root):
    """Acquire and cross-check original geometry, rock placement and explosions."""
    from src.toolchain.msx import stage_one,rocks,death
    print('Checking/preparing original native-state inputs...',flush=True)
    program,base=stage_one.acquire(root)
    cells=(base/'work.bin').read_bytes()[:1792]
    rocks.acquire(root,program,cells)
    death.acquire(root)


def prepare(root, stage='all'):
    root=Path(root).resolve()
    assets=graphics(root)
    if stage in ('all','scenes'):scenes(root,assets)
    if stage in ('all','native'):native(root)
    if stage=='all':
        from src.toolchain.screen4.title_reference import ensure
        ensure(root)
    print(f'Arcade {stage} inputs ready: assets/arcade',flush=True)
