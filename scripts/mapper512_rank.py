"""Factor original victim rankings into HUD costs and per-family edge costs."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/toolchain/screen4'),str(ROOT)]
from session_phase import compiled_cycles


def ranking_basis(records, bundle=None):
    """Return8896 canonical bytes; all16640 original ranking bytes must agree.

    No new rank policy: preserve the original unoptimized cost estimator,256
    quantization and254 clamp. Cold reconstruction avoids active ranking work.
    Output:4160 HUD low bytes,4160 HUD high bytes,4x8x9 LE edge words. Last old index is the
    unknown-cache entry. No original-derived fixture is stored in source.
    """
    bundle=Path(bundle or ROOT/'references/build/game');rom=(bundle/'newrallyx.rom').read_bytes()
    image=rom[16384:];hud=[]
    for current in range(64):
        at=(4+current)*16384;row=[]
        for old in range(65):
            bank,lo,hi=rom[at+0x2600+(old%64)*3:at+0x2603+(old%64)*3]
            row.append(compiled_cycles(image,bank,lo+hi*256) if old<64 and bank else rom[at+0x900]*16*17+250)
        hud.append(row)
    rows={(r['layout'],r['current']):r['costs'] for r in json.loads((bundle/'session-phase-costs.json').read_text())['rows']}
    edges=[[[rows[layout,fx][old]-hud[fx][old] for old in list(range(8))+[64]] for fx in range(8)] for layout in range(4)]
    for current in range(64):
        for layout in range(4):
            values=[hud[current][old]+edges[layout][current%8][old%8 if old<64 else 8] for old in range(65)]
            assert values==rows[layout,current]
            assert bytes(min(254,(v+128)//256) for v in values)==records[current]['data'][0x800+layout*256:0x841+layout*256]
    words=b''.join(value.to_bytes(2,'little') for row in hud for value in row)
    result=words[::2]+words[1::2]
    result+=b''.join(value.to_bytes(2,'little') for family in edges for row in family for value in row)
    assert len(result)==8896
    return result
