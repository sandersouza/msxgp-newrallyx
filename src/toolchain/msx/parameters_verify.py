"""Independent original post-flag difficulty/velocity parameter proof."""
import os
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .fuel_verify import source_seed


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    component=info.get('parameter_component')
    if not component:raise ValueError('Parameter proof requires linked original $1b1f')
    out=destination(root,args.output);out.mkdir(parents=True);require_ignored(root,[out/'cases.bin'])
    cases=[(r,c,p,busy) for r in range(2,21) for c in (0,4,5,7,8,9,10) for p in range(5) for busy in (0,1)]
    seed=bytearray(source_seed(bundle))
    seed[0x2d2:0x2d4]=(component['table_pointer']-0x8000).to_bytes(2,'little')
    seed[0x2d8]=component['round_limit'];seed[0x28f]=0x30
    (out/'source-seed.bin').write_bytes(seed);(out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Parameter proof requires MAME0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/msx/parameters_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','90']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,PARAMETERS_OUTPUT=str(out)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    syms=symbols(bundle/'raster-scroll.sym');bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    native=bytearray(seed)
    for at in (0x988,0x98a,0x98c,0x98e,0x990,0x99a,0x99c):
        native[at:at+2]=(int.from_bytes(native[at:at+2],'little')+0x6000).to_bytes(2,'little')
    native[0x2d2:0x2d4]=component['table_pointer'].to_bytes(2,'little');native[0x28f]=0xb0
    (out/'native-seed.bin').write_bytes(native)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach n {cases native-seed} {set f [open [file join $out "$n.bin"] rb];set data($n) [read $f];close $f}',
        'set result [open [file join $out msx.bin] wb];set index 0;set started 0',
        'proc issue {} {',f' if {{$::index=={len(cases)}}} {{close $::result;exit 0;return}}',
        ' debug write_block memory 0xe000 $::data(native-seed)',
        ' set p [expr {$::index*4}];binary scan [string range $::data(cases) $p [expr {$p+3}]] cu* c',
        ' foreach a {0xe1b0 0xe271 0xe28a 0xe292} v $c {debug write memory $a $v}',
        f' debug write memory 0x7000 {syms["PLAYER_BANK"]}',
        ' set p 0xd110;foreach v {243 205 31 155 195 64 209} {debug write memory $p $v;incr p}',
        ' reg SP 0xc7f0;reg PC 0xd110','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved [debug read_block VRAM 0 131072];issue}}',
        'debug set_bp 0xd140 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read_block VRAM 0 131072] ne $::saved} {error "Parameter adapter changed VRAM/stack"}',
        ' foreach a {0xe28f 0xe2b1 0xe2d6 0xe24e 0xe26e 0xe288 0xe251} {puts -nonewline $::result [binary format c [debug read memory $a]]}',
        ' puts -nonewline $::result [debug read_block memory 0xe025 8];incr ::index;issue','}',
        'after time 90 {puts stderr "Parameter proof timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    original=bytearray((out/'original.bin').read_bytes());actual=(out/'msx.bin').read_bytes()
    if len(original)!=len(cases)*15:raise ValueError('Incomplete original parameter proof')
    for i in range(len(cases)):original[i*15]|=128
    if actual!=original:
        at=next((i for i,(a,b) in enumerate(zip(actual,original)) if a!=b),min(len(actual),len(original)))
        raise ValueError(f'Original parameter mismatch {cases[at//15]}, byte{at%15}')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Parameter proof BIOS changed')
    verify_manifest(bundle)
    first=[list(actual[i*15:i*15+15]) for i,c in enumerate(cases) if c[0]==2 and c[2]==4 and c[3]==0]
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),bytes_per_case=15,
        first_round_flag_thresholds=first,vram_unchanged=True,stack_unchanged=True,
        relocation='Original terrain-page value OR128, pointers relocated; all other output bytes exact',
        scope='Isolated original post-flag parameters across rounds2..20, counts0/4/5/7/8/9/10, four per-life phases plus lucky phase0, busy gate'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact original parameter cases: {out}/report.json')
    return out
