"""Original selected enemy state/visibility/contact oracle against assembled MSX code."""
import os
import statistics
import subprocess
from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .fuel_verify import source_seed

RANGES=((0,0x1a8),(0x1b5,1),(0x248,10),(0x814,12))
RECORD=sum(n for _,n in RANGES)+1


def cases_for():
    cases=[(2,0,0,0,0)]
    for i in range(2400):
        joy=(223,247,239,251)[i//150%4]
        cases.append((0,joy,int(i%4==3),0,0))
    offsets=(-128,-12,-11,-10,-1,0,1,10,11,12,127)
    cases.extend((1,(112+x)&255,(116+y)&255,hidden,0) for x in offsets for y in offsets for hidden in (0,1))
    return cases


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    count=info.get('enemy_count')
    if info.get('incremental_stage') not in (8,9) or count not in (1,2):raise ValueError('Enemy proof requires stage 08/09 with one or two enemies')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    cases=cases_for();(out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    seed=bytearray(source_seed(bundle));seed[0x28f]=0x30;seed[0x99e:0x9a0]=(0x9f40).to_bytes(2,'little')
    (out/'source-seed.bin').write_bytes(seed)
    inputs=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Enemy oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/msx/enemy_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','90']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,ENEMY_OUTPUT=str(out),ENEMY_COUNT=str(count)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        f'set f [open {tcl(bundle/"player-seed.bin")} rb];set seed [read $f];close $f',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set costs [open [file join $out cycles.tsv] w];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/5} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {error "Enemy logic changed VRAM"};close $::result;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*5}] [expr {$::index*5+4}]] cu* c;lassign $c ::kind a b hidden unused',
        f' set code {{243 62 {syms["PLAYER_BANK"]} 50 0 112}}',
        ' if {$::kind!=0} {debug write_block memory 0xe000 $::seed;debug write memory 0xc5d0 0}',
        ' if {$::kind==2} {',
        f'  lappend code 205 108 140 205 {syms["Enemy_Init"]&255} {syms["Enemy_Init"]>>8} 42 39 224 34 105 224 34 45 224',
        ' } elseif {$::kind==1} {',
        '  foreach {at v} [list 0xe004 147 0xe005 224 0xe074 112 0xe076 116 0xe094 $a 0xe096 $b 0xe093 $hidden] {debug write memory $at $v}',
        '  lappend code 221 33 104 224 253 33 4 224 6 5 205 138 131',
        ' } else {',
        '  debug write memory 0xe3f0 $a',
        f'  lappend code 205 {syms["Enemy_PreMove"]&255} {syms["Enemy_PreMove"]>>8} 205 105 128 205 82 144',
        '  if {$b} {lappend code 205 223 157}',
        f'  lappend code 205 {syms["Enemy_AfterMove"]&255} {syms["Enemy_AfterMove"]>>8}',
        ' }',
        ' lappend code 195 96 198;set p 0xc600;foreach v $code {debug write memory $p $v;incr p}',
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc600','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved_vram [debug read_block VRAM 0 131072];issue}}',
        'debug set_bp 0xc660 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Enemy component stack imbalance"}',
        *[f' puts -nonewline $::result [debug read_block memory {0xe000+a} {n}]' for a,n in RANGES],
        ' puts -nonewline $::result [binary format c [debug read memory 0xc5d0]]',
        ' puts $::costs "$::index $::kind [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        ' incr ::index;issue','}',
        'after time 180 {puts stderr "Enemy microprobe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    expected=(out/'original.bin').read_bytes();actual=(out/'msx.bin').read_bytes()
    if len(expected)!=len(cases)*RECORD or len(actual)!=len(expected):raise ValueError('Incomplete enemy component proof')
    for i,c in enumerate(cases):
        a,b=actual[i*RECORD:(i+1)*RECORD],expected[i*RECORD:(i+1)*RECORD]
        if a!=b:
            offsets=[j for j,(x,y) in enumerate(zip(a,b)) if x!=y]
            raise ValueError(f'Enemy mismatch case {i}, {c}, offsets {offsets[:20]}: {a[offsets[0]]:02x}/{b[offsets[0]]:02x}')
    if inputs!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())) or bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Source/BIOS changed')
    verify_manifest(bundle)
    rows=[r.split() for r in (out/'cycles.tsv').read_text().splitlines()]
    json_write(out/'report.json',dict(cases=len(cases),logical_steps=2400,contact_cases=242,rom_sha256=digest(args.rom),mame_version=version,
        byte_ranges=RANGES,bytes_per_case=RECORD,virtual_sprite_pointer_relocation='Exact six-slot pointer ABI +0x6000, constrained to original descriptor addresses',
        costs={kind:dict(median_cycles=statistics.median(int(r[2]) for r in rows if int(r[1])==kind),max_cycles=max(int(r[2]) for r in rows if int(r[1])==kind)) for kind in (0,1,2)},
        vram_unchanged=True,scope='Selected original enemy initializer/AI/motion/facing/virtual sprite visibility and contact; original camera prefixes return before bitmap redraw; externally clocked component, no natural IRQ/foreground equivalence claim'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact original enemy/visibility/contact states: {out}/report.json')
    return out
