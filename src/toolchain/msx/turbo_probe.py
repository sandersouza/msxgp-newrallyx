"""Qualify factory CPU modes with a synthetic cartridge, never a frequency override.

The cartridge keeps BIOS Page0 visible and uses CHGCPU/GETCPU on turboR.
This is a controller/instruction benchmark, not a gameplay acceptance test.
All binaries, BIOS-derived runtime state and emulator files stay in references/.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.toolchain.msx.emulator import tcl

MACHINES = tuple('Panasonic_FS-A1' + model for model in ('FX', 'WX', 'WSX', 'ST', 'GT')) + ('Sony_HB-F1XV',)

SOURCE = '''
    OUTPUT "probe.rom"
    ORG $4000
    db "AB"
    dw boot,0,0,0,0,0,0
boot:
    di
    ld sp,$f300
    xor a
    ld ($c000),a
    ld a,($002d)
    cp 3
    jr nc,turbor
    in a,($40)
    cpl
    ld ($c001),a
    ld a,8
    out ($40),a
    in a,($40)
    cp $f7
    jr nz,unsupported
    in a,($41)
    bit 2,a
    jr nz,unsupported
    ld ($c002),a
    or 1
    out ($41),a
    call sample
    ld a,1
    ld ($c000),a
    ld a,($c002)
    and $fe
    out ($41),a
    call sample
    ld a,($c002)
    out ($41),a
    jr restore_selector
unsupported:
    ld a,($c001)
    out ($40),a
    call sample
    jr finished
restore_selector:
    ld a,($c001)
    out ($40),a
    jr finished
turbor:
    call $0183
    ld ($c003),a
    xor a
    call $0180
    di
    call sample
    ld a,1
    ld ($c000),a
    call $0180
    di
    call sample
    ld a,2
    ld ($c000),a
    call $0180
    di
    call sample
    ld a,($c003)
    call $0180
    di
finished:
    jr finished
sample:
    ld hl,ram_start
    ld de,$c100
    ld bc,ram_end-ram_start
    ldir
    call rom_start
    call $c100
    ret
rom_start:
    ld bc,4096
rom_loop:
    add hl,de
    dec bc
    ld a,b
    or c
    jr nz,rom_loop
rom_done:
    ret
ram_start:
    ld bc,4096
    add hl,de
    dec bc
    ld a,b
    or c
    jr nz,$-4
ram_done:
    ret
ram_end:
    defs $8000-$,$ff
'''


def run(output, machine):
    out = output / machine
    out.mkdir(parents=True, exist_ok=False)
    (out / 'probe.asm').write_text(SOURCE)
    subprocess.run([str(ROOT / '.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', '--sym=probe.sym', 'probe.asm'],
                   cwd=out, check=True, capture_output=True)
    syms = {n: int(v, 16) for n, v in re.findall(r'(?m)^([\w.]+): EQU 0x([\da-fA-F]+)', (out / 'probe.sym').read_text())}
    script = f'''
set save_settings_on_exit false
set renderer none
set sound_driver null
set throttle off
filepool add -path {tcl(ROOT / 'references/msxbios')} -types system_rom -position 1
machine {machine}
set firmwareswitch off
set z80_freq_locked true
cart {tcl(out / 'probe.rom')} -romtype Normal
reset
set records [open {tcl(out / 'samples.tsv')} w]
puts $records "mode\tlocation\tseconds\tz80_hz\tcpu\tlocked\tcontroller"
set running 0
proc start {{location}} {{set ::start($location) [machine_info time]}}
proc stop {{location}} {{
 set controller [expr {{[lsearch -exact [debug list] "S1990 regs"]>=0 ? [debug read "S1990 regs" 6] : [debug read ioports 65]}}]
 puts $::records "[debug read memory 0xc000]\t$location\t[expr {{[machine_info time]-$::start($location)}}]\t[machine_info z80_freq]\t[get_active_cpu]\t$::z80_freq_locked\t$controller"
 flush $::records
}}
debug set_bp {syms['boot']} {{[debug read memory 0x4000]==65 && [debug read memory 0x4001]==66}} {{set ::running 1}}
debug set_bp {syms['rom_start']} {{$::running}} {{start rom}}
debug set_bp {syms['rom_done']} {{$::running}} {{stop rom}}
debug set_bp 49408 {{$::running}} {{start ram}}
debug set_bp {49408 + syms['ram_done'] - syms['ram_start']} {{$::running}} {{stop ram}}
debug set_bp {syms['finished']} {{$::running}} {{set ::running 0;close $::records;exit 0}}
after time 20 {{puts stderr "Factory CPU probe timed out";exit 2}}
'''
    (out / 'probe.tcl').write_text(script)
    env = dict(os.environ, OPENMSX_HOME=str(out / 'home'), OPENMSX_USER_DATA=str(out / 'userdata'))
    with (out / 'openmsx.log').open('w') as log:
        result = subprocess.run(['openmsx', '-script', str(out / 'probe.tcl')], env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=60)
    record = dict(machine=machine, returncode=result.returncode,
                  synthetic_rom_sha256=hashlib.sha256((out / 'probe.rom').read_bytes()).hexdigest(),
                  log=str((out / 'openmsx.log').relative_to(ROOT)))
    if result.returncode:
        record['error'] = (out / 'openmsx.log').read_text()[-2000:]
        return record
    with (out / 'samples.tsv').open() as file:
        record['samples'] = list(csv.DictReader(file, delimiter='\t'))
    expected = 6 if machine.endswith(('ST', 'GT')) else 2 if machine.startswith('Sony') else 4
    if len(record['samples']) != expected or any(float(r['seconds']) <= 0 for r in record['samples']):
        record['returncode'] = 2
        record['error'] = 'Missing or invalid benchmark samples; inspect emulator log'
    elif expected > 2:
        base = float(record['samples'][0]['seconds'])
        for row in record['samples']:
            mode = int(row['mode'])
            r800 = expected == 6 and mode > 0
            hz = 5369318 if expected == 4 and mode else 3579545
            if row['locked'] != 'true' or row['cpu'] != ('r800' if r800 else 'z80') or int(row['z80_hz']) != hz:
                raise ValueError(f'Incorrect factory CPU mode: {row}')
            if expected == 6 and int(row['controller']) != (96, 64, 0)[mode]:
                raise ValueError(f'Incorrect R800 ROM/DRAM controller state: {row}')
            if mode and not float(row['seconds']) < base * .8:
                raise ValueError(f'Mode did not accelerate instructions: {row}')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--machine', choices=MACHINES, action='append')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'references'):
        parser.error('Probe outputs must stay below ignored references/')
    results = [run(output, machine) for machine in args.machine or MACHINES]
    report = dict(scope='Synthetic controller and CPU elapsed-time qualification; BIOS Page0 visible; not gameplay',
                  emulator=subprocess.check_output(['openmsx', '-v'], text=True).strip(), results=results)
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return int(any(r['returncode'] for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
