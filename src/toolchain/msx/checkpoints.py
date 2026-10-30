"""Named local test cartridges, bound to immutable ignored build evidence."""
import json
from pathlib import Path
import re
import os
from uuid import uuid4

from src.toolchain.scenes.bundle import digest, verify_manifest
from src.toolchain.scenes.storage import json_write, require_ignored

LATEST_ROM = Path('references/build/latest.rom')


def publish_latest(root, rom):
    """Atomically point the local latest cartridge at an unchanged sealed bundle."""
    root, rom = root.resolve(), rom.resolve()
    build = root/'references/build'
    if not rom.is_relative_to(build) or not rom.is_file():
        raise ValueError('Latest cartridge must be below references/build')
    verify_manifest(rom.parent)
    latest = root/LATEST_ROM
    if latest.is_dir():
        raise ValueError('Latest cartridge path is a directory')
    pending = build/f'.latest-{uuid4().hex}.rom'
    require_ignored(root, [rom, latest, pending])
    try:
        pending.symlink_to(os.path.relpath(rom, build))
        pending.replace(latest)
    finally:
        pending.unlink(missing_ok=True)
    return latest


def resolve_latest(root):
    latest = root/LATEST_ROM
    if not latest.is_file():
        raise ValueError('Latest cartridge missing; run make build NATIVE=1 or make build NO_HUD=1')
    rom = latest.resolve()
    if not rom.is_relative_to((root/'references/build').resolve()):
        raise ValueError('Latest cartridge must be below references/build')
    verify_manifest(rom.parent)
    return rom


def registry_path(root):
    return root/'references/build/checkpoints.json'


def inventory(root):
    path = registry_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
        entries = data['checkpoints']
        if data['schema_version'] != 1 or not isinstance(entries, dict):
            raise ValueError
        for name, entry in entries.items():
            if (not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name)
                    or not isinstance(entry, dict)
                    or set(entry) != {'rom', 'rom_sha256', 'manifest_sha256', 'description', 'kind'}
                    or any(not isinstance(value, str) or not value for value in entry.values())
                    or entry['kind'] not in ('reference', 'diagnostic', 'experimental')):
                raise ValueError
        return entries
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Invalid local checkpoint registry') from error


def resolve(root, name):
    entries = inventory(root)
    if name not in entries:
        raise ValueError(f'Unknown checkpoint: {name}. Run make checkpoints to list available builds.')
    entry = entries[name]
    path = Path(entry['rom'])
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Checkpoint cartridge must be below references/build')
    rom = (root/path).resolve()
    if not rom.is_relative_to((root/'references/build').resolve()) or not rom.is_file():
        raise ValueError(f'Checkpoint cartridge is missing: {name}')
    if digest(rom) != entry['rom_sha256'] or digest(rom.parent/'manifest.json') != entry['manifest_sha256']:
        raise ValueError(f'Checkpoint evidence changed: {name}')
    verify_manifest(rom.parent)
    return rom, entry


def publish(root, name, rom, description, kind='experimental'):
    root, rom = root.resolve(), rom.resolve()
    if (not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name)
            or not isinstance(description, str) or not description.strip()
            or kind not in ('reference', 'diagnostic', 'experimental')):
        raise ValueError('Invalid checkpoint name, description or kind')
    if not rom.is_relative_to(root/'references/build') or not rom.is_file():
        raise ValueError('Checkpoint cartridge must be below references/build')
    require_ignored(root, [rom, registry_path(root)])
    verify_manifest(rom.parent)
    entries = inventory(root)
    entry = dict(rom=rom.relative_to(root).as_posix(), rom_sha256=digest(rom),
                 manifest_sha256=digest(rom.parent/'manifest.json'),
                 description=description.strip(), kind=kind)
    if name in entries and entries[name] != entry:
        raise ValueError(f'Checkpoint name already published: {name}; choose a new name')
    entries[name] = entry
    json_write(registry_path(root), dict(schema_version=1, checkpoints=entries))
    return registry_path(root)
