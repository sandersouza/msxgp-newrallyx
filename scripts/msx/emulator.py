"""Launch the current cartridge in an isolated openMSX session."""
import os
import subprocess
from scripts.scenes.bundle import digest
from scripts.scenes.storage import require_ignored
from .build import destination


def tcl(value):
    """Quote one literal Tcl word without command/variable substitution."""
    value = str(value)
    return '"' + ''.join('\\'+c if c in '\\"$[]{}' else '\\n' if c=='\n' else c for c in value) + '"'


def reference_machine(root, name):
    return (f'source {tcl(root/"scripts/msx/mapper_reference.tcl")}\n'
            f'nrallyx_reference_machine {tcl(name)}')


def scanout_recording_tcl(output, startup_pc):
    """Force every raw video frame without changing guest clocks or state.

    openMSX's automatic host deadline can skip a rendered frame even with both
    frameskip settings zero. Recording keeps complete raw frames available.
    Start at cartridge startup, after the video system has been initialized.
    """
    action=(f'if {{[catch {{record start -videoonly {tcl(output/"scanout.avi")}}} problem]}} '
            '{puts stderr $problem;exit 2};set ::scanout_recording_started 1')
    return (f'debug set_bp {startup_pc} '
            '{![info exists ::scanout_recording_started]} {'+action+'}')


def run(root, args):
    output = destination(root,args.output)
    if not args.bios.is_dir():
        raise ValueError('Supply compatible BIOS files below references/msxbios or supply --bios')
    if not args.rom.is_file():
        raise ValueError('Cartridge missing; run make build or supply --rom')
    bios_hashes = {p.relative_to(args.bios).as_posix():digest(p)
                   for p in sorted(args.bios.rglob('*')) if p.is_file()}
    require_ignored(root,[output/'session.tcl', output/'emulator.log'])
    output.mkdir(parents=True)
    env = dict(os.environ, OPENMSX_HOME=str(output/'home'), OPENMSX_USER_DATA=str(output/'userdata'))
    # The process gets its own user data/settings/cache; no global configuration changes.
    lines = ['set save_settings_on_exit false',
             f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
             f'if {{[catch {{{reference_machine(root,args.machine)}}} problem]}} {{',
             '  puts stderr "BIOS/machine load failed: $problem. Check machine ROM SHA-1 requirements and --bios."',
             '  exit 2', '}',
             'set firmwareswitch off', 'set speed 100', 'set throttle on',
             'set vsync off',
             'set z80_freq 3579545', 'set z80_freq_locked false',
             'set gamma 1.0', 'set brightness 0', 'set contrast 0',
             'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
             'set scanline 0', 'set blur 0', 'set noise 0',
             f'cart {tcl(args.rom.resolve())} -romtype ASCII16', 'reset']
    script=output/'session.tcl'
    script.write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem; exit 2}\n')
    command=[args.openmsx,'-script',str(script)]
    with (output/'emulator.log').open('w') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                              timeout=None)
    if result.returncode:
        raise ValueError(f'openMSX failed; inspect {output}/emulator.log. Check selected machine and supplied BIOS hashes.')
    if bios_hashes != {p.relative_to(args.bios).as_posix():digest(p)
                      for p in sorted(args.bios.rglob('*')) if p.is_file()}:
        raise ValueError('BIOS inventory changed during emulation')
    require_ignored(root,[p for p in output.rglob('*') if p.is_file()])
