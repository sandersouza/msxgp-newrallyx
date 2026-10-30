"""Stable character identities and color bytes across eight boundary phases.

Every source still decodes to the existing authorized edge pixels. Allocate a
character for its complete eight-phase signature, then encode all phases using
the same row color pair. Runtime phase changes consequently transfer patterns
without repeatedly replacing identical color bytes. No RAM or extra VRAM slots.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from edge import edge_tiles


def family(sources, which, slot, *, capacity=48):
    signatures = {}
    names = bytearray()
    for source in sources:
        phases = [edge_tiles(source, fx)[which] for fx in range(8)]
        colors = bytearray()
        patterns = [bytearray() for _ in range(8)]
        for y in range(8):
            values = sorted({v for pixels in phases for v in pixels[y*8:y*8+8]})
            assert 1 <= len(values) <= 2, 'Stable encoding would reduce edge colors'
            bg, fg = values[0], values[-1]
            colors.append(fg*16+bg)
            for pattern, pixels in zip(patterns, phases):
                pattern.append(sum((v == fg) << (7-x) for x, v in enumerate(pixels[y*8:y*8+8])))
        signature = bytes(colors), tuple(map(bytes, patterns))
        if signature not in signatures:
            signatures[signature] = len(signatures)
        names.append(slot+signatures[signature])
    assert len(signatures) <= capacity, 'Stable atlas exceeds its character allocation'
    colors = b''.join(c for c, _ in signatures)
    return [(bytes(names), b''.join(p[fx] for _, p in signatures), colors, len(signatures))
            for fx in range(8)]


def compare_bundles(before, after, out):
    """Decode actual LUT-selected characters, independent of atlas identities."""
    import hashlib
    import json
    from pathlib import Path
    before, after, out = map(Path, (before, after, out))
    old, new = [(p/'banks.bin').read_bytes() for p in (before, after)]
    count = json.loads((after/'prepare.json').read_text())['scenery_tiles']
    pixels = 0
    for phase in range(64):
        page = (3+phase)*16384
        for slot, lut, patterns, colors in ((160, 0xa00, 0xb00, 0xd00),
                                            (208, 0x1000, 0x1100, 0x1300)):
            for source in range(count):
                decoded = []
                for data in (old, new):
                    tile = data[page+lut+source]-slot
                    p = data[page+patterns+tile*8:page+patterns+tile*8+8]
                    c = data[page+colors+tile*8:page+colors+tile*8+8]
                    decoded.append(bytes(c[y] >> 4 if p[y] & (128 >> x) else c[y] & 15
                                         for y in range(8) for x in range(8)))
                assert decoded[0] == decoded[1], (phase, slot, source)
                pixels += 64
        for offset, length_at in ((0xd00, 0xf00), (0x1300, 0x1500)):
            length = new[page+length_at]*8
            zero = 3*16384
            assert new[page+offset:page+offset+length] == new[zero+offset:zero+offset+length]
    unchanged = ['terrain-patterns.bin', 'terrain-colors.bin', 'palette.bin', 'map.bin',
                 'game-native-raw.bin', 'game-sprite-templates.bin', 'game-hud-digits.bin',
                 'game-hud-life.bin', 'game-hud-colors.bin']+[f'hud-{p:02d}.bin' for p in range(64)]
    for name in unchanged:
        assert (before/name).read_bytes() == (after/name).read_bytes(), name
    reports = [json.loads((p/'boundary-cost.json').read_text()) for p in (before, after)]
    known = [f'{a}->{b}' for a in range(8) for b in range(8) if a != b]
    result = dict(complete=True, phases=64, source_tiles=count, exact_decoded_pixels=pixels,
                  unchanged_asset_files=len(unchanged),
                  before_sha256=hashlib.sha256((before/'fixed-hud.rom').read_bytes()).hexdigest(),
                  after_sha256=hashlib.sha256((after/'fixed-hud.rom').read_bytes()).hexdigest(),
                  known_phase_mean_payload_bytes={name: sum(d['costs'][k]['payload_bytes'] for k in known)/len(known)
                                                  for name, d in zip(('before', 'after'), reports)},
                  scope='All64 phase LUTs decoded for every live source tile in both edge atlases; exact displayed pixel equality. Stable color bytes across all phases. Known-phase payload mean is an equal-weight transfer-size diagnostic, not a gameplay gain.')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', required=True)
    p.add_argument('--after', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    compare_bundles(a.before, a.after, a.out)
