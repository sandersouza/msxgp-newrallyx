"""Synthetic source-pixel, clipping, sentinel and assembled Z80 contracts.

python3 src/screen4/test_game_sprites.py
python3 src/screen4/test_game_sprites.py --emulator --bios PATH
"""
import argparse
import json
import statistics
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import unittest

from game_sprites import masked_planes, native_templates, prepare_reference

ROOT = Path(__file__).resolve().parents[2]


def synthetic_templates():
    rng = random.Random(20261027)
    return bytes(rng.randrange(256) for _ in range(768))


def actors_at(x, y, animation=0, kind=0):
    return [(x, y, animation, kind)] + [(0, 0, 0, 255)] * 7


class ExactSprites(unittest.TestCase):
    def test_native_template_layout(self):
        bank = bytes(i // 64 for i in range(1536))
        self.assertEqual(native_templates(bank), b''.join(bytes([i*2])*64 for i in range(12)))

    def test_clipping_keeps_every_visible_source_pixel(self):
        source = synthetic_templates()[:64]
        for x in (-7, 0, 7, 8, 100, 184, 185, 199):
            for y in (-15, -1, 0, 100, 196, 197, 211):
                masked = masked_planes(source, x, y)
                for plane in (0, 32):
                    for row in range(16):
                        for col in range(16):
                            at = plane + col // 8 * 16 + row
                            bit = 128 >> col % 8
                            visible = 8 <= x+col < 200 and 0 <= y+row < 212
                            self.assertEqual(bool(masked[at] & bit), visible and bool(source[at] & bit))

    def test_all_scroll_phases_preserve_full_sprite_including_bottom_row(self):
        templates = bytes([255]) * 768
        for cy in range(256):
            result = prepare_reference(templates, actors_at(100, 100), cy)
            pixels = set()
            for slot in range(18):
                sy, sx, pattern, _ = result['sat'][slot*4:slot*4+4]
                if not result['colors'][slot*16] & 15:
                    continue
                self.assertNotEqual(sy, 216)
                group = pattern // 4
                for row in range(16):
                    for col in range(16):
                        at = group*32+col//8*16+row
                        if result['patterns'][at] & (128 >> col%8):
                            pixels.add((sx+col, ((sy+1-cy)&255)+row))
            self.assertEqual(pixels, {(x,y) for x in range(100,116) for y in range(100,116)})

    def test_excess_sentinel_actors_are_culled_as_whole_cars(self):
        result = prepare_reference(bytes([255])*768, [(100,100,0,1)]*8, 117)
        self.assertEqual(result['culled'], list(range(1,8)))
        self.assertEqual(sum(bool(c & 15) for c in result['colors'][::16]),4)


def verify_emulator(bios, source_dir=None, output=None, optimized=False):
    sys.path.insert(0, str(ROOT))
    from scripts.msx.emulator import reference_machine, tcl
    out = Path(output or ROOT / 'outputs/fixed-hud/sprite-synthetic').resolve()
    source_dir = Path(source_dir or Path(__file__).parent).resolve()
    out.mkdir(parents=True, exist_ok=True)
    templates = synthetic_templates()
    (out/'game-sprite-templates.bin').write_bytes(templates)
    shutil.copyfile(source_dir/'game-sprites.inc', out/'game-sprites.inc')
    extra = ''
    if optimized:
        for name in ('game-sprite-mask-fast.inc','game-sprite-clip-fast.inc','game-packet-fast.inc'):
            if (source_dir/name).exists():
                shutil.copyfile(source_dir/name, out/name)
                extra += f'    INCLUDE "{name}"\n'
    defines = '    DEFINE GAMEPLAY_CONFIGURED 1\nGAME_RENDER_OPT EQU 1\n'
    if optimized and (source_dir/'game-sprite-clip-fast.inc').exists():
        defines += '    DEFINE GAME_SPRITE_CLIP_FAST 1\n'
    (out/'probe.asm').write_text((defines if optimized else '')+'''    OUTPUT "probe.rom"
cy EQU $c002
    ORG $4000
    db "AB"
    dw boot,0,0,0,0,0,0
boot:
    di
    ld sp,$f380
    call GameSprites_Init
main:
    jp main
    INCLUDE "game-sprites.inc"
'''+extra+'''
    ASSERT $ < $8000
    defs $8000-$,$ff
''')
    subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'), '--nologo', '--sym=probe.sym', 'probe.asm'],cwd=out,check=True)
    syms = {m[1]:int(m[2],16) for m in re.finditer(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)',(out/'probe.sym').read_text())}
    cases = []
    for cy in range(256):
        cases.append((cy, cy&1, actors_at(100,100,cy%12,cy&1)))
    for x in (-300,-16,-8,-7,-1,0,7,8,184,185,199,200,255,300):
        for y in (-300,-16,-15,-1,0,196,197,211,212,255,300):
            cases.append((117, len(cases)&1, actors_at(x,y, len(cases)%12, len(cases)&1)))
    for cy in range(256):
        cases.append((cy, cy&1, [(8+i*21,100,i%12,i&1) for i in range(8)]))
    rng = random.Random(411)
    for _ in range(300):
        cases.append((rng.randrange(256),rng.randrange(2),[(rng.randrange(-20,220),rng.randrange(-20,230),rng.randrange(14),rng.choice((0,1,255))) for _ in range(8)]))
    workload_ranges = {}
    def add_workload(label, sequence):
        start = len(cases)
        cases.extend(sequence)
        # Exclude the two explicit cache warm-up frames in each set.
        workload_ranges[label] = (start+2,len(cases))
    interior = [(20+i*20,100,i%12,i&1) for i in range(8)]
    add_workload('eight-interior-unchanged-warm',[(0,i&1,interior) for i in range(32)])
    add_workload('eight-interior-animation-change',[(0,i&1,[(x,y,(a+i)%12,k) for x,y,a,k in interior]) for i in range(32)])
    add_workload('eight-interior-scroll-only',[(i,i&1,interior) for i in range(101)])
    add_workload('eight-right-clipped-animation-change',[(0,i&1,[(199,100,(a+i)%12,k) for x,y,a,k in interior]) for i in range(32)])
    add_workload('four-vertical-clipped-animation-change',[(0,i&1,[(x,211,(a+i)%12,k) for x,y,a,k in interior[:4]]+[(0,0,0,255)]*4) for i in range(32)])
    add_workload('sentinel-animation-change',[(117,i&1,actors_at(100,100,i%12,i&1)) for i in range(32)])
    # Every clipped worldY with horizontal masks, both ordinary and sentinel216
    # positions. Include both sprite sets, ink kinds and native animations.
    for y in list(range(-15,0))+list(range(197,212)):
        for x in list(range(-7,9))+list(range(184,200)):
            for sentinel in (False,True):
                cy = (217-y)&255 if sentinel else (216-y)&255
                cases.append((cy,len(cases)&1,actors_at(x,y,len(cases)%12,len(cases)&1)))
    packed = bytearray()
    expected = bytearray()
    for cy, target, actors in cases:
        packed.extend((cy, 1-target))
        for x,y,animation,kind in actors:
            packed.extend(x.to_bytes(2,'little',signed=True)+y.to_bytes(2,'little',signed=True)+bytes((animation,kind)))
        result = prepare_reference(templates,actors,cy,target)
        expected.extend(result['sat']+result['colors']+result['patterns']+bytes((sum(1<<i for i in result['culled']),)))
    (out/'cases.bin').write_bytes(packed)
    lines = ['set save_settings_on_exit false','set renderer none','set sound_driver null',
             f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
             reference_machine(ROOT,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
             'set z80_freq 3579545','set z80_freq_locked false','set limitsprites true',f'cart {tcl(out/"probe.rom")} -romtype Normal','reset',
             f'set out {tcl(out)}',
             'set f [open [file join $out cases.bin] rb];set data [read $f];close $f',
             'set result [open [file join $out actual.bin] wb];set timing [open [file join $out cycles.txt] w];set preparation [open [file join $out prepare-cycles.txt] w];set publication [open [file join $out commit-cycles.txt] w];set index 0;set started 0',
             'proc issue {} {',
             f' if {{$::index=={len(cases)}}} {{close $::result;close $::timing;close $::preparation;close $::publication;exit 0;return}}',
             ' set at [expr {$::index*50}];binary scan [string range $::data $at [expr {$at+1}]] cu* c',
             ' debug write memory 0xc002 [lindex $c 0]',
             f' debug write memory {syms["GS_Set"]} [lindex $c 1]',
             ' debug write_block memory 0xc800 [string range $::data [expr {$at+2}] [expr {$at+49}]]',
             f' set p 0xd110;foreach v [list 243 205 {syms["GameSprites_Prepare"]&255} {syms["GameSprites_Prepare"]>>8} 205 {syms["GameSprites_Commit"]&255} {syms["GameSprites_Commit"]>>8} 195 64 209] {{debug write memory $p $v;incr p}}',
             ' set ::started_at [machine_info time]',
             ' reg SP 0xf380;reg PC 0xd110','}',
             f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
             f'debug set_bp {syms["GameSprites_Commit"]} {{$::started}} {{set ::prepared_at [machine_info time]}}',
             'debug set_bp 0xd140 {$::started} {',
             ' puts $::timing [expr {round(([machine_info time]-$::started_at)*3579545)}]',
             ' puts $::preparation [expr {round(($::prepared_at-$::started_at)*3579545)}]',
             ' puts $::publication [expr {round(([machine_info time]-$::prepared_at)*3579545)}]',
             ' set target [expr {[debug read memory 0xcd40]*576+0x2800}]',
             ' puts -nonewline $::result [debug read_block memory 0xc980 72]',
             ' puts -nonewline $::result [debug read_block VRAM 0x18e0 288]',
             ' puts -nonewline $::result [debug read_block VRAM $target 576]',
             f' puts -nonewline $::result [debug read_block memory {syms["GS_Culled"]} 1]',
             ' set target [expr {[debug read memory 0xcd40]*576+0x2800}]',
             ' if {[debug read_block VRAM 0x1a38 72] ne [debug read_block memory 0xc980 72]} {error "SAT upload differs"}',
             ' incr ::index;issue','}',
             'after time 300 {puts stderr "Sprite probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
                       env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual = (out/'actual.bin').read_bytes()
    if len(actual) != len(expected):
        raise AssertionError('Incomplete emulator output')
    for case in range(len(cases)):
        a = actual[case*937:(case+1)*937]
        e = expected[case*937:(case+1)*937]
        relevant = [i*4 for i in range(18)] + [936]
        for group in range(18):
            if e[72+group*16] & 15:
                relevant.extend(range(group*4,(group+1)*4))
                relevant.extend(range(72+group*16,72+(group+1)*16))
                relevant.extend(range(360+group*32,360+(group+1)*32))
        for offset in relevant:
            if a[offset] != e[offset]:
                raise AssertionError(f'Z80 differs case={case} input={cases[case]} offset={offset}: actual={a[offset:offset+8].hex()} expected={e[offset:offset+8].hex()}')
    timings = [int(v) for v in (out/'cycles.txt').read_text().split()]
    preparation = [int(v) for v in (out/'prepare-cycles.txt').read_text().split()]
    publication = [int(v) for v in (out/'commit-cycles.txt').read_text().split()]
    workloads = {}
    selections = [('one-car-all-scroll',timings[:256]),('eight-cars-all-scroll',timings[410:666]),('all-cases',timings)]
    selections += [(label,timings[start:end]) for label,(start,end) in workload_ranges.items()]
    for label, values in selections:
        ordered = sorted(values)
        workloads[label] = dict(calls=len(values),mean=statistics.mean(values),minimum=min(values),
            p99=ordered[int((len(values)-1)*.99)],maximum=max(values))
    for label,(start,end) in workload_ranges.items():
        workloads[label]['prepare_mean'] = statistics.mean(preparation[start:end])
        workloads[label]['prepare_maximum'] = max(preparation[start:end])
        workloads[label]['commit_mean'] = statistics.mean(publication[start:end])
        workloads[label]['commit_maximum'] = max(publication[start:end])
    ledger = dict(cpu_hz=3579545,machine='Panasonic_FS-A1WSX_NR128',
        routines='GameSprites_Prepare + GameSprites_Commit',
        scope='inclusive wrapper DI/CALL/CALL/JP; dirty active-pattern uploads and dirty-color/SAT publication; elapsed emulated time times reference CPU clock includes wait states; no synchronization waits or HUD/native game costs',
        synthetic_asset_sha256=__import__('hashlib').sha256(templates).hexdigest(),
        rom_sha256=__import__('hashlib').sha256((out/'probe.rom').read_bytes()).hexdigest(),
        cases=len(cases), optimized=optimized,
        timings=workloads)
    (out/'cycle-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(f'Assembled Z80 and VRAM byte contracts passed {len(cases)} synthetic cases')
    print(json.dumps(workloads,indent=2))


if __name__ == '__main__':
    if '--emulator' in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--emulator',action='store_true')
        parser.add_argument('--bios',required=True)
        parser.add_argument('--source-dir',type=Path)
        parser.add_argument('--out',type=Path)
        parser.add_argument('--optimized',action='store_true')
        args=parser.parse_args()
        verify_emulator(args.bios,args.source_dir,args.out,args.optimized)
    else:
        unittest.main()
