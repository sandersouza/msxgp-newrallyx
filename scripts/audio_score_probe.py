#!/usr/bin/env python3
"""Check compiled Start duration against captured original sound-call endings."""
import argparse
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audio_sequencer_probe import SAMPLE
from scripts.msx.build import destination
from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    rom = args.rom.resolve(); reference = args.reference.resolve()
    verify_manifest(rom.parent); verify_manifest(reference)
    count = read_json(reference/'report.json')['sequencer_cases']
    raw = (reference/'sequencer.bin').read_bytes()
    if len(raw) != count*SAMPLE*2: raise ValueError('Incomplete original sound-call evidence')
    spans = []; start = None
    for i in range(count):
        before = raw[i*SAMPLE*2+0x9f5]
        after = raw[(i*2+1)*SAMPLE+0x9f5]
        if before & 128:
            if start is None: start = i
            if not after & 128:
                spans.append(i-start+1); start = None
        else:
            start = None
    frames=read_json(rom.parent/'audio-relocation.json')['compiled_scores']['intro']['frames']
    if (rom.parent/'audio-intro-frames.bin').stat().st_size not in (frames*6,frames*9):
        raise ValueError('Incomplete compiled intro frames')
    # The original observes the terminator on the call after the final note.
    # This oracle uses captured code execution, independently of our parser.
    passed = bool(spans) and all(frames*2 == calls-1 for calls in spans)
    out = destination(root, args.output); require_ignored(root, [out/'report.json']); out.mkdir(parents=True)
    json_write(out/'report.json', dict(passed=passed, rom_sha256=digest(rom),
        original_start_calls=spans, compiled_start_score_frames=frames,
        compiled_start_reference_ticks=frames*2,
        scope='Captured unmodified original Start-request entry/exit snapshots; '
              'group termination includes all three original parts. '
              'Duration oracle only, not waveform/timbre or additional channel fidelity.'))
    if not passed: raise ValueError('Compiled Start duration outlives the original music group')
    seal(out)
    print(f'Compiled Start ends with original three-voice group: {out}/report.json')


if __name__ == '__main__': main()
