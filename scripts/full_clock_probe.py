#!/usr/bin/env python3
"""Execute the elapsed-VBlank clock against an independent rational oracle."""
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
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bios',type=Path,default=Path('references/msxbios'))
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    bundle=args.rom.resolve().parent;verify_manifest(bundle)
    syms=symbols(bundle/'raster-scroll.sym');clock=read_json(bundle/'build.json')['native_clock']
    out=destination(root,args.output);require_ignored(root,[out/'results.tsv']);out.mkdir(parents=True)
    cases=[];expected=[]
    for n,(fraction,last,elapsed,due,paused) in enumerate(itertools.product(
            (0,1,13650,65535),(0,250),(0,1,2,4,8,9),(0,2,11,12),(0,1))):
        current=(last+elapsed)&255;dropped=65535 if n&1 else 0
        cases.append((fraction,last,current,due,paused,dropped))
        total=fraction+min(elapsed,clock['maximum_elapsed_refreshes'])*clock['rate']
        produced=min(elapsed,clock['maximum_elapsed_refreshes'])*clock.get('base_ticks_per_refresh',1)+total//65536
        pending=due+produced;limit=clock['maximum_pending_ticks']
        expected.append((current,0 if paused else min(limit,pending),
            fraction if paused else total%65536,
            dropped if paused else (dropped+max(0,pending-limit))&65535))
    addresses=[syms[k] for k in ('Full_ClockLast','Full_ClockDue','Full_ClockDropped')]
    last,due,dropped=addresses;entry=syms['Full_ClockFrame']
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)};set started 0;set index 0',
        'set cases {'+' '.join('{'+ ' '.join(map(str,c))+'}' for c in cases)+'}',
        'set result [open [file join $out results.tsv] w]',
        'proc word {at} {expr {[debug read memory $at]+256*[debug read memory [expr {$at+1}]]}}',
        'proc putword {at value} {debug write memory $at [expr {$value&255}];debug write memory [expr {$at+1}] [expr {$value>>8}]}',
        'proc issue {} {',
        ' if {$::index==[llength $::cases]} {close $::result;exit 0}',
        ' lassign [lindex $::cases $::index] fraction last current due paused dropped',
        f' debug write memory {last} $last;debug write memory {due} $due;putword {dropped} $dropped',
        ' debug write memory 0xc00a $current;debug write memory 0xc009 $paused;putword 0xc402 $fraction',
        f' set at 0xd150;foreach value {{243 205 {entry&255} {entry>>8} 195 96 209}} {{debug write memory $at $value;incr at}}',
        ' reg SP 0xc7f0;reg PC 0xd150','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{',
        ' set ::started 1;set ::native [debug read_block memory 0xe000 4096]',
        ' set ::vram [debug read_block VRAM 0 131072];set ::primary [debug read ioports 168];set ::mapper [debug read ioports 252];issue','}',
        'debug set_bp 0xd160 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read_block memory 0xe000 4096] ne $::native || [debug read_block VRAM 0 131072] ne $::vram || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::mapper} {puts stderr "Clock changed native RAM, VRAM, stack or slot mapping";exit 2}',
        f' puts $::result "[debug read memory {last}] [debug read memory {due}] [word 0xc402] [word {dropped}]"',
        ' incr ::index;issue','}',
        'after time 120 {puts stderr "Clock proof timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=120,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=[tuple(map(int,l.split())) for l in (out/'results.tsv').read_text().splitlines()]
    if actual!=expected:
        at=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),min(len(actual),len(expected)))
        raise ValueError(f'Elapsed clock mismatch at synthetic case {at}: {cases[at]}')
    verify_manifest(bundle)
    from scripts.msx.presentation_clock_verify import verify
    publication_cases=verify(root,args,out/'presentation',syms)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),
        publication_clock=dict(cases=publication_cases,
            scope='Minimum two physical refreshes, first-packet parity, both late phases, byte-counter wrap and empty queue. Stack/index/native RAM/mapping preserved; only the expected SAT end marker changes when eligible.'),
        native_ram_unchanged=True,vram_unchanged=True,slot_mapping_restored=True,
        scope='Executed rational elapsed-VBlank accumulation, fractional carries, counter wrap, bounded debt/discard accounting and pause; natural cadence is a separate gate.'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} elapsed-clock cases pass: {out}/report.json')


if __name__=='__main__':main()
