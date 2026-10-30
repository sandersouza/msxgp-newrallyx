"""Synthetic source-pixel/counter and assembled Z80 HUD contracts."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import argparse
import json
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import unittest

from game_hud import display_keys,prepare_reference,read_score,sprite_pattern
ROOT = Path(__file__).resolve().parents[3]


def native_score(value):
    ordered = [int(d) for d in f'{value:08d}']
    return bytes(ordered[4:]+ordered[:4])


def synthetic_assets():
    rng = random.Random(127)
    digits = bytes(rng.randrange(256) for _ in range(80))+bytes(8)
    life = bytes(3<=x<=12 and 1<=y<=10 for y in range(16) for x in range(16))
    return digits,sprite_pattern(life)+sprite_pattern(bytes(16)+life[:240])


class Counters(unittest.TestCase):
    def test_native_digit_order_and_saturation(self):
        self.assertEqual(read_score(native_score(123456)),[0x12,0x34,0x56])
        self.assertEqual(read_score(native_score(1000000)),[0x99]*3)
        self.assertEqual(read_score(native_score(999998)),[0x99,0x99,0x98])

    def test_round_lives_fuel_boundaries(self):
        keys=display_keys(bytes(8),bytes(8),2,5,60)
        self.assertEqual(keys[6:], [0xa1,1,1,1,1,16,16,16])
        self.assertEqual(display_keys(bytes(8),bytes(8),255,0,0)[6:],[0x99,0,0,0,0,0,0,0])

    def test_hud_never_terminates_following_world_sprites(self):
        digits,life=synthetic_assets()
        keys=display_keys(native_score(20000),native_score(17),2,5,60)
        for cy in range(256):
            sat,patterns=prepare_reference(digits,life,keys,cy)
            self.assertTrue(all(y!=216 for y in sat[::4]))
            self.assertEqual(len(patterns),448)


def verify_emulator(bios, *, source=None, output=None):
    sys.path.insert(0,str(ROOT))
    from src.toolchain.msx.emulator import reference_machine,tcl
    out=Path(output) if output else ROOT/'outputs/fixed-hud/hud-synthetic'
    source=Path(source) if source else source_path('game-hud.inc')
    out.mkdir(parents=True,exist_ok=True)
    digits,life=synthetic_assets()
    colors=bytes([6]*48+[12]*48+[15]*16+[9]*112)
    for name,payload in (('digits',digits),('life',life),('colors',colors)):
        (out/f'game-hud-{name}.bin').write_bytes(payload)
    shutil.copyfile(source,out/'game-hud.inc')
    mapping='''    in a,($a8)
    rlca
    rlca
    and 3
    ld c,a
    ld b,0
    ld hl,$fcc1
    add hl,bc
    bit 7,(hl)
    jr z,.primary
    ld a,($ffff)
    cpl
    ld b,a
    rlca
    rlca
    and 3
    ld d,a
    ld a,b
    and $fc
    or d
    ld ($ffff),a
.primary:
    in a,($a8)
    and $fc
    or c
    out ($a8),a
'''
    (out/'probe.asm').write_text('    OUTPUT "probe.rom"\ncy EQU $c002\n ORG $4000\n db "AB"\n dw boot,0,0,0,0,0,0\nboot:\n di\n ld sp,$f380\n'+mapping+' call GameHUD_Init\nmain:\n jp main\n INCLUDE "game-hud.inc"\n ASSERT $<$8000\n defs $8000-$,$ff\n')
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo','--sym=probe.sym','probe.asm'],cwd=out,check=True)
    syms={m[1]:int(m[2],16) for m in re.finditer(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)',(out/'probe.sym').read_text())}
    cases=[(cy,native_score(20000),native_score(17),2,5,60) for cy in range(256)]
    for value in (0,1,999998,999999,1000000,99999999):
        for lives in (0,1,2,5,255):
            for fuel in (0,1,5,6,30,59,60,255):
                cases.append((value&255,native_score(value),native_score(value),255,lives,fuel))
    rng=random.Random(711)
    for _ in range(300):
        cases.append((rng.randrange(256),bytes(rng.randrange(16) for _ in range(8)),bytes(rng.randrange(16) for _ in range(8)),rng.randrange(256),rng.randrange(8),rng.randrange(64)))
    workloads={}
    def add(label,sequence):
        start=len(cases)
        cases.extend(sequence)
        workloads[label]=(start+1,len(cases))
    add('unchanged-all-fields',[(0,native_score(20000),native_score(17),2,5,60)]*32)
    add('one-score-pair-change',[(0,native_score(20000),native_score(i),2,5,60) for i in range(32)])
    add('normal-scroll-only',[(cy,native_score(20000),native_score(17),2,5,60) for cy in range(64,96)])
    add('scroll-all-phases',[(cy,native_score(20000),native_score(17),2,5,60) for cy in range(256)])
    add('fuel-only-all-native-values',[(64,native_score(20000),native_score(17),2,5,fuel) for fuel in list(range(256))+list(reversed(range(256)))])
    add('fuel-scroll-and-sentinels',[(cy,native_score(20000),native_score(17),2,5,(cy*7)%61) for cy in list(range(256))+list(reversed(range(256)))])
    add('score-carry-and-hi-threshold',[(64,native_score(max(20000,value)),native_score(value),2,5,60) for value in (0,9,10,99,100,999,1000,9999,10000,19999,20000,20001,99999,100000,999998,999999,1000000,99999999,0)])
    add('round-saturation-and-lifecycle',[(64,native_score(20000),native_score(17),rnd,5,60) for rnd in list(range(256))+[255,254,200,101,100,99,2,1,0,2]])
    add('lives-saturation-and-lifecycle',[(64,native_score(20000),native_score(17),2,lives,60) for lives in list(range(256))+[255,5,4,3,2,1,0,5]])
    add('sentinel-lifecycle',[(cy,native_score(hi),native_score(score),rnd,lives,fuel)
        for cy in (13,33,157,185,209) for cy in (cy-1,cy,cy+1,cy,cy-1)
        for hi,score,rnd,lives,fuel in ((20000,17,2,5,60),(20000,19999,99,1,1),(20001,20001,255,0,0),(20001,0,2,5,60))])
    # Repeated Init must invalidate every cache, including when visible values
    # equal the preceding frame. Exercise all camera phases with visible/hidden
    # fuel/lives, not only the first boot's single phase.
    resets=[]
    for cy in range(256):
        for lives_count,fuel in ((5,60),(0,0)):
            resets.append(len(cases))
            cases.append((cy,native_score(20000),native_score(17),2,lives_count,fuel))
    packed=bytearray()
    expected=bytearray()
    for cy,high,score,rnd,lives_count,fuel in cases:
        packed.extend(bytes((cy,))+high+score+bytes((rnd,lives_count,fuel)))
        keys=display_keys(high,score,rnd,lives_count,fuel)
        sat,patterns=prepare_reference(digits,life,keys,cy)
        expected.extend(sat+patterns)
    (out/'cases.bin').write_bytes(packed)
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
           f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
           reference_machine(ROOT,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set limitsprites true',
           f'cart {tcl(out/"probe.rom")} -romtype Normal','reset',f'set out {tcl(out)}',
           'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
           f'set resets {{{" ".join(map(str,resets))}}}',
           'set result [open [file join $out actual.bin] wb];set guards [open [file join $out guards.bin] wb];set pending [open [file join $out pending.bin] wb];set native [open [file join $out native.bin] wb];set times [open [file join $out cycles.txt] w];set index 0;set started 0',
           'proc issue {} {',f' if {{$::index=={len(cases)}}} {{close $::result;close $::guards;close $::pending;close $::native;close $::times;exit 0;return}}',
           ' set at [expr {$::index*20}];binary scan [string range $::data $at [expr {$at+19}]] cu* c',
           ' debug write memory 0xc002 [lindex $c 0]',
           ' debug write_block memory 0xe060 [string range $::data [expr {$at+1}] [expr {$at+8}]]',
           ' debug write_block memory 0xe0a0 [string range $::data [expr {$at+9}] [expr {$at+16}]]',
           ' debug write memory 0xe1b0 [lindex $c 17];debug write memory 0xe00f [lindex $c 18];debug write memory 0xe26b [lindex $c 19]',
           ' debug write_block memory 0x22b6 [string repeat \x7a 10];debug write_block memory 0x22ce [string repeat \x3c 50]',
           ' set code [list 243]',
           f' if {{[lsearch -exact $::resets $::index]>=0}} {{lappend code 205 {syms["GameHUD_Init"]&255} {syms["GameHUD_Init"]>>8}}}',
           f' lappend code 205 {syms["GameHUD_Prepare"]&255} {syms["GameHUD_Prepare"]>>8} 205 {syms["GameHUD_Commit"]&255} {syms["GameHUD_Commit"]>>8} 195 64 209',
           ' set p 0xd110;foreach v $code {debug write memory $p $v;incr p}',
           ' set ::begin [machine_info time];reg SP 0xf380;reg PC 0xd110','}',
           f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
           f'debug set_bp {syms["GameHUD_Commit"]} {{$::started}} {{set ::commit [machine_info time];puts -nonewline $::pending [debug read_block memory 0x2260 2];puts -nonewline $::pending [debug read_block memory 0x2000 448]}}',
           'debug set_bp 0xd140 {$::started} {',
           ' puts $::times [list [expr {round(($::commit-$::begin)*3579545)}] [expr {round(([machine_info time]-$::commit)*3579545)}]]',
           ' puts -nonewline $::result [debug read_block VRAM 0x1a00 56]',
           ' puts -nonewline $::result [debug read_block VRAM 0x2c80 448]',
           ' puts -nonewline $::guards [debug read_block memory 0x22b6 10];puts -nonewline $::guards [debug read_block memory 0x22ce 50]',
           ' puts -nonewline $::native [debug read_block memory 0xe060 8];puts -nonewline $::native [debug read_block memory 0xe0a0 8]',
           ' foreach addr {0xe1b0 0xe00f 0xe26b} {puts -nonewline $::native [binary format c [debug read memory $addr]]}',
           ' incr ::index;issue','}',
           'after time 60 {puts stderr "HUD probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
                       env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'actual.bin').read_bytes()
    if len(actual)!=len(expected):
        raise AssertionError('Incomplete HUD emulator output')
    for case in range(len(cases)):
        a=actual[case*504:(case+1)*504]
        e=expected[case*504:(case+1)*504]
        if a[:56]!=e[:56]:
            raise AssertionError(f'HUD SAT differs case{case}: {a[:56].hex()} expected {e[:56].hex()}')
        for slot in range(14):
            group=(e[slot*4+2]-144)//4
            source=a[56+group*32:56+(group+1)*32]
            target=e[56+slot*32:56+(slot+1)*32]
            if source!=target:
                raise AssertionError(f'HUD active pattern differs case{case} input={cases[case]} slot{slot}: actual={source.hex()} expected={target.hex()}')
    if (out/'guards.bin').read_bytes() != (b'\x7a'*10+b'\x3c'*50)*len(cases):
        raise AssertionError('HUD preparation overwrote adjacent reserved RAM')
    pending=(out/'pending.bin').read_bytes()
    native=(out/'native.bin').read_bytes()
    previous_patterns=bytearray(448)
    previous_patterns[7*32:9*32]=life
    for case,(_,high,score,rnd,lives_count,fuel) in enumerate(cases):
        if native[case*19:(case+1)*19] != high+score+bytes((rnd,lives_count,fuel)):
            raise AssertionError(f'Native counter storage changed case{case}')
        entry=pending[case*450:(case+1)*450]
        dirty=int.from_bytes(entry[:2],'little')
        if dirty & ~0x387f:
            raise AssertionError(f'Unexpected immutable life group dirty case{case}: {dirty:04x}')
        for group in list(range(7))+list(range(11,14)):
            if dirty & (1<<group):
                previous_patterns[group*32:(group+1)*32]=entry[2+group*32:2+(group+1)*32]
            actual_group=actual[case*504+56+group*32:case*504+56+(group+1)*32]
            if actual_group != previous_patterns[group*32:(group+1)*32]:
                raise AssertionError(f'Dirty pattern publication differs case{case} group{group}')
    times=[tuple(map(int,line.split())) for line in (out/'cycles.txt').read_text().splitlines()]
    stats={}
    for label,(start,end) in workloads.items():
        values=times[start:end]
        stats[label]=dict(calls=len(values),prepare_mean=statistics.mean(v[0] for v in values),prepare_maximum=max(v[0] for v in values),commit_mean=statistics.mean(v[1] for v in values),commit_maximum=max(v[1] for v in values),inclusive_maximum=max(sum(v) for v in values))
    ledger=dict(cpu_hz=3579545,machine='Panasonic_FS-A1WSX_NR128',cases=len(cases),scope='inclusive DI/CALL Prepare/CALL Commit/JP wrapper; emulated elapsed time times CPU clock including wait states; excludes synchronization/render/core/audio',rom_sha256=__import__('hashlib').sha256((out/'probe.rom').read_bytes()).hexdigest(),timings=stats)
    (out/'cycle-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(f'Assembled Z80 HUD contracts passed {len(cases)} cases')
    print(json.dumps(stats,indent=2))


if __name__=='__main__':
    if '--emulator' in sys.argv:
        parser=argparse.ArgumentParser()
        parser.add_argument('--emulator',action='store_true')
        parser.add_argument('--bios',required=True)
        parser.add_argument('--source',type=Path)
        parser.add_argument('--output',type=Path)
        args=parser.parse_args()
        verify_emulator(args.bios,source=args.source,output=args.output)
    else:
        unittest.main()
