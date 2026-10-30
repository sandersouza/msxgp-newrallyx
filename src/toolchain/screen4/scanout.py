"""Check every lossless recorded frame after the first oracle-covered state.

Run analyze.py first. This catches mixed frames between the commit captures;
comparison covers all 320x240 pixels, without crops or similarity thresholds.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image

BASE=Path(__file__).resolve().parents[3]/'references/experiments/fixed-hud'
PROBE=Path(sys.argv[1]) if len(sys.argv)>1 else Path((BASE/'last-probe.txt').read_text().strip())
metadata=json.loads((PROBE/'metadata.json').read_text())
assert metadata['mode']=='continuous', 'Use the continuous keyboard probe'
assert metadata['rom_sha256']==hashlib.sha256((BASE/'fixed-hud.rom').read_bytes()).hexdigest()
analysis=json.loads((PROBE/'analysis.json').read_text())
assert analysis['complete'], 'Commit-capture oracle must pass first'
known={}
for path in PROBE.glob('oracle-*.png'):
    n=int(path.stem.split('-')[1])
    expected=Image.open(path).convert('RGB').tobytes()
    key=hashlib.sha256(expected).digest()
    known.setdefault(key,set()).add(n)
minimum=min(n for values in known.values() for n in values)
command=['ffmpeg','-v','error','-i',str(PROBE/'scanout.avi'),'-f','rawvideo','-pix_fmt','rgb24','pipe:1']
process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
frame=0;first=None;last=0;checked=0;unmatched=[];seen=set()
while True:
    data=process.stdout.read(320*240*3)
    if not data: break
    assert len(data)==320*240*3, 'Truncated decoded frame'
    frame+=1
    possible=known.get(hashlib.sha256(data).digest(),set())
    candidates=sorted(n for n in possible if n>=last)
    if first is None: candidates=[n for n in candidates if n==minimum]
    if candidates:
        if first is None: first=frame
        last=candidates[0];seen.add(last);checked+=1
    elif first is not None:
        unmatched.append(frame)
        if len(unmatched)<=4:
            Image.frombytes('RGB',(320,240),data).save(PROBE/f'scanout-failure-{frame}.png')
stderr=process.stderr.read().decode()
assert process.wait()==0, stderr
report=dict(rom_sha256=metadata['rom_sha256'],total_recorded_frames=frame,
            first_oracle_covered_frame=first,checked_frames=checked,
            distinct_presentations_seen=len(seen),unmatched_frames=unmatched,
            note='Boot and first three unlisted movement states precede oracle coverage.',
            complete=first is not None and checked>=300 and len(seen)>=250 and not unmatched)
(PROBE/'scanout-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(0 if report['complete'] else 1)
