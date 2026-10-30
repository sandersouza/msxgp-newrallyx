"""Reproducible reference source view without changing either checkout.

Only authored Git files are exported. Local contributor inputs are hardlinked into
the ignored view; reference build products have their own output directory.
The exact revision remains reachable after the audio branch is renamed/merged.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
REFERENCE_REVISION = '6d562a791b0cc242119a31dd686ff8e93eb94fe0'


def source_view(revision=REFERENCE_REVISION):
    """Export immutable authored Git bytes; link only explicit contributor inputs.

    The cache is disposable. The revision marker is not sufficient validation:
    compare authored files against git archive before reusing an existing view.
    """
    commit = subprocess.check_output(['git','rev-parse',revision+'^{commit}'],cwd=ROOT,text=True).strip()
    target = (ROOT/'references/cache/source-views'/commit).resolve()
    marker = target/'source-view.json'
    archive = subprocess.check_output(['git','archive',commit],cwd=ROOT)
    if marker.exists():
        assert json.loads(marker.read_text())['revision'] == commit
        # A revision marker alone cannot detect local edits to a cached export.
        with tarfile.open(fileobj=io.BytesIO(archive)) as files:
            for member in files:
                if member.isfile() and not member.name.startswith('references/'):
                    path=target/member.name
                    if not path.is_file() or path.read_bytes()!=files.extractfile(member).read():
                        raise ValueError(f'Modified reference source export: {path}; preserve it and rebuild a clean source view')
        return target
    target.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as files:
        files.extractall(target,filter='data')
    for name in ('.tools','.venv'):
        if not (target/name).exists():
            (target/name).symlink_to((ROOT/name).resolve(),target_is_directory=True)
    inputs=target/'references';inputs.mkdir(exist_ok=True)
    # Never recursively import references/: issue traces and prior build trees
    # are not source inputs, and copying them recreates the old disk explosion.
    for name in ('roms','msxbios'):
        source=ROOT/'references'/name
        if not source.is_dir():continue
        def link_input(source,destination):
            if source.name=='.gitkeep':
                return
            if destination.is_symlink():
                destination.unlink()
            if source.is_dir():
                destination.mkdir(exist_ok=True)
                for item in source.iterdir():
                    link_input(item,destination/item.name)
            elif not destination.exists():
                os.link(source.resolve(),destination)
        link_input(source,inputs/source.name)
    # Immutable reference code expects its historical input layout. Only these
    # validated canonical inputs are hardlinked into the disposable private view.
    for source_name, target_name in (
        ('nrallyx','assets/nrallyx'),
        ('scenes/normal','scenes/rom-input/normal'),
        ('scenes/overlap','scenes/rom-input/overlap'),
        ('scenes/captures','scenes/review-fixed-v3'),
        ('native/native-v1','stage-one/native-v1'),
        ('native/rocks-v1','stage-one/rocks-v1'),
        ('native/death-v1','stage-one/death-v1')):
        source=ROOT/'assets/arcade'/source_name
        if source.is_dir():
            destination=inputs/target_name
            destination.parent.mkdir(parents=True,exist_ok=True)
            link_input(source,destination)
    # Root ignore rules deliberately expose repository placeholders. They have
    # no role in this generated source view and must not appear as user changes.
    for placeholder in inputs.rglob('.gitkeep'):
        placeholder.unlink()
    marker.write_text(json.dumps(dict(revision=commit,archive_sha256=hashlib.sha256(archive).hexdigest(),
        output_scope='Private build/checkpoint directories; contributor inputs hardlinked locally.'),indent=2)+'\n')
    return target


def build_reference(revision=REFERENCE_REVISION):
    """Reuse only a sealed, hash-matching pinned reference; rebuild on a cache miss."""
    view=source_view(revision)
    destination=ROOT/'references/cache/audio-reference'
    marker=destination/'build.json'
    if marker.exists():
        record=json.loads(marker.read_text())
        bundle=Path(record['bundle']).resolve()
        from src.toolchain.scenes.bundle import verify_manifest
        if (record['revision']==json.loads((view/'source-view.json').read_text())['revision']
                and bundle.is_relative_to(view/'references/build') and (bundle/'raster-scroll.rom').is_file()):
            verify_manifest(bundle)
            if hashlib.sha256((bundle/'raster-scroll.rom').read_bytes()).hexdigest()==record['rom_sha256']:
                exported=destination/'newrallyx-audio.rom'
                if not exported.is_file() or hashlib.sha256(exported.read_bytes()).hexdigest()!=record['rom_sha256']:
                    shutil.copyfile(bundle/'raster-scroll.rom',exported)
                print('Audio reference: verified pinned cache')
                return exported
    subprocess.run([str(ROOT/'.venv/bin/python'),'-B','scripts/project.py','build','--full-game','--audio'],cwd=view,check=True)
    rom=view/'references/build/newrallyx.rom'
    from src.toolchain.msx.checkpoints import resolve_latest
    bundle=resolve_latest(view).parent
    destination.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(rom,destination/'newrallyx-audio.rom')
    (destination/'build.json').write_text(json.dumps(dict(revision=json.loads((view/'source-view.json').read_text())['revision'],
        rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),source_view=str(view),bundle=str(bundle),
        renderer='Production SCREEN5',audio=True,flag_popups=True),indent=2)+'\n')
    print(destination/'newrallyx-audio.rom')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-only',action='store_true')
    parser.add_argument('--revision',default=REFERENCE_REVISION);args=parser.parse_args()
    print(source_view(args.revision)) if args.source_only else build_reference(args.revision)
