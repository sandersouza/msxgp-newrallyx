"""Validate contributor ROMs against pinned public metadata, without mutation."""
import hashlib
import json
from pathlib import Path
import re
import zlib


def load_metadata() -> dict:
    metadata = json.loads(Path(__file__).with_name('nrallyx.json').read_text())
    if (not isinstance(metadata, dict) or metadata.get('set') != 'nrallyx'
            or metadata.get('schema_version') != 1
            or not isinstance(metadata.get('source'), dict)
            or not isinstance(metadata['source'].get('commit'), str)
            or not isinstance(metadata.get('roms'), list)
            or not metadata['roms']
            or any(not isinstance(record, dict) or 'region' not in record
                   or 'loads' not in record for record in metadata['roms'])):
        raise ValueError('Invalid bundled nrallyx metadata schema/source')
    return metadata


def input_records(roms: dict[str, bytes]) -> list[dict]:
    return [{'name': name, 'size': len(data),
             'crc32': f'{zlib.crc32(data):08x}',
             'sha1': hashlib.sha1(data).hexdigest()}
            for name, data in sorted(roms.items())]


def validate_roms(input_dir: Path, metadata: dict) -> dict[str, bytes]:
    if input_dir.is_symlink() or not input_dir.is_dir():
        raise ValueError(f'Input must be an unpacked ROM directory: {input_dir}')
    result = {}
    if not isinstance(metadata, dict):
        raise ValueError('Invalid ROM inventory: expected an object')
    records = metadata.get('roms')
    if not isinstance(records, list) or not records:
        raise ValueError('Invalid ROM inventory: expected nonempty roms list')
    for entry in records:
        if not isinstance(entry, dict):
            raise ValueError('Invalid ROM inventory record')
        name, size = entry.get('name'), entry.get('size')
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', name)
                or name in ('.', '..') or name in result
                or type(size) is not int or size <= 0):
            raise ValueError(f'Invalid ROM inventory filename/size: {name!r}')
        for key, digits in (('crc32', 8), ('sha1', 40)):
            if not isinstance(entry.get(key), str) or not re.fullmatch(
                    f'[0-9a-f]{{{digits}}}', entry[key]):
                raise ValueError(f'Invalid {key} metadata for {name}')
        if 'region' in entry or 'loads' in entry:
            loads = entry.get('loads')
            if (entry.get('region') not in ('maincpu','gfx1','gfx2','proms','namco')
                    or not isinstance(loads, list) or not loads):
                raise ValueError(f'Invalid region/load metadata for {name}')
            expected_offset = 0
            for load in loads:
                if (not isinstance(load, dict)
                        or any(type(load.get(key)) is not int for key in
                               ('file_offset','region_offset','size'))
                        or load['file_offset'] != expected_offset
                        or load['region_offset'] < 0 or load['size'] <= 0
                        or load['file_offset'] + load['size'] > size):
                    raise ValueError(f'Invalid load segment for {name}')
                expected_offset += load['size']
            if expected_offset != size:
                raise ValueError(f'Load segments do not cover {name}')
        path = input_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing/nonregular ROM {name}: supply the supported nrallyx set')
        with path.open('rb') as stream:
            data = stream.read(size + 1)
        if len(data) != size:
            raise ValueError(f'Wrong size for {name}: expected {size} bytes; supply supported nrallyx ROMs')
        actual = input_records({name: data})[0]
        for key in ('crc32', 'sha1'):
            if actual[key] != entry[key]:
                raise ValueError(f'Corrupt or unsupported ROM {name}: expected {key} {entry[key]}, got {actual[key]}')
        result[name] = data
    return result
