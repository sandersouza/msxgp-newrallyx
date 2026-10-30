"""Deterministic payloads and guarded publication inside ignored references."""
from collections.abc import Callable
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unicodedata
import uuid

from PIL import Image, __version__ as PILLOW_VERSION
from . import TOOL_VERSION, SCHEMA_VERSION

TOOL_NAME = 'newrallyx-graphics'
PAYLOAD_PATHS = frozenset(
    [f'{group}/{name}' for group in ('tiles','sprites','dots')
     for name in ('indices.bin','atlas-indexed.png')]
    + [f'{group}/color-{code:02d}.png' for group in ('tiles','sprites') for code in range(64)]
    + ['dots/color-00.png','palette.json','graphics.json'])


def _json_write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_payload(directory: Path, pixels: dict[str, bytes], palette: dict,
                  graphics: dict, inputs: list[dict], source: dict) -> dict:
    for group in ('tiles','sprites','dots'):
        layout = graphics['groups'][group]
        width, height = layout['width'], layout['height']
        data = pixels[group]
        if len(data) != width * height * layout['count'] or any(v > 3 for v in data):
            raise ValueError(f'Invalid source indices for {group}')
        folder = directory/group
        folder.mkdir()
        (folder/'indices.bin').write_bytes(data)
        atlas = Image.new('P', tuple(layout['atlas_size']))
        atlas.putpalette([0,0,0,85,85,85,170,170,170,255,255,255] + [0]*756)
        for slot in layout['slots']:
            start = slot['id'] * width * height
            tile = Image.frombytes('P', (width,height), data[start:start+width*height])
            atlas.paste(tile, (slot['x'], slot['y']))
        atlas.save(folder/'atlas-indexed.png', optimize=False, compress_level=9)
        codes = range(1) if group == 'dots' else range(64)
        source_pixels = atlas.tobytes()
        for code in codes:
            indices = palette['dot_indices'] if group == 'dots' else palette['variants'][code]
            alpha = (palette['dot_alpha'] if group == 'dots' else
                     palette['sprite_alpha'][code] if group == 'sprites' else [255]*4)
            colors = [tuple(palette['rgb'][index]) + (a,) for index, a in zip(indices, alpha)]
            image = Image.new('RGBA', atlas.size)
            image.putdata([colors[index] for index in source_pixels])
            image.save(folder/f'color-{code:02d}.png', optimize=False, compress_level=9)
    _json_write(directory/'palette.json', palette)
    _json_write(directory/'graphics.json', graphics)
    manifest = dict(tool={'name': TOOL_NAME, 'version': TOOL_VERSION},
        schema_version=SCHEMA_VERSION, source=source,
        runtime={'python': platform.python_version(), 'pillow': PILLOW_VERSION},
        parameters={'set': 'nrallyx', 'orientation': 'unflipped',
                    'index_encoding': 'uint8 ID,row,column',
                    'atlas_columns': {'tiles':16,'sprites':8,'dots':8}},
        inputs=sorted(inputs, key=lambda entry: entry['name']),
        outputs=[dict(path=name, size=(directory/name).stat().st_size,
                      sha256=_sha256(directory/name)) for name in sorted(PAYLOAD_PATHS)])
    _json_write(directory/'manifest.json', manifest)
    return manifest


def _git(root, args, data=None):
    try:
        result = subprocess.run(['git','-C',str(root),*args], input=data,
                                capture_output=True)
    except OSError as error:
        raise ValueError(f'Git is required to verify ignored output: {error}') from error
    if result.returncode not in (0,1):
        raise ValueError('Git could not verify output safety: ' + result.stderr.decode(errors='replace').strip())
    return result


def _ignored(root, paths):
    names = [str(p.relative_to(root)) for p in paths]
    data = b''.join(os.fsencode(name)+b'\0' for name in names)
    result = _git(root, ['check-ignore','--no-index','-z','--stdin'], data)
    ignored = set(result.stdout.split(b'\0'))
    if any(os.fsencode(name) not in ignored for name in names):
        raise ValueError('Generated output is not fully ignored by Git; repair references ignore rules')


def _canonical_spelling(path):
    """Recover existing directory entry spellings, including case/Unicode aliases."""
    path = path.absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        child = current/part
        if child.exists():
            identity = child.stat(follow_symlinks=False)
            for entry in current.iterdir():
                actual = entry.stat(follow_symlinks=False)
                if (actual.st_dev, actual.st_ino) == (identity.st_dev, identity.st_ino):
                    child = entry
                    break
        current = child
    return current


def _case_insensitive(path):
    current = path
    while not current.is_dir():
        current = current.parent
    while current.name:
        alternate = current.with_name(current.name.swapcase())
        if alternate != current:
            return alternate.exists() and alternate.samefile(current)
        current = current.parent
    return False


def _check_path(root, input_dir, output):
    if '..' in output.parts:
        raise ValueError('Output path must not contain ..')
    output = output.absolute()
    for path in [output, *output.parents]:
        if path.is_symlink():
            raise ValueError(f'Symlink output component is unsafe: {path}')
        if path.exists() and not path.is_dir():
            raise ValueError(f'Output component is not a directory: {path}')
    output = _canonical_spelling(output)
    allowed = [_canonical_spelling(root/name) for name in ('references/assets','assets/arcade')]
    if not any(output != base and output.is_relative_to(base) for base in allowed):
        raise ValueError(f'Output must be a strict descendant of {allowed}')
    source = _canonical_spelling(input_dir.resolve())
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Output overlaps input directory')
    insensitive = _case_insensitive(output)
    def key(path):
        return tuple(unicodedata.normalize('NFC', part).casefold() if insensitive else part
                     for part in path.parts)
    output_key = key(output)
    tracked = _git(root, ['ls-files','-z','--']).stdout.split(b'\0')
    for name in filter(None, tracked):
        candidate = _canonical_spelling(root/os.fsdecode(name))
        if key(candidate)[:len(output_key)] == output_key:
            raise ValueError('Output contains tracked files; refusing to modify it')
    _ignored(root, [output/name for name in sorted(PAYLOAD_PATHS | {'manifest.json'})])
    return output


def _verified_output(directory):
    try:
        paths = list(directory.rglob('*'))
        if any(path.is_symlink() or not (path.is_file() or path.is_dir()) for path in paths):
            raise ValueError('Output contains symlinks or nonregular files')
        actual = {path.relative_to(directory).as_posix() for path in paths if path.is_file()}
        directories = {path.relative_to(directory).as_posix() for path in paths if path.is_dir()}
        if actual != PAYLOAD_PATHS | {'manifest.json'} or directories != {'tiles','sprites','dots'}:
            raise ValueError('Output has missing or unknown files/directories')
        manifest = json.loads((directory/'manifest.json').read_text())
        if (manifest.get('tool') != {'name':TOOL_NAME,'version':TOOL_VERSION}
                or manifest.get('schema_version') != SCHEMA_VERSION):
            raise ValueError('Output is not recognized as a supported extraction')
        records = manifest['outputs']
        if (not isinstance(records, list) or len(records) != len(PAYLOAD_PATHS)
                or {entry['path'] for entry in records} != PAYLOAD_PATHS):
            raise ValueError('Invalid output manifest inventory')
        for entry in records:
            path = directory/entry['path']
            if entry['size'] != path.stat().st_size or entry['sha256'] != _sha256(path):
                raise ValueError(f'Modified output: {entry["path"]}')
        return manifest
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError(f'Cannot overwrite unrecognized or modified output {directory}: {error}') from error


def publish_output(repo_root: Path, input_dir: Path, output_dir: Path,
                   overwrite: bool, writer: Callable[[Path], dict]) -> dict:
    root = _canonical_spelling(repo_root.resolve())
    output = _check_path(root, input_dir, output_dir)
    if output.exists() and not overwrite:
        raise ValueError(f'Output exists: {output}; use --overwrite only for an unchanged complete extraction')
    lock = output.with_name(f'.{output.name}.lock')
    backup = output.with_name(f'.{output.name}.backup-{uuid.uuid4().hex}')
    _ignored(root, [lock,backup,output.with_name(f'.{output.name}.staging-probe')/'manifest.json'])
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        remnants = sorted(output.parent.glob(f'.{output.name}.backup-*'))
        recovery = (f'; preserved backups: {", ".join(map(str, remnants))}. '
                    f'If {output} is absent, inspect and restore the complete backup to {output}'
                    if remnants else '')
        raise ValueError(f'Extraction lock exists: {lock}; stop concurrent work or inspect/remove a stale lock before retrying{recovery}') from error
    staging = None
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(f'pid={os.getpid()}\n')
        if output.exists():
            _verified_output(output)
        staging = Path(tempfile.mkdtemp(prefix=f'.{output.name}.staging-', dir=output.parent))
        _ignored(root, [staging/name for name in PAYLOAD_PATHS | {'manifest.json'}])
        writer(staging)
        manifest = _verified_output(staging)
        # Recheck destination before replacing it, including modifications during encoding.
        _check_path(root, input_dir, output)
        if output.exists():
            if not overwrite:
                raise ValueError(f'Output appeared during extraction: {output}')
            _verified_output(output)
            output.rename(backup)
        try:
            staging.rename(output)
            staging = None
        except OSError as error:
            if backup.exists():
                try:
                    backup.rename(output)
                except OSError as rollback:
                    raise OSError(f'Publication and rollback failed; recover old output from {backup}: {rollback}') from error
            raise
        if backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError as error:
                raise OSError(f'Output installed at {output}; old backup remains at {backup}: {error}') from error
        return manifest
    finally:
        try:
            if staging is not None and staging.exists():
                shutil.rmtree(staging)
        finally:
            lock.unlink()
