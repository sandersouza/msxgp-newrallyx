"""Original Z80 boundary oracle vs the assembled MSX contact/event consumer."""
import os
import statistics
import subprocess

from src.toolchain.graphics.roms import load_metadata, validate_roms, input_records
from src.toolchain.scenes.bundle import digest, read_json, verify_manifest
from src.toolchain.scenes.storage import json_write, require_ignored, seal
from .build import destination
from .emulator import reference_machine, tcl
from .hud_verify import symbols


def cases_for(rocks):
    cases=[]
    offsets=(-25,-24,-13,-12,-1,0,1,12,13,24,25)
    for rock in rocks:
        cell=rock-0x9800;x,y=cell%32,cell//32
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                for ox in offsets:
                    for oy in offsets:
                        cases.append((0x9800+(y+dy)*32+x+dx,ox,oy))
    # Explicit repeated contact, departure, re-entry and switching objects.
    cases += [(rocks[0],0,0)]*5+[(rocks[0]+1,0,0)]+[(rocks[0],0,0)]*5
    cases += [(rocks[1],0,0)]*5+[(rocks[1]+1,0,0),(rocks[1],0,0)]
    return cases


def analyze(cases, rocks, original, rows, *, resets=()):
    if len(original)!=len(cases)*3 or len(rows)!=len(cases):
        raise ValueError('Incomplete original/native collision evidence')
    previous=events=last=0;cycles=[];hits=0
    for i,(case,row) in enumerate(zip(cases,rows,strict=True)):
        if i in resets:previous=events=last=0
        hit=original[i*3];cell=int.from_bytes(original[i*3+1:i*3+3],'little')
        if hit not in (0,1) or hit and cell not in rocks:
            raise ValueError('Original oracle returned an unsupported contact')
        contact=rocks.index(cell)+1 if hit else 0
        if contact!=previous and contact:
            events+=1;last=cell
        if len(row)!=6 or row[:5]!=[i,contact,events,cell,last] or row[5]<=0:
            raise ValueError(f'Original/native rock contact mismatch at case {i}: {case}, {row}')
        previous=contact;hits+=hit;cycles.append(row[5])
    return dict(cases=len(cases),contact_cases=hits,entry_events=events,
                median_cycles=statistics.median(cycles),max_cycles=max(cycles),
                max_ms=max(cycles)/3579.545,
                scope='Original contact geometry/rock branch with empty flags and zero grace; assembled event debounce; dedicated microprobe, not gameplay/RGB')


def original_oracle(root,out,cases,rock_data):
    """Replay contact inputs with the original geometry and rock branch."""
    (out/'cases.bin').write_bytes(b''.join(a.to_bytes(2,'little')+bytes((x&255,y&255)) for a,x,y in cases))
    (out/'rock-cells.bin').write_bytes(rock_data)
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Rock oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/msx/rock_collision_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','60']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,ROCK_COLLISION_OUTPUT=str(out)),
                       stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    return version


def verify(root,args):
    verify_manifest(args.rom.parent)
    info=read_json(args.rom.parent/'build.json')
    if info.get('incremental_stage')!=2 or not info.get('rock_collision'):
        raise ValueError('Rock collision proof requires a sealed stage 02 cartridge')
    out=destination(root,args.output)
    require_ignored(root,[out/'cases.bin',out/'results.tsv'])
    out.mkdir(parents=True)
    source=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    rock_data=(args.rom.parent/'rock-cells.bin').read_bytes()
    if len(rock_data)!=4:raise ValueError('Expected the two-rock original fixture')
    rocks=[int.from_bytes(rock_data[n:n+2],'little') for n in (0,2)]
    cases=cases_for(rocks)
    version=original_oracle(root,out,cases,rock_data)
    syms=symbols(args.rom.parent/'raster-scroll.sym')
    call=syms['Rock_Update']
    code=[0xf3,0x3e,syms['PLAYER_BANK'],0x32,0x00,0x70,0xcd,call&255,call>>8,0x76]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,args.machine),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set data [read $f];close $f;binary scan $data cu* cases',
        'set results [open [file join $out results.tsv] w];set index 0;set started 0',
        'proc next_case {} {',
        ' if {$::index==[llength $::cases]/4} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {puts stderr "Collision probe changed VRAM";exit 2};close $::results;exit 0}',
        ' lassign [lrange $::cases [expr {$::index*4}] [expr {$::index*4+3}]] lo hi x y',
        ' foreach {a v} [list 0xe079 $lo 0xe07a $hi 0xe06d $x 0xe06f $y] {debug write memory $a $v}',
        ' set ::saved_guest [debug read_block memory 0xe000 4096]',
        ' reg SP 0xc7f0;reg PC 0xc600', '}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{',
        ' set ::started 1',
        ' set ::saved_vram [debug read_block VRAM 0 131072]',
        *[f' debug write memory {0xc600+i} {v}' for i,v in enumerate(code)],
        ' for {set a 0xc480} {$a<0xc488} {incr a} {debug write memory $a 0}',
        ' next_case', '}',
        f'debug set_bp {call} {{$::started}} {{set ::begin [machine_info time]}}',
        'debug set_bp 0xc609 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {puts stderr "Rock consumer unbalanced stack";exit 2}',
        ' if {[debug read_block memory 0xe000 4096] ne $::saved_guest} {puts stderr "Rock consumer changed player RAM";exit 2}',
        ' set contact [debug read memory 0xc480]',
        ' set events [expr {[debug read memory 0xc482]+256*[debug read memory 0xc483]}]',
        ' set cell [expr {[debug read memory 0xc486]+256*[debug read memory 0xc487]}]',
        ' set last [expr {[debug read memory 0xc484]+256*[debug read memory 0xc485]}]',
        ' puts $::results "$::index $contact $events $cell $last [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        ' incr ::index;next_case', '}',
        'after time 60 {puts stderr "Rock collision probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')),
            stdout=log,stderr=subprocess.STDOUT)
    rows=[list(map(int,r.split())) for r in (out/'results.tsv').read_text().splitlines()]
    report=analyze(cases,rocks,(out/'original.bin').read_bytes(),rows)
    verify_manifest(args.rom.parent)
    if source!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):
        raise ValueError('Source ROMs changed during collision proof')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('BIOS inventory changed during collision proof')
    report.update(rom_sha256=digest(args.rom),mame_version=version,
                  original_player_ram_unchanged=True,vram_unchanged=True,
                  candidate_manifest_sha256=digest(args.rom.parent/'manifest.json'),
                  oracle_script_sha256=digest(root/'src/toolchain/msx/rock_collision_native.lua'))
    json_write(out/'report.json',report)
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} original/native rock boundary and event cases: {out}/report.json')
    return out
