#!/usr/bin/env python3
"""Explicit native experiments and strict evidence checks; never publish a default ROM."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.msx.native_build import build_probe
from scripts.msx.native_probe import verify_probe
from scripts.msx.native_verify import capture_reference, acquire, verify_reset
from scripts.msx.native_compare import compare_acquisition

ROOT = Path(__file__).resolve().parents[1]


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command',required=True)
    reference = commands.add_parser('reference',help='Capture a fresh unmodified arcade replay')
    reference.add_argument('--output',type=Path,required=True)
    reference.add_argument('--frames',type=int,default=3200)
    reference.add_argument('--replay',type=Path)
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
    build.add_argument('--assets',type=Path,default=ROOT/'references/assets/nrallyx')
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
        elif a.command == 'build-probe':
            result = build_probe(ROOT,a.output,a.assembler,a.hz,probe=a.mode,
                reset_reference=a.reference,optimize=a.coordinate_table,
                function_probe=a.function_proof,fine_irq=a.fine_irq,
                video_reference=a.video_reference,assets_path=a.assets,
                execution_references=tuple(a.execution_reference))
        elif a.command == 'acquire':
            result = acquire(ROOT,a)
        elif a.command == 'verify-reset':
            result = verify_reset(ROOT,a.rom,a.output,a.bios,a.reference,machine=a.machine,openmsx=a.openmsx)
        elif a.command == 'verify-probe':
            result = verify_probe(ROOT,a.rom,a.output,a.bios,machine=a.machine,openmsx=a.openmsx,
                host_segment=a.host_segment,small_memory=a.small_memory)
        elif a.command == 'run':
            from scripts.scenes.bundle import verify_manifest
            from scripts.msx.emulator import run
            verify_manifest(a.rom.parent)
            report = json.loads((a.rom.parent/'build.json').read_text())
            if a.rom.name != 'native.rom' or report.get('mode') != 'logic-probe':
                raise ValueError('Require a sealed original-logic native candidate')
            run(ROOT,a)
            result = a.output
        elif a.command == 'verify-inputs':
            from scripts.msx.native_inputs import verify_inputs
            result = verify_inputs(ROOT,a)
        else:
            result = compare_acquisition(ROOT,a.rom.parent,a.capture,a.reference,a.output)
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(f'Native check failed: {error}',file=sys.stderr)
        return 1
    print(str(result) if isinstance(result,Path) else json.dumps(result,sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
