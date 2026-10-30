"""Resolve host-tool siblings separately from authored MSX runtime sources.

No symlink mirrors or copied source trees are used: includes remain in
src/screen4 and Python/Lua/Tcl/JavaScript siblings remain in this tool package.
"""
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[2]
RUNTIME = ROOT/'src/screen4'


def source_path(name):
    name=Path(name)
    if name.is_absolute() or '..' in name.parts:
        raise ValueError('Source sibling must be relative to its owning directory')
    if name.suffix in ('.asm','.inc') or name.parts[0] in ('modules','hud'):
        return RUNTIME/name
    return TOOLS/name
