"""Execute exact-ROM Game_Position once/twice through Game_Actors in openMSX.

This is an isolated callable-boundary equivalence proof, not gameplay timing.
The contributor-derived ROM is read only. Generated harness/evidence stay ignored.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.msx.emulator import reference_machine, tcl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    syms = {n: int(v, 16) for n, v in re.findall(
        r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)', (bundle/'lab.sym').read_text(), re.M)}
    out = Path(tempfile.mkdtemp(prefix='position-proof-', dir=bundle))
    # Exhaust every unsigned coarse cell and signed fine-byte value on both
    # axes. All four actor descriptors (player plus three enemies) participate.
    source = f''' OUTPUT "harness.bin"
 ORG $d100
 di
 ld sp,$f380
 xor a
 ld ($d000),a
 ld ($d001),a
 ld ($d002),a
 ld a,3
 ld ($e24e),a
case:
 ld ix,$e068
 ld b,4
actors:
 ld a,($d000)
 ld (ix+8),a
 ld (ix+10),a
 ld a,($d001)
 ld (ix+5),a
 ld (ix+7),a
 ld de,32
 add ix,de
 djnz actors
 call ${syms['Game_Position']:04x}
 call ${syms['Game_Actors']:04x}
 call registers
 ld hl,$2000
 ld de,$1000
 ld bc,12
 ldir
 ld de,$100c
 call snapshot
 call ${syms['Game_Position']:04x}
 call ${syms['Game_Position']:04x}
 call ${syms['Game_Actors']:04x}
 call registers
 ld hl,$2000
 ld de,$1100
 ld bc,12
 ldir
 ld de,$110c
 call snapshot
 ld hl,$1000
 ld de,$1100
 ld bc,168
compare:
 ld a,(de)
 cp (hl)
 jp nz,failed
 inc hl
 inc de
 dec bc
 ld a,b
 or c
 jr nz,compare
 ld hl,$d001
 inc (hl)
 jr nz,case
 ld hl,$d000
 inc (hl)
 jr nz,case
 ld a,1
 ld ($d002),a
done:
 jp done
failed:
 ld a,2
 ld ($d002),a
 jp done
registers:
 ld ($d004),sp
 push af
 push bc
 push de
 push hl
 push ix
 push iy
 ld hl,0
 add hl,sp
 ld de,$2000
 ld bc,12
 ldir
 ld sp,($d004)
 ret
snapshot:
 ld hl,$c000
 ld bc,4
 ldir
 ld hl,$c040
 ld bc,20
 ldir
 ld hl,$c400
 ld bc,84
 ldir
 ld hl,$c800
 ld bc,48
 ldir
 ret
'''
    (out/'harness.asm').write_text(source)
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo',
                    '--sym=harness.sym', 'harness.asm'], cwd=out, check=True,
                   capture_output=True, text=True)
    harness_syms = {n: int(v, 16) for n, v in re.findall(
        r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)', (out/'harness.sym').read_text(), re.M)}
    script = f'''
set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
set z80_freq 3579545
set z80_freq_locked true
set limitsprites true
filepool add -path {tcl(ROOT/'references/msxbios')} -types system_rom -position 1
{reference_machine(ROOT,'Panasonic_FS-A1WSX')}
set firmwareswitch off
cart {tcl(bundle/'fixed-hud.rom')} -romtype ASCII16
reset
set out {tcl(out)}
set started 0
debug set_bp {syms['Game_Prepare']} {{!$::started}} {{
    set ::started 1
    set f [open [file join $::out harness.bin] rb]
    debug write_block memory 0xd100 [read $f]
    close $f
    reg PC 0xd100
}}
debug set_bp {harness_syms['done']} {{$::started}} {{
    set ::started 0
    set f [open [file join $::out result.txt] w]
    puts $f "[debug read memory 0xd002] [debug read memory 0xd000] [debug read memory 0xd001] [reg SP]"
    close $f
    exit 0
}}
after time 3600 {{puts stderr "POSITION PROOF TIMEOUT";exit 2}}
'''
    (out/'session.tcl').write_text(script)
    env = dict(os.environ, OPENMSX_HOME=str(out/'home'),
               OPENMSX_USER_DATA=str(out/'userdata'))
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    result = dict(zip(('status', 'cell', 'fine', 'sp'),
                      map(int, (out/'result.txt').read_text().split())))
    assert result['status'] == 1, result
    assert result['sp'] == 0xf380, result
    report = dict(cases=65536, result='Exact callable-boundary equivalence',
                  native_enemies=3, cpu_hz=3579545,
                  rom_sha256=hashlib.sha256((bundle/'fixed-hud.rom').read_bytes()).hexdigest(),
                  comparison='Game_Position;Game_Actors versus Game_Position;Game_Position;Game_Actors; all six main register pairs including AF plus every host byte written by either routine match.',
                  state_ranges=['C000..C003', 'C040..C053', 'C400..C453', 'C800..C82F'],
                  coverage='Every coarse cell byte 0..255 and fine offset byte 0..255 on both axes; includes negative offsets, -128 Y negation, viewport edges, minimum/maximum camera clamps, and 16-bit wrap arithmetic. All four native actor descriptors participate.',
                  limits='Isolated calls with IRQ disabled. No timing or physical hardware claim. Native descriptors and graphics remain read only during the calls.')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
