"""Reject phase-dependent color substitutions in the scenery beside the HUD.

The earlier full-frame oracle explicitly reproduced those substitutions. This
separate contract requires a fixed seven-pixel dominant-source-color band and
an eight-pixel black gutter. Neither rule has a fine-phase exception.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib
import json
from pathlib import Path
import sys
from collections import Counter
from PIL import Image

BASE=Path(__file__).resolve().parents[3]/'references/experiments/fixed-hud'
rom_hash=hashlib.sha256((BASE/'fixed-hud.rom').read_bytes()).hexdigest()
if len(sys.argv)>1:
    probe=Path(sys.argv[1])
else:
    candidates=[]
    for path in BASE.glob('probe-*/metadata.json'):
        metadata=json.loads(path.read_text())
        if (metadata['mode']=='matrix' and metadata['rom_sha256']==rom_hash
                and (path.parent/'analysis.json').is_file()):
            candidates.append(path.parent)
    if not candidates:
        raise SystemExit('Run verify.py --matrix and analyze.py for the current ROM first.')
    probe=max(candidates,key=lambda p:(p/'analysis.json').stat().st_mtime_ns)
metadata=json.loads((probe/'metadata.json').read_text())
assert metadata['rom_sha256']==rom_hash
world=Image.open(BASE/'maze.png').convert('RGB')
states={}
for line in (probe/'frames.tsv').read_text().splitlines():
    n,_,x,y,*_=line.split()
    states[int(n)]=(int(x),int(y))
rows=[]
for path in sorted(probe.glob('frame-*.png')):
    n=int(path.stem.split('-')[1]);x,y=states[n]
    if y!=1032 or not 264<=x<=272: continue
    actual=Image.open(path).convert('RGB')
    mismatches=[]
    for yy in range(212):
        for xx in range(8):
            got=actual.getpixel((32+xx,14+yy))
            if got!=(0,0,0):
                mismatches.append(dict(pixel=[xx,yy],expected=[0,0,0],actual=got))
        for xx in range(193,200):
            start=(x+xx)//8*8
            row=[world.getpixel((start+i,y+yy)) for i in range(8)]
            expected=Counter(row).most_common(1)[0][0]
            got=actual.getpixel((32+xx,14+yy))
            if expected!=got:
                mismatches.append(dict(pixel=[xx,yy],expected=expected,actual=got))
        for xx in range(200,208):
            got=actual.getpixel((32+xx,14+yy))
            if got!=(0,0,0):
                mismatches.append(dict(pixel=[xx,yy],expected=[0,0,0],actual=got))
    rows.append(dict(phase=x%8,frame=n,wrong_scene_pixels=len(mismatches),examples=mismatches[:3]))
assert set(r['phase'] for r in rows)==set(range(8)), 'Missing horizontal phases'
assert any(states[r['frame']][0]==272 for r in rows), 'Missing eighth-pixel reset'
report=dict(rom_sha256=rom_hash,probe=str(probe),phases=rows,
            passed=all(r['wrong_scene_pixels']==0 for r in rows))
(probe/'edge-contract.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=report['passed'],probe=str(probe),
                     wrong_scene_pixels_by_phase={r['phase']:r['wrong_scene_pixels'] for r in rows}),indent=2))
sys.exit(0 if report['passed'] else 1)
