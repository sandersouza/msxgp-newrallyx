"""Differential original/native round preparation component proof."""
import os
import subprocess

from src.toolchain.graphics.roms import input_records, load_metadata, validate_roms
from src.toolchain.scenes.bundle import digest, read_json, verify_manifest
from src.toolchain.scenes.record import lua_literal
from src.toolchain.scenes.storage import json_write, require_ignored, seal
from .build import destination
from .emulator import reference_machine, tcl
from .hud_verify import symbols
from .native_reset import PROGRAM_SHA256
from .round_objects import owners, at as object_at


def relocated_seed(source):
    """Relocate declared pointer fields, retaining object-cell identifiers."""
    if len(source) != 4096:
        raise ValueError('Incomplete round seed')
    native = bytearray(source)
    for at in range(0x988, 0x99e, 2):
        value = int.from_bytes(native[at:at+2], 'little')
        if not 0x8000 <= value < 0x9000:
            raise ValueError(f'Unexpected round RAM pointer at {at:03x}')
        native[at:at+2] = (value+0x6000).to_bytes(2, 'little')
    for at in (0x1b3, 0x1b9, 0x2d2):
        value = int.from_bytes(native[at:at+2], 'little')
        if not 0 <= value < 0x4000:
            raise ValueError(f'Unexpected round ROM pointer at {at:03x}')
        native[at:at+2] = (value+0x8000).to_bytes(2, 'little')
    native[0x28f] |= 128
    return bytes(native)


def verify(root, args):
    bundle = args.rom.resolve().parent
    reference = args.reference.resolve()
    verify_manifest(bundle); verify_manifest(reference)
    source = input_records(validate_roms(root/'references/roms/nrallyx', load_metadata()))
    if read_json(reference/'report.json')['roms'] != source or digest(bundle/'native-program.bin') != PROGRAM_SHA256:
        raise ValueError('Round proof inputs differ from the verified contributor program')
    component = read_json(bundle/'round-preparation.json')
    if component['native_entry'] != 0x88bf:
        raise ValueError('Unexpected round preparation entry')
    out = destination(root, args.output)
    require_ignored(root, [out/'source-seed.bin']); out.mkdir(parents=True)
    seed = (reference/'case-000-video.bin').read_bytes()
    if seed[0x1b0] != 2 or seed[0x20] != 2:
        raise ValueError('Expected original first-game seed')
    native = relocated_seed(seed)
    (out/'source-seed.bin').write_bytes(seed); (out/'native-seed.bin').write_bytes(native)
    cases = [[round_, value & 255, value >> 8]
             for round_ in range(2, args.last_round+2) for value in (1, 0x1234)]
    (out/'cases.bin').write_bytes(bytes(v for case in cases for v in case))
    config = out/'config.lua'
    config.write_text('return '+lua_literal(dict(output=str(out.resolve()), cases=cases))+'\n')
    version = subprocess.check_output([args.mame, '-version'], text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Round proof requires MAME 0.289')
    command = [args.mame, 'nrallyx', '-noreadconfig', '-noplugins', '-nocheat',
        '-rompath', str(root/'references/roms'), '-video', 'none', '-sound', 'none',
        '-nothrottle', '-noautosave', '-noautoframeskip', '-frameskip', '0',
        '-skip_gameinfo', '-debug', '-debugger', 'none', '-autoboot_delay', '0',
        '-autoboot_script', str(root/'src/toolchain/msx/round_prepare_native.lua'),
        '-cfg_directory', str(out/'cfg'), '-nvram_directory', str(out/'nvram'),
        '-seconds_to_run', str(10+len(cases)*2)]
    with (out/'mame.log').open('w') as log:
        subprocess.run(command, check=True, timeout=180, stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, ROUND_PREPARE_CONFIG=str(config.resolve())))
    original = (out/'original.bin').read_bytes()
    if not (out/'complete').is_file() or len(original) != len(cases)*4096:
        raise ValueError(f'Incomplete source preparation proof: {out}/mame.log')
    syms = symbols(bundle/'raster-scroll.sym')
    bios = {str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    lines = ['set save_settings_on_exit false', 'set renderer none', 'set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root, args.machine), 'set firmwareswitch off', 'set throttle off',
        'set z80_freq 3579545', 'set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16', 'reset', f'set out {tcl(out)}',
        'foreach n {cases native-seed} {set f [open [file join $out "$n.bin"] rb];set data($n) [read $f];close $f}',
        'set result [open [file join $out msx.bin] wb];set objects [open [file join $out objects.bin] wb];set lookups [open [file join $out lookups.bin] wb];set index 0;set started 0',
        'proc issue {} {',
        f' if {{$::index=={len(cases)}}} {{close $::result;close $::objects;close $::lookups;exit 0;return}}',
        ' debug write_block memory 0xe000 $::data(native-seed)',
        ' set p [expr {$::index*3}];binary scan [string range $::data(cases) $p [expr {$p+2}]] cu* c',
        ' lassign $c round lo hi;debug write memory 0xe1b0 [expr {$round-1}]',
        ' debug write memory 0xe000 $lo;debug write memory 0xe001 $hi;debug write memory 0xe292 0',
        f' debug write memory 0x7000 {syms["PLAYER_BANK"]}',
        ' debug write memory 0xdbff 90;debug write memory 0xdf80 165',
        ' set p 0xd110;foreach v {243 205 191 136 205 0 172 195 64 209} {debug write memory $p $v;incr p}',
        ' reg SP 0xc7f0;reg PC 0xd110', '}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved [debug read_block VRAM 0 131072];issue}}',
        'debug set_bp 0xd140 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read_block VRAM 0 131072] ne $::saved} {error "Round adapter changed VRAM/stack"}',
        ' if {[debug read memory 0xdbff]!=90 || [debug read memory 0xdf80]!=165} {error "Object-map bounds changed"}',
        ' puts -nonewline $::result [debug read_block memory 0xe000 4096]',
        ' puts -nonewline $::objects [debug read_block memory 0xdc00 896]',
        ' set p 0xd150;foreach v {243 205 6 172 195 96 209} {debug write memory $p $v;incr p}',
        ' reg PC 0xd150', '}',
        'debug set_bp 0xd160 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read_block VRAM 0 131072] ne $::saved} {error "Object lookup changed VRAM/stack"}',
        ' puts -nonewline $::lookups [debug read_block memory 0xe400 1792];incr ::index;issue', '}',
        'after time 180 {puts stderr "Native round preparation timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx, '-script', str(out/'session.tcl')], check=True, timeout=180,
            stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'msx.bin').read_bytes()
    expected = b''.join(relocated_seed(original[i:i+4096]) for i in range(0,len(original),4096))
    if actual != expected:
        at = next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b), min(len(actual),len(expected)))
        raise ValueError(f'Round preparation mismatch case {at//4096}, offset {at%4096:03x}, fixture {cases[at//4096]}')
    packed = [owners(original[i:i+4096]) for i in range(0,len(original),4096)]
    if (out/'objects.bin').read_bytes() != b''.join(packed):
        raise ValueError('Dynamic object ownership differs from original placements')
    if (out/'lookups.bin').read_bytes() != bytes(object_at(p,cell) for p in packed for cell in range(1792)):
        raise ValueError('Native object lookup differs from independent cell ownership')
    if bios != {str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('Round proof BIOS changed')
    verify_manifest(bundle); verify_manifest(reference)
    if source != input_records(validate_roms(root/'references/roms/nrallyx', load_metadata())):
        raise ValueError('Round proof source ROMs changed')
    json_write(out/'report.json', dict(rom_sha256=digest(args.rom), reference_manifest_sha256=digest(reference/'manifest.json'),
        cases=len(cases), bytes_per_case=4096, vram_unchanged=True, stack_unchanged=True,
        last_displayed_round=args.last_round, random_seeds=[1,0x1234],
        object_map_bytes=896,object_cells_checked=len(cases)*1792,object_map_canaries=True,
        source_sha256={str(p.relative_to(root)):digest(p) for p in
                       (root/'src/toolchain/msx/round_prepare_native.lua', root/'src/toolchain/msx/round_prepare_verify.py')},
        scope='Isolated increment, parameter and object-placement outputs; declared pointer/page relocation only. '
              'No full-match, presentation, transition or wall-clock equivalence claim.'))
    require_ignored(root, [p for p in out.rglob('*') if p.is_file()]); seal(out)
    print(f'{len(cases)} exact original/native round preparation cases: {out}/report.json')
    return out
