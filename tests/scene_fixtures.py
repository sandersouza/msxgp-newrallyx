"""Generated scene inputs only; no contributor game data."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from graphics_fixtures import synthetic_payload
from src.toolchain.graphics.export import write_payload
from src.toolchain.graphics.roms import load_metadata


def json_write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def seal(path):
    records = []
    for item in sorted(path.iterdir()):
        if item.name != 'manifest.json':
            data = item.read_bytes()
            records.append(dict(path=item.name, size=len(data), sha256=hashlib.sha256(data).hexdigest()))
    json_write(path/'manifest.json', dict(schema_version=1, outputs=records))


def assets_at(path, *, blank=False):
    path.mkdir(parents=True)
    pixels, palette, graphics = synthetic_payload()
    if blank:
        pixels = {name: bytes(len(data)) for name, data in pixels.items()}
    write_payload(path, pixels, palette, graphics, [], load_metadata()['source'])
    return path


def capture_at(path, assets):
    path.mkdir(parents=True)
    state = dict(schema_version=1, set='nrallyx', source=load_metadata()['source'],
        emulator='0.289', roms=[], assets_sha256=hashlib.sha256((assets/'manifest.json').read_bytes()).hexdigest(),
        visible=[0,16,288,240], state_frame=10, bitmap_frame=10,replay_frame=10,
        phase='vblank-rising-before-irq', emulated_time='0.16', reset_generation=0,
        registers=dict(scroll_x=0, scroll_y=0, flip=0), initialized=True,
        shadow_factor=0.6, inputs=[], acquisition='synthetic test')
    json_write(path/'capture.json', state)
    # Tile attribute bit 6 clears the hardware's implicit X flip.
    ram = bytearray(4096)
    ram[0x800:] = bytes([0x40])*2048
    (path/'video.bin').write_bytes(ram)
    (path/'radar-attributes.bin').write_bytes(bytes(16))
    Image.new('RGB', (288,224)).save(path/'reference.png')
    seal(path)
    return path
