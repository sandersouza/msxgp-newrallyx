"""Shared synthetic graphics and real temporary Git repositories."""
from pathlib import Path
import subprocess
import tempfile
from scripts.graphics.decode import decode_graphics, decode_palette, graphics_metadata


def temporary_repo(test):
    temp = tempfile.TemporaryDirectory(prefix='graphics test ')
    test.addCleanup(temp.cleanup)
    root = Path(temp.name).resolve()
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    (root / '.gitignore').write_text('/references/**\n')
    (root / 'references/assets').mkdir(parents=True)
    inputs = root / 'references/roms/synthetic'
    inputs.mkdir(parents=True)
    return root, inputs, root / 'references/assets/synthetic'


def synthetic_payload():
    gfx = bytearray(4096)
    gfx[8] = 0x80
    palette = decode_palette(bytes([0,1] + [0]*30), bytes([0,1,2,3]*64))
    return decode_graphics(bytes(gfx), bytes(256)), palette, graphics_metadata()
