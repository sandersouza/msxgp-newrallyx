"""Staged publication with explicit verified replacement of local scene bundles."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unicodedata
import uuid
from .bundle import digest, verify_manifest


def require_ignored(root, paths):
    root=root.resolve()
    names=[]
    for path in paths:
        try:
            names.append(path.absolute().relative_to(root).as_posix())
        except ValueError as error:
            raise ValueError('Generated data must stay in this checkout') from error
    if not names:
        return
    result=subprocess.run(['git','-C',str(root),'check-ignore','--no-index','--verbose','--stdin','-z'],
        input=b''.join(name.encode()+b'\0' for name in names),capture_output=True)
    fields=result.stdout.decode().split('\0')[:-1]
    if len(fields)%4:
        raise ValueError('Git returned an invalid ignore-rule response')
    ignored={fields[i+3] for i in range(0,len(fields),4) if not fields[i+2].startswith('!')}
    if result.returncode not in (0,1) or any(name not in ignored for name in names):
        raise ValueError('Every generated payload must be ignored by Git')


def json_write(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def seal(path):
    if any(p.is_symlink() for p in path.rglob('*')):
        raise ValueError('Generated payloads cannot contain symlinks')
    records = [dict(path=p.relative_to(path).as_posix(), size=p.stat().st_size,
                    sha256=digest(p)) for p in sorted(path.rglob('*'))
               if p.is_file() and p != path/'manifest.json']
    json_write(path/'manifest.json', dict(schema_version=1, outputs=records))


def verify_replacement(path, expected=None):
    manifest=verify_manifest(path,expected)
    names={record['path'] for record in manifest['outputs']}|{'manifest.json'}
    directories={parent.as_posix() for name in names for parent in Path(name).parents
                 if parent != Path('.')}
    for item in path.rglob('*'):
        name=item.relative_to(path).as_posix()
        if (item.is_dir() and name not in directories
                or not item.is_dir() and not item.is_file()):
            raise ValueError('Bundle contains unknown directories or nonregular entries')
    return manifest


def safe_destination(root: Path, destination: Path, *, overwrite=False):
    root = root.resolve()
    if '..' in destination.parts:
        raise ValueError('Parent traversal is not allowed')
    dest = destination.absolute()
    if any(p.is_symlink() for p in [dest, *dest.parents]):
        raise ValueError('Symlink output path')
    dest = dest.resolve()
    allowed = [root/'references/scenes',root/'assets/arcade/scenes']
    if not any(dest.is_relative_to(base) and dest != base for base in allowed):
        raise ValueError('Output must be strictly below references/scenes')
    if dest.exists() and not overwrite:
        raise ValueError('Output exists; select a fresh directory or use --overwrite for an unchanged complete bundle')
    def git(args, data=None):
        result = subprocess.run(['git','-C',str(root),*args], input=data, capture_output=True)
        if result.returncode not in (0,1):
            raise ValueError('Git cannot verify output protection')
        return result
    relative = dest.relative_to(root).as_posix()
    folded = unicodedata.normalize('NFC',relative).casefold()
    tracked = git(['ls-files','-z']).stdout.decode().split('\0')
    for name in tracked:
        candidate = unicodedata.normalize('NFC',name).casefold()
        if candidate == folded or candidate.startswith(folded+'/'):
            raise ValueError('Output aliases tracked data')
    require_ignored(root,[dest/'capture.json',dest/'probe.bin'])
    if dest.exists():
        verify_replacement(dest)
    return dest


def publish_bundle(root: Path, destination: Path, writer, *, payloads=None, overwrite=False):
    dest = safe_destination(root, destination, overwrite=overwrite)
    planned=None
    if payloads is not None:
        planned=set(payloads)|{'manifest.json'}
        if any(Path(p).is_absolute() or '..' in Path(p).parts for p in planned):
            raise ValueError('Invalid planned output path')
        require_ignored(root,[dest/p for p in planned])
    if overwrite and planned is None:
        raise ValueError('Overwrite requires an explicit planned payload inventory')
    if dest.exists():
        verify_replacement(dest,planned-{'manifest.json'})
    dest.parent.mkdir(parents=True, exist_ok=True)
    lock = dest.with_name('.'+dest.name+'.lock')
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError('Output is locked by another run') from error
    stage = None
    backup = dest.with_name('.'+dest.name+'.backup-'+uuid.uuid4().hex)
    try:
        safe_destination(root, dest, overwrite=overwrite)
        stage = Path(tempfile.mkdtemp(prefix='.'+dest.name+'.staging-', dir=dest.parent))
        if planned is not None:
            require_ignored(root,[stage/p for p in planned])
        writer(stage)
        actual={p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}|{'manifest.json'}
        if planned is not None and actual != planned:
            raise ValueError('Generated output differs from planned inventory')
        require_ignored(root,[stage/p for p in actual]+[dest/p for p in actual])
        seal(stage)
        verify_replacement(stage,planned-{'manifest.json'} if planned is not None else None)
        safe_destination(root, dest, overwrite=overwrite)
        if dest.exists():
            verify_replacement(dest,planned-{'manifest.json'})
            require_ignored(root,[backup/p for p in planned])
            dest.rename(backup)
        try:
            stage.rename(dest)
        except OSError as error:
            if backup.exists():
                try:
                    backup.rename(dest)
                except OSError as rollback:
                    raise OSError(f'Publication and rollback failed; restore the old bundle from {backup} to {dest}: {rollback}') from error
            raise
        stage = None
        if backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError as error:
                raise OSError(f'New bundle installed at {dest}; old backup retained at {backup}: {error}') from error
    finally:
        try:
            if stage is not None:
                shutil.rmtree(stage)
        finally:
            lock.rmdir()
