#!/usr/bin/env python3
"""Acquire ordered original sound commands/WSG writes without changing gameplay."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.extract_graphics import _region
from scripts.graphics.roms import input_records, load_metadata, validate_roms
from scripts.msx.audio_reference import summarize
from scripts.msx.build import destination
from scripts.scenes.bundle import digest
from scripts.scenes.storage import json_write, require_ignored, seal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--frames', type=int, default=7200)
    p.add_argument('--sequencer', action='store_true', help='Capture every sound-call entry/exit for differential execution')
    p.add_argument('--record',action='store_true',help='Also record the original emulator PCM to reference.wav')
    args = p.parse_args()
    if not 2000 <= args.frames <= 36000:
        raise ValueError('Capture must contain 2000..36000 original refreshes')
    root = Path(__file__).resolve().parents[1]
    out = destination(root, args.output)
    require_ignored(root, [out/'frames.tsv', out/'wave-prom.bin'])
    metadata = load_metadata()
    roms = validate_roms(root/'references/roms/nrallyx', metadata)
    source = input_records(roms)
    version = subprocess.check_output(['mame', '-version'], text=True).strip()
    if not version.startswith('0.289 '):
        raise ValueError('Audio inventory requires pinned MAME 0.289')
    out.mkdir(parents=True)
    (out/'wave-prom.bin').write_bytes(_region(roms, metadata, 'namco', 512))
    script = root/'scripts/msx/audio_inventory.lua'
    command = ['mame', 'nrallyx', '-noreadconfig', '-noplugins', '-nocheat',
               '-rompath', str(root/'references/roms'), '-video', 'none', '-sound', 'none',
               '-nothrottle', '-noautosave', '-noautoframeskip', '-frameskip', '0',
               '-skip_gameinfo', '-debug', '-debugger', 'none', '-autoboot_delay', '0',
               '-autoboot_script', str(script), '-cfg_directory', str(out/'cfg'),
               '-nvram_directory', str(out/'nvram'), '-seconds_to_run',
               str(int(args.frames * .0165) + 10)]
    if args.record:command.extend(['-wavwrite',str(out/'reference.wav')])
    with (out/'mame.log').open('w') as log:
        subprocess.run(command, check=True, timeout=240, stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, AUDIO_INVENTORY_OUTPUT=str(out),
                                AUDIO_INVENTORY_SEQUENCER=str(int(args.sequencer)),
                                AUDIO_INVENTORY_FRAMES=str(args.frames)))
    if '[LUA ERROR]' in (out/'mame.log').read_text() or not (out/'complete').is_file():
        raise ValueError(f'Incomplete original sound capture; inspect {out}/mame.log')
    frames = [list(map(int, line.split())) for line in (out/'frames.tsv').read_text().splitlines()]
    # Keep MAME's original subframe time strings in the raw file; analysis uses
    # frame tags and write order, without claiming CPU-cycle timing accuracy.
    writes = [tuple(map(int, line.split()[:4])) for line in (out/'writes.tsv').read_text().splitlines()]
    if not (out/'boot-ready').is_file():
        raise ValueError('Original reset completion was not observed')
    report = summarize(frames, writes, boot_frame=int((out/'boot-ready').read_text()))
    if args.sequencer:
        count = int((out/'sequencer-count').read_text())
        if count <= 0 or (out/'sequencer.bin').stat().st_size != count * 2 * (3072 + 32):
            raise ValueError('Incomplete sound-call boundary evidence')
        report['sequencer_cases'] = count
    if len(frames) != args.frames or not report['maximum_active_voices']:
        raise ValueError('Missing captured refreshes or audible WSG activity')
    if input_records(validate_roms(root/'references/roms/nrallyx', metadata)) != source:
        raise ValueError('Contributor ROMs changed during sound capture')
    report.update(roms=source, emulator=version, script_sha256=digest(script),
                  source_commit=metadata['source']['commit'], guest_state_writes=False,
                  audio_output='Original emulator PCM in reference.wav; no subjective verdict' if args.record else 'Disabled for register acquisition; no listening or timbre qualification',
                  sampling='Consecutive original frame-end states plus every ordered request/WSG/latch write; '
                           'real coin/start/periodic smoke inputs. No seeded challenge or low-fuel coverage claimed.')
    json_write(out/'report.json', report)
    require_ignored(root, [f for f in out.rglob('*') if f.is_file()])
    seal(out)
    print(f'{len(frames)} original sound frames, {len(writes)} ordered writes: {out}/report.json')


if __name__ == '__main__':
    main()
