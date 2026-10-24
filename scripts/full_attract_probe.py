#!/usr/bin/env python3
"""Observe original cast pixels, autonomous demonstration and credit interruption."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.attract import cast
from scripts.msx.screen5 import packed
from scripts.scenes.bundle import digest,load_assets,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);out=destination(root,args.output);require_ignored(root,[out/'title.vram']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'activate_input_layer -blocking full_attract',f'cart {tcl(args.rom.resolve())} -romtype ASCII16',
        'reset',f'set out {tcl(out)}']
    script=r'''
set phase title;set age 0;set demo 0;set frames 0
proc snapshot {name} {
    foreach {ext bytes} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072]] {
        set f [open [file join $::out "$name.$ext"] wb];puts -nonewline $f $bytes;close $f
    }
}
proc step {} {
    incr ::age
    set state [debug read memory 0xc7d0];set attract [debug read memory 0xc7ee]
    switch $::phase {
        title {
            if {$state==1 && [debug read memory 0xc7dd] && ![info exists ::high]} {snapshot title;set ::high [debug read_block memory 0xe060 8]}
            if {$state==0 && $attract} {
                incr ::demo;snapshot demo-start
                if {[debug read memory 0xe020]!=0 || [debug read memory 0xe021]!=0 || [debug read memory 0xe00f]!=1} {error "Original attract mode contract diverged"}
                set ::position [debug read_block memory 0xe068 24]
                set ::phase demo;set ::age 0
            }
        }
        demo {
            if {$::age==150} {
                snapshot demo-moving
                if {[debug read_block memory 0xe068 24] eq $::position} {error "Attract player did not move"}
            }
            if {$state==1 && !$attract} {
                if {[debug read_block memory 0xe060 8] ne $::high} {error "Attract changed retained record"}
                set ::phase again;set ::age 0
            }
        }
        again {if {$state==0 && $attract} {
            keymatrixdown 0 32;set ::phase coin;set ::age 0
        }}
        coin {
            if {$::age==4} {keymatrixup 0 32}
            if {$state==1 && !$attract && [debug read memory 0xc7dd]} {
                if {[debug read memory 0xc7d2]!=1} {error "Attract credit interruption lost coin"}
                keymatrixdown 0 2;set ::phase start;set ::age 0
            }
        }
        start {
            if {$::age==4} {keymatrixup 0 2}
            if {$state==0 && !$attract} {
                if {[debug read memory 0xe020]!=1 || ![debug read memory 0xe021] || [debug read memory 0xe00f]!=3} {error "Human start retained attract state"}
                snapshot human;exit 0
            }
        }
    }
    after time 0.02 poll
}
proc poll {} {if {[catch {step} p]} {puts stderr $p;exit 2}}
set VDP.too_fast_vram_access_callback {puts stderr "Attract VRAM timing violation";exit 2}
after time 150 {puts stderr "Attract cycle timeout";exit 2}
after time 0.02 poll
'''
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=120,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    palette=(bundle/'palette.bin').read_bytes();image,_=cast(root,palette);expected=packed(image)
    actual=(out/'title.vram').read_bytes()[0x10000:0x16a00]
    for y in list(range(16,184))+list(range(200,208)):
        if actual[y*128:(y+1)*128]!=expected[y*128:(y+1)*128]:
            raise ValueError(f'Original cast pixels changed at row {y}')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cast_source_rows=176,
        native_mode=0,human_mode=1,guest_state_writes=False,
        scope='Real no-credit title/demo/title cycle, original cast at 1:1 and coin interruption followed by fresh human start.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'Original cast and autonomous attract cycle pass: {out}/report.json')


if __name__=='__main__':main()
