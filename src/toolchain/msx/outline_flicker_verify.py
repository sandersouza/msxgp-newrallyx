"""Execute all outline/radar priorities with exact SAT, row-color and EC checks."""
import os
import statistics
import subprocess
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .outline_flicker import order
from src.toolchain.scenes.bundle import read_json,verify_manifest,digest
from src.toolchain.scenes.storage import require_ignored,json_write,seal


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    out=destination(root,args.output);out.mkdir(parents=True);s=symbols(bundle/'raster-scroll.sym')
    cases=[(scroll,phase,ec1,ec2) for scroll in range(256) for phase in range(4) for ec1,ec2 in ((0,0),(128,0),(0,128))]
    (out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    flags=read_json(bundle/'player.json')['flags'];canonical=bytes(v for i in range(24) for v in (63,32+i*7&255,i*4,i))
    (out/'canonical.bin').write_bytes(canonical)
    code=bytes((243,62,6,211,153,62,128,211,153,62,66,211,153,62,129,211,153,205))+s['Flicker_Publish'].to_bytes(2,'little')+bytes((205,))+s['Outline_Commit'].to_bytes(2,'little')+bytes((195,64,199))
    (out/'probe.bin').write_bytes(code)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set cmdtiming real','set z80_freq 3579545','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach n {probe cases canonical} {set f [open [file join $out "$n.bin"] rb];set $n [read $f];close $f}',
        f'set flags {{{" ".join(map(str,flags))}}};set n -1;set started 0;set results [open [file join $out results.bin] wb];set costs [open [file join $out costs.tsv] w]',
        'proc issue {} {incr ::n;if {$::n==3072} {if {[debug read_block VRAM 0 65536] ne $::scene || [debug read_block memory 0xe000 4096] ne $::native} {puts stderr "Changed maze/native state";exit 2};close $::results;close $::costs;exit 0;return};binary scan [string range $::cases [expr {$::n*4}] [expr {$::n*4+3}]] cu* c;lassign $c scroll phase ec1 ec2;',
        f'debug write memory {s["Flicker_Phase"]} $phase;debug write memory {s["Outline_Front"]} 0;debug write memory {s["Outline_Ready"]} 0;debug write memory {s["scroll_y"]} $scroll;debug write memory {s["Enemy1_LastEC"]} $ec1;debug write memory {s["Enemy2_LastEC"]} $ec2;',
        f'debug write memory {s["player_drawn"]} [lindex $::flags [expr {{$::n%12}}]];debug write memory {s["Enemy1_Index"]} [expr {{($::n/12)%12}}];debug write memory {s["Enemy2_Index"]} [expr {{($::n/144)%12}}];debug write memory {s["point_color"]} [expr {{$::n%2?11:8}}];',
        'debug write_block memory 0xc100 [string range $::canonical 0 67];debug write_block memory 0xc410 [string range $::canonical 68 75];debug write_block memory 0xc600 [string range $::canonical 76 83];debug write_block memory 0xc610 [string range $::canonical 84 91];debug write_block memory 0xc620 [string range $::canonical 92 95];',
        'set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc700','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{set ::started 1;set ::scene [debug read_block VRAM 0 65536];set ::native [debug read_block memory 0xe000 4096];debug write_block memory 0xc700 $::probe;issue}}',
        'debug set_bp 0xc740 {$::started} {if {[reg SP]!=0xc7f0} {puts stderr "Stack imbalance";exit 2};puts -nonewline $::results [debug read_block VRAM 126464 97];puts -nonewline $::results [debug read_block VRAM 125952 384];',
        f'puts -nonewline $::results [binary format c* [list [debug read memory {s["Outline_DisplayPhase"]}] [debug read memory {s["Outline_Front"]}] [debug read memory {s["Outline_Ready"]}] [debug read {{VDP regs}} 5]]];puts $::costs "$::n [expr {{round(([machine_info time]-$::begin)*3579545)}}]";issue}}',
        'set VDP.too_fast_vram_access_callback {puts stderr "VRAM timing violation";exit 2}','after time 90 {puts stderr "Outline probe timeout";exit 2}']
    (out/'session.tcl').write_text('\n'.join(lines))
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'results.bin').read_bytes();size=485
    if len(raw)!=len(cases)*size:raise ValueError('Incomplete outline priority trace')
    pixels=(bundle/'player-pixels.bin').read_bytes();base=(bundle/'sprite-colors.bin').read_bytes()
    for n,(scroll,phase,ec1,ec2) in enumerate(cases):
        colors=bytearray(base);colors[12*16:13*16]=bytes([43 if n%2 else 40])*16
        for slot,pose,ec in ((17,n%12,0),(19,n//12%12,ec1),(21,n//144%12,ec2)):
            rows=[]
            for y in range(16):
                row=pixels[pose*256+y*16:pose*256+y*16+16]
                ink=9 if row.count(9)>row.count(3) else 3
                if slot!=17:ink=10 if ink==9 else 6
                rows.append(ink|32|ec)
            if slot==17 and (scroll+107)&255==216:rows=rows[:1]+rows[:-1]
            colors[slot*16:(slot+1)*16]=bytes(rows)
            colors[(slot+1)*16:(slot+2)*16]=bytes([(11 if slot==17 else 14)|32|ec])*16
        p=(phase+1)%4;indices=order(p)
        expected=b''.join(canonical[i*4:i*4+4] for i in indices)+bytes((216,))+b''.join(colors[i*16:i*16+16] for i in indices)+bytes((p,1,0,223))
        actual=raw[n*size:(n+1)*size]
        if actual!=expected:
            first=next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b)
            raise ValueError(f'Outline transaction mismatch case{n}, byte{first}: {actual[first]} != {expected[first]}')
    cycles=[int(line.split()[1]) for line in (out/'costs.tsv').read_text().splitlines()]
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),elapsed_cycles=dict(median=statistics.median(cycles),maximum=max(cycles)),
        native_state_unchanged=True,maze_unchanged=True,atomic_table_commit=True,
        scope='Actual outline SAT/color/EC transactions and complete inactive-table commit; all scroll phases, four priorities and twelve poses; not moving-game acceptance'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} actual outline transactions: {out}/report.json')
