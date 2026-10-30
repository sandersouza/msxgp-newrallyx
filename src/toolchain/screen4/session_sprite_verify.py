"""Run the established synthetic full-pixel matrix against the session clipper."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import hashlib,json,shutil,tempfile
from pathlib import Path
from test_game_sprites import verify_emulator

ROOT=Path(__file__).resolve().parents[3]
HERE = RUNTIME


def verify(bundle):
    from session_reference import configure
    configure(bundle)
    bundle=Path(bundle).resolve()
    out=Path(tempfile.mkdtemp(prefix='sprite-clip-proof-',dir=bundle))
    sources=out/'sources';sources.mkdir()
    for name in ('game-sprites.inc','game-sprite-mask-fast.inc','game-packet-fast.inc'):
        shutil.copyfile(HERE/name,sources/name)
    helper=HERE/'session-sprite-clip.inc'
    (sources/'game-sprite-clip-fast.inc').write_text(
        (HERE/'game-sprite-clip-fast.inc').read_text().replace('GS_ClippedCopyFast:','GS_LegacyClippedCopyFast:',1)+'\n'+helper.read_text())
    verify_emulator(ROOT/'references/msxbios',sources,out/'probe',True)
    result=dict(passed=True,rom_sha256=hashlib.sha256((cartridge_path(bundle)).read_bytes()).hexdigest(),
        helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),path=str(out),
        scope='Synthetic complete-pattern/SAT/color matrix, including vertical/horizontal clips and sentinel216. Component cycles are not integrated FPS.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/build/game');a=p.parse_args();verify(a.bundle)
