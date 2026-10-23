"""Original flag branch vs assembled collection: boundary and persistence cases."""
import os
import statistics
import subprocess
from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols


def cases_for(records):
    offsets=(-25,-24,-13,-12,-1,0,1,12,13,24,25)
    cases=[]
    for f in records:
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                for x in offsets:
                    for y in offsets:cases.append((f['address']+dy*32+dx,x,y,1))
    # Repeated contact, departure/re-entry, all ten in original order, then reset.
    for f in records:cases.extend([(f['address'],0,0,0)]*2+[(f['address']+1,0,0,0),(f['address'],0,0,0)])
    cases.append((records[0]['address'],0,0,1))
    return cases


def analyze(cases,records,original,rows):
    if len(original)!=len(cases)*22 or len(rows)!=len(cases):raise ValueError('Incomplete flag oracle evidence')
    count=last=kind=0;hits=0;costs=[]
    for i,((cell,x,y,reset),row) in enumerate(zip(cases,rows,strict=True)):
        if reset:count=last=kind=0
        ref=original[i*22:(i+1)*22];hit=ref[0];active=list(ref[1:12]);board=list(ref[12:22])
        if not 0<=hit<=10 or active[0]!=0 or any(a not in (0,1) for a in active):raise ValueError('Invalid original flag result')
        if any(v!=(f['kind'] if active[n] else 0) for n,(f,v) in enumerate(zip(records,board),1)):
            raise ValueError('Original cell/list collection mutation differs')
        if hit:count+=1;last=hit;kind=records[hit-1]['kind'];hits+=1
        if row[:4]!=[i,count,last,kind] or row[4:15]!=active or row[15]<=0:
            raise ValueError(f'Original/MSX collection mismatch at {i}: {row}')
        costs.append(row[15])
    return dict(cases=len(cases),collection_events=hits,median_elapsed_cycles=statistics.median(costs),
        max_elapsed_cycles=max(costs),scope='Original geometry, flag slot/type, cell/list clearing and one-time collection; score/fuel/graphics excluded')


def original_oracle(root,out,cases,record_data):
    (out/'cases.bin').write_bytes(b''.join(c.to_bytes(2,'little')+bytes((x&255,y&255,r)) for c,x,y,r in cases))
    (out/'flag-records.bin').write_bytes(record_data)
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Flag oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/msx/flags_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','240']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,FLAGS_OUTPUT=str(out)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    return version


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    if read_json(bundle/'build.json').get('incremental_stage')!=4:raise ValueError('Flag proof requires stage 04')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    source=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    records=read_json(bundle/'flags.json')['records'];cases=cases_for(records)
    version=original_oracle(root,out,cases,(bundle/'flag-records.bin').read_bytes())
    syms=symbols(bundle/'raster-scroll.sym');init=syms['Flag_Init'];call=syms['Flag_Update']
    # DI; map selected original geometry; call it; publish DE; call flag consumer.
    code=[0xf3,0x3e,syms['PLAYER_BANK'],0x32,0,0x70,0xcd,0x74,0x97,0xed,0x53,0x86,0xc4,0xcd,call&255,call>>8,0x76]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];binary scan [read $f] cu* cases;close $f',
        'set index 0;set started 0;set result [open [file join $out results.tsv] w]',
        'proc next_case {} {',
        ' if {$::index==[llength $::cases]/5} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {error "Flag detector changed VRAM"};close $::result;exit 0;return}',
        ' lassign [lrange $::cases [expr {$::index*5}] [expr {$::index*5+4}]] lo hi x y reset',
        ' foreach {a v} [list 0xe079 $lo 0xe07a $hi 0xe06d $x 0xe06f $y] {debug write memory $a $v}',
        ' set ::saved_guest [debug read_block memory 0xe000 4096]',
        ' reg SP 0xc7f0;reg PC [expr {$reset?0xc620:0xc600}]',
        '}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{',
        ' set ::started 1;set ::saved_vram [debug read_block VRAM 0 131072]',
        *[f'debug write memory {0xc600+i} {v}' for i,v in enumerate(code)],
        *[f'debug write memory {0xc620+i} {v}' for i,v in enumerate([0xf3,0xcd,init&255,init>>8,0xc3,0,0xc6])],
        'next_case','}',
        f'debug set_bp {call} {{$::started}} {{set ::begin [machine_info time]}}',
        'debug set_bp 0xc610 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read_block memory 0xe000 4096] ne $::saved_guest} {error "Flag detector changed player RAM/stack"}',
        ' binary scan [debug read_block memory 0xc500 14] cu* state',
        ' set count [lindex $state 11];set last [lindex $state 12];set kind [lindex $state 13]',
        ' puts $::result "$::index $count $last $kind [join [lrange $state 0 10]] [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        ' incr ::index;next_case','}',
        'after time 60 {puts stderr "Flag boundary test timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    rows=[list(map(int,r.split())) for r in (out/'results.tsv').read_text().splitlines()]
    report=analyze(cases,records,(out/'original.bin').read_bytes(),rows)
    if source!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):raise ValueError('Original ROMs changed')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle)
    report.update(rom_sha256=digest(args.rom),original_player_ram_unchanged=True,vram_unchanged=True,mame_version=version,
                  harness_source_sha256=digest(root/'scripts/msx/flags_native.lua'))
    json_write(out/'report.json',report);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} original/MSX flag boundary/persistence cases: {out}/report.json')
    return out
