"""Differential native gameplay/audio fixture for the fixed-RAM binding.

The original mapper-backed cartridge is the frozen control. All variants use
keyboard startup/held up and the same explicit two-byte PRNG seed fixture.
No simulation, collision, sound clock or F10 state is intercepted.
"""
import hashlib
import json
from pathlib import Path
from compact_tick_verify import trace
from mapper512_reference import reference

ROOT = Path(__file__).resolve().parents[1]


def verify():
    reference()
    names = ['game-compact-runtime', 'game-fixedram-runtime', 'game-fixedram-megaram-runtime']
    runs = [trace(ROOT/'references/build'/name, 'mapper' if i == 0 else 'plain', 4096)
            for i, name in enumerate(names)]
    for name, (_, rows) in zip(names[1:], runs[1:]):
        assert rows == runs[0][1], (name, next((i for i, (a, b) in enumerate(zip(runs[0][1], rows)) if a != b), None))
    result = dict(passed=True, native_ticks=4096, controlled_rng_seed=0x1234,
                  variants={name: hashlib.sha256((ROOT/'references/build'/name/'newrallyx.rom').read_bytes()).hexdigest() for name in names},
                  trace_sha256=hashlib.sha256(('\n'.join(runs[0][1])+'\n').encode()).hexdigest(),
                  scope='Each native tick: original768-byte E000..E2FF state, all14 PSG registers and host game/death/round state. Real startup; held up; explicit seed fixture. No full natural-course, listening or physical-hardware claim.')
    for out, _ in runs:
        (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    verify()
