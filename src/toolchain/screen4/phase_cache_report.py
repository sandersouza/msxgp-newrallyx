"""Bind cache correctness and graphics preservation to the measured cartridge."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BUNDLE=ROOT/'references/experiments/stage-one-3-enemies'


def main():
    digest=hashlib.sha256((BUNDLE/'fixed-hud.rom').read_bytes()).hexdigest()
    previous=BUNDLE/'baseline-299b5380'
    payloads=['terrain-patterns.bin','terrain-colors.bin','palette.bin','game-sprite-templates.bin',
              'game-hud-digits.bin','game-hud-life.bin','hud.bin','map.bin','flag-records.bin']
    payloads += [f'hud-{n:02d}.bin' for n in range(64)]
    for name in payloads:
        assert (BUNDLE/name).read_bytes()==(previous/name).read_bytes(),name
    hud=json.loads((ROOT/'references/experiments/phase-cache-hud-proof/summary.json').read_text())
    assert hud['rom_sha256']==digest and hud['complete'] and hud['cases']==16640
    lives=[]
    for path in BUNDLE.glob('route-*/phase-cache.json'):
        value=json.loads(path.read_text())
        if value.get('rom_sha256')==digest:lives.append((path,value))
    assert lives,'Missing live visible-set guard'
    path,live=max(lives,key=lambda row:row[0].stat().st_mtime)
    assert live['visible_set_unchanged']
    report=dict(rom_sha256=digest,before_sha256=hashlib.sha256((previous/'fixed-hud.rom').read_bytes()).hexdigest(),
        unchanged_payloads=payloads,unchanged_payload_count=len(payloads),
        transition_probe=hud,live_probe=live,live_source=str(path),
        rom_bytes=(BUNDLE/'fixed-hud.rom').stat().st_size,before_rom_bytes=(previous/'fixed-hud.rom').stat().st_size,
        extra_ram_bytes=7,ram_range='C027..C02D',extra_initialized_vram_bytes=8192,
        physical_vram_bytes=131072,pattern_sets=4,name_tables=2,
        placement='Foreground: select an inactive exact phase or next victim, update its HUD/boundary/radar. VBlank: publish R4/R10 and existing name/SAT registers. Native logic, input clock, audio and graphics payloads unchanged.',
        limitations='First-stage keyboard route and synthetic phase transitions in openMSX; no physical hardware or later-phase validation. No stable zero-miss claim.')
    target=ROOT/'outputs/fixed-hud/phase-cache-proof.json'
    target.write_text(json.dumps(report,indent=2)+'\n');print(target)


if __name__=='__main__':main()
