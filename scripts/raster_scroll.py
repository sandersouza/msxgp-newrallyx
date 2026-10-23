#!/usr/bin/env python3
"""Build, run or verify the full-screen hardware-scroll diagnostic."""
import argparse
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.msx.raster_scroll import build
from scripts.msx.emulator import run


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'run', 'verify', 'verify-hud', 'verify-player', 'verify-hud-cost','verify-rock-collision','verify-rock-route','verify-death','verify-death-copies','verify-flag-copies','verify-flags','verify-flag-route','verify-score','verify-fuel','verify-lives','verify-life-route','verify-enemy','verify-enemy-presentation','verify-enemy-route','verify-player-blitter-cost','verify-radar-blitter-cost','verify-bitmap-blitters','verify-sprite-flicker','verify-flicker-stress','verify-enemy-radar-pair','verify-radar-cells','verify-sprite-upload','verify-radar-base','verify-solid-runs','verify-tile-strips'))
    parser.add_argument('--output', type=Path, required=True, help='Fresh output directory')
    parser.add_argument('--rom', type=Path, default=Path('references/build/newrallyx.rom'))
    parser.add_argument('--normal', type=Path, default=Path('references/scenes/rom-input/normal'))
    parser.add_argument('--overlap', type=Path, default=Path('references/scenes/rom-input/overlap'))
    parser.add_argument('--assets', type=Path, default=Path('references/assets/nrallyx'))
    parser.add_argument('--captures', type=Path, default=Path('references/scenes/review-fixed-v3'))
    parser.add_argument('--hz', type=int, choices=(50, 60), default=50)
    parser.add_argument('--assembler', type=Path, default=root/'.tools/sjasmplus/1.24.0/sjasmplus')
    parser.add_argument('--bios', type=Path, default=Path('references/msxbios'))
    parser.add_argument('--machine', default='Panasonic_FS-A1WSX')
    parser.add_argument('--openmsx', default='openmsx')
    parser.add_argument('--headless', action='store_true', help='Verify player RAM/timing without a display or RGB captures')
    parser.add_argument('--no-hud', action='store_true', help='Build the selected-player baseline without HUD updates')
    parser.add_argument('--simple-maze', action='store_true', help='Stage09 diagnostic: merge blue terrain outlines into wall color; preserve object graphics')
    parser.add_argument('--tile-mode', action='store_true', help='SCREEN 4 stage00/01 driving prototype with explicit two-color scenery rows')
    parser.add_argument('--radar-quantum', type=int, choices=(1,2), default=1, help='Stage09 strip diagnostic: snap radar points to this pixel grid; game coordinates unchanged')
    parser.add_argument('--tile-strips', action='store_true', help='Stage09 diagnostic: exact three-tile VDP copies; preserve original scenery colors')
    parser.add_argument('--player-blitter', action='store_true', help='Experimental bitmap player with exact save-under restoration')
    parser.add_argument('--radar-blitter', action='store_true', help='Diagnostic full-copy blue 48x80 bitmap radar; requires --player-blitter')
    parser.add_argument('--sprite-flicker', action='store_true', help='Stage09 two-enemy priority rotation; keep VDP sprite limits enabled')
    parser.add_argument('--flicker-stress', action='store_true', help='Boot paused with two original enemy graphics aligned over the radar')
    parser.add_argument('--cache-columns', type=int, choices=(36,40,48,64), help='Diagnostic cache width; visible viewport remains unchanged')
    parser.add_argument('--stage', type=int, choices=range(10), default=0, help='Incremental stage 0..9: baseline through enemy population diagnostics')
    parser.add_argument('--enemies', type=int, choices=range(9), help='Explicit diagnostic enemy population')
    parser.add_argument('--enemy-planes', type=int, choices=(1,2), help='Population diagnostic: red silhouette or original two-plane colors')
    parser.add_argument('--separate-radar-points', action='store_true', help='Stage09 diagnostic: retain the old independent point sprites')
    parser.add_argument('--enemy-logic-only', action='store_true', help='Stage 08 control without enemy graphics/contact effects')
    parser.add_argument('--enemy-render-only', action='store_true', help='Stage 08 diagnostic: render enemies without applying their contact to lives')
    parser.add_argument('--rock-focus', action='store_true', help='Verify keyboard edge/clipping/cache-eviction routes at each original rock')
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify-sprite-upload':
            from scripts.msx.sprite_upload_verify import verify
            verify(root,args)
        elif args.command in ('verify-radar-cells','verify-radar-base'):
            args.radar_base=args.command=='verify-radar-base'
            from scripts.msx.radar_cells_verify import verify
            verify(root,args)
        elif args.command == 'verify-flicker-stress':
            from scripts.msx.flicker_stress_verify import verify
            verify(root,args)
        elif args.command == 'verify-sprite-flicker':
            from scripts.msx.sprite_flicker_verify import verify
            verify(root,args)
        elif args.command == 'verify-bitmap-blitters':
            from scripts.msx.bitmap_blitter_verify import verify
            verify(root,args)
        elif args.command == 'verify-enemy-radar-pair':
            from scripts.msx.radar_pair_verify import verify
            verify(root,args)
        elif args.command in ('verify-player-blitter-cost','verify-radar-blitter-cost'):
            from scripts.msx.player_blitter_verify import verify
            verify(root,args,radar=args.command=='verify-radar-blitter-cost')
        elif args.command == 'verify-flag-copies':
            from scripts.msx.death_copy_verify import verify
            verify(root,args,kind='flags')
        elif args.command == 'verify-solid-runs':
            from scripts.msx.solid_run_verify import verify
            verify(root,args)
        elif args.command == 'verify-tile-strips':
            from scripts.msx.tile_strip_verify import verify
            verify(root,args)
        elif args.command == 'verify-enemy-route':
            from scripts.msx.enemy_route_verify import verify
            verify(root,args)
        elif args.command == 'verify-enemy-presentation':
            from scripts.scenes.bundle import read_json
            if read_json(args.rom.parent/'build.json').get('enemy_count')==2:
                from scripts.msx.enemy_population_verify import verify
            else:
                from scripts.msx.enemy_presentation_verify import verify
            verify(root,args)
        elif args.command == 'verify-enemy':
            from scripts.msx.enemy_verify import verify
            verify(root,args)
        elif args.command == 'verify-life-route':
            from scripts.msx.lives_route_verify import verify
            verify(root,args)
        elif args.command == 'verify-lives':
            from scripts.msx.lives_verify import verify
            verify(root,args)
        elif args.command == 'verify-death-copies':
            from scripts.msx.death_copy_verify import verify
            verify(root,args)
        elif args.command == 'verify-fuel':
            from scripts.msx.fuel_verify import verify
            verify(root,args)
        elif args.command == 'verify-score':
            from scripts.msx.score_verify import verify
            verify(root,args)
        elif args.command == 'verify-flag-route':
            from scripts.msx.flag_route_verify import verify
            verify(root,args)
        elif args.command == 'verify-flags':
            from scripts.msx.flags_verify import verify
            verify(root,args)
        elif args.command == 'verify-death':
            from scripts.msx.death_verify import verify
            verify(root,args)
        elif args.command == 'verify-rock-route':
            from scripts.msx.rock_route_verify import verify
            verify(root,args)
        elif args.command == 'verify-rock-collision':
            from scripts.msx.rock_collision_verify import verify
            verify(root,args)
        elif args.command == 'verify-hud-cost':
            from scripts.msx.hud_verify import measure_attributes
            measure_attributes(root,args)
        elif args.command == 'verify-player':
            from scripts.msx.player_verify import verify
            verify(root,args)
        elif args.command == 'verify-hud':
            from scripts.msx.hud_verify import verify
            verify(root,args)
        elif args.command == 'verify':
            from scripts.msx.raster_verify import verify
            verify(root, args)
        else:
            (build if args.command == 'build' else run)(root, args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
