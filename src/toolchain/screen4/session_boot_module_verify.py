"""Validate the optional startup contract, including a build without replay."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from session_reference import cartridge_path

import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def verify(bundle):
    from session_reference import configure
    configure(bundle)
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
    subprocess.run([sys.executable,'-B',str(ROOT/'src/toolchain/screen4/session_verify.py'),
        '--bundle',str(bundle),'--scenario','start','--contracts'],check=True)
    report=dict(passed=True,hardware_check=False,rom_sha256=hashlib.sha256((cartridge_path(bundle)).read_bytes()).hexdigest(),
        replay_resources_bytes=0,scope='No replay/scan-key/data symbols; zero replay resources; real-keyboard start and graphics contracts pass with shared HUD/test workers retained.')
    (bundle/'startup-module-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=ROOT/'references/build/game');verify(p.parse_args().bundle)
