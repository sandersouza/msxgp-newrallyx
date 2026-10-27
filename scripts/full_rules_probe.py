#!/usr/bin/env python3
"""Compare original phase/speed thresholds against the linked native routines."""
import argparse
import itertools
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.round_prepare_verify import relocated_seed
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.record import lua_literal
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=Path('references/build/issue12-round-inventory-v13'))
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);verify_manifest(args.reference)
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    seed=(args.reference/'case-000-video.bin').read_bytes()
    (out/'source-seed.bin').write_bytes(seed);(out/'native-seed.bin').write_bytes(relocated_seed(seed))
    cases=list(itertools.product((2,3,4,8,16,255),(0,39,40,79,80,199,200,255),(0,1,2),(0,4,5,7,8,10),(0,1)))
    (out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    (out/'config.lua').write_text('return '+lua_literal(dict(output=str(out),cases=[list(case) for case in cases]))+'\n')
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Phase-clock oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-debug','-debugger','none','-autoboot_delay','0',
        '-autoboot_script',str(root/'scripts/msx/full_rules_native.lua'),
        '-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','120']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,check=True,timeout=120,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,FULL_RULES_CONFIG=str(out/'config.lua')))
    original=(out/'original.bin').read_bytes()
    if len(original)!=4096*len(cases) or not (out/'complete').is_file():raise ValueError('Incomplete original phase-clock evidence')
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach n {cases native-seed} {set f [open [file join $out "$n.bin"] rb];set data($n) [read $f];close $f}',
        'set index 0;set started 0;set result [open [file join $out msx.bin] wb]']
    script=r'''
proc issue {} {
    if {$::index==[string length $::data(cases)]/5} {close $::result;exit 0;return}
    debug write_block memory 0xe000 $::data(native-seed)
    binary scan [string range $::data(cases) [expr {$::index*5}] [expr {$::index*5+4}]] cu* c
    foreach at {0xe1b0 0xe289 0xe28c 0xe271 0xe292} value $c {debug write memory $at $value}
    debug write memory 0x7000 @BANK@
    set at 0xd150;foreach value {243 205 31 155 205 253 131 195 96 209} {debug write memory $at $value;incr at}
    reg SP 0xc7f0;reg PC 0xd150
}
debug set_bp @MAIN@ {!$::started} {set ::started 1;set ::vram [debug read_block VRAM 0 131072];issue}
debug set_bp 0xd160 {$::started} {
    if {[reg SP]!=0xc7f0 || [debug read_block VRAM 0 131072] ne $::vram} {error "Phase clock changed stack/VRAM"}
    puts -nonewline $::result [debug read_block memory 0xe000 4096]
    incr ::index;issue
}
after time 120 {puts stderr "Native phase-clock proof timeout";exit 2}
'''.replace('@BANK@',str(syms['PLAYER_BANK'])).replace('@MAIN@',str(syms['main']))
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=120,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    expected=b''.join(relocated_seed(original[i:i+4096]) for i in range(0,len(original),4096))
    actual=(out/'msx.bin').read_bytes()
    if actual!=expected:
        at=next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b)
        raise ValueError(f'Original phase-clock mismatch: case {at//4096} {cases[at//4096]}, offset {at%4096:03x}')
    verify_manifest(bundle);verify_manifest(args.reference)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),bytes_per_case=4096,
        stack_unchanged=True,vram_unchanged=True,
        scope='Original $1b1f + $03fd phase clock: normal/challenge/late rounds, threshold boundaries, countdown, collected flags and empty-fuel parameter lock. Declared pointer/page relocation only.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'{len(cases)} exact original phase-clock cases pass: {out}/report.json')


if __name__=='__main__':main()
