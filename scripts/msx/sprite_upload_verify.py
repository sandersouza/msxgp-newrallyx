"""Exercise interruptible uploads across real raster/VBlank interrupts."""
import os
import statistics
import subprocess

from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    syms=symbols(bundle/'raster-scroll.sym')
    if 'Sprite_ResumeUpload' not in syms:raise ValueError('Interruptible sprite upload cartridge required')
    out=destination(root,args.output);require_ignored(root,[out/'results.bin']);out.mkdir(parents=True)
    cases=[(count,16+29*(repeat%4)) for repeat in range(16) for count in range(1,129)]
    (out/'cases.bin').write_bytes(b''.join(bytes(c) for c in cases))
    code=bytes((243,205,syms['Sprite_Upload']&255,syms['Sprite_Upload']>>8,195,64,199))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set results [open [file join $out results.bin] wb];set costs [open [file join $out cycles.tsv] w];set irq [open [file join $out irq.tsv] w];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/2} {if {[debug read_block VRAM 0 65536] ne $::scene || [debug read_block memory 0xe000 4096] ne $::native} {error "Upload changed maze/native state"};close $::results;close $::costs;close $::irq;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*2}] [expr {$::index*2+1}]] cu* c;lassign $c count offset',
        ' set payload {};for {set i 0} {$i<128} {incr i} {lappend payload [expr {($::index*13+$i*29)&255}]}',
        ' debug write_block memory 0xc900 [binary format c* $payload]',
        ' debug write_block VRAM 122880 [string repeat [binary format c 165] 256]',
        ' set ::begin [machine_info time];reg HL 0xc900;reg DE [expr {0x6000+$offset}];reg B $count;reg SP 0xc7f0;reg PC 0xc700','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::scene [debug read_block VRAM 0 65536];set ::native [debug read_block memory 0xe000 4096]',
        *[f' debug write memory {0xc700+i} {v}' for i,v in enumerate(code)],'issue','}',
        f'debug set_bp {syms["Sprite_ResumeUpload"]} {{$::started}} {{puts $::irq "$::index [debug read memory 0xc03c] [debug read memory 0xc0a0] [expr {{[reg HL]-0xc900}}]"}}',
        'debug set_bp 0xc740 {$::started} {',
        ' binary scan [string range $::cases [expr {$::index*2}] [expr {$::index*2+1}]] cu* c;lassign $c count offset',
        f' if {{[reg SP]!=0xc7f0 || [reg HL]!=0xc900+$count || [reg DE]!=0x6000+$offset+$count || [debug read memory {syms["Sprite_UploadActive"]}]}} {{error "Upload return/register contract"}}',
        ' puts -nonewline $::results [debug read_block VRAM 122880 256];puts $::costs [expr {round(([machine_info time]-$::begin)*3579545)}];incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Upload VRAM timing violation";exit 2}',
        'after time 60 {puts stderr "Upload component timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=90,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'results.bin').read_bytes()
    if len(raw)!=256*len(cases):raise ValueError('Incomplete upload evidence')
    for n,(count,offset) in enumerate(cases):
        expected=bytearray([165])*256;expected[offset:offset+count]=bytes((n*13+i*29)&255 for i in range(count))
        if raw[n*256:(n+1)*256]!=expected:raise ValueError(f'Interrupted upload/canary mismatch {n}, {count} bytes')
    irqs=[list(map(int,r.split())) for r in (out/'irq.tsv').read_text().splitlines()]
    phases={r[2] for r in irqs}
    expected_phases={0,1,2}
    if 'radar_interrupt' in syms:expected_phases.add(3)
    if 'radar_close_interrupt' in syms:expected_phases.add(4)
    if 'prefetch_guard_interrupt' in syms:expected_phases.add(5)
    if phases!=expected_phases or len(irqs)<50:raise ValueError(f'Insufficient actual interrupt overlap: {len(irqs)}, phases {phases}')
    if any(not 0<=r[3]<=cases[r[0]][0] for r in irqs):raise ValueError('IRQ resumed from an invalid source offset')
    costs=[int(v) for v in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=len(cases) or bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Upload evidence/source changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),real_interrupt_overlaps=len(irqs),raster_phases=sorted(phases),
        distinct_interrupted_offsets=len({r[3] for r in irqs}),maze_unchanged=True,native_state_unchanged=True,
        elapsed_cycles=dict(median=statistics.median(costs),maximum=max(costs)),strict_vram_timing=True,
        scope='Actual uploads of every length1..128 across real header/footer/guard/VBlank IRQs; exact destination/canaries, register/stack contract, fixture RAM/offscreen VRAM writes; not whole-game display acceptance'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} uploads, {len(irqs)} real interrupt overlaps: {out}/report.json')
