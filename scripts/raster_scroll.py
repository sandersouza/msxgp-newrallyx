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
    parser.add_argument('command', choices=('build', 'run', 'verify', 'verify-hud', 'verify-player', 'verify-hud-cost','verify-rock-collision','verify-rock-route','verify-death','verify-death-copies','verify-flag-copies','verify-flags','verify-flag-route','verify-score','verify-fuel','verify-lives','verify-life-route','verify-enemy','verify-enemy-presentation','verify-enemy-route','verify-player-blitter-cost','verify-radar-blitter-cost','verify-bitmap-blitters','verify-sprite-flicker','verify-flicker-stress','verify-enemy-radar-pair','verify-radar-cells','verify-sprite-upload','verify-radar-base','verify-solid-runs','verify-tile-strips','verify-smoke','verify-smoke-route','verify-smoke-flags','verify-smoke-copies','verify-completion','verify-completion-route','verify-parameters','verify-session','verify-session-inputs','verify-hud-alerts','verify-steering','verify-lucky-route'))
    parser.add_argument('--output', type=Path, required=True, help='Fresh output directory')
    parser.add_argument('--rom', type=Path, default=Path('references/build/newrallyx.rom'))
    parser.add_argument('--normal', type=Path, default=Path('references/scenes/rom-input/normal'))
    parser.add_argument('--overlap', type=Path, default=Path('references/scenes/rom-input/overlap'))
    parser.add_argument('--assets', type=Path, default=Path('references/assets/nrallyx'))
    parser.add_argument('--captures', type=Path, default=Path('references/scenes/review-fixed-v3'))
    parser.add_argument('--hz', type=int, choices=(50, 60), default=50)
    parser.add_argument('--logic-hz', type=int, choices=(55,60), help='Stage10/11 temporal diagnostic; preserve original graphics and rules at an explicit slower tick rate')
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
    parser.add_argument('--radar-blitter', action='store_true', help='Experimental blue 48x80 bitmap radar with an independent blinking player sprite')
    parser.add_argument('--sprite-flicker', action='store_true', help='Stage09 two-enemy priority rotation; keep VDP sprite limits enabled')
    parser.add_argument('--outline-flicker', action='store_true', help='Stage09 body-first independent car outlines and rotating sprite radar')
    parser.add_argument('--flicker-stress', action='store_true', help='Boot paused with two original enemy graphics aligned over the radar')
    parser.add_argument('--cache-columns', type=int, choices=(36,40,48,64), help='Diagnostic cache width; visible viewport remains unchanged')
    parser.add_argument('--stage', type=int, choices=range(13), default=0, help='Incremental stage 0..12: baseline through single-player sessions')
    parser.add_argument('--enemies', type=int, choices=range(9), help='Explicit diagnostic enemy population')
    parser.add_argument('--enemy-planes', type=int, choices=(1,2), help='Population diagnostic: red silhouette or original two-plane colors')
    parser.add_argument('--separate-radar-points', action='store_true', help='Stage09 diagnostic: retain the old independent point sprites')
    parser.add_argument('--enemy-logic-only', action='store_true', help='Stage 08 control without enemy graphics/contact effects')
    parser.add_argument('--smoke-component', action='store_true', help='Link original smoke/expiry logic for an isolated proof; no gameplay smoke yet')
    parser.add_argument('--completion-component', action='store_true', help='Link bounded remaining-fuel completion converter for isolated original proof')
    parser.add_argument('--round-component', action='store_true', help='Stage12 isolated original next-round preparation proof; gameplay transitions stay bounded')
    parser.add_argument('--full-game', action='store_true', help='Development complete-game integration with dynamic original rounds')
    parser.add_argument('--smoke-stress', action='store_true', help='Repeat Space smoke during the steering regression, or extend the stage10 smoke route with firing and rock death/restart')
    parser.add_argument('--natural-game-over', action='store_true', help='Session proof waits for all three real enemy deaths before its isolated UI edge cases')
    parser.add_argument('--lucky-first', action='store_true', help='Completion route collects L first to stress its fuel bonus and header split')
    parser.add_argument('--enemy-render-only', action='store_true', help='Stage 08 diagnostic: render enemies without applying their contact to lives')
    parser.add_argument('--rock-focus', action='store_true', help='Verify keyboard edge/clipping/cache-eviction routes at each original rock')
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify-steering':
            from scripts.msx.steering_verify import verify
            verify(root,args)
        elif args.command == 'verify-lucky-route':
            from scripts.msx.completion_route_verify import verify
            verify(root,args)
        elif args.command == 'verify-hud-alerts':
            from scripts.msx.hud_alerts_verify import verify
            verify(root,args)
        elif args.command == 'verify-session-inputs':
            from scripts.msx.session_inputs_verify import verify
            verify(root,args)
        elif args.command == 'verify-session':
            from scripts.msx.session_verify import verify
            verify(root,args)
        elif args.command == 'verify-completion-route':
            from scripts.msx.completion_route_verify import verify
            verify(root,args)
        elif args.command == 'verify-smoke-copies':
            from scripts.msx.death_copy_verify import verify
            verify(root,args,kind='smoke')
        elif args.command == 'verify-parameters':
            from scripts.msx.parameters_verify import verify
            verify(root,args)
        elif args.command == 'verify-completion':
            from scripts.msx.fuel_verify import verify
            verify(root,args)
        elif args.command == 'verify-smoke-flags':
            from scripts.msx.smoke_flag_verify import verify
            verify(root,args)
        elif args.command == 'verify-smoke-route':
            from scripts.msx.smoke_route_verify import verify
            verify(root,args)
        elif args.command == 'verify-smoke':
            from scripts.msx.smoke_verify import verify
            verify(root,args)
        elif args.command == 'verify-sprite-upload':
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
            if read_json(args.rom.parent/'build.json').get('enemy_count',0)>1:
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
