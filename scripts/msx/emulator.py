"""Session-local openMSX startup and real keyboard/screenshot integration."""
import os
from pathlib import Path
import subprocess
from PIL import Image, ImageChops
from scripts.scenes.bundle import digest
from scripts.scenes.storage import json_write, require_ignored
from .build import destination


def tcl(value):
    """Quote one literal Tcl word without command/variable substitution."""
    value = str(value)
    return '"' + ''.join('\\'+c if c in '\\"$[]{}' else '\\n' if c=='\n' else c for c in value) + '"'


def run(root, args, *, verify=False):
    output = destination(root,args.output)
    if not args.bios.is_dir():
        raise ValueError('Supply compatible BIOS files below references/msxbios; set MSX_BIOS')
    if not args.rom.is_file():
        raise ValueError('Cartridge missing; run make rom or set ROM')
    bios_hashes = {p.relative_to(args.bios).as_posix():digest(p)
                   for p in sorted(args.bios.rglob('*')) if p.is_file()}
    require_ignored(root,[output/n for n in ['session.tcl','emulator.log','normal.png','overlap.png',
                                           'normal-return.png','normal.txt','overlap.txt','normal-return.txt',
                                           'integration.json','machine.txt']])
    output.mkdir(parents=True)
    env = dict(os.environ, OPENMSX_HOME=str(output/'home'), OPENMSX_USER_DATA=str(output/'userdata'))
    # The process gets its own user data/settings/cache; no global configuration changes.
    lines = ['set save_settings_on_exit false',
             f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
             f'if {{[catch {{machine {tcl(args.machine)}}} problem]}} {{',
             '  puts stderr "BIOS/machine load failed: $problem. Check machine ROM SHA-1 requirements and MSX_BIOS."',
             '  exit 2', '}',
             'set firmwareswitch off', 'set speed 100', 'set throttle on',
             'set z80_freq 3579545', 'set z80_freq_locked false',
             'set gamma 1.0', 'set brightness 0', 'set contrast 0',
             'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
             'set scanline 0', 'set blur 0', 'set noise 0',
             f'cart {tcl(args.rom.resolve())} -romtype ASCII16', 'reset']
    if verify:
        lines += [
            'proc checked {body} {if {[catch {uplevel #0 $body} problem]} {puts stderr $problem; exit 2}}',
            'proc capture_case {name expected} {',
            '  global z80_freq speed',
            '  if {[debug read "memory" 0xc000] != $expected} {error "Keyboard scene selection failed"}',
            f'  screenshot -raw -size auto [file join {tcl(output)} "$name.png"]',
            f'  set f [open [file join {tcl(output)} "$name.txt"] w]',
            '  puts $f [vdpregs]', '  puts $f [machine_info time]',
            '  puts $f [debug read "memory" 0xc000]',
            '  puts $f "z80_hz=[set z80_freq] speed=[set speed]"',
            '  close $f', '}',
            'after time 8 {checked {capture_case normal 0; keymatrixdown 0 4}}',
            'after time 9 {checked {keymatrixup 0 4}}',
            'after time 10 {checked {capture_case overlap 1; keymatrixdown 0 2}}',
            'after time 11 {checked {keymatrixup 0 2}}',
            'after time 12 {checked {capture_case normal-return 0; exit}}',
        ]
    script=output/'session.tcl'
    script.write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem; exit 2}\n')
    command=[args.openmsx,'-script',str(script)]
    with (output/'emulator.log').open('w') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                              timeout=60 if verify else None)
    if result.returncode:
        raise ValueError(f'openMSX failed; inspect {output}/emulator.log. Check selected machine and supplied BIOS hashes.')
    if bios_hashes != {p.relative_to(args.bios).as_posix():digest(p)
                      for p in sorted(args.bios.rglob('*')) if p.is_file()}:
        raise ValueError('BIOS inventory changed during emulation')
    require_ignored(root,[p for p in output.rglob('*') if p.is_file()])
    if verify:
        reports={}
        for name in ['normal','overlap','normal-return']:
            path=output/f'{name}.png'
            if not path.is_file():
                raise ValueError(f'openMSX did not capture {name}; inspect {output}/emulator.log')
            with Image.open(path) as actual, Image.open(args.rom.parent/f'{"normal" if name=="normal-return" else name}.png') as expected:
                if actual.size != (320,240) or expected.size != (256,212):
                    raise ValueError('Expected 320x240 raw NTSC capture and 256x212 reference')
                # Remove only the known unscaled NTSC border, with R18=0.
                active = actual.convert('RGB').crop((32,14,288,226))
                diff = ImageChops.difference(expected.convert('RGB'),active)
                reports[name]=dict(raw_size=list(actual.size),active_rectangle=[32,14,288,226],
                                   mismatches=sum(any(c) for c in diff.get_flattened_data()),
                                   max_channel_difference=max(diff.tobytes()),
                                   bounds=diff.getbbox(),tolerance=0)
        json_write(output/'integration.json',dict(machine=args.machine,rom_sha256=digest(args.rom),
                   openmsx=subprocess.run([args.openmsx,'--version'],capture_output=True,text=True).stdout.strip(),
                   cpu_hz=3579545,cpu_speed_percent=100,bios_sha256=bios_hashes,
                   keyboard='row 0, bit 2 (2), then bit 1 (1)',scenes=reports))
        print({name: report['mismatches'] for name,report in reports.items()})
        if any(report['mismatches'] for report in reports.values()):
            raise ValueError('Screenshot comparison failed; inspect integration.json')
