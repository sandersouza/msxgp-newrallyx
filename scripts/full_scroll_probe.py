#!/usr/bin/env python3
"""Execute every circular scroll transition and initial scene latch."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest,verify_manifest,read_json
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);s=symbols(bundle/'raster-scroll.sym');entry=s['Full_LatchScrollY']
    out=destination(root,args.output);require_ignored(root,[out/'result.bin']);out.mkdir(parents=True)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set index 0;set started 0;set result [open [file join $out result.bin] wb]',
        'proc issue {} {',
        ' if {$::index==65792} {',
        '  if {[debug read_block memory 0xe000 4096] ne $::native || [debug read_block VRAM 0 131072] ne $::vram} {error "Scroll latch changed native state or VRAM"}',
        '  close $::result;exit 0;return',' }',
        f' debug write memory {s["scroll_y"]} [expr {{$::index&255}}]',
        f' debug write memory {s["irq_scroll_y"]} [expr {{($::index>>8)&255}}]',
        f' debug write memory {s["Full_ScrollValid"]} [expr {{$::index<65536}}]',
        f' set at 0xd150;foreach value {{243 205 {entry&255} {entry>>8} 195 96 209}} {{debug write memory $at $value;incr at}}',
        ' reg SP 0xc7f0;reg PC 0xd150','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{set ::started 1;set ::native [debug read_block memory 0xe000 4096];set ::vram [debug read_block VRAM 0 131072];issue}}',
        'debug set_bp 0xd160 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Scroll latch changed stack"}',
        f' puts -nonewline $::result [binary format c* [list [reg A] [debug read memory {s["irq_scroll_y"]}] [debug read memory {s["Full_ScrollValid"]}]]]',
        ' incr ::index;issue','}',
        'after time 120 {puts stderr "Scroll proof timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=120,
            stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,
                OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    policy=read_json(bundle/'build.json')['terrain_ownership']['vertical_presentation']
    ordinary=policy['ordinary_maximum_pixels'];threshold=policy['catch_up_threshold_pixels']
    expected=bytearray()
    for n in range(65792):
        target=n&255;current=(n>>8)&255;delta=(target-current+128)%256-128
        limit=min(4,(abs(delta)+1)//2) if policy.get('policy')=='half-distance' else ordinary if abs(delta)<=threshold else 4
        value=(current+max(-limit,min(limit,delta)))%256 if n<65536 else target
        expected.extend((value,value,1))
    if (out/'result.bin').read_bytes()!=expected:raise ValueError('Circular scroll latch differs from bounded-distance oracle')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=65792,maximum_pixels=4,
        ordinary_maximum_pixels=ordinary,catch_up_threshold_pixels=threshold,
        native_ram_unchanged=True,vram_unchanged=True,stack_unchanged=True,
        scope='All 65,536 circular byte transitions plus 256 initial scene latches; real frame timing is verified separately.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'65792 circular scroll cases pass: {out}/report.json')


if __name__=='__main__':main()
