"""Compile exact unrolled name-ring metadata stores into unused phase-bank ROM.

The resident worker selects mapper bank4 and tail-jumps toAA00. No RAM, extra
ROM banks, graphics changes or runtime code generation. Interrupts keep their
existing mapper ownership; this worker performs RAM reads/writes only.
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

ENTRY = 0xaa00
OFFSET = ENTRY-0x8000


def source(names_base=0x2000):
    lines = [' OUTPUT "game-ring-refresh.bin"', ' ORG $aa00',
             ' ; A=mapcol,C=maprow; inline the original Ring_Position.',
             ' and 31', ' ld e,a', ' ld a,c', ' and 31',
             ' rrca', ' rrca', ' rrca', ' ld l,a', ' and 3', ' or $d8',
             ' ld h,a', ' ld a,l', ' and $e0', ' or e', ' ld l,a']
    for row in range(28):
        p, b = 0xce00+row*4, 0xc920+row*3
        lines += [' ld a,l', f' ld (${p:04x}),a', ' ld a,h', ' sub $b8',
                  f' ld (${p+1:04x}),a', ' ld a,(hl)', f' ld (${b+2:04x}),a',
                  ' push hl', ' ld a,l', ' add a,24', ' and 31', ' ld c,a',
                  ' ld a,l', ' and $e0', ' or c', ' ld l,a', ' ld a,l',
                  f' ld (${p+2:04x}),a', ' ld a,h', ' sub $b8',
                  f' ld (${p+3:04x}),a', ' ld a,(hl)', f' ld (${b:04x}),a',
                  ' ld a,l', ' inc a', ' and 31', ' ld c,a', ' ld a,l',
                  ' and $e0', ' or c', ' ld l,a', ' ld a,(hl)',
                  f' ld (${b+1:04x}),a', ' pop hl', ' ld a,l', ' add a,32',
                  ' ld l,a', f' jr nc,.same_{row}', ' inc h', ' ld a,h',
                  ' and 3', ' or $d8', ' ld h,a', f'.same_{row}:']
    # Same final metadata cursors, loop counter and cache pointer as before.
    lines += [' ld ix,$c974', ' ld de,$ce70', ' ld b,0', ' ret',
              ' ASSERT $ <= $c000']
    return ('\n'.join(lines)+'\n').replace('sub $b8',f'sub ${0xd8-(names_base>>8):02x}')


def compile_worker(root, out,names_base=0x2000):
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out/'game-ring-refresh.asm').write_text(source(names_base))
    r = subprocess.run([str(root/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo',
                        '--sym=game-ring-refresh.sym', 'game-ring-refresh.asm'],
                       cwd=out, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout+r.stderr
    return (out/'game-ring-refresh.bin').read_bytes()


def append_worker(banks, root, out,names_base=0x2000):
    data = compile_worker(root, out,names_base)
    result = bytearray(banks)
    at = 3*16384+OFFSET  # Resident bank0; first HUD phase is mapper bank4.
    assert all(v in (0, 255) for v in result[at:at+len(data)]), 'Refresh worker overlaps phase resources'
    result[at:at+len(data)] = data
    report = dict(entry=ENTRY, mapper_bank=4, bytes=len(data), extra_banks=0, extra_ram=0,
                  sha256=hashlib.sha256(data).hexdigest(),
                  scope='Exact28-row ring pointer and boundary-ID rebuild, unrolled into free ROM. Inclusive cost remains under Ring_Prepare.')
    (Path(out)/'ring-refresh.json').write_text(json.dumps(report, indent=2)+'\n')
    return result
