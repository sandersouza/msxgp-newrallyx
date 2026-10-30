"""Execute minimum-refresh publication, first-packet parity and counter wrap."""
import os
import subprocess
from .emulator import reference_machine,tcl


def verify(root,args,out,s):
    if 'Full_PresentClockValid' not in s:return 0
    out.mkdir()
    cases=[(1,last,(last+delta)&255,1) for last in range(256)
           for delta in (0,1,2,3,4,255)]
    cases += [(0,37,current,1) for current in range(256)]
    cases += [(valid,0,current,0) for valid in (0,1) for current in (0,1,2,3,255)]
    expected=[]
    for valid,last,current,ready in cases:
        commit=bool(ready and (((current-last)&255)>=2 if valid else current&1))
        expected.append(bytes((0 if commit else ready,current if commit else last,
            1 if commit else valid,0x34 if commit else 0x10,
            0x12 if commit else 0x32,82 if commit else 37)))
    enter,leave,commit=(s[k] for k in ('Full_CacheEnter','Full_CacheLeave','Full_PresentCommit'))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
        'set z80_freq 3579545','set z80_freq_locked true','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set cases {'+' '.join('{'+ ' '.join(map(str,c))+'}' for c in cases)+'}',
        'set started 0;set index 0;set result [open [file join $out result.bin] wb]',
        'proc issue {} {',
        ' if {$::index==[llength $::cases]} {close $::result;exit 0;return}',
        ' lassign [lindex $::cases $::index] valid last current ready',
        f' foreach {{at value}} [list {s["Full_PresentClockValid"]} $valid {s["Full_PresentLastTick"]} $last {s["Full_PresentReady"]} $ready {s["ticks"]} $current {s["Full_CacheHeld"]} 0 {s["Full_PresentLength"]} 1 {s["Full_PresentNextX"]} 52 {s["Full_PresentNextX"]+1} 18 {s["Full_PresentNextY"]} 82 {s["Full_PresentActiveX"]} 16 {s["Full_PresentActiveX"]+1} 50 {s["irq_scroll_y"]} 37] {{debug write memory $at $value}}',
        ' debug write VRAM 0x1f648 52;set ::front [debug read_block VRAM 0 131072]',
        ' set ::expected_commit [expr {$ready && ($valid?(($current-$last)&255)>=2:($current&1))}]',
        ' reg IX 9029;reg IY 17767;reg SP 0xc7f0;reg PC 0xd150','}',
        f'debug set_bp {s["main"]} {{!$::started}} {{',
        ' set ::started 1;set ::native [debug read_block memory 0xe000 4096];set ::primary [debug read ioports 168];set ::mapper [debug read ioports 252]',
        ' debug write {VDP regs} 0 [expr {[debug read {VDP regs} 0]&239}];debug write {VDP regs} 1 [expr {[debug read {VDP regs} 1]&223}]',
        f' set at 0xd150;foreach byte {{243 205 {enter&255} {enter>>8} 195 96 209}} {{debug write memory $at $byte;incr at}}',
        f' set at 0xd170;foreach byte {{205 {commit&255} {commit>>8} 205 {leave&255} {leave>>8} 195 128 209}} {{debug write memory $at $byte;incr at}}',
        ' issue','}',
        'debug set_bp 0xd160 {$::started} {',
        f' debug write_block memory {s["Full_PresentDirty"]} [string repeat [binary format c 0] 7]',
        ' reg PC 0xd170','}',
        'debug set_bp 0xd180 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [reg IX]!=9029 || [reg IY]!=17767 || [debug read_block memory 0xe000 4096] ne $::native || [debug read ioports 168]!=$::primary || [debug read ioports 252]!=$::mapper} {puts stderr "Presentation clock damaged registers, native RAM or mapping";exit 2}',
        ' set expected $::front;if {$::expected_commit} {set expected [string replace $expected 128584 128584 [binary format c 216]]}',
        ' if {[debug read_block VRAM 0 131072] ne $expected} {puts stderr "Presentation clock changed unexpected VRAM";exit 2}',
        f' puts -nonewline $::result [binary format c* [list [debug read memory {s["Full_PresentReady"]}] [debug read memory {s["Full_PresentLastTick"]}] [debug read memory {s["Full_PresentClockValid"]}] [debug read memory {s["Full_PresentActiveX"]}] [debug read memory {s["Full_PresentActiveX"]+1}] [debug read memory {s["irq_scroll_y"]}]]]',
        ' incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Presentation clock VDP timing violation";exit 2}',
        'after time 120 {puts stderr "Presentation clock timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],stdout=log,
            stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'result.bin').read_bytes()
    if actual!=b''.join(expected):raise ValueError('Adaptive presentation clock differs from refresh oracle')
    return len(cases)
