"""Execute grouped death copies at cache-page/wrap boundaries and small budgets."""
import os
import statistics
import subprocess
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols


def verify(root,args,*,kind='death'):
    bundle=args.rom.parent;verify_manifest(bundle)
    info=read_json(bundle/'build.json')
    if info.get('incremental_stage',0)<6:raise ValueError('Grouped copy proof requires stage 06 or later')
    if kind=='flags' and not info.get('enemy_rendered'):raise ValueError('Grouped flag copy proof requires stage 08')
    out=destination(root,args.output);require_ignored(root,[out/'cache.bin']);out.mkdir(parents=True)
    cases=[(x,y,b) for x in range(64) for y in (0,29,30,31) for b in (1,9)]
    (out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    syms=symbols(bundle/'raster-scroll.sym')
    call,wait=syms['Smoke_Stream' if kind=='smoke' else 'Flag_StreamRows' if kind=='flags' else 'Death_StreamRows'],syms['stage_wait_command']
    jobs,ax,ay=(0xc70e,0xc740,0xc741) if kind=='smoke' else (0xc50e,0xc50f,0xc510) if kind=='flags' else (0xc494,0xc492,0xc493)
    code=[0xf3,0x06,9,0xcd,call&255,call>>8,0xcd,wait&255,wait>>8,0x76]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set cache [open [file join $out cache.bin] wb];set costs [open [file join $out cycles.tsv] w];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/3} {close $::cache;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*3}] [expr {$::index*3+2}]] cu* c;lassign $c x y budget',
        ' debug write_block VRAM 0 [string repeat [binary format c 170] 65536]',
        f' foreach {{a v}} [list 0xc400 {int(kind=="smoke")} 0xc418 0 0xc490 {int(kind=="death")} {ax} $x {ay} $y {jobs} {1 if kind=="smoke" else 9} 0xc602 $budget] {{debug write memory $a $v}}',
        *([' debug write_block memory 0xe400 [string repeat [binary format c 0] 1024]',
           ' debug write_block memory 0xd300 [string repeat [binary format c 0] 2048];debug write_block memory 0xdb00 [string repeat [binary format c 0] 32]',
           ' foreach {a v} [list 0xc701 1 0xc702 $x 0xc703 $y 0xc70c 0 0xc70d 1 0xc70f 0 0xc742 0 0xc5e8 0 0xc46f [expr {($x-4)&255}] 0xc470 [expr {($y-3)&255}]] {debug write memory $a $v}',
           ' for {set sy 0} {$sy<3} {incr sy} {for {set sx 0} {$sx<3} {incr sx} {debug write memory [expr {0xe400+((($y+$sy-10)&31)*32)+(($x+$sx-3)&31)}] [expr {189+$sy*3+$sx}]}}'] if kind=='smoke' else []),
        f' debug write memory {info.get("death",{}).get("display_state_address",0xc490)} {int(kind=="death")}',
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc600','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;',
        *[f'debug write memory {0xc600+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc609 {$::started} {',
        *([f' if {{[debug read memory {jobs}]}} {{debug write memory {syms["Stage_GuardClosed"]} 0;reg SP 0xc7f0;reg PC 0xc600;return}}'] if kind=='smoke' else []),
        f' if {{[reg SP]!=0xc7f0 || [debug read memory {jobs}]!=0 || [debug read memory 0xc468]!=8'+('' if kind=='smoke' else ' || [reg B]!=0')+f'}} {{puts stderr "Grouped copy invalid case$::index SP[reg SP] jobs[debug read memory {jobs}] width[debug read memory 0xc468] B[reg B]";exit 2}}',
        ' puts -nonewline $::cache [debug read_block VRAM 0 65536]',
        ' puts $::costs "$::index [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        ' incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Grouped death VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Grouped death copy timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    tiles=(bundle/'death-pixels.bin').read_bytes()
    if kind=='smoke':tiles=(bundle/'smoke-pixels.bin').read_bytes()
    if kind=='flags':
        from .stage_one import acquire,reconstruct
        program,reference=acquire(root);cells,_,_=reconstruct(program,reference);cell=cells.index(0)
        world=(bundle/'stage-world.bin').read_bytes();tx=3+cell%32*3;ty=3+cell//32*3
        tiles=bytes(world[(ty*8+y)*816+tx*8+x] for y in range(8) for x in range(8))*9
    with (out/'cache.bin').open('rb') as f:
        for i,(tx,ty,budget) in enumerate(cases):
            expected=bytearray([170])*65536
            for y in range(24):
                for x in range(24):
                    pixel=tiles[(y//8*3+x//8)*64+y%8*8+x%8]
                    px=(tx*8+x)%512;py=(ty*8+y)%256
                    at=(px//256)*32768+py*128+(px%256)//2
                    expected[at]=expected[at]&15|pixel<<4 if px%2==0 else expected[at]&240|pixel
            if f.read(65536)!=expected:raise ValueError(f'Grouped death copy pixels differ at case {i}: {tx},{ty}, budget {budget}')
        if f.read(1):raise ValueError('Extra grouped copy captures')
    costs=[int(r.split()[1]) for r in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=len(cases):raise ValueError('Incomplete grouped copy costs')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),cache_bytes_per_case=65536,
        kind=kind,median_cycles=statistics.median(costs),max_cycles=max(costs),strict_vram_timing=True,
        scope='Assembled 24x8 grouped copies; all 64 horizontal cache tile positions, vertical wrap, small budgets, exact original pixels and unchanged surrounding canary; synthetic component harness'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact grouped death/cache-wrap cases: {out}/report.json')
    return out
