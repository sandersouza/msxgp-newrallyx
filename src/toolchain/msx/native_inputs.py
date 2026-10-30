"""Validate assembled hardware-adapter evidence without claiming gameplay."""
import csv
from concurrent.futures import ThreadPoolExecutor
import gzip
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

JOYSTICK_CASES = ((63, 255), (62, 223), (61, 239), (59, 251), (55, 247),
                  (47, 253), (31, 255), (0, 193), (63, 255))
OUTPUT_CASES = (0, 1, 2, 3, 16, 64, 128, 255)


def analyze_joystick(path: Path) -> dict:
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    cases = [(joy, expected, prior) for joy, expected in JOYSTICK_CASES for prior in OUTPUT_CASES]
    fields = {'case','joystick_level','expected','psg_before','ppi_before','actual','ppi_after','psg_after'}
    if len(rows) != len(cases):
        raise ValueError('Incomplete emulated joystick proof')
    for n, (row, (joy, expected, prior)) in enumerate(zip(rows, cases)):
        if set(row) != fields or any(not isinstance(v, str) or not v.isdecimal() for v in row.values()):
            raise ValueError('Malformed emulated joystick proof')
        expected_row = dict(case=n, joystick_level=joy, expected=expected,
                            psg_before=prior, ppi_before=prior ^ 0xa0, actual=expected,
                            ppi_after=prior ^ 0xa0, psg_after=prior)
        if {k: int(v) for k, v in row.items()} != expected_row:
            raise ValueError(f'Emulated joystick mapping/output preservation failed at case {n}')
    return dict(joystick_cases=len(rows), joystick_directions_verified=True,
                emulated_peripheral_state=True, physical_controller_verified=False,
                gameplay_verified=False)


def verify_inputs(root: Path, args) -> Path:
    """Run real keyboard I/O and synthetic joystick peripheral levels in openMSX.

    Joystick snapshots come from this cartridge's cold boot, with only the
    emulator peripheral status changed. Never seed or change original game RAM.
    All machine snapshots and cartridges remain in ignored output directories.
    """
    import argparse
    from .build import destination
    from .emulator import reference_machine, tcl
    from .native_probe import symbols
    from .native_verify import acquire
    from src.toolchain.scenes.bundle import digest, read_json, verify_manifest
    from src.toolchain.scenes.storage import json_write, require_ignored, seal

    verify_manifest(args.rom.parent)
    report = read_json(args.rom.parent/'build.json')
    if args.rom.name != 'native.rom' or not report.get('video_candidate'):
        raise ValueError('Input proof requires a sealed video candidate')
    output = destination(root, args.output)
    require_ignored(root, [output/'base.oms', output/'joystick.tsv'])
    output.mkdir(parents=True)
    candidate_hash = digest(args.rom.parent/'manifest.json')
    before = {str(p): digest(p) for p in args.bios.rglob('*') if p.is_file()}
    keyboard_args = argparse.Namespace(**{**vars(args), 'output': output/'keyboard',
        'hz': report['timing']['nominal_hz'], 'ticks': 128, 'profile': None,
        'scanout': False, 'input_proof': True})
    acquire(root, keyboard_args)
    syms = symbols(args.rom.parent/'native.sym')

    def execute(script, folder):
        path = folder/'probe.tcl'
        path.write_text('if {[catch {\n'+'\n'.join(script)+'\n} problem]} {puts stderr $problem; exit 2}\n')
        with (folder/'emulator.log').open('w') as log:
            subprocess.run([args.openmsx,'-script',str(path)],check=True,timeout=120,
                env=dict(os.environ,OPENMSX_HOME=str(folder/'home'),OPENMSX_USER_DATA=str(folder/'userdata')),
                stdout=log,stderr=subprocess.STDOUT)

    common = ['set save_settings_on_exit false','set sound_driver null','set renderer none',
              f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1']
    execute(common + [reference_machine(root,args.machine),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        'catch {unplug joyporta}','plug joyporta msxjoystick1',
        f'debug set_bp {syms["Native_ReadInputs"]} {{[reg IM] == 2 && [reg I] == 208}} {{store_machine [machine] {tcl(output/"base.oms")}; exit 0}}',
        'after time 120 {puts stderr "Input state capture timeout"; exit 2}'], output)
    base = gzip.decompress((output/'base.oms').read_bytes())
    cases = [(joy, expected, prior) for joy, expected in JOYSTICK_CASES for prior in OUTPUT_CASES]

    def joystick(item):
        n, (joy, expected, prior) = item
        folder = output/f'joystick-{n:02d}'
        folder.mkdir()
        state = ET.fromstring(base)
        node = state.find('.//joystickportA/Connector/pluggable[@type="MSXJoystick"]/status')
        if node is None:
            raise ValueError('Missing emulated joystick peripheral state')
        node.text = str(joy)
        header = b'<?xml version="1.0" ?>\n<!DOCTYPE openmsx-serialize SYSTEM "openmsx-serialize.dtd">\n'
        require_ignored(root, [folder/'input.oms'])
        (folder/'input.oms').write_bytes(gzip.compress(header+ET.tostring(state,encoding='utf-8')))
        ppi = prior ^ 0xa0
        execute(common + [f'set selected [restore_machine {tcl(folder/"input.oms")}]',
            'set old [machine]','if {$old ne ""} {delete_machine $old}','activate_machine $selected',
            'set throttle off','keymatrixup 0 255','keymatrixup 8 255',
            'proc game_bytes {} {return "[debug read_block memory 32768 4096][debug read_block memory 38912 2048][debug read_block memory 40960 392]"}',
            'set original [game_bytes]',
            f'debug write "PSG regs" 15 {prior}',f'debug write ioports 170 {ppi}',
            f'debug set_bp {syms["Native_InputReturn"]} {{}} {{',
            'if {$::original ne [game_bytes]} {puts stderr "Input adapter changed original RAM"; exit 2}',
            f'set file [open {tcl(folder/"result.tsv")} w]',
            f'puts $file "{n}\t{joy}\t{expected}\t{prior}\t{ppi}\t[debug read memory {syms["Native_InputCache"]}]\t[debug read ioports 170]\t[debug read {{PSG regs}} 15]"',
            'close $file; exit 0','}',
            'after time 0.1 {puts stderr "Input return timeout"; exit 2}'],folder)
        return (folder/'result.tsv').read_text().strip().split('\t')

    rows = [joystick((0,cases[0]))]  # Fail before dispatching the remaining cases.
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows.extend(pool.map(joystick,list(enumerate(cases))[1:]))
    with (output/'joystick.tsv').open('w') as stream:
        writer = csv.writer(stream,delimiter='\t')
        writer.writerow(('case','joystick_level','expected','psg_before','ppi_before','actual','ppi_after','psg_after'))
        writer.writerows(rows)
    verify_manifest(args.rom.parent)
    if candidate_hash != digest(args.rom.parent/'manifest.json') or before != {
            str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('Input proof source/BIOS inventory changed')
    json_write(output/'verification.json',{
        **analyze_keyboard(output/'keyboard/physical-inputs.tsv'),
        **analyze_joystick(output/'joystick.tsv'), 'candidate_manifest_sha256': candidate_hash,
        'original_game_ram_unchanged': True})
    require_ignored(root, [p for p in output.rglob('*') if p.is_file()])
    seal(output)
    return output


def analyze_keyboard(path: Path) -> dict:
    cases = ((0, 0, 255), (0, 32, 127), (0, 2, 191), (8, 32, 223),
             (8, 64, 239), (8, 16, 251), (8, 128, 247), (8, 1, 253), (8, 177, 209))
    priors = (0, 1, 2, 3, 16, 64, 128, 255)
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    if len(rows) != len(cases)*len(priors):
        raise ValueError('Incomplete physical keyboard proof')
    fields = {'case', 'row', 'mask', 'prior', 'expected', 'actual',
              'ppi_before', 'ppi_after', 'psg_after', 'p2', 'dip'}
    for n, row in enumerate(rows):
        if set(row) != fields or any(not isinstance(v, str) or not v.isdecimal() for v in row.values()):
            raise ValueError('Malformed physical keyboard proof')
        values = {key: int(value) for key, value in row.items()}
        r, mask, expected = cases[n//len(priors)]
        if (values['case'] != n or values['row'] != r or values['mask'] != mask
                or values['prior'] != priors[n%len(priors)]
                or values['expected'] != expected or values['actual'] != expected
                or not 0 <= values['ppi_before'] <= 255
                or values['ppi_before'] != values['ppi_after']
                or values['prior'] != values['psg_after']
                or values['p2'] != 255 or values['dip'] != 195):
            raise ValueError(f'Physical keyboard mapping/output preservation failed at case {n}')
    return dict(keyboard_cases=len(rows), keyboard_matrix_verified=True,
                joystick_directions_verified=False, gameplay_verified=False)
