"""Synthetic all-phase/all-flag-mask radar variant and generated Z80 contracts.

python src/toolchain/screen4/test_game_radar.py
python src/toolchain/screen4/test_game_radar.py --emulator --bios references/msxbios
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from prepare import shifted_hud
from radar_variants import name_program, prepare_phase

ROOT = Path(__file__).resolve().parents[3]


def synthetic_hud(blue=1, yellow=12):
    # Three flags deliberately share some phase-local characters. Nontrivial
    # slot order makes reversed bit packing visible without native ROM data.
    cells = [(5, 3), (20, 30), (3, 3), (22, 3), (4, 30),
             (21, 3), (3, 30), (20, 3), (4, 3), (21, 30)]
    records = [dict(address=0x9800+y*32+x) for x, y in cells]
    hud = bytearray([blue])*(48*212)
    for x, y in cells:
        hud[(70+y*106//56)*48+8+x] = yellow
    return bytes(hud), records


def pixels(payload, tile):
    count = (len(payload)-224)//16
    pattern = payload[224+tile*8:224+(tile+1)*8]
    colors = payload[224+count*8+tile*8:224+count*8+(tile+1)*8]
    assert len(pattern) == len(colors) == 8
    return bytes(colors[y] >> 4 if pattern[y] & (128 >> x) else colors[y] & 15
                 for y in range(8) for x in range(8))


def point(record, phase):
    cell = record['address']-0x9800
    x = 8+cell%32+phase%8
    y = 70+(cell//32)*106//56+phase//8
    return (y//8)*7+x//8, (y%8)*8+x%8


def execute(code, active, names=0xd400):
    """Independent semantics for only the emitted instructions, no assembler."""
    memory = bytearray([0xee])*65536
    memory[0xa700:0xa700+len(code)] = code
    memory[0xc501:0xc50b] = active
    a = b = h = l = de = 0
    pc = 0xa700
    writes = {}
    while True:
        op = memory[pc]
        pc += 1
        if op in (0x3a, 0x11, 0x32):
            address = memory[pc]+256*memory[pc+1]
            pc += 2
            if op == 0x3a:
                a = memory[address]
            elif op == 0x11:
                de = address
            else:
                assert names <= address < names+1024
                assert address not in writes
                writes[address] = a
                memory[address] = a
        elif op == 0x87:
            a = a*2 & 255
        elif op == 0x47:
            b = a
        elif op == 0xb0:
            a |= b
        elif op == 0x6f:
            l = a
        elif op == 0x26:
            h = memory[pc]
            pc += 1
        elif op == 0x19:
            h, l = divmod((h*256+l+de) & 65535, 256)
        elif op == 0x7e:
            a = memory[h*256+l]
        elif op == 0xc9:
            return writes
        else:
            raise AssertionError(f'Unexpected opcode {op:02x} at {pc-1:04x}')


def expected_names(groups, mask, names=0xd400):
    result = {}
    for group in groups:
        selected = sum(((mask >> slot) & 1) << bit for bit, slot in enumerate(group['slots']))
        row, column = divmod(group['entry'], 7)
        result[names+row*32+26+column] = group['ids'][selected]
    return result


def phases():
    hud, records = synthetic_hud()
    for phase in range(64):
        n, p, c, _ = shifted_hud(hud, phase%8, phase//8, 11)
        payload, groups = prepare_phase(n+p+c, records, phase, 1)
        yield phase, payload, groups


class ExactRadar(unittest.TestCase):
    def test_every_local_visibility_mask_preserves_pixels_and_rgb(self):
        # Reversed numeric ink ordering also checks that variant encoding never
        # assumes that the foreground bit must represent the flag color.
        for blue, yellow, black in ((1, 12, 11), (9, 3, 6)):
            hud, records = synthetic_hud(blue, yellow)
            rgb = [bytes((i*13, 255-i*11, i*7)) for i in range(16)]
            for phase in range(64):
                n, p, c, _ = shifted_hud(hud, phase%8, phase//8, black)
                original = n+p+c
                prepared, groups = prepare_phase(original, records, phase, blue)
                self.assertEqual(prepared[:224], n)
                self.assertEqual(sorted(slot for group in groups for slot in group['slots']), list(range(10)))
                self.assertLessEqual((len(prepared)-224)//16, 64)
                # Existing character IDs keep their complete original pixels.
                for tile in set(n):
                    self.assertEqual(pixels(prepared, tile), pixels(original, tile))
                for group in groups:
                    expected_slots = [i for i, record in enumerate(records) if point(record, phase)[0] == group['entry']]
                    self.assertEqual(group['slots'], expected_slots)
                    source = pixels(original, n[group['entry']])
                    for mask, tile in enumerate(group['ids']):
                        expected = bytearray(source)
                        for bit, slot in enumerate(expected_slots):
                            if not mask & (1 << bit):
                                expected[point(records[slot], phase)[1]] = blue
                        actual = pixels(prepared, tile-96)
                        self.assertEqual(actual, expected, (phase, group, mask))
                        self.assertEqual(b''.join(rgb[x] for x in actual), b''.join(rgb[x] for x in expected))

    def test_generated_program_all_65536_phase_and_global_flag_masks(self):
        for phase, payload, groups in phases():
            code = name_program(groups)
            self.assertLess(0xa700+len(code), 0xc000)
            for mask in range(1024):
                active = bytes((mask >> i) & 1 for i in range(10))
                self.assertEqual(execute(code, active), expected_names(groups, mask), (phase, mask))


def verify_emulator(bios):
    sys.path.insert(0, str(ROOT))
    from src.toolchain.msx.emulator import reference_machine, tcl
    out = ROOT/'outputs/fixed-hud/radar-synthetic'
    out.mkdir(parents=True, exist_ok=True)
    programs, expected = bytearray(), bytearray()
    for phase, payload, groups in phases():
        code = name_program(groups)
        assert len(code) <= 512
        programs.extend(code.ljust(512, b'\0'))
        for mask in range(1024):
            names = bytearray([0xee])*1024
            for address, value in expected_names(groups, mask).items():
                names[address-0xd400] = value
            expected.extend(names)
    (out/'programs.bin').write_bytes(programs)
    (out/'expected.bin').write_bytes(expected)
    (out/'probe.asm').write_text(''' OUTPUT "probe.rom"
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
main:
 jp main
 defs $8000-$,$ff
''')
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', 'probe.asm'], cwd=out, check=True)
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT, 'Panasonic_FS-A1WSX'), 'set firmwareswitch off', 'set throttle off',
             'set z80_freq 3579545', 'set z80_freq_locked false', 'set limitsprites true',
             f'cart {tcl(out/"probe.rom")} -romtype Normal', 'reset', f'set out {tcl(out)}',
             'set f [open [file join $out programs.bin] rb];set programs [read $f];close $f',
             'set f [open [file join $out expected.bin] rb];set expected [read $f];close $f',
             'set index 0;set started 0;set blank [binary format c* [lrepeat 1024 238]]',
             'proc issue {} {',
             ' if {$::index==65536} {puts "Generated Z80 radar names passed 65536 cases";exit 0;return}',
             ' set mask [expr {$::index&1023}]',
             ' if {$mask==0} {',
             '  set at [expr {($::index>>10)*512}]',
             '  debug write_block memory 0xa700 [string range $::programs $at [expr {$at+511}]]',
             '  debug write_block memory 0xd400 $::blank',
             ' }',
             ' for {set i 0} {$i<10} {incr i} {debug write memory [expr {0xc501+$i}] [expr {($mask>>$i)&1}]}',
             ' set p 0xd110;foreach v {205 0 167 195 64 209} {debug write memory $p $v;incr p}',
             ' reg SP 0xf380;reg PC 0xd110', '}',
             'debug set_bp 0x4014 {!$::started} {set ::started 1;issue}',
             'debug set_bp 0xd140 {$::started} {',
             ' set at [expr {$::index*1024}]',
             ' if {[debug read_block memory 0xd400 1024] ne [string range $::expected $at [expr {$at+1023}]]} {error "Generated radar mismatch $::index"}',
             ' incr ::index;issue', '}',
             'after time 60 {puts stderr "Radar probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx', '-script', str(out/'session.tcl')], check=True, stdout=log, stderr=subprocess.STDOUT,
                       timeout=90, env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    report = dict(complete=True, cases=65536, phases=64, masks_per_phase=1024,
                  machine='Panasonic_FS-A1WSX_NR128', cpu_hz=3579545,
                  rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(),
                  programs_sha256=hashlib.sha256(programs).hexdigest(),
                  scope='Generated native Z80 programs, all 1024 name RAM bytes compared; synthetic flags/HUD only; no complete gameplay or scanout claim')
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Generated native Z80 radar names passed all 65,536 phase/mask cases')


if __name__ == '__main__':
    if '--emulator' in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--emulator', action='store_true')
        parser.add_argument('--bios', required=True)
        verify_emulator(parser.parse_args().bios)
    else:
        unittest.main()
