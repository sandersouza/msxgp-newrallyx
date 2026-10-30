#!/usr/bin/env python3
"""Build the default development ROM or launch it in an isolated openMSX session."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.toolchain.msx.build import destination
from src.toolchain.msx.raster_scroll import build as build_rom
from src.toolchain.msx.emulator import run as run_emulator
from src.toolchain.scenes.storage import require_ignored, json_write
from src.toolchain.msx.checkpoints import inventory, resolve, publish_latest, resolve_latest


ROM = Path('dist/newrallyx.rom')


def build_renderer(root, output, *, no_hud=False, stage=0, player_blitter=False,radar_blitter=False,hz=50,sprite_flicker=False,flicker_stress=False,outline_flicker=False,enemies=None,full_game=False,audio=False,no_flag_popups=False):
    from src.toolchain.graphics.canonical import promote
    promote(root)
    args = argparse.Namespace(
        output=output, hz=hz, no_hud=no_hud, stage=stage,
        player_blitter=player_blitter,radar_blitter=radar_blitter,
        sprite_flicker=sprite_flicker,flicker_stress=flicker_stress,
        outline_flicker=outline_flicker,
        enemies=enemies,full_game=full_game,audio=audio,no_flag_popups=no_flag_popups,
        cache_columns=48 if player_blitter else None,
        assets=root/'assets/arcade/nrallyx',
        captures=root/'assets/arcade/scenes/captures',
        normal=root/'assets/arcade/scenes/normal',
        overlap=root/'assets/arcade/scenes/overlap',
        assembler=root/'.tools/sjasmplus/1.24.0/sjasmplus',
    )
    return build_rom(root, args)


def build(root, *, no_hud=False, native=False, stage=12,player_blitter=False,radar_blitter=False,hz=None,sprite_flicker=False,flicker_stress=False,outline_flicker=False,enemies=None,full_game=False,audio=False,no_flag_popups=False):
    """Build a selected-routine cartridge, optionally with complete progression.

    The legacy native switch is a compatibility alias for this active baseline.
    """
    if hz is None:hz=60 if full_game else 50
    output = destination(root, root/'references/build'/f'default-{uuid4().hex}')
    output.parent.mkdir(parents=True,exist_ok=True)
    rom = root/'dist/legacy/newrallyx.rom'
    rom.parent.mkdir(parents=True,exist_ok=True)
    if rom.is_symlink() or (rom.exists() and not rom.is_file()):
        raise ValueError(f'Default ROM must be a regular file: {rom}')
    pending = output.with_suffix('.rom.tmp')
    require_ignored(root, [rom, pending])
    built_rom = build_renderer(root, output, no_hud=no_hud, stage=stage,
                              player_blitter=player_blitter,radar_blitter=radar_blitter,
                              hz=hz,sprite_flicker=sprite_flicker,flicker_stress=flicker_stress,outline_flicker=outline_flicker,enemies=enemies,full_game=full_game,audio=audio,no_flag_popups=no_flag_popups)
    # Keep the sealed bundle unchanged; publish a separate, stable ROM path.
    try:
        shutil.copyfile(built_rom, pending)
        pending.replace(rom)
    finally:
        pending.unlink(missing_ok=True)
    from src.toolchain.msx.resource_assets import publish as publish_resources
    publish_resources(root,rom,'legacy')
    latest = publish_latest(root, built_rom)
    json_write(rom.parent/'manifest.json',dict(rom=rom.relative_to(root).as_posix(),
        rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),bytes=rom.stat().st_size,
        mapper='ASCII16',presenter='Preserved legacy SCREEN5',minimum_mapper_ram_kib=128,
        source_bundle=str(built_rom.parent),status='Legacy comparison cartridge'))
    print(f'Default ROM: {rom.relative_to(root)}')
    print(f'Stage {stage:02d} (HUD {"off" if no_hud else "on"}); latest: {latest.relative_to(root)}')
    return built_rom


def run(root, rom=ROM, checkpoint=None, latest=False):
    if latest:
        if checkpoint is not None or rom != ROM:
            raise ValueError('Choose only one of latest, checkpoint or ROM')
        rom = resolve_latest(root)
    if checkpoint is not None:
        rom, entry = resolve(root, checkpoint)
        print(f'Checkpoint: {checkpoint} ({entry["kind"]}) - {entry["description"]}', flush=True)
    args = argparse.Namespace(
        rom=root/rom, output=root/'references/sessions'/f'openmsx-{uuid4().hex}',
        bios=root/'references/msxbios', machine='Panasonic_FS-A1WSX', openmsx='openmsx',
    )
    print(f'Running ROM: {args.rom}', flush=True)
    run_emulator(root, args)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'run', 'checkpoints'))
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--rom', type=Path, default=ROM, help='Cartridge to launch with run')
    selection.add_argument('--checkpoint', help='Named local test cartridge; list with make checkpoints')
    selection.add_argument('--latest', action='store_true', help='Launch references/build/latest.rom')
    parser.add_argument('--no-hud', action='store_true', help='Build the active incremental baseline without HUD')
    parser.add_argument('--player-blitter', action='store_true', help='Stage 00/01 diagnostic: bitmap player, no player sprites')
    parser.add_argument('--radar-blitter', action='store_true', help='Slow full-copy blue 48x80 radar diagnostic; requires --player-blitter')
    parser.add_argument('--sprite-flicker', action='store_true', help='Stage09 two-enemy priority rotation experiment')
    parser.add_argument('--outline-flicker', action='store_true', help='Independent body/outline priority experiment with sprite radar')
    parser.add_argument('--flicker-stress', action='store_true', help='Paused original-graphics stress fixture')
    parser.add_argument('--hz', type=int, choices=(50,60), help='VDP refresh; defaults to60 for full gameplay,50 for bounded stages; original tick remains16.5ms')
    parser.add_argument('--native', action='store_true', help='Compatibility alias: selected-player baseline, no full arcade loop')
    parser.add_argument('--full-game',action='store_true',help='Stage12 full gameplay, original round progression and two-player sessions')
    parser.add_argument('--no-flag-popups',action='store_true',help='Compile out flag-local point inscriptions')
    parser.add_argument('--audio',action='store_true',help='Buffered three-voice PSG music, tonal effects and hardware-envelope engine; requires --full-game')
    parser.add_argument('--stage', type=int, choices=range(13), default=12, help='Incremental stage 0..12; default: approved single-player session')
    parser.add_argument('--enemies', type=int, choices=range(4), help='Explicit enemy population: stage08 supports one; stage09 supports up to three')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == 'run':
            run(root, args.rom, args.checkpoint, args.latest)
        elif args.command == 'checkpoints':
            entries = inventory(root)
            if not entries:
                print('No local checkpoints. They are published as test builds become available.')
            for name, entry in entries.items():
                print(f'{name:24} {entry["kind"]:13} {entry["description"]}')
        else:
            build(root, no_hud=args.no_hud, native=args.native, stage=args.stage,
                  player_blitter=args.player_blitter,radar_blitter=args.radar_blitter,
                  hz=args.hz,sprite_flicker=args.sprite_flicker,flicker_stress=args.flicker_stress,outline_flicker=args.outline_flicker,enemies=args.enemies,full_game=args.full_game,audio=args.audio,no_flag_popups=args.no_flag_popups)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
