"""Check the corrected RNG stream with original-ROM placement and video oracles.

Natural keyboard starts are read-only. The separate declared seed injection is
only an algorithm fixture, not evidence of natural lifecycle fidelity.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.msx_flag_seed_probe import run
from scripts.arcade_maze_flags_probe import place_objects
from src.toolchain.graphics.roms import load_metadata,validate_roms
from scripts.extract_graphics import _region


def main(output=None):
    rows=[run(d,baseline=False) for d in (0,.5,2)]
    repeat=run(0,baseline=False,repeat=1)
    assert rows[0]['flag_positions_sha256']==repeat['flag_positions_sha256']
    assert len({r['flag_positions_sha256'] for r in rows})>1
    assert len({r['rng_before_prepare'] for r in rows})==3
    controlled=run(0,override_seed=0x1234,baseline=False)
    m=load_metadata()
    program=_region(validate_roms(ROOT/'references/roms/nrallyx',m),m,'maincpu',16384)
    for r in rows+[repeat,controlled]:
        seed=r['rng_before_placement'] if r['controlled_seed'] is not None else r['rng_before_prepare']
        state,calls,flags,_=place_objects(program,seed,0x30,r['rock_count'])
        assert state==r['rng_after_placement']
        assert hashlib.sha256(flags).hexdigest()==r['flag_positions_sha256']
        assert r['graphics_passed']
    report=dict(passed=True,rom_sha256=hashlib.sha256((ROOT/'dist/newrallyx.rom').read_bytes()).hexdigest(),
        main_ram_kib=64,natural_starts=rows,repeat=repeat,controlled_seed=controlled,
        scope='Real keyboard credit/start, three delays plus repeat, default-DIP seed and every observed menu PRNG advance checked, no reset through new-game seed copy, exact original flag/rock model, independent world/HUD/car oracle. Controlled seed fixture separately labeled; lifecycle/performance are separate checks.')
    target=Path(output) if output else ROOT/'docs/measurements/cartridge/issue42-rng-correction.json'
    target.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    main(parser.parse_args().output)
