"""Compare linked original smoke rules and complete tile rings against MAME."""
import os
import statistics
import subprocess

from src.toolchain.graphics.roms import input_records,load_metadata,validate_roms
from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .fuel_verify import source_seed
from .hud_verify import symbols

RANGES=((0x26a,2),(0x290,2),(0x9f4,1),(0x88,32),(0x1b5,1),(0x400,1024),(0xc00,1024))
RECORD=sum(n for _,n in RANGES)


def cases_for(flags):
    # kind, history, active-low input, pending clouds, fuel whole/fraction,
    # round, active game, facing, road code/attribute, scroll X/Y,
    # physical anchor X/Y, enemy stun age and cloud-local enemy tile X/Y.
    base=(0,6,253,0,60,0,2,1,240,129,149,0,2,112,116,0,0,0)
    cases=[]
    def case(**values):
        names=('kind','hist','joy','pending','fuel','frac','round','enabled','flag','code','attr','mx','my','px','py','age','dx','dy')
        cases.append(tuple(values.get(k,v) for k,v in zip(names,base)))
    for hist in (0,3,6,7,12,15):
        for joy in (253,255):
            for pending in (0,1,2,3):
                for fuel in (0,1,2,9,10,11,12,60):case(hist=hist,joy=joy,pending=pending,fuel=fuel)
    for flag in flags:
        for phase in range(8):
            for edge in (0,248):case(pending=3,flag=flag,mx=phase,my=phase,px=edge,py=edge)
    for name,values in dict(round=(0,1,3,4,5,8,255),enabled=(0,1),frac=(0,1,9),
                            code=(0,128,129,130,189,197,198,255),attr=(0,21,69,128,149,255)).items():
        for value in values:case(**{name:value})
    for flag in flags:
        for age in (0,1,2,4,135,136):
            for dy in range(3):
                for dx in range(3):case(kind=1,flag=flag,age=age,dx=dx,dy=dy,attr=69)
    for code in (128,129,188,189,190,197,198,255):case(kind=2,code=code)
    return list(dict.fromkeys(cases))


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('smoke_component'):raise ValueError('Build the selected original smoke component first')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    flags=read_json(bundle/'player.json')['flags'];cases=cases_for(flags)
    (out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    seed=bytearray(source_seed(bundle));seed[0x28f]=0x30;seed[0x99e:0x9a0]=(0x9f40).to_bytes(2,'little')
    (out/'source-seed.bin').write_bytes(seed)
    inputs=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Smoke oracle requires MAME0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/msx/smoke_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','90']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,SMOKE_OUTPUT=str(out)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        f'set f [open {tcl(bundle/"player-seed.bin")} rb];set seed [read $f];close $f',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set costs [open [file join $out cycles.tsv] w];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/18} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {error "Smoke logic changed VRAM"};close $::result;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*18}] [expr {$::index*18+17}]] cu* c',
        ' lassign $c kind hist joy pending fuel frac round enabled flag code attr mx my px py age dx dy',
        ' debug write_block memory 0xe000 $::seed',
        ' debug write_block memory 0xe400 [string repeat [binary format c $code] 1024]',
        ' debug write_block memory 0xec00 [string repeat [binary format c $attr] 1024]',
        ' foreach {at v} [list 0xe290 $hist 0xe291 $pending 0xe3f0 $joy 0xe26b $fuel 0xe26a $frac 0xe1b0 $round 0xe021 $enabled 0xe077 $flag 0xe04d $mx 0xe04f $my 0xe074 $px 0xe076 $py 0xe9f4 0] {debug write memory $at $v}',
        f' set instructions {{243 62 {syms["PLAYER_BANK"]} 50 0 112}}',
        ' if {$kind==1} {',
        '  set col [expr {(($mx+$px+3)&255)/8}];set row [expr {((-$my-$py-8)&255)/8}]',
        '  for {set y 0} {$y<3} {incr y} {for {set x 0} {$x<3} {incr x} {debug write memory [expr {0xe400+(($row+$y)%32)*32+($col+$x)%32}] [expr {189+$y*3+$x}]}}',
        '  foreach {at v} [list 0xe088 $age 0xe09d 1 0xe097 $flag 0xe094 [expr {($px+$dx*8)&255}] 0xe096 [expr {($py-$dy*8)&255}]] {debug write memory $at $v}',
        '  lappend instructions 221 33 136 224 205 133 129',
        ' } elseif {$kind==2} {',
        f'  lappend instructions 205 108 140 205 {syms["Enemy_Init"]&255} {syms["Enemy_Init"]>>8} 205 214 140',
        ' } else {lappend instructions 205 100 143}',
        ' lappend instructions 195 64 209;set p 0xd110;foreach v $instructions {debug write memory $p $v;incr p}',
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xd110','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved_vram [debug read_block VRAM 0 131072];issue}}',
        'debug set_bp 0xd140 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Smoke component stack imbalance"}',
        *[f' puts -nonewline $::result [debug read_block memory {0xe000+a} {n}]' for a,n in RANGES],
        ' puts $::costs "$::index [expr {round(([machine_info time]-$::begin)*3579545)}]";incr ::index;issue','}',
        'after time 180 {puts stderr "Smoke component timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'msx.bin').read_bytes();expected=(out/'original.bin').read_bytes()
    if len(expected)!=len(cases)*RECORD or len(actual)!=len(expected):raise ValueError('Incomplete smoke proof')
    for n,c in enumerate(cases):
        a,b=actual[n*RECORD:(n+1)*RECORD],expected[n*RECORD:(n+1)*RECORD]
        if a!=b:
            differences=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
            raise ValueError(f'Smoke mismatch case {n}, {c}, offsets {differences[:16]}: {a[differences[0]]:02x}/{b[differences[0]]:02x}')
    if inputs!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())) or bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('Original inputs or BIOS changed during smoke proof')
    verify_manifest(bundle)
    costs=[int(r.split()[1]) for r in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=len(cases):raise ValueError('Missing smoke costs')
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),mame_version=version,
        verification_source_sha256={name:digest(root/name) for name in ('src/toolchain/msx/smoke_verify.py','src/toolchain/msx/smoke_native.lua')},
        activation_cases=sum(c[0]==0 for c in cases),expiry_cases=sum(c[0]==1 for c in cases),enemy_ai_cases=sum(c[0]==2 for c in cases),
        complete_code_and_attribute_bytes_per_case=2048,elapsed_cycles=dict(median=statistics.median(costs),maximum=max(costs)),
        vram_unchanged=True,scope='Selected original debounce/fuel/placement/full tile rings/enemy stun and expiry; no keyboard/bitmap publication or natural gameplay timing acceptance'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact original smoke component cases: {out}/report.json')
    return out
