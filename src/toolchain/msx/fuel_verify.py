"""Tick-by-tick original fuel/deceleration/lucky oracle against assembled MSX code."""
import os
import statistics
import struct
import subprocess
from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .score_verify import packet

RECORD=44


def cases_for():
    # kind, round, fuel in decimal tenths, collected, mode, clock, enabled,
    # rate, duration, initial score/high, lucky request/multiplier bits.
    cases=[]
    for round_ in (2,5,9,13):
        for fuel in (0,1,2,3,4,5,9,10,11,17,599,600):
            cases.append((1,round_,fuel,9,1,0,1,9,0,0,20000,2))
        for count,mode in ((10,1),(9,0)):
            cases.append((1,round_,600,count,mode,7,1,9,0,19990,20000,3))
        for score in (19990,79990,99999990):
            cases.append((1,round_,17,9,1,0,1,9,0,score,20000,3))
    cases.append((0,2,600,0,1,0,1,9,6600,0,20000,0))
    for fuel in (0,1,2,9,10,11,100):
        for clock in (0,8,9):
            cases.append((0,2,fuel,0,1,clock,1,9,24,0,20000,0))
    cases.append((0,2,100,0,1,0,0,9,32,0,20000,0))
    return cases


def completion_cases():
    cases=[]
    for round_ in (2,5,9,13):
        for fuel in (0,1,2,3,4,5,9,10,11,17,599,600):
            cases.append((2,round_,fuel,10,3,7,1,9,0,0,20000,1))
        for score in (19990,79990,99999990):
            cases.append((2,round_,17,10,3,0,1,9,0,score,20000,3))
        cases.append((2,round_,600,10,0,7,1,9,0,19990,20000,1))
    return cases


def encode_case(c):
    kind,round_,fuel,count,mode,clock,enabled,rate,ticks,score,high,flags=c
    return bytes((kind,round_,fuel%10,fuel//10,count,mode,clock,enabled,rate))+struct.pack('<H',ticks)+packet(score)+packet(high)+bytes((flags,))


def compare(cases,original,actual):
    if not original or len(original)%RECORD or len(actual)!=len(original):raise ValueError('Incomplete fuel proof')
    rows=[original[i:i+RECORD] for i in range(0,len(original),RECORD)]
    previous=(-1,-1);done=set()
    for i,r in enumerate(rows):
        case,tick=struct.unpack('<HH',r[:4])
        if case>=len(cases) or (case,tick)!=(previous[0],previous[1]+1) and (case,tick)!=(previous[0]+1,0):
            raise ValueError('Fuel trace is not consecutive')
        if r[-1]:done.add(case)
        if r!=actual[i*RECORD:(i+1)*RECORD]:
            raise ValueError(f'Original fuel mismatch case {case}, tick {tick}, fixture {cases[case]}: {r.hex()} / {actual[i*RECORD:(i+1)*RECORD].hex()}')
        previous=(case,tick)
    if done!=set(range(len(cases))):raise ValueError('Missing complete fuel cases')
    return len(rows)


def original_oracle(root,out):
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Fuel oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/msx/fuel_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','600']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,FUEL_OUTPUT=str(out)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    return version


def source_seed(bundle,native=None):
    seed=bytearray((bundle/'player-seed.bin').read_bytes() if native is None else native)
    if len(seed)!=4096:raise ValueError('Expected complete native source seed')
    for at in (0x988,0x98a,0x98c,0x98e,0x990,0x99a,0x99c):
        seed[at:at+2]=(int.from_bytes(seed[at:at+2],'little')-0x6000).to_bytes(2,'little')
    for at in (0x1b3,0x1b9):seed[at:at+2]=(int.from_bytes(seed[at:at+2],'little')-0x8000).to_bytes(2,'little')
    if read_json(bundle/'build.json').get('parameter_component'):
        seed[0x2d2:0x2d4]=(int.from_bytes(seed[0x2d2:0x2d4],'little')-0x8000).to_bytes(2,'little')
    return seed


def route_capture(syms,out):
    """Read-only observation at the real keyboard route's lucky event/ticks."""
    return [f'set bonus_out [open {tcl(out/"bonus.bin")} wb];set bonus_times [open {tcl(out/"bonus-times.tsv")} w];set bonus_tick -1;set bonus_observing 0',
        'proc bonus_record {} {',
        ' incr ::bonus_tick;puts $::bonus_times "$::frames $::bonus_tick";puts -nonewline $::bonus_out [binary format ss 0 $::bonus_tick]',
        ' foreach a {0xe26a 0xe26b 0xe269 0xe020 0xe023 0xe292 0xe289 0xe28c 0xe28a} {puts -nonewline $::bonus_out [binary format c [debug read memory $a]]}',
        ' foreach {a size} {0xe144 8 0xe0a0 8 0xe060 8} {puts -nonewline $::bonus_out [debug read_block memory $a $size]}',
        ' foreach a {0xe00f 0xe1b2 0xe2d0 0xe027 0xe028 0xe9f4} {puts -nonewline $::bonus_out [binary format c [debug read memory $a]]}',
        f' set done [expr {{[debug read memory {syms["Fuel_Active"]}]==0}}]',
        ' puts -nonewline $::bonus_out [binary format c $done];if {$done} {set ::bonus_observing 0;close $::bonus_out;close $::bonus_times}','}',
        f'debug set_bp {syms["Fuel_Begin"]} {{[reg IM]==2 && ([debug read memory 0xe023]&2)!=0 && [debug read memory 0xe271]!=10}} {{',
        ' set ::bonus_observing 1',
        f' set f [open {tcl(out/"lucky-native-seed.bin")} wb];puts -nonewline $f [debug read_block memory 0xe000 4096];close $f',
        f' set f [open {tcl(out/"bonus-case.bin")} wb]',
        ' puts -nonewline $f [binary format c 1]',
        ' foreach a {0xe1b0 0xe26a 0xe26b 0xe271 0xe020 0xe269 0xe28b 0xe26e} {puts -nonewline $f [binary format c [debug read memory $a]]}',
        ' puts -nonewline $f [binary format s 0];puts -nonewline $f [debug read_block memory 0xe0a0 8];puts -nonewline $f [debug read_block memory 0xe060 8]',
        ' puts -nonewline $f [binary format c [debug read memory 0xe023]];close $f','}',
        f'debug set_bp {syms["Score_AfterFuelBegin"]} {{$::bonus_observing && $::bonus_tick==-1}} {{bonus_record}}',
        f'debug set_bp {syms["Player_AfterFuel"]} {{$::bonus_observing && $::bonus_tick>=0}} {{bonus_record}}']


def verify_route(root,bundle,out):
    oracle=out/'fuel-original';oracle.mkdir()
    raw=(out/'bonus-case.bin').read_bytes()
    if len(raw)!=28:raise ValueError('Expected one real lucky conversion')
    live=out/'lucky-native-seed.bin'
    (oracle/'cases.bin').write_bytes(raw)
    (oracle/'source-seed.bin').write_bytes(source_seed(bundle,live.read_bytes() if live.exists() else None))
    original_oracle(root,oracle)
    return compare([None],(oracle/'original.bin').read_bytes(),(out/'bonus.bin').read_bytes())


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    info=read_json(bundle/'build.json');completion=getattr(args,'command','')=='verify-completion'
    if completion:
        if not info.get('completion_component'):raise ValueError('Completion proof requires a linked completion component')
    elif info.get('incremental_stage')!=6:raise ValueError('Fuel proof requires stage 06')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    cases=completion_cases() if completion else cases_for();(out/'cases.bin').write_bytes(b''.join(map(encode_case,cases)))
    (out/'source-seed.bin').write_bytes(source_seed(bundle))
    source={str(p):digest(p) for p in (root/'references/roms').rglob('*') if p.is_file()}
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    version=original_oracle(root,out)
    syms=symbols(bundle/'raster-scroll.sym')
    begin=syms['Completion_Begin'] if completion else syms['Fuel_Begin']
    tick=syms['Completion_Tick'] if completion else syms['Fuel_Tick']
    finished=f'[debug read memory {syms["Completion_BonusState"]}]==2' if completion else f'[debug read memory {syms["Fuel_Active"]}]==0'
    code=[0xf3,0x3e,syms['PLAYER_BANK'],0x32,0,0x70,0xcd,0,0,0x76]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        f'set f [open {tcl(bundle/"player-seed.bin")} rb];set seed [read $f];close $f',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set costs [open [file join $out cycles.tsv] w];set index -1;set tick 0;set started 0',
        'proc call_component {address} {debug write memory 0xc607 [expr {$address&255}];debug write memory 0xc608 [expr {$address>>8}];reg SP 0xc7f0;reg PC 0xc600;set ::begin [machine_info time]}',
        'proc next_case {} {',
        ' incr ::index;set ::tick 0',
        ' if {$::index==[string length $::cases]/28} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {error "Fuel component changed VRAM"};close $::result;close $::costs;exit 0;return}',
        ' set p [expr {$::index*28}];set c [string range $::cases $p [expr {$p+27}]];binary scan $c cu* v',
        ' lassign $v ::kind round frac whole count mode clock enabled rate lo hi',
        ' set ::limit [expr {$lo+256*$hi}]',
        ' debug write_block memory 0xe000 $::seed',
        f' debug write_block memory {syms["Fuel_Active"]} [binary format c* {{0 0 0 0 0 0 0 0}}]',
        *([f' debug write_block memory {syms["Completion_BonusState"]} [binary format c* {{0 0 0}}]'] if completion else []),
        ' foreach {a val} [list 0xe1b0 $round 0xe26a $frac 0xe26b $whole 0xe271 $count 0xe020 $mode 0xe269 $clock 0xe28b $enabled 0xe26e $rate 0xe023 [lindex $v 27]] {debug write memory $a $val}',
        ' debug write_block memory 0xe0a0 [string range $c 11 18];debug write_block memory 0xe060 [string range $c 19 26]',
        ' set ::saved_player [debug read_block memory 0xe068 24]',
        f' call_component [expr {{$::kind?{begin}:{tick}}}]','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{',
        'set ::started 1;set ::saved_vram [debug read_block VRAM 0 131072]',
        *[f'debug write memory {0xc600+i} {v}' for i,v in enumerate(code)],'next_case','}',
        'debug set_bp 0xc609 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read_block memory 0xe068 24] ne $::saved_player} {error "Fuel changed movement/stack"}',
        f' set done [expr {{$::kind?({finished}):$::tick==$::limit-1}}]',
        ' puts -nonewline $::result [binary format ss $::index $::tick]',
        ' foreach a {0xe26a 0xe26b 0xe269 0xe020 0xe023 0xe292 0xe289 0xe28c 0xe28a} {puts -nonewline $::result [binary format c [debug read memory $a]]}',
        ' foreach {a size} {0xe144 8 0xe0a0 8 0xe060 8} {puts -nonewline $::result [debug read_block memory $a $size]}',
        ' foreach a {0xe00f 0xe1b2 0xe2d0 0xe027 0xe028 0xe9f4} {puts -nonewline $::result [binary format c [debug read memory $a]]}',
        ' puts -nonewline $::result [binary format c $done]',
        ' puts $::costs "$::index $::tick [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        f' if {{$done}} {{next_case}} else {{incr ::tick;if {{$::tick>=10000}} {{error "Fuel timeout"}};call_component {tick}}}','}',
        'after time 300 {puts stderr "Fuel microprobe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    count=compare(cases,(out/'original.bin').read_bytes(),(out/'msx.bin').read_bytes())
    costs=[int(r.split()[2]) for r in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=count:raise ValueError('Incomplete fuel costs')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()} or source!={str(p):digest(p) for p in (root/'references/roms').rglob('*') if p.is_file()}:raise ValueError('Source/BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(cases=len(cases),ticks=count,rom_sha256=digest(args.rom),mame_version=version,
        median_cycles=statistics.median(costs),p95_cycles=sorted(costs)[int(len(costs)*.95)],max_cycles=max(costs),
        vram_unchanged=True,movement_unchanged=True,
        scope=('Externally clocked original remaining-fuel completion conversion, all four round branches; exact gauge, score, high score, life bits and per-tick state; no foreground/sound wait claim' if completion else
            'Externally clocked original consumption, empty deceleration and full lucky conversion; exact gauge, score, high score, life bits and per-tick state; no full arcade IRQ timing claim')))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} cases / {count} exact original fuel ticks: {out}/report.json')
    return out
