#!/usr/bin/env python3
"""Explicit native experiments and strict evidence checks; never publish a default ROM."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))

from src.toolchain.msx.native_build import build_probe
from src.toolchain.msx.native_probe import verify_probe
from src.toolchain.msx.native_verify import capture_reference, acquire, verify_reset
from src.toolchain.msx.native_compare import compare_acquisition

ROOT = Path(__file__).resolve().parents[3]


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command',required=True)
    reference = commands.add_parser('reference',help='Capture a fresh unmodified arcade replay')
    reference.add_argument('--output',type=Path,required=True)
    reference.add_argument('--frames',type=int,default=3200)
    reference.add_argument('--replay',type=Path)
    checkpoint = commands.add_parser('checkpoint', help='Publish an immutable name for an existing sealed local test cartridge')
    checkpoint.add_argument('--name', required=True)
    checkpoint.add_argument('--rom', type=Path, required=True)
    checkpoint.add_argument('--description', required=True)
    checkpoint.add_argument('--kind', choices=('reference', 'diagnostic', 'experimental'), default='experimental')
    build = commands.add_parser('build-probe',help='Build an explicit headless/synthetic probe, never gameplay')
    build.add_argument('--mode',choices=('loader','runtime','irq','reset','logic'),required=True)
    build.add_argument('--output',type=Path,required=True)
    build.add_argument('--assembler',type=Path,default=ROOT/'.tools/sjasmplus/1.24.0/sjasmplus')
    build.add_argument('--hz',type=int,choices=(50,60),default=50)
    build.add_argument('--reference',type=Path,help='Sealed arcade evidence, required for reset/logic')
    build.add_argument('--coordinate-table',action='store_true',help='Experimental equivalent coordinate arithmetic')
    build.add_argument('--function-proof',action='store_true',help='Exhaustive function proof before original reset')
    build.add_argument('--fine-irq',action='store_true',help='Experimental scanline deadline clock')
    build.add_argument('--video-reference',type=Path,help='Explicit sealed renderer bundle for the live video candidate')
    build.add_argument('--hardware-actors',action='store_true',help='Experimental hardware actor renderer; explicit video candidate only')
    build.add_argument('--no-hud',action='store_true',help='Compile out HUD/radar preparation, drawing and raster uploads for comparison')
    build.add_argument('--no-actors',action='store_true',help='Scenery-only benchmark: retain all game rules, omit actor presentation')
    build.add_argument('--freeze-presentation',action='store_true',help='Timing benchmark: prepare one page, then run all logic without further rendering')
    build.add_argument('--foreground-render-only',action='store_true',help='Timing experiment: keep rendering out of the logical game IRQ')
    build.add_argument('--no-edge-clear',action='store_true',help='Diagnostic: omit the right-edge repair to measure its restoration cost')
    build.add_argument('--tick-foreground',action='store_true',help='Scheduling experiment: one original foreground pass per logical tick while game IRQs are enabled')
    build.add_argument('--actor-cache',action='store_true',help='Reuse exact unclipped hardware actor patterns across prepared frames')
    build.add_argument('--assets',type=Path,default=ROOT/'assets/arcade/nrallyx')
    build.add_argument('--execution-reference',type=Path,action='append',default=[],help='Supplemental sealed source execution for additional branches')
    run = commands.add_parser('run', help='Launch a sealed native candidate in an isolated emulator session')
    run.add_argument('--rom',type=Path,required=True)
    run.add_argument('--output',type=Path,required=True)
    run.add_argument('--bios',type=Path,default=ROOT/'references/msxbios')
    run.add_argument('--machine',default='Panasonic_FS-A1WSX')
    run.add_argument('--openmsx',default='openmsx')
    inputs = commands.add_parser('verify-inputs', help='Verify keyboard matrix and emulated joystick hardware adapters')
    inputs.add_argument('--rom',type=Path,required=True)
    inputs.add_argument('--reference',type=Path,required=True)
    inputs.add_argument('--output',type=Path,required=True)
    inputs.add_argument('--bios',type=Path,default=ROOT/'references/msxbios')
    inputs.add_argument('--machine',default='Panasonic_FS-A1WSX')
    inputs.add_argument('--openmsx',default='openmsx')
    actors = commands.add_parser('verify-actor-sprites', help='Verify isolated hardware actor fixtures; no runtime integration claim')
    actors.add_argument('--rom',type=Path,required=True)
    actors.add_argument('--capture',type=Path,required=True)
    actors.add_argument('--output',type=Path,required=True)
    actors.add_argument('--frames',nargs='+',type=int,required=True)
    actors.add_argument('--bios',type=Path,default=ROOT/'references/msxbios')
    actors.add_argument('--machine',default='Panasonic_FS-A1WSX')
    actors.add_argument('--openmsx',default='openmsx')
    for name in ('acquire','verify-reset','verify-probe'):
        c = commands.add_parser(name)
        c.add_argument('--rom',type=Path,required=True)
        c.add_argument('--output',type=Path,required=True)
        c.add_argument('--bios',type=Path,default=ROOT/'references/msxbios')
        c.add_argument('--machine',default='Panasonic_FS-A1WSX')
        c.add_argument('--openmsx',default='openmsx')
        if name != 'verify-probe':
            c.add_argument('--reference',type=Path,required=True)
        if name == 'acquire':
            c.add_argument('--hz',type=int,choices=(50,60),required=True)
            c.add_argument('--ticks',type=int)
            c.add_argument('--profile',nargs=2,type=int,metavar=('START','END'))
            c.add_argument('--scanout',action='store_true',help='Capture actual raster screenshots with the display renderer')
            c.add_argument('--input-proof',action='store_true',help='Exercise keyboard matrix adapter separately from logical replay')
        if name == 'verify-probe':
            c.add_argument('--host-segment',type=int)
            c.add_argument('--small-memory',action='store_true')
    compare = commands.add_parser('compare',help='Strict complete-byte offline replay check; divergence exits nonzero')
    compare.add_argument('--rom',type=Path,required=True)
    compare.add_argument('--capture',type=Path,required=True)
    compare.add_argument('--reference',type=Path,required=True)
    compare.add_argument('--output',type=Path,required=True)
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        if a.command == 'reference':
            result = capture_reference(ROOT,a.output,frames=a.frames,replay_path=a.replay)
        elif a.command == 'checkpoint':
            from src.toolchain.msx.checkpoints import publish
            result = publish(ROOT, a.name, a.rom, a.description, a.kind)
        elif a.command == 'build-probe':
            result = build_probe(ROOT,a.output,a.assembler,a.hz,probe=a.mode,
                reset_reference=a.reference,optimize=a.coordinate_table,
                function_probe=a.function_proof,fine_irq=a.fine_irq,
                video_reference=a.video_reference,assets_path=a.assets,
                execution_references=tuple(a.execution_reference),hardware_actors=a.hardware_actors,
                hud_enabled=not a.no_hud, actors_enabled=not a.no_actors,
                freeze_presentation=a.freeze_presentation,
                render_in_game_irq=not a.foreground_render_only, edge_clear=not a.no_edge_clear,
                tick_foreground=a.tick_foreground, actor_cache=a.actor_cache)
        elif a.command == 'acquire':
            result = acquire(ROOT,a)
        elif a.command == 'verify-reset':
            result = verify_reset(ROOT,a.rom,a.output,a.bios,a.reference,machine=a.machine,openmsx=a.openmsx)
        elif a.command == 'verify-probe':
            result = verify_probe(ROOT,a.rom,a.output,a.bios,machine=a.machine,openmsx=a.openmsx,
                host_segment=a.host_segment,small_memory=a.small_memory)
        elif a.command == 'run':
            from src.toolchain.scenes.bundle import verify_manifest
            from src.toolchain.msx.emulator import run
            verify_manifest(a.rom.parent)
            report = json.loads((a.rom.parent/'build.json').read_text())
            if a.rom.name != 'native.rom' or report.get('mode') != 'logic-probe':
                raise ValueError('Require a sealed original-logic native candidate')
            run(ROOT,a)
            result = a.output
        elif a.command == 'verify-inputs':
            from src.toolchain.msx.native_inputs import verify_inputs
            result = verify_inputs(ROOT,a)
        elif a.command == 'verify-actor-sprites':
            from src.toolchain.msx.native_sprite_probe import verify_actor_sprites
            result = verify_actor_sprites(ROOT,a.rom,a.capture,a.output,a.bios,
                frames=a.frames,openmsx=a.openmsx,machine=a.machine)
        else:
            result = compare_acquisition(ROOT,a.rom.parent,a.capture,a.reference,a.output)
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(f'Native check failed: {error}',file=sys.stderr)
        return 1
    print(str(result) if isinstance(result,Path) else json.dumps(result,sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
