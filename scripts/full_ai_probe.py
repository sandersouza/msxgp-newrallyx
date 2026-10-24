#!/usr/bin/env python3
"""Compare guarded AI transform reuse with three unmodified original calls."""
import argparse
import itertools
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.build import destination
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.msx.round_prepare_verify import relocated_seed
from scripts.scenes.bundle import digest,verify_manifest
from scripts.scenes.record import lua_literal
from scripts.scenes.storage import require_ignored,json_write,seal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=Path('references/build/issue12-round-inventory-v13'))
    p.add_argument('--motion',action='store_true',help='Compare three original movement calls, including all fine-byte values')
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);verify_manifest(args.reference)
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    seed=(args.reference/'case-003-video.bin').read_bytes()
    if seed[0x1b0]!=4 or seed[0x24e]!=7:raise ValueError('Expected original first-challenge seed')
    (out/'source-seed.bin').write_bytes(seed);(out/'native-seed.bin').write_bytes(relocated_seed(seed))
    cases=[]
    for n,(position,axis,velocity,center,mask) in enumerate(itertools.product(
            ((5,8),(15,20),(25,50),(15,52),(15,1)),(0,255),(2,253),(0,1,255),range(128))):
        cases.append([*position,axis,velocity,center,mask,(n//128)%11,(n//1024)%4,n%3])
    (out/'cases.bin').write_bytes(bytes(v for c in cases for v in c))
    (out/'config.lua').write_text('return '+lua_literal(dict(output=str(out),cases=cases,entry=0x69 if args.motion else 0xcd6,motion=int(args.motion)))+'\n')
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('AI oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-debug','-debugger','none','-autoboot_delay','0',
        '-autoboot_script',str(root/'scripts/msx/full_ai_native.lua'),
        '-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','600']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,check=True,timeout=180,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,FULL_AI_CONFIG=str(out/'config.lua')))
    original=(out/'original.bin').read_bytes()
    if len(original)!=4096*len(cases) or not (out/'complete').is_file():raise ValueError('Incomplete original AI evidence')
    syms=symbols(bundle/'raster-scroll.sym')
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach n {cases native-seed} {set f [open [file join $out "$n.bin"] rb];set data($n) [read $f];close $f}',
        'set index 0;set started 0;set result [open [file join $out msx.bin] wb]']
    script=r'''
proc execute {} {
    debug write memory 0x7000 @BANK@
    set at 0xd150;foreach value {@CALL@} {debug write memory $at $value;incr at}
    reg SP 0xc7f0;reg PC 0xd150
}
proc issue {} {
    if {$::index==[string length $::data(cases)]/9} {close $::result;exit 0;return}
    set ::step 1
    debug write_block memory 0xe000 $::data(native-seed)
    binary scan [string range $::data(cases) [expr {$::index*9}] [expr {$::index*9+8}]] cu* c
    set ::case $c
    lassign $c x y axis velocity center mask guard page mutate
    foreach at {0xe070 0xe072 0xe06b 0xe06a 0xe05b} value [list $x $y $axis $velocity $center] {debug write memory $at $value}
    foreach at {0xe025 0xe026 0xe029 0xe02a 0xe3f1 0xe3f8} {debug write memory $at 0}
    debug write memory 0xe24e 7;debug write memory 0xe28f [expr {0xb0+$page}]
    debug write memory 0xc701 [expr {$guard==1 || $guard==10}]
    debug write_block memory 0xd160 [string repeat [binary format c [expr {$guard==1}]] 32]
    if {$guard==10} {debug write_block memory 0xe400 [string repeat [binary format c 0] 1024]}
    for {set i 0} {$i<7} {incr i} {
        set p [expr {0xe088+$i*32}]
        foreach offset {0 1 2 19 21} {debug write memory [expr {$p+$offset}] 0}
        debug write memory [expr {$p+3}] [expr {($mask>>$i)&1?255:0}]
        if {@MOTION@} {
            foreach offset {4 5 6 7} multiplier {7 17 11 23} {
                debug write memory [expr {$p+$offset}] [expr {($::index+$i*$multiplier)&255}]
            }
            if {($::index+$i)%3==1} {
                debug write memory [expr {$p+1}] [expr {$::index&255}]
                debug write memory [expr {$p+2}] $velocity
            }
        }
    }
    switch $guard {
        2 {debug write memory 0xe025 32;debug write memory 0xe026 2}
        3 {debug write memory 0xe088 1}
        4 {debug write memory 0xe0db 2}
        5 {debug write memory 0xe0fd 1}
        6 {debug write memory 0xe0a9 1}
        7 {debug write memory 0xe10b 7}
        8 {debug write memory 0xe08d 1}
        9 {debug write memory 0xe08f 255}
    }
    execute
}
debug set_bp @MAIN@ {!$::started} {
    set ::started 1;set ::vram [debug read_block VRAM 0 131072]
    set ::shadow [debug read_block memory 0xd230 120];set ::irq [debug read_block memory 0xd2d2 3]
    issue
}
debug set_bp 0xd160 {$::started} {
    if {[reg SP]!=0xc7f0 || [debug read_block VRAM 0 131072] ne $::vram ||
        [debug read_block memory 0xd230 120] ne $::shadow || [debug read_block memory 0xd2d2 3] ne $::irq} {error "AI reuse changed VRAM/stack/player shadow/IRQ trampoline"}
    if {$::step==3} {
        puts -nonewline $::result [debug read_block memory 0xe000 4096]
        incr ::index;issue
    } else {
        incr ::step
        if {$::step==3} {
            switch [lindex $::case 8] {
                1 {debug write memory 0xe070 [expr {[debug read memory 0xe070]+1}]}
                2 {debug write memory 0xe05b [expr {([debug read memory 0xe05b]+1)&255}]}
            }
        }
        execute
    }
}
after time 240 {puts stderr "Native repeated-AI proof timeout";exit 2}
'''.replace('@BANK@',str(syms['PLAYER_BANK'])).replace('@MAIN@',str(syms['main'])).replace('@MOTION@',str(int(args.motion))).replace('@CALL@','243 205 105 128 195 96 209' if args.motion else '243 205 0 182 195 96 209')
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n'+script+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=180,
            stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'msx.bin').read_bytes()
    if len(actual)!=len(original):raise ValueError('Incomplete native repeated-AI evidence')
    for n in range(len(cases)):
        expected=bytearray(relocated_seed(original[n*4096:(n+1)*4096]));observed=bytearray(actual[n*4096:(n+1)*4096])
        expected[0x3f1:0x3f9]=observed[0x3f1:0x3f9]=bytes(8)
        if observed!=expected:
            at=next(i for i,(a,b) in enumerate(zip(observed,expected)) if a!=b)
            raise ValueError(f'Original AI mismatch: case {n} {cases[n]}, offset {at:03x}: {observed[at]:02x}/{expected[at]:02x}')
    verify_manifest(bundle);verify_manifest(args.reference)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),original_calls_per_case=3,
        compared_bytes_per_case=4088,declared_host_scratch=[0xe3f1,0xe3f9],
        stack_unchanged=True,vram_unchanged=True,player_shadow_unchanged=True,irq_trampoline_unchanged=True,
        component='movement' if args.motion else 'AI',
        scope=('Original repeated movement versus guarded zero-velocity adapter: all fine-byte values, fractional bytes, both axes, moving/stationary/startup/stun paths and player centering.' if args.motion else 'Original repeated AI state versus guarded transform lookup: all seven direction combinations, four maps, centering/heading/velocity inputs, key changes and smoke/moving/stunned/startup/same-cell/invalid-axis fallbacks.')))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'{len(cases)} exact repeated original AI cases pass: {out}/report.json')


if __name__=='__main__':main()
