"""Original life decrement/waits/restart and first post-restart flag oracle."""
import os
import statistics
import subprocess
from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .fuel_verify import source_seed
from .score_verify import packet
from .hud_verify import symbols


def cases_for():
    return [(lives,ordinal,count,fuel%10,fuel//10)
            for lives in (1,2,3,9) for ordinal,count in ((0,0),(3,4),(8,9)) for fuel in (0,1,599,600)]


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    if read_json(bundle/'build.json').get('incremental_stage')!=7:raise ValueError('Life proof requires stage 07')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    cases=cases_for();(out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    seed=bytearray((bundle/'player-seed.bin').read_bytes());seed[0xa0:0xa8]=packet(19990)
    (out/'msx-seed.bin').write_bytes(seed)
    original=bytearray(source_seed(bundle));original[0xa0:0xa8]=packet(19990)
    (out/'source-seed.bin').write_bytes(original)
    source=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Life oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/msx/lives_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','180']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,LIVES_OUTPUT=str(out)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    syms=symbols(bundle/'raster-scroll.sym')
    code=[0xf3,0x3e,syms['PLAYER_BANK'],0x32,0,0x70,0xcd,0,0,0x76]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set f [open [file join $out msx-seed.bin] rb];set seed [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set costs [open [file join $out cycles.tsv] w];set index -1;set started 0',
        'proc component {address} {debug write memory 0xc607 [expr {$address&255}];debug write memory 0xc608 [expr {$address>>8}];set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc600}',
        'proc issue {} {',
        ' incr ::index;set ::age 0;set ::phase loss',
        ' if {$::index==[string length $::cases]/5} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {error "Life core changed VRAM"};close $::result;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*5}] [expr {$::index*5+4}]] cu* c;lassign $c lives ordinal ::count frac whole',
        ' debug write_block memory 0xe000 $::seed',
        ' foreach {a v} [list 0xe00f $lives 0xe250 $ordinal 0xe271 $::count 0xe26a $frac 0xe26b $whole 0xe023 1 0xe020 3 0xe292 1 0xe289 199 0xc490 1 0xc491 0 0xc494 0 0xc5c0 0 0xc5c1 0 0xc5c2 0 0xc50b $::count 0xc50d 1 0xc540 $::count 0xc54f 0] {debug write memory $a $v}',
        ' debug write_block memory 0xc500 [binary format c* {0 0 1 0 1 1 1 1 1 1 1}]',
        ' debug write_block memory 0xc520 [binary format c* {0 0 34 152 0 0 38 152 48 153 50 153 52 153 54 153 56 153 58 153}]',
        ' set ::flags [debug read_block memory 0xc500 11];set ::cells [debug read_block memory 0xc520 20]',
        f' component {syms["Life_Begin"]}','}',
        'proc record {} {',
        ' puts -nonewline $::result [binary format ss $::index $::age]',
        ' foreach a {0xe00f 0xe020 0xe250 0xe271 0xe023 0xe26a 0xe26b 0xe292 0xe289 0xe28b 0xe1b2 0xe2d0} {puts -nonewline $::result [binary format c [debug read memory $a]]}',
        ' foreach {a size} {0xe025 8 0xe0a0 8 0xe060 8 0xe068 24} {puts -nonewline $::result [debug read_block memory $a $size]}',
        ' set remaining [debug read memory 0xe00f];set spare [expr {$remaining>0?min($remaining-1,9):0}]',
        f' if {{[debug read memory {syms["lives"]}]!=$spare}} {{error "Life HUD differs from original remaining count"}}',
        ' issue','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved_vram [debug read_block VRAM 0 131072]',
        *[f'debug write memory {0xc600+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc609 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Life core stack imbalance"}',
        ' puts $::costs "$::index $::phase [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        ' switch $::phase {',
        f' loss {{set ::phase hold;component {syms["Death_Tick"]}}}',
        ' hold {',
        '  incr ::age;if {$::age>120} {error "Life wait did not return"}',
        f'  if {{[debug read memory 0xc490]!=2}} {{component {syms["Death_Tick"]}}} elseif {{[debug read memory 0xe00f]==0}} {{set ::phase publish;component {syms["Life_Publish"]}}} else {{set ::phase restart;component {syms["Player_RestartNative"]}}}',' }',
        ' restart {',
        '  if {[debug read_block memory 0xc500 11] ne $::flags || [debug read_block memory 0xc520 20] ne $::cells || [debug read memory 0xe250]!=0 || [debug read memory 0xe271]!=$::count} {error "Life restart lost collection state/ordinal"}',
        '  debug write memory 0xc50b [expr {$::count+1}]',
        f'  set ::phase points;component {syms["Score_Update"]}',' }',
        f' points {{set ::phase publish;component {syms["Life_Publish"]}}}',
        ' publish {record}',' }','}',
        'after time 180 {puts stderr "Life microprobe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    original=(out/'original.bin').read_bytes();actual=(out/'msx.bin').read_bytes()
    if len(original)!=len(cases)*64 or len(actual)!=len(original):raise ValueError('Incomplete life proof')
    for i,c in enumerate(cases):
        a,b=actual[i*64:(i+1)*64],original[i*64:(i+1)*64]
        if a!=b:raise ValueError(f'Life mismatch case {i}, {c}: {a.hex()} / {b.hex()}')
        if int.from_bytes(a[2:4],'little')!=(96 if c[0]==1 else 120):raise ValueError('Original life timer differs')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()} or source!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):raise ValueError('Source/BIOS changed')
    verify_manifest(bundle)
    costs=[r.split() for r in (out/'cycles.tsv').read_text().splitlines()]
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),mame_version=version,
        phases={k:dict(median_cycles=statistics.median(int(r[2]) for r in costs if r[1]==k),max_cycles=max(int(r[2]) for r in costs if r[1]==k)) for k in ('loss','hold','restart','points','publish')},
        vram_unchanged=True,collection_preserved=True,nonfinal_ticks=120,final_ticks=96,
        scope='Externally clocked original life decrement/waits, selected restart RAM/car init and first post-restart flag; exact current/high score, award bits, fuel, speed and descriptor; HUD spare count; no full arcade dispatcher'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact original life/restart/next-flag cases: {out}/report.json')
    return out
