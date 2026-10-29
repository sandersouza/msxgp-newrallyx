"""Validate the optional startup contract, including a build without replay."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def verify(bundle):
    bundle=Path(bundle).resolve()
    meta=json.loads((bundle/'session-boot.json').read_text())
    if meta['enabled']:
        from session_boot_verify import verify as pixels
        from session_boot_skip_verify import verify as skip
        pixels(bundle);skip(bundle)
        return
    symbols=(bundle/'lab.sym').read_text()
    for name in ('GameSession_BootShow','GameSession_BootAnyKey','GameSession_BootKeyGate','GameSession_BootFrames','GameSession_BootPalette'):
        assert not re.search(r'(?m)^'+name+':',symbols),('Disabled startup emitted a module symbol',name)
    assert meta['compressed_bytes']==meta['frame_count']==0
    # Real keyboard start verifies shared workers survive module omission; full
    # graphics contracts include the supplied footer and HUD/sprite state.
    subprocess.run([sys.executable,'-B',str(ROOT/'src/screen4/session_verify.py'),
        '--bundle',str(bundle),'--scenario','start','--contracts'],check=True)
    report=dict(passed=True,hardware_check=False,rom_sha256=hashlib.sha256((bundle/'fixed-hud.rom').read_bytes()).hexdigest(),
        replay_resources_bytes=0,scope='No replay/scan-key/data symbols; zero replay resources; real-keyboard start and graphics contracts pass with shared HUD/test workers retained.')
    (bundle/'startup-module-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/experiments/full-session');verify(p.parse_args().bundle)
