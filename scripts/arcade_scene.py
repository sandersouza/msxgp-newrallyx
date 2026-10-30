#!/usr/bin/env python3
"""Capture and reconstruct contributor-supplied New Rally-X scenes locally."""
import argparse
from pathlib import Path
import sys
from PIL import ImageChops

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.toolchain.scenes.bundle import load_assets, load_capture
from src.toolchain.scenes.compare import compare
from src.toolchain.scenes.record import capture_gameplay
from src.toolchain.scenes.render import render
from src.toolchain.scenes.storage import json_write, publish_bundle
from src.toolchain.scenes.bundle import digest
from src.toolchain.scenes.layout import compose
from src.toolchain.scenes.analyze import analyze


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['capture','reconstruct','preview','analyze'])
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--assets',type=Path,default=Path('assets/arcade/nrallyx'))
    parser.add_argument('--capture',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',type=Path,default=Path('src/toolchain/scenes/gameplay-inputs.json'))
    parser.add_argument('--frames',type=int,nargs='+',default=[2200,2410,2411,2760,2761])
    parser.add_argument('--overwrite',action='store_true',
        help='Replace only an unchanged complete bundle with the same payload inventory')
    args=parser.parse_args(argv)
    try:
        if args.command=='capture':
            capture_gameplay(args.root,args.assets,args.output,args.replay,args.frames,overwrite=args.overwrite)
            print(f'Captured frames {args.frames}: {args.output}')
            return 0
        if args.capture is None:
            raise ValueError('--capture is required for reconstruction')
        assets=load_assets(args.assets)
        capture=load_capture(args.capture,assets)
        frame=render(capture,assets)
        report=compare(capture.reference,frame.image)
        report['provenance']=dict(capture_sha256=digest(args.capture/'manifest.json'),assets_sha256=assets.sha256)
        def writer(stage):
            frame.image.save(stage/'reconstruction.png',optimize=False,compress_level=9)
            ImageChops.difference(capture.reference,frame.image).save(stage/'difference.png')
            json_write(stage/'comparison.json',report)
            if args.command in ('preview','analyze') and report['mismatches']==0:
                preview=compose(frame,capture,assets)
                preview.image.save(stage/'preview.png',optimize=False,compress_level=9)
                json_write(stage/'layout.json',preview.transforms)
                if args.command=='analyze':
                    constraints=analyze(preview,assets)
                    constraints['provenance']=report['provenance']
                    json_write(stage/'constraints.json',constraints)
        payloads=['reconstruction.png','difference.png','comparison.json']
        if args.command in ('preview','analyze') and report['mismatches']==0:
            payloads+=['preview.png','layout.json']
            if args.command=='analyze': payloads+=['constraints.json']
        publish_bundle(args.root,args.output,writer,payloads=payloads,overwrite=args.overwrite)
        print(f'{report["mismatches"]} mismatching pixels: {args.output}')
        return int(report['mismatches']!=0)
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(f'Error: {error}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
