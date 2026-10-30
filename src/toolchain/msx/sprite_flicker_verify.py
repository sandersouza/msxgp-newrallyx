"""Execute the cartridge priority rotation over every vertical scroll phase."""
import os
import statistics
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .sprite_flicker import permutation,selected


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if info.get('outline_flicker'):
        from .outline_flicker_verify import verify as verify_outline
        return verify_outline(root,args)
    if not info.get('sprite_flicker'):raise ValueError('Flicker cartridge required')
    out=destination(root,args.output);require_ignored(root,[out/'results.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym');slots=info['sprites']['total_slots']
    cases=[(scroll,ec1,ec2,phase) for scroll in range(256) for ec1,ec2 in ((0,0),(128,0),(0,128)) for phase in (0,1)]
    inputs=bytearray();canonical=[]
    for scroll,ec1,ec2,phase in cases:
        attrs=bytearray()
        for slot in range(slots):
            y=20+(slot//3)*15 if slot<12 else (64 if slot in (12,13,23) else 82 if slot<17 else 108 if slot<19 else 64)
            ay=(scroll+y-1)&255
            if ay==216:ay=215
            attrs.extend((ay,32+slot*7&255,slot*4,slot))
        attrs.append(216);canonical.append(bytes(attrs))
        inputs.extend(bytes((ec1,ec2,phase))+attrs)
    (out/'cases.bin').write_bytes(inputs)
    # Disable only VDP IRQ sources for this isolated table transaction. The
    # renderer deliberately yields between chunks; a footer IRQ otherwise owns
    # and replaces the fuel SAT entries midway through an artificial case.
    code=bytes((243,62,6,211,153,62,128,211,153,62,66,211,153,62,129,211,153,205))+syms['Flicker_Publish'].to_bytes(2,'little')+bytes((195,64,199))
    (out/'probe.bin').write_bytes(code)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach n {cases probe} {set f [open [file join $out "$n.bin"] rb];set $n [read $f];close $f}',
        f'set bytes {slots*4+4};set index 0;set started 0',
        'set results [open [file join $out results.bin] wb];set costs [open [file join $out costs.tsv] w]',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/$::bytes} {if {[debug read_block VRAM 0 65536] ne $::scene || [debug read_block memory 0xe000 4096] ne $::native} {error "Flicker changed maze or native state"};close $::results;close $::costs;exit 0;return}',
        ' set c [string range $::cases [expr {$::index*$::bytes}] [expr {($::index+1)*$::bytes-1}]];binary scan [string range $c 0 2] cu* h;lassign $h ec1 ec2 phase;set attrs [string range $c 3 end]',
        f' debug write memory {syms["Enemy1_LastEC"]} $ec1;debug write memory {syms["Enemy2_LastEC"]} $ec2;debug write memory {syms["Flicker_Phase"]} $phase',
        ' debug write_block memory 0xc100 [string range $attrs 0 67];debug write_block memory 0xc410 [string range $attrs 68 75]',
        ' debug write_block memory 0xc600 [string range $attrs 76 83];debug write_block memory 0xc610 [string range $attrs 84 91]',
        *([' debug write_block memory 0xc620 [string range $attrs 92 95]'] if slots==24 else []),
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc700','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::scene [debug read_block VRAM 0 65536];set ::native [debug read_block memory 0xe000 4096];debug write_block memory 0xc700 $::probe;issue}}',
        f'debug set_bp 0xc740 {{$::started}} {{if {{[reg SP]!=0xc7f0}} {{error "Flicker stack imbalance"}};puts -nonewline $::results [debug read_block VRAM 128512 {slots*4+1}];puts -nonewline $::results [debug read_block VRAM 128096 64];puts -nonewline $::results [debug read_block VRAM 128304 64];puts $::costs "$::index [expr {{round(([machine_info time]-$::begin)*3579545)}}]";incr ::index;issue}}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Flicker VRAM timing violation";exit 2}',
        'after time 60 {puts stderr "Flicker probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'results.bin').read_bytes();size=slots*4+129
    if len(raw)!=len(cases)*size:raise ValueError('Incomplete flicker trace')
    white=bytes([info['sprites']['white']|32])*64;boosted=0
    for n,((scroll,ec1,ec2,phase),attrs) in enumerate(zip(cases,canonical)):
        r=raw[n*size:(n+1)*size];order=permutation(slots,phase^1)
        expected=b''.join(attrs[i*4:i*4+4] for i in order)+bytes((216,))
        if r[:slots*4+1]!=expected:raise ValueError(f'Flicker permutation changed actors/terminator: {n}')
        enemy=b''.join(bytes([ec|38])*16+bytes([ec|106])*16 for ec in (ec1,ec2))
        colors=(enemy+white) if phase^1 else (white+enemy)
        if r[slots*4+1:]!=colors:raise ValueError(f'Flicker split CC pair/color/EC: {n}')
        chosen,peak=selected(expected,scroll,64)
        if phase^1 and not {6,7,8,9}<=set(s for s,dy in chosen):raise ValueError('Boosted complete actors starved')
        boosted+=bool(phase^1 and peak>8)
    costs=[int(r.split()[1]) for r in (out/'costs.tsv').read_text().splitlines()]
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),boosted_overflow_cases=boosted,
        nominal_hz=info['timing']['nominal_hz'],elapsed_cycles=dict(median=statistics.median(costs),maximum=max(costs)),
        strict_vram_timing=True,native_state_unchanged=True,maze_unchanged=True,
        scope='Isolated actual permutation/color upload with VDP IRQ sources disabled; all256 scroll phases, CC/EC pair grouping and guaranteed enemy priority every second publication; not whole-game interrupt/frame acceptance'))
    verify_manifest(bundle);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} executed flicker permutations: {out}/report.json')
