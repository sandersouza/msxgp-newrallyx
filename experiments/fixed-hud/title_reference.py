"""Reconstruct the approved wordmark from contributor ROMs and authored strokes.

No original game pixels are distributed here. Output belongs under references/.
The RGBA digest pins the user's approved 162x10 image independently of PNG codec.
"""
import hashlib
from PIL import Image, ImageDraw
from scripts.extract_graphics import _region
from scripts.graphics.roms import load_metadata, validate_roms
from scripts.graphics.decode import decode_graphics

APPROVED_RGBA = '08aca7699f839b8ab54ba446c1b908394d110faca774404dc430c485e2ee5a89'


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
    c = [row[35:43] for row in mask]
    o = [row[45:53] for row in mask]
    m = [row[23:33] for row in mask]
    r = [row[:6] for row in c[:2]] + [[1,1,0,0,0,0] for _ in range(6)]
    e = [row[:] for row in o]
    e[3:8] = [[1]*8, [1]*8, c[5][:], c[6][:], c[7][:]]
    parse = lambda rows: [[int(p == '#') for p in row] for row in rows]
    glyphs = dict(r=r, e=e, o=o, w=m[::-1],
        t=parse(['.##...', '.##...', '######', '######', '.##...',
                 '.##...', '.##...', '.##...', '.#####', '..####']),
        k=parse(['##......', '##......', '##....##', '##...##.', '##..##..',
                 '#####...', '#####...', '##..##..', '##...##.', '##....##']))
    retro = Image.new('RGBA', (88,10)); x = 2
    for ch in 'retrowork':
        glyph = glyphs[ch]; top = 0 if len(glyph) == 10 else 2
        for y,row in enumerate(glyph):
            for dx,ink in enumerate(row):
                if ink: retro.putpixel((x+dx,top+y), (255,0,0,255))
        x += len(glyph[0])+2
    result = Image.new('RGBA', (162,10))
    result.alpha_composite(namco, (0,2))
    ImageDraw.Draw(result).rectangle((62,5,67,6), fill=(255,0,0,255))
    result.alpha_composite(retro, (74,0))
    verify(result)
    return result


def verify(image):
    if image.size != (162,10) or hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest() != APPROVED_RGBA:
        raise ValueError('Wordmark differs from the approved 162x10 artwork; refusing to substitute it')


def ensure(root):
    path = root/'references/exports/namco-retrowork/namco-retrowork-162x10.png'
    if not path.exists():
        image = generate(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    with Image.open(path) as image: verify(image)
    return path
