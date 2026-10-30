"""Extract the original arcade wordmark from contributor-supplied ROM tiles.

No original game pixels are distributed here. The approved wordmark belongs in ignored assets/namco-title-56x8.png.
The RGBA digest pins the native 56x8 tile block independently of PNG codec.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib
from PIL import Image
from scripts.extract_graphics import _region
from src.toolchain.graphics.roms import load_metadata, validate_roms
from src.toolchain.graphics.decode import decode_graphics

APPROVED_RGBA = '8ff819c2ef5a2f330805c9e5d97dc3b958889d246d797e82dc5807b3d2e13760'


def generate(root):
    metadata = load_metadata()
    roms = validate_roms(root/'references/roms/nrallyx', metadata)
    tiles = decode_graphics(_region(roms, metadata, 'gfx1', 4096),
                            _region(roms, metadata, 'gfx2', 256))['tiles']
    mask = [[int(tiles[(25+x//8)*64+y*8+x%8] == 1)
             for x in range(56)] for y in range(8)]
    namco = Image.new('RGBA', (56, 8))
    for y,row in enumerate(mask):
        for x,ink in enumerate(row):
            if ink: namco.putpixel((x,y), (255,0,0,255))
    verify(namco)
    return namco


def verify(image):
    if image.size != (56,8) or hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest() != APPROVED_RGBA:
        raise ValueError('Wordmark differs from the original arcade 56x8 tiles; refusing to substitute it')


def ensure(root):
    path = root/'assets/namco-title-56x8.png'
    if not path.exists():
        image = generate(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    with Image.open(path) as image: verify(image)
    return path
