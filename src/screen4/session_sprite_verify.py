"""Run the established synthetic full-pixel matrix against the session clipper."""
import hashlib,json,shutil,tempfile
from pathlib import Path
from test_game_sprites import verify_emulator

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def verify(bundle):
    bundle=Path(bundle).resolve()
    out=Path(tempfile.mkdtemp(prefix='sprite-clip-proof-',dir=bundle))
    sources=out/'sources';sources.mkdir()
    for name in ('game-sprites.inc','game-sprite-mask-fast.inc','game-packet-fast.inc'):
        shutil.copyfile(HERE/name,sources/name)
    helper=HERE/'session-sprite-clip.inc'
    (sources/'game-sprite-clip-fast.inc').write_text(
        (HERE/'game-sprite-clip-fast.inc').read_text().replace('GS_ClippedCopyFast:','GS_LegacyClippedCopyFast:',1)+'\n'+helper.read_text())
    verify_emulator(ROOT/'references/msxbios',sources,out/'probe',True)
    result=dict(passed=True,rom_sha256=hashlib.sha256((bundle/'fixed-hud.rom').read_bytes()).hexdigest(),
        helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),path=str(out),
        scope='Synthetic complete-pattern/SAT/color matrix, including vertical/horizontal clips and sentinel216. Component cycles are not integrated FPS.')
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/experiments/full-session');a=p.parse_args();verify(a.bundle)
