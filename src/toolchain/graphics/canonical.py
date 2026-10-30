"""Promote a validated temporary extraction, removing only identical copies."""
from pathlib import Path
import shutil
from .export import _verified_output


def promote(root):
    root=Path(root)
    temporary=root/'references/assets/nrallyx'
    target=root/'assets/arcade/nrallyx'
    if not temporary.exists():return target
    if temporary.is_symlink() or target.is_symlink():raise ValueError('Asset bundles must not be symlinks')
    _verified_output(temporary)
    if target.exists():
        _verified_output(target)
        for source in temporary.rglob('*'):
            if source.is_file() and source.read_bytes()!=(target/source.relative_to(temporary)).read_bytes():
                raise ValueError('Temporary and canonical assets differ; preserve both for review')
        shutil.rmtree(temporary)
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary.rename(target)
    return target
