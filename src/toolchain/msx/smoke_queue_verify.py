"""Exercise bounded cloud publication jobs across full queues and ring wraps."""
import os
import subprocess

from .emulator import reference_machine,tcl


def verify(root,args,out,syms):
    out.mkdir()
    cases=[];expected=[]
    modes=(0,64) if 'Smoke_EnqueueRow' in syms else (0,)
    if 'Full_EnqueueSmoke' in syms:modes+=(128,)  # Native successful-placement priority.
    for head in range(32):
        for count in (0,1,16,31,32):
            for duplicate in sorted({-1,0,count//2,count-1}):
                if duplicate>=count:continue
                for mode in modes:
                    state=bytearray([165])*148
                    state[:4]=bytes((head,(head+count)&31,count,0))
                    for i in range(count):
                        p=52+3*((head+i)&31)
                        state[p:p+3]=bytes((i+10,i+40,64+i%3 if i&1 and len(modes)>1 else i%9))
                    x,y=(200,201) if duplicate<0 else (duplicate+10,duplicate+40)
                    wanted=bytearray(state)
                    request=0 if mode==128 else mode
                    if duplicate>=0:
                        at=54+3*((head+duplicate)&31)
                        wanted[at]=request if wanted[at]&64 else 0
                    elif count==32:wanted[3]=1
                    else:
                        tail=(head+count)&31
                        wanted[52+3*tail:55+3*tail]=bytes((x,y,request))
                        wanted[1]=(tail+1)&31;wanted[2]+=1
                    if mode==128 and (duplicate>=0 or count<32):
                        at=52+3*((head+duplicate)&31) if duplicate>=0 else 52+3*((head+count)&31)
                        first=52+3*head
                        wanted[first:first+3],wanted[at:at+3]=wanted[at:at+3],wanted[first:first+3]
                    cases.append(bytes((x,y,mode))+state);expected.append(bytes(wanted))
    (out/'cases.bin').write_bytes(b''.join(cases))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
        'set result [open [file join $out actual.bin] wb];set index 0;set started 0',
        'proc issue {} {',f' if {{$::index=={len(cases)}}} {{close $::result;exit 0;return}}',
        ' set at [expr {$::index*151}];binary scan [string range $::data $at [expr {$at+2}]] cu* c',
        ' debug write_block memory 0xc70c [string range $::data [expr {$at+3}] [expr {$at+150}]]',
        f' set target [expr {{[lindex $c 2]==128?{syms.get("Full_EnqueueSmoke",syms["Smoke_Enqueue"])}:[lindex $c 2]?{syms.get("Smoke_EnqueueRow",syms["Smoke_Enqueue"])}:{syms["Smoke_Enqueue"]}}}]',
        ' set p 0xd110;foreach v [list 243 205 [expr {$target&255}] [expr {$target>>8}] 195 64 209] {debug write memory $p $v;incr p}',
        ' reg BC [expr {([lindex $c 0]<<8)|[lindex $c 1]}];reg IX 9029;reg IY 17767;reg SP 0xc7f0;reg PC 0xd110','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved [debug read_block VRAM 0 131072];issue}}',
        'debug set_bp 0xd140 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [reg IX]!=9029 || [reg IY]!=17767} {error "Smoke queue changed stack or index registers"}',
        ' if {[debug read_block VRAM 0 131072] ne $::saved} {error "Queue mutated VRAM"}',
        ' puts -nonewline $::result [debug read_block memory 0xc70c 148];incr ::index;issue','}',
        'after time 90 {puts stderr "Smoke queue timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'actual.bin').read_bytes();wanted=b''.join(expected)
    if actual!=wanted:
        at=next((i for i,(a,b) in enumerate(zip(actual,wanted)) if a!=b),min(len(actual),len(wanted)))
        raise ValueError(f'Smoke queue wrap/dedup/full behavior differs at case{at//148}, byte{at%148}')
    return len(cases)
