"""Synthetic exact boundary-packet allocation, poisoned tails and bank checks."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from game_boundary_fast import ARRAYS, BANK_BYTES, PHASE_BANK_FIRST, POINTER_OFFSET, append_packets, packet


def synthetic_banks():
    # Existing HUD packet pages follow all64 phase banks; the boundary builder
    # must append to them without assuming a fixed first packet bank.
    banks = bytearray([255])*(71*BANK_BYTES)
    for phase in range(64):
        fx = phase & 7
        start = (PHASE_BANK_FIRST+phase)*BANK_BYTES
        counts = ((1, 2, 3, 5, 17, 31, 47, 48)[fx], (48, 47, 31, 17, 5, 3, 2, 1)[fx])
        banks[start+0x0f00], banks[start+0x1500] = counts
        for which, (offset, count_at, destination) in enumerate(ARRAYS):
            length = counts[which//2]*8
            # Patterns vary sparsely, colors preserve long common prefixes.
            data = bytes(((i*13+17+(fx*7 if i % 17 == 0 else 0)) & 255)
                         if which % 2 == 0 else ((i//8*3+0x41) & 255) for i in range(length))
            banks[start+offset:start+offset+length] = data
        banks[start+0x3ff0] = phase
    return banks


def independent_arrays(banks, fx):
    start = (3+fx)*16384
    counts = (banks[start+0x0f00]*8, banks[start+0x1500]*8)
    return ((0x0500, bytes(banks[start+0x0b00:start+0x0b00+counts[0]])),
            (0x4500, bytes(banks[start+0x0d00:start+0x0d00+counts[0]])),
            (0x0680, bytes(banks[start+0x1100:start+0x1100+counts[1]])),
            (0x4680, bytes(banks[start+0x1300:start+0x1300+counts[1]])))


def decode(banks, phase, previous):
    at = (3+phase)*16384+0x2900+previous*3
    bank, lo, hi = banks[at:at+3]
    cursor = (bank-1)*16384+(hi*256+lo)-0x8000
    end = bank*16384
    writes = []
    while True:
        assert cursor+3 <= end, 'Header crosses mapper page'
        lo, hi, length = banks[cursor:cursor+3]
        cursor += 3
        if not length:
            assert lo == hi == 0
            return bank, writes
        assert cursor+length <= end, 'Payload crosses mapper page'
        writes.append((lo+hi*256, bytes(banks[cursor:cursor+length])))
        cursor += length


class ExactBoundaryPackets(unittest.TestCase):
    def test_every_transition_both_tables_all_fy_and_poisoned_absent_tails(self):
        source = synthetic_banks()
        before = bytes(source)
        with tempfile.TemporaryDirectory() as directory:
            result = append_packets(source, directory)
            report = json.loads((Path(directory)/'boundary-cost.json').read_text())
        self.assertEqual(source, before, 'The caller input must remain untouched')
        self.assertEqual(report['transitions'], 72)
        self.assertGreaterEqual(report['first_packet_bank'], 72)
        for current in range(8):
            expected = independent_arrays(source, current)
            allowed = {base+i for base, data in expected for i in range(len(data))}
            for previous in range(9):
                _, writes = decode(result, current, previous)
                for fy in range(1, 8):
                    self.assertEqual(decode(result, current+fy*8, previous), decode(result, current, previous))
                written = {base+i for base, data in writes for i in range(len(data))}
                self.assertLessEqual(written, allowed)
                old = independent_arrays(source, previous) if previous < 8 else tuple((base, b'') for base, _ in expected)
                for (base, old_data), (_, new_data) in zip(old, expected):
                    for i, value in enumerate(new_data):
                        if i >= len(old_data) or old_data[i] != value:
                            self.assertIn(base+i, written, (previous, current, base, i))
                for back in range(2):
                    for poison in (0x5a, 0xee, 0xff):
                        memory = bytearray([poison])*131072
                        for base, data in old:
                            memory[base+back*0x8000:base+back*0x8000+len(data)] = data
                        original = memory[:]
                        for base, data in writes:
                            self.assertLessEqual(len(data), 255)
                            memory[base+back*0x8000:base+back*0x8000+len(data)] = data
                        for base, data in expected:
                            self.assertEqual(memory[base+back*0x8000:base+back*0x8000+len(data)], data,
                                             (previous, current, back, poison, base))
                        for base, data in writes:
                            original[base+back*0x8000:base+back*0x8000+len(data)] = data
                        self.assertEqual(memory, original)
        # Existing pages change only in the27 reserved bytes of each phase.
        for phase in range(64):
            at = (3+phase)*BANK_BYTES+POINTER_OFFSET
            source[at:at+27] = result[at:at+27]
        self.assertEqual(result[:len(source)], source)

    def test_chunks_and_gap_merging_remain_bounded_and_exact(self):
        empty = (b'',)*4
        data = bytes(range(256))+bytes(range(128))
        current = (data, b'', b'', b'')
        encoded = packet(empty, current)
        self.assertEqual(encoded[2], 255)
        self.assertEqual(encoded[258+2], 129)
        old = (bytes(50), b'', b'', b'')
        new = bytearray(50)
        new[0] = new[13] = new[27] = 1
        encoded = packet(old, (bytes(new), b'', b'', b''))
        self.assertEqual(encoded[:3], bytes((0, 5, 14)))
        self.assertEqual(encoded[17:20], bytes((27, 5, 1)))

    def test_identical_atlases_deduplicate_all_empty_packets(self):
        source = synthetic_banks()
        with tempfile.TemporaryDirectory() as directory:
            result = append_packets(source, directory)
        references = []
        for current in range(8):
            at = (3+current)*BANK_BYTES+POINTER_OFFSET+current*3
            references.append(bytes(result[at:at+3]))
        self.assertEqual(len(set(references)), 1)
        self.assertEqual(decode(result, 0, 0)[1], [])

    def test_fy_dependent_graphics_and_pointer_collisions_are_rejected(self):
        for at in ((3+8)*BANK_BYTES+0x0b00, 3*BANK_BYTES+POINTER_OFFSET):
            source = synthetic_banks()
            source[at] = 127
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(AssertionError):
                    append_packets(source, directory)


def verify_emulator(bios, bundle=None):
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    sys.path.insert(0, str(root))
    from src.toolchain.msx.emulator import reference_machine, tcl
    out = (root/'references/experiments/fixed-hud/boundary-fast-bundle' if bundle else
           root/'outputs/fixed-hud/boundary-fast-synthetic')
    out.mkdir(parents=True, exist_ok=True)
    if bundle:
        bundle = Path(bundle).resolve()
        source_rom = next(path for path in (bundle/'fixed-hud.rom', bundle/'measured.rom') if path.exists())
        rom = out/'probe.rom'
        rom.write_bytes(source_rom.read_bytes())
        source = banks = rom.read_bytes()[16384:]
        (out/'probe.sym').write_bytes((bundle/'lab.sym').read_bytes())
    else:
        source = synthetic_banks()
        banks = append_packets(source, out)
        lab = (here/'lab.asm').read_text()
        worker = 'hud_upload:\n'+lab[lab.index('.packet:\n', lab.index('hud_upload:\n')):lab.index('.full:\n', lab.index('hud_upload:\n'))]
        (out/'probe.asm').write_text(''' OUTPUT "probe.rom"
phase EQU $c01d
prior_phase EQU $c020
hud_page EQU $c024
back EQU $c006
     MACRO reg number,value
     ld a,value
     out ($99),a
     ld a,$80+number
     out ($99),a
     ENDM
     ORG $4000
     db "AB"
     dw boot,0,0,0,0,0,0
boot:
     di
     ld sp,$f380
     call $0138
     rrca
     rrca
     and 3
     ld c,a
     ld b,0
     ld hl,$fcc1
     add hl,bc
     ld a,(hl)
     and $80
     or c
     ld c,a
     ld de,4
     add hl,de
     ld a,(hl)
     and $0c
     or c
     ld h,$80
     call $0024
     ld a,4
     call $005f
     di
     reg 0,4
     reg 1,$42
     reg 8,$28
     reg 9,$80
main:
     jp main
    '''+f' INCLUDE "{here/"game-boundary-fast.inc"}"\n'+worker+'''
Probe_End:
     ASSERT $ < $8000
     defs $8000-$,$ff
    ''')
        assembled = subprocess.run([str(root/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', '--sym=probe.sym', 'probe.asm'], cwd=out, capture_output=True, text=True)
        if assembled.returncode:
            raise AssertionError(assembled.stdout+assembled.stderr)
        rom = out/'probe.rom'
        rom.write_bytes(rom.read_bytes()+banks)
    syms = {n: int(v, 16) for n, v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)', (out/'probe.sym').read_text())}
    (out/'phase-banks.bin').write_bytes(banks[3*16384:67*16384])
    initial, expected, cases = bytearray(), bytearray(), []
    for previous in range(9):
        for current in range(8):
            phase = ((previous+current) & 7)*8+current
            for table in range(2):
                memory = bytearray([0xee])*131072
                if previous < 8:
                    for at, data in independent_arrays(source, previous):
                        memory[at+table*0x8000:at+table*0x8000+len(data)] = data
                initial.extend(memory)
                for at, data in independent_arrays(source, current):
                    memory[at+table*0x8000:at+table*0x8000+len(data)] = data
                expected.extend(memory)
                prior = 255 if previous == 8 else previous+8*((current+3) & 7)
                cases.append((phase, prior, table))
    (out/'initial.bin').write_bytes(initial)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(root, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(rom)} -romtype ASCII16', 'reset', f'set out {tcl(out)}',
             'set f [open [file join $out initial.bin] rb];set initial [read $f];close $f',
             'set f [open [file join $out phase-banks.bin] rb];set phase_banks [read $f];close $f',
             'set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w]',
             'set index 0;set started 0;set fast 0',
             'set VDP.too_fast_vram_access_callback {if {$::started} {incr ::fast}}',
             'set cases {'+' '.join('{'+f'{phase} {prior} {table}'+'}' for phase, prior, table in cases)+'}',
             'proc issue {} {',
             f' if {{$::index=={len(cases)}}} {{close $::result;close $::timing;set f [open [file join $::out strict.txt] w];puts $f $::fast;close $f;exit 0;return}}',
             ' lassign [lindex $::cases $::index] phase prior table',
             ' set at [expr {$::index*131072}];debug write_block VRAM 0 [string range $::initial $at [expr {$at+131071}]]',
             ' debug write memory 0xc01d $phase;debug write memory 0xc020 $prior;debug write memory 0xc006 $table',
             f' set p 0xd180;foreach v [list 62 [expr {{$phase+4}}] 50 0 112 205 {syms["GameBoundary_Upload"]&255} {syms["GameBoundary_Upload"]>>8} 243 195 192 209] {{debug write memory $p $v;incr p}}',
             ' reg SP 0xf380;reg PC 0xd180', '}',
             f'debug set_bp {syms["loop" if bundle else "main"]} {{!$::started}} {{set ::started 1;issue}}',
             f'debug set_bp {syms["GameBoundary_Upload"]} {{$::started}} {{set ::begin [machine_info time]}}',
             'debug set_bp 0xd188 {$::started} {set ::cycles [expr {round(([machine_info time]-$::begin)*3579545)}]}',
             'debug set_bp 0xd1c0 {$::started} {',
             ' lassign [lindex $::cases $::index] phase prior table',
             ' set at [expr {$phase*16384}]',
             ' if {[debug read_block memory 0x8000 16384] ne [string range $::phase_banks $at [expr {$at+16383}]]} {puts stderr "Phase mapper not restored case=$::index phase=$phase";exit 3}',
             ' puts -nonewline $::result [debug read_block VRAM 0 131072];puts $::timing $::cycles',
             ' incr ::index;issue', '}',
             'after time 60 {puts stderr "Boundary probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, stdout=log, stderr=subprocess.STDOUT,
                       timeout=90, env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'actual.bin').read_bytes()
    if actual != expected:
        at = next(i for i, (a, e) in enumerate(zip(actual, expected)) if a != e)
        raise AssertionError(f'Native boundary mismatch case {at//131072}, VRAM address {at%131072:05x}')
    callbacks = int((out/'strict.txt').read_text())
    assert callbacks == 0, f'Strict VRAM timing callbacks: {callbacks}'
    values = [int(v) for v in (out/'cycles.txt').read_text().split()]
    report = dict(complete=True, cases=len(cases), transitions=72, back_buffers=2,
                  exact_vram_bytes_per_case=131072, strict_vram_callbacks=callbacks,
                  cpu_hz=3579545, video_hz_nominal=60, machine='Panasonic_FS-A1WSX_NR128', hardware_sprite_limits=True,
                  helper_bytes=syms['GameBoundary_Upload_End']-syms['GameBoundary_Upload'],
                  helper_sha256=hashlib.sha256((here/'game-boundary-fast.inc').read_bytes()).hexdigest(),
                  rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
                  cycles=dict(mean=sum(values)/len(values), minimum=min(values), maximum=max(values)),
                  bundle=str(bundle) if bundle else None,
                  scope=('Compiled bundle with actual atlas payloads and resident helper/packet worker. ' if bundle else 'Synthetic four-atlas payloads and existing packet worker verbatim. ')+' Inclusive helper entry-to-return elapsed cycles including wait states. Full128KiB VRAM plus exact restored phase mapper checked. SCREEN4 display-on60Hz strict callback. No integrated gameplay/presentation/physical-hardware claim.')
    (out/'native-result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    if '--emulator' in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--emulator', action='store_true')
        parser.add_argument('--bios', required=True)
        parser.add_argument('--bundle', type=Path)
        args = parser.parse_args()
        verify_emulator(args.bios, args.bundle)
    else:
        unittest.main()
