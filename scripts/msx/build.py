"""Build a reproducible local cartridge from verified compact scene bundles."""
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image
from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal
from .screen5 import convert


def destination(root, path):
    path = path.absolute()
    if '..' in path.parts or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('Output cannot traverse parents or symlinks')
    if not path.is_relative_to(root.resolve()/'references/build'):
        raise ValueError('Output must be below references/build')
    if path.exists():
        raise ValueError('Output exists; select a fresh output directory')
    return path


def build(root, normal, overlap, output, assembler):
    output = destination(root, output)
    names = ['normal.sc5','overlap.sc5','normal.png','overlap.png','palette.bin',
             'conversion.json','build.json','static-scene.asm','static-scene.rom',
             'static-scene.sym','static-scene.lst','assembly.log','manifest.json']
    require_ignored(root, [output/name for name in names])
    images, inputs = [], []
    for source in (normal, overlap):
        verify_manifest(source)
        layout = read_json(source/'layout.json')
        if (layout.get('status') != 'approved' or layout.get('name') != 'compact'
                or layout.get('maze') != dict(source=[12,6,212,218],destination=[0,0,200,212])
                or read_json(source/'comparison.json').get('mismatches') != 0):
            raise ValueError('Input must be an approved compact bundle with exact arcade reconstruction')
        with Image.open(source/'preview.png') as im:
            images.append(im.convert('RGB'))
        inputs.append(dict(manifest_sha256=digest(source/'manifest.json'),
                           preview_sha256=digest(source/'preview.png')))
    palette, scenes, colors = convert(images)
    if not assembler.is_file():
        raise ValueError('Pinned assembler missing; run make environment or set SJASMPLUS')
    version = subprocess.run([str(assembler.resolve()),'--version'],capture_output=True,text=True,check=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_name('.'+output.name+'.lock')
    lock.mkdir()
    stage = None
    try:
        destination(root, output)
        stage = Path(tempfile.mkdtemp(prefix='.'+output.name+'-', dir=output.parent))
        require_ignored(root, [stage/name for name in names])
        (stage/'palette.bin').write_bytes(palette)
        for name, (bitmap, preview, _) in zip(('normal','overlap'), scenes):
            (stage/f'{name}.sc5').write_bytes(bitmap)
            preview.save(stage/f'{name}.png')
        json_write(stage/'conversion.json', dict(policy='nearest V9958 RGB333 DAC; reject merges; sorted RGB palette',
                   colors=colors, scenes={name: scene[2] for name,scene in zip(('normal','overlap'),scenes)}))
        shutil.copyfile(root/'src/static-scene.asm',stage/'static-scene.asm')
        result = subprocess.run([str(assembler.resolve()),'--nologo','--sym=static-scene.sym',
                                 '--lst=static-scene.lst','static-scene.asm'],cwd=stage,capture_output=True,text=True)
        (stage/'assembly.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError(f'Assembly failed: {result.stdout}{result.stderr}')
        rom = (stage/'static-scene.rom').read_bytes()
        if (len(rom) != 131072 or rom[:2] != b'AB' or rom[16384:43520] != scenes[0][0]
                or rom[49152:76288] != scenes[1][0]):
            raise ValueError('Cartridge layout validation failed')
        json_write(stage/'build.json',dict(schema_version=1,mapper='ASCII16',size=len(rom),
                   rom_sha256=digest(stage/'static-scene.rom'),inputs=inputs,
                   assembler=(version.stdout+version.stderr).strip(),assembler_sha256=digest(assembler),
                   source_sha256=digest(root/'src/static-scene.asm'),
                   layout=dict(code_offset=0,normal_offset=16384,overlap_offset=49152,
                               scene_bytes=27136,ram=[49152,62336],vram=[0,27136])))
        require_ignored(root, [p for p in stage.rglob('*') if p.is_file()])
        seal(stage)
        if output.exists():
            raise ValueError('Output appeared during build')
        stage.rename(output)
        stage = None
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        lock.rmdir()
    return output/'static-scene.rom'
