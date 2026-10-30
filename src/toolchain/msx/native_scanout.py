"""Full-border raster oracle for already verified native prepared pages."""
import json
from pathlib import Path

from PIL import Image, ImageChops

from .display import DISPLAY_SHIFT
from .native_probe import symbols
from .native_sprites import published_actors
from .raster_scroll import bordered, palette_rgb
from src.toolchain.scenes.bundle import digest, verify_manifest


def compose(vram, hud, page, palette, fuel_colors, life_colors, *, actor_sprites=None):
    """Decode bitmap addressing and mode-2 HUD priority in screen coordinates.

    Source-to-bitmap correctness is a separate exhaustive prepared-page gate.
    This checks actual scanout: header split, scrolling, sprites and full border.
    """
    if (len(vram) != 131072 or len(hud) != 1140 or page not in (0, 1)
            or len(palette) != 32 or len(fuel_colors) != 48 or len(life_colors) != 48):
        raise ValueError('Incomplete native raster inputs')
    pixels = bytearray(256*212)
    high, low, sy = hud[0x1a:0x1d]
    # R26/R27 encode the complete bitmap displacement, including its fine phase.
    sx = ((high*8-low) & 255)
    def bitmap(base, x, y):
        value = vram[base+y*128+x//2]
        return (value >> (0 if x & 1 else 4)) & 15
    extra_attrs = extra_colors = b''
    slots = 17
    if actor_sprites is not None:
        if actor_sprites.get('supported') is not True:
            raise ValueError('Unsupported hardware actor frame')
        extra_attrs, extra_colors = actor_sprites['attributes'], actor_sprites['colors']
        slots += actor_sprites['slots']
        vram = bytearray(vram)
        data = actor_sprites['patterns']
        for at in range(actor_sprites['slots']):
            target = 0x1f800+(extra_attrs[at*4+2] & 252)*8
            vram[target:target+32] = data[at*32:(at+1)*32]
    sat = hud[0x100:0x144]+extra_attrs+bytes((216,))
    footer = sat[:56]+hud[0x290:0x29c]+extra_attrs+bytes((216,))
    colors = vram[0x1f400:0x1f4e0]
    for y in range(212):
        if y < 8:
            for x in range(256):
                pixels[y*256+x] = bitmap(0x18000, x, y)
        elif y >= 11:
            for x in range(8, 256):
                pixels[y*256+x] = bitmap(page*32768, (x+sx) & 255, (y+sy) & 255)
            row_sat = footer if y >= 176 else sat
            row_colors = colors+(life_colors if y >= 176 else fuel_colors)+extra_colors
            sprites = []
            for slot in range(slots):
                at = slot*4
                ay, ax, pattern = row_sat[at:at+3]
                if ay == 216:
                    break
                dy = ((y+sy)-(ay+1)) & 255
                if dy < 16:
                    sprites.append((slot, ax, pattern, dy))
            # CC planes combine within the preceding CC=0 group; group priority
            # remains first-sprite-wins. Transparent entries still count to eight.
            groups = []
            for slot, ax, pattern, dy in sprites[:8]:
                color = row_colors[slot*16+dy]
                if not color & 64:
                    groups.append([])
                if groups:
                    groups[-1].append((ax-(32 if color & 128 else 0), pattern, dy, color & 15))
            for group in reversed(groups):
                ink = {}
                for ax, pattern, dy, color in group:
                    base = 0x1f800+(pattern & 252)*8
                    for dx in range(16):
                        if (8 <= ax+dx < 256 and color and
                                vram[base+dy+(16 if dx >= 8 else 0)] & (128 >> (dx & 7))):
                            ink[ax+dx] = ink.get(ax+dx, 0) | color
                for x, color in ink.items():
                    pixels[y*256+x] = color
    rgb = palette_rgb(palette)
    image = Image.new('RGB', (256, 212))
    image.putdata([rgb[color] for color in pixels])
    shifted = Image.new('RGB', image.size, rgb[0])
    shifted.paste(image, (DISPLAY_SHIFT, 0))
    return bordered(shifted, palette)


def verify_scanout(output: Path, rom: Path):
    """Require every requested capture and compare all 320x240 RGB pixels."""
    verify_manifest(output)
    verify_manifest(rom.parent)
    runtime = json.loads((output/'runtime.json').read_text())
    if runtime.get('candidate_manifest_sha256') != digest(rom.parent/'manifest.json'):
        raise ValueError('Native scanout belongs to a different candidate')
    syms = symbols(rom.parent/'native.sym')
    cartridge = rom.read_bytes()
    fuel_at = syms['sprite_colors']-0x4000+14*16
    life_at = syms['life_colors']-0x4000
    fuel = cartridge[fuel_at:fuel_at+48]
    life = cartridge[life_at:life_at+48]
    palette = (rom.parent/'native-palette.bin').read_bytes()
    hardware = json.loads((rom.parent/'build.json').read_text()).get('hardware_actors', False)
    reports = []
    for boundary in (200, 1100, 1800, 2400):
        name = f'scanout-{boundary}'
        try:
            metadata = json.loads((output/f'{name}.json').read_text())
            frame = metadata['prepared_frame']
            if type(frame) is not int or frame < 1:
                raise ValueError('Invalid scanout frame')
            if (metadata['time']-metadata['active_since'] < .070 or
                    metadata['vdp_frame']-metadata['active_vdp_frame'] < 3):
                raise ValueError('Native scanout did not settle for three VDP frames')
            prefix = f'video-frame-{frame:05d}'
            vram = (output/f'{prefix}-vram.bin').read_bytes()
            hud = (output/f'{prefix}-hud.bin').read_bytes()
            host = (output/f'{prefix}-host.bin').read_bytes()
            actors = published_actors(hud, vram, host[0x16]) if hardware and hud[0x176] else None
            expected = compose(vram, hud, host[0x16], palette, fuel, life, actor_sprites=actors)
            with Image.open(output/f'{name}.png') as capture:
                actual = capture.convert('RGB')
        except (OSError, KeyError, json.JSONDecodeError) as error:
            raise ValueError(f'Missing native scanout evidence: {name}') from error
        if actual.size != expected.size:
            raise ValueError(f'Unexpected native scanout dimensions: {name}')
        difference = ImageChops.difference(actual, expected)
        mismatches = sum(pixel != (0, 0, 0) for pixel in difference.get_flattened_data())
        reports.append(dict(boundary=boundary, prepared_frame=frame,
                            different_pixels=mismatches, bounds=difference.getbbox()))
    return dict(rom_sha256=digest(rom), rendered_rgb_verified=all(
        row['different_pixels'] == 0 for row in reports), captures=reports,
        compared_pixels=len(reports)*320*240, gameplay_verified=False)
