"""Validate hashed captures and their original graphics provenance."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from decimal import Decimal, InvalidOperation
from PIL import Image
from src.toolchain.graphics.roms import load_metadata


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'Cannot read JSON {path}: {error}') from error


def verify_manifest(path, expected=None):
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Bundle must be a regular directory')
    path = path.resolve()
    manifest = read_json(path/'manifest.json')
    if not isinstance(manifest,dict) or manifest.get('schema_version') != 1 or type(manifest.get('schema_version')) is not int:
        raise ValueError('Unsupported manifest version')
    records = manifest.get('outputs')
    if not isinstance(records, list) or not records:
        raise ValueError('Missing payload inventory')
    names = set()
    for record in records:
        if not isinstance(record,dict):
            raise ValueError('Invalid payload record')
        name = record.get('path', '')
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_./+-]+', name)
                or any(p in ('', '.', '..') for p in name.split('/'))
                or name.startswith('/') or name in names or name == 'manifest.json'):
            raise ValueError('Invalid payload path')
        names.add(name)
        item = path/name
        if any(p.is_symlink() for p in [item, *item.parents]):
            raise ValueError('Symlink in payload path')
        if (not item.is_file() or type(record.get('size')) is not int
                or item.stat().st_size != record['size']
                or digest(item) != record.get('sha256')):
            raise ValueError(f'Payload integrity failure: {name}')
    inventory=list(path.rglob('*'))
    if any(p.is_symlink() for p in inventory):
        raise ValueError('Unlisted symlink in bundle')
    actual = {p.relative_to(path).as_posix() for p in inventory if p.is_file()}
    if actual != names | {'manifest.json'} or (expected is not None and names != expected):
        raise ValueError('Unexpected payload inventory')
    return manifest


@dataclass
class Assets:
    pixels: dict
    palette: dict
    metadata: dict
    manifest: dict
    sha256: str


@dataclass
class Capture:
    state: dict
    video: bytes
    radar: bytes
    reference: Image.Image


def load_assets(path: Path) -> Assets:
    manifest = verify_manifest(path)
    if manifest.get('source') != load_metadata()['source']:
        raise ValueError('Unsupported asset source')
    pixels = {}
    for group, size in [('tiles',16384), ('sprites',16384), ('dots',128)]:
        data = (path/group/'indices.bin').read_bytes()
        if len(data) != size or any(p > 3 for p in data):
            raise ValueError(f'Invalid {group} source pens')
        pixels[group] = data
    palette = read_json(path/'palette.json')
    if (not isinstance(palette,dict) or len(palette.get('rgb',[])) != 32 or len(palette.get('lookup',[])) != 256
            or any(type(p) is not int or not 0 <= p < 16 for p in palette['lookup'])
            or any(not isinstance(c,list) or len(c) != 3 or
                   any(type(v) is not int or not 0 <= v <= 255 for v in c) for c in palette['rgb'])):
        raise ValueError('Invalid asset palette')
    return Assets(pixels, palette, read_json(path/'graphics.json'), manifest, digest(path/'manifest.json'))


def load_capture(path: Path, assets: Assets) -> Capture:
    verify_manifest(path, {'capture.json','video.bin','radar-attributes.bin','reference.png'})
    state = read_json(path/'capture.json')
    if (not isinstance(state,dict) or type(state.get('schema_version')) is not int or state['schema_version'] != 1
            or state.get('set') != 'nrallyx' or state.get('emulator') != '0.289'
            or state.get('source') != load_metadata()['source']
            or state.get('assets_sha256') != assets.sha256
            or state.get('visible') != [0,16,288,240]
            or state.get('phase') != 'vblank-rising-before-irq'
            or state.get('initialized') is not True):
        raise ValueError('Unsupported or incoherent capture provenance/phase')
    for field in ('state_frame','bitmap_frame','reset_generation'):
        if type(state.get(field)) is not int or state[field] < 0:
            raise ValueError(f'Invalid {field}')
    if state['state_frame'] != state['bitmap_frame']:
        raise ValueError('State/bitmap frame mismatch')
    if type(state.get('replay_frame')) is not int or state['replay_frame'] < 1:
        raise ValueError('Missing/invalid replay_frame')
    try:
        if not isinstance(state.get('emulated_time'),str):
            raise ValueError('Missing emulated_time')
        value=state['emulated_time']
        if ',' in value and not re.fullmatch(r'\d+\.\d{3},\d{3},\d{3}',value):
            raise ValueError('Invalid MAME-formatted emulated_time')
        time=Decimal(value.replace(',',''))
        if not time.is_finite() or time<0:
            raise ValueError('Invalid emulated_time')
    except InvalidOperation as error:
        raise ValueError('Invalid emulated_time') from error
    regs = state.get('registers', {})
    if not isinstance(regs,dict):
        raise ValueError('Invalid registers')
    for field, maximum in [('scroll_x',255),('scroll_y',255),('flip',1)]:
        if type(regs.get(field)) is not int or not 0 <= regs[field] <= maximum:
            raise ValueError(f'Invalid/uninitialized register: {field}')
    if (not isinstance(state.get('inputs'),list) or not isinstance(state.get('acquisition'),str)
            or not isinstance(state.get('roms'),list)
            or type(state.get('shadow_factor')) not in (int,float)
            or not 0 <= state['shadow_factor'] <= 1):
        raise ValueError('Missing capture metadata')
    if state['roms'] != assets.manifest['inputs']:
        raise ValueError('Capture ROM provenance differs from assets')
    video, radar = (path/'video.bin').read_bytes(), (path/'radar-attributes.bin').read_bytes()
    if len(video) != 4096 or len(radar) != 16:
        raise ValueError('Invalid capture RAM size')
    with Image.open(path/'reference.png') as image:
        if image.size != (288,224) or image.mode != 'RGB':
            raise ValueError('Reference must be native 288x224 RGB')
        reference = image.copy()
    return Capture(state, video, radar, reference)
