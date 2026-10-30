"""Exact phase-local uniform radar source metadata; no contributor data retained."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib
import json
from pathlib import Path

BANK_BYTES = 16384
PHASE_BANK_FIRST = 3
TABLE_OFFSET = 0x2940


def uniform_source_colors(patterns, colors, count):
    """Return 64 source-color bytes; zero conservatively requests normal copying."""
    assert 0 <= count <= 64
    assert len(patterns) >= count*8 and len(colors) >= count*8
    result = bytearray(64)
    for index in range(count):
        start = index*8
        color = colors[start]
        if (color and patterns[start:start+8] == b'\xff'*8
                and colors[start:start+8] == bytes((color,))*8):
            result[index] = color
    return bytes(result)


def append_metadata(banks, out):
    """Return copied banks with 64 exact source-color bytes per phase page."""
    assert len(banks) % BANK_BYTES == 0
    result = bytearray(banks)
    eligible = []
    for phase in range(64):
        start = (PHASE_BANK_FIRST+phase)*BANK_BYTES
        page = result[start:start+BANK_BYTES]
        assert len(page) == BANK_BYTES, 'Missing complete phase bank'
        count = page[0x900]
        data = uniform_source_colors(page[0x100:0x500], page[0x500:0x900], count)
        at = start+TABLE_OFFSET
        assert all(value in (0, 255) for value in result[at:at+64]), 'Radar source metadata overlaps existing phase data'
        result[at:at+64] = data
        eligible.append(sum(bool(value) for value in data))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report = dict(complete=True, phases=64, table_offset=TABLE_OFFSET,
                  metadata_bytes=64*64, eligible_characters_by_phase=eligible,
                  input_banks_sha256=hashlib.sha256(banks).hexdigest(),
                  output_banks_sha256=hashlib.sha256(result).hexdigest(),
                  scope='An eligible source has exactly eight FF pattern bytes and eight equal nonzero color bytes. Zero requests the original 16-byte clone. No changed pixels, persistent RAM or transfer suppression.')
    (out/'radar-source-metadata.json').write_text(json.dumps(report, indent=2)+'\n')
    return result
