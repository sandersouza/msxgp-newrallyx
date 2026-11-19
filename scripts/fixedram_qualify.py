"""Run exact-artifact fixed-RAM qualification; no builds or publication.

Independent emulator processes own separate session/profile directories. Smoke
and natural-lifecycle checks share a session name, so lifecycle runs last.
Contributor assets, BIOS and private DOS validation inputs must be prepared.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / '.venv/bin/python')


def run():
    tasks = []
    cart = 'references/build/game-fixedram-runtime'
    mega = 'references/build/game-fixedram-megaram-runtime'
    def add(name, script, args=(), env=None):
        tasks.append((name, script, list(args), env or {}))
    for backend, bundle in [('cart', cart), ('mega', mega)]:
        for round_number, enemies in [(5, 3), (10, 5), (13, 6)]:
            add(f'{backend}-profile-{enemies}', 'src/toolchain/screen4/session_profile.py', ['--bundle', bundle],
                dict(NRX_PROFILE_SEED='0x1234', NRX_PROFILE_ROUND=str(round_number),
                     NRX_PROFILE_ENEMIES=str(enemies), NRX_REFERENCE_RAM_KIND='plain'))
    for machine, ram in [('Panasonic_FS-A1WSX', 128), ('Sony_HB-F1XDJ', 64),
                         ('Panasonic_FS-A1ST', 256), ('Panasonic_FS-A1GT', 512)]:
        add(f'profile-{machine}-{ram}', 'src/toolchain/screen4/session_profile.py', ['--bundle', cart],
            dict(NRX_PROFILE_SEED='0x1234', NRX_PROFILE_ROUND='5', NRX_PROFILE_ENEMIES='3',
                 NRX_REFERENCE_MACHINE=machine, NRX_REFERENCE_RAM_KIB=str(ram)))
    for case in ['integration', 'flags', 'smoke', 'two-player', 'attract', 'controls', 'radar']:
        add('session-' + case, 'src/toolchain/screen4/session_verify.py',
            ['--bundle', cart, '--scenario', case, '--headless', '--contracts'],
            dict(NRX_REFERENCE_RAM_KIND='plain'))
    for case in ['boot', 'audio', 'rocks', 'speed', 'sprite']:
        add(case, f'src/toolchain/screen4/session_{case}_verify.py', ['--bundle', cart],
            dict(NRX_REFERENCE_RAM_KIND='plain'))
    for mode in ['rom', 'dos', 'basic']:
        add('smoke-' + mode, 'scripts/compact_game_verify.py',
            ['--mode', mode, '--size', '768', '--fixed-ram', '--ram-kind', 'plain'])
        fmode = mode if mode == 'rom' else 'mega-' + mode
        add('f10-' + mode, 'scripts/f10_verify.py',
            ['--mode', fmode, '--fixed-ram', '--ram-kind', 'plain'] + ([] if mode == 'rom' else ['--quick']))
    for topology in ['shared', 'unexpanded']:
        add('slot-' + topology, 'scripts/compact_game_verify.py',
            ['--mode', 'rom', '--fixed-ram', '--ram-kind', 'plain', '--topology', topology])
    add('mega-shared', 'scripts/compact_game_verify.py',
        ['--mode', 'basic', '--size', '768', '--fixed-ram', '--ram-kind', 'plain', '--topology', 'shared'])
    # Reject insufficient MegaRAM without modifying its contents.
    add('mega-too-small', 'scripts/compact_game_verify.py',
        ['--mode', 'basic', '--size', '512', '--fixed-ram', '--ram-kind', 'plain'])
    out = ROOT / 'references/build/fixedram-qualification'
    out.mkdir(exist_ok=True)
    def execute(task):
        name, script, args, env = task
        with (out / (name + '.log')).open('w') as log:
            p = subprocess.run([PYTHON, '-B', script, *args], cwd=ROOT,
                               env=dict(os.environ, SDL_AUDIODRIVER='dummy', **env), stdout=log, stderr=subprocess.STDOUT)
        result = dict(name=name, returncode=p.returncode, script=script, args=args, env=env)
        print(json.dumps(result), flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(execute, tasks))
    for mode in ['rom', 'dos', 'basic']:
        results.append(execute(('gameover-' + mode, 'scripts/fixedram_gameover_verify.py', ['--mode', mode], {})))
    (out / 'commands.json').write_text(json.dumps(results, indent=2) + '\n')
    if any(r['returncode'] for r in results):
        raise SystemExit('Qualification failed; inspect named logs before retrying.')


if __name__ == '__main__':
    run()
