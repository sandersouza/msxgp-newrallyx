#!/usr/bin/env python3
"""Execute flag labels, torus boundaries and authoritative erasure on Z80."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.msx.emulator import reference_machine,tcl
from scripts.msx.hud_verify import symbols
from scripts.scenes.bundle import digest,verify_manifest,load_assets
from scripts.scenes.storage import require_ignored,json_write,seal
from scripts.msx.flag_popup import image
from scripts.msx.stage_one import acquire,WIDTH
from scripts.full_game_probe import world


def addresses(x,y):
    return [((x+col)//32%2)*32768+(y%32*8+row)*128+((x+col)%32)*4+byte
            for row in range(8) for col in range(3) for byte in range(4)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path.cwd();rom=args.rom.resolve();bundle=rom.parent;verify_manifest(bundle)
    s=symbols(bundle/'raster-scroll.sym');out=args.output.resolve()
    if not s.get('FLAG_POPUPS'):raise ValueError('Popup-enabled candidate required')
    require_ignored(root,[out/'session.tcl']);out.mkdir(parents=True)
    cases=[(ordinal,mult,x,y) for mult in (1,2) for ordinal in range(1,11)
           for x,y in [((24,14),(31,15),(32,16),(63,31))[(ordinal-1)%4]]]
    # RAM trampolines map Page0 for exact owner fixtures, then use production ABI.
    enter=[243,205,s['Full_CacheEnter']&255,s['Full_CacheEnter']>>8,195,126,209]
    draw=[243,205,s['Popup_Frame']&255,s['Popup_Frame']>>8,243,195,127,209]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null','set throttle off',
        'set cmdtiming real','set limitsprites true',
        f'filepool add -path {tcl(root/"references/msxbios")} -types system_rom -position 1',
        reference_machine(root,'Panasonic_FS-A1WSX'),'set firmwareswitch off',f'cart {tcl(rom)} -romtype ASCII16','reset',
        f'set out {tcl(out)};set nr_started 0;set nr_index 0;set nr_phase prepare',
        'set nr_cases {'+' '.join('{'+f'{o} {m} {x} {y}'+'}' for o,m,x,y in cases)+'}',
        'set nr_costs [open [file join $out costs.tsv] w]',
        'proc nr_issue {} {',
        f' if {{$::nr_index=={len(cases)}}} {{close $::nr_costs;exit 0;return}}',
        ' set ::nr_phase prepare;reg SP 0xf380;reg PC 0xd140',
        '}',
        f'debug set_bp {s["main"]} {{!$::nr_started}} {{set ::nr_started 1',
        f' foreach device [debug list] {{if {{[debug desc $device] eq "memory mapper" && [debug size $device]>=131072}} {{set ::nr_mapper $device;set ::nr_base [expr {{([debug read memory {s["Full_CacheSegment"]}]&([debug size $device]/16384-1))*16384}}];break}}}}',
        f' foreach {{at value}} [list {s["Session_State"]} 0 {s["paused"]} 0 {s["Death_State"]} 0 {s["Flag_Jobs"]} 0 {s["Full_Attract"]} 0] {{debug write memory $at $value}}',
        ' debug write_block memory '+str(s['Smoke_Display'])+' [string repeat [binary format c 0] 2048]',
        ' set f [open [file join $::out seed.state] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
        ' set at 0xd140;foreach v {'+' '.join(map(str,enter))+'} {debug write memory $at $v;incr at}',
        ' set at 0xd150;foreach v {'+' '.join(map(str,draw))+'} {debug write memory $at $v;incr at}',
        ' nr_issue}',
        'debug set_bp 0xd17e {$::nr_started} {',
        ' lassign [lindex $::nr_cases $::nr_index] ordinal mult x y',
        ' for {set col 0} {$col<3} {incr col} {set xx [expr {$x+$col}];set at [expr {0x2000+($y&31)*128+($xx&63)*2}];debug write memory $at $xx;debug write memory [expr {$at+1}] $y}',
        f' foreach {{at v}} [list {s["Popup_Active"]} 0 {s["Popup_Pending"]} 1 {s["Flag_X"]} $x {s["Flag_Y"]} [expr {{$y-1}}] 0xe250 $ordinal 0xe023 [expr {{$mult-1}}]] {{debug write memory $at $v}}',
        ' set f [open [file join $::out "$::nr_index.before"] wb];puts -nonewline $f [debug read_block VRAM 0 65536];close $f',
        ' set ::nr_phase draw;set ::nr_begin [machine_info time];reg PC 0xd150',
        '}',
        'debug set_bp 0xd17f {$::nr_started} {',
        ' puts $::nr_costs "$::nr_index $::nr_phase [expr {([machine_info time]-$::nr_begin)*1000}]"',
        ' set f [open [file join $::out "$::nr_index.$::nr_phase"] wb];puts -nonewline $f [debug read_block VRAM 0 65536];close $f',
        ' if {$::nr_phase eq "draw"} {',
        f'  if {{![debug read memory {s["Popup_Active"]}]}} {{error "Popup was not painted"}}',
        '  lassign [lindex $::nr_cases $::nr_index] ordinal mult x y',
        # A previous terrain copy can leave a smoke source in scratch. Erasure
        # must capture this cell and publish its own smoke identity instead.
        f'  debug write memory {s["Smoke_Valid"]} 1;debug write memory {s["Smoke_Left"]} $x;debug write memory {s["Smoke_Top"]} $y;debug write memory {s["Smoke_DrawCode"]} 189',
        '  debug write_block memory 0xe400 [string repeat [binary format c 0] 1024]',
        '  if {$::nr_index==19} {',
        '   set at [expr {$::nr_base+0x2000+($y&31)*128+($x&63)*2}];debug write $::nr_mapper $at [expr {$x+64}]',
        '   for {set row 0} {$row<8} {incr row} {set at [expr {($x/32%2)*32768+($y%32*8+$row)*128+($x%32)*4}];debug write_block VRAM $at [string repeat [binary format c 85] 4]}',
        '  }',
        f'  debug write memory {s["Popup_Age"]} 45',
        '  set ::nr_phase erase;set ::nr_begin [machine_info time];reg PC 0xd150',
        ' } else {incr ::nr_index;nr_issue}',
        '}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Popup VRAM timing violation";exit 2}',
        'after time 90 {puts stderr "Popup probe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,timeout=90,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    program,_=acquire(root);assets=load_assets(root/'references/assets/nrallyx');palette=(bundle/'palette.bin').read_bytes()
    state=(out/'seed.state').read_bytes();scene=world(program,state[0x2000:],state[0x534:0x53f],assets,palette)
    road=(bundle/'stage-atlas.bin').read_bytes();road_pixels=[]
    sx=s['FLAG_EMPTY_X'];sy=s['FLAG_EMPTY_Y']-16
    for y in range(8):
        for x in range(8):
            v=road[(sy+y)*128+(sx+x)//2];road_pixels.append((v&15) if x&1 else v>>4)
    for i,(ordinal,mult,x,y) in enumerate(cases):
        at=addresses(x,y);before=(out/f'{i}.before').read_bytes();drawn=(out/f'{i}.draw').read_bytes();erased=(out/f'{i}.erase').read_bytes()
        text,expected=image(ordinal,mult,road_pixels,s['WHITE'])
        if bytes(drawn[a] for a in at)!=expected:raise ValueError(f'Incorrect label {text} at torus {x},{y}')
        owned=set(at)
        if any(a!=b for pos,(a,b) in enumerate(zip(before,drawn)) if pos not in owned):raise ValueError('Popup altered unrelated terrain')
        expected=bytes(85 if i==19 and col==0 else (scene[(y*8+row)*WIDTH+(x*8+col*8+byte*2)]<<4)|scene[(y*8+row)*WIDTH+(x*8+col*8+byte*2+1)]
            for row in range(8) for col in range(3) for byte in range(4))
        if bytes(erased[a] for a in at)!=expected:raise ValueError(f'Popup erasure did not regenerate original terrain {i}')
        if any(a!=b for pos,(a,b) in enumerate(zip(drawn,erased)) if pos not in owned):raise ValueError('Popup erasure altered unrelated terrain')
    costs=[line.split() for line in (out/'costs.tsv').read_text().splitlines()]
    json_write(out/'report.json',dict(rom_sha256=digest(rom),passed=True,cases=len(cases),
        maximum_paint_ms=max(float(r[2]) for r in costs if r[1]=='draw'),maximum_erase_ms=max(float(r[2]) for r in costs if r[1]=='erase'),
        scope='Seeded actual Z80 popup ABI with real raster interrupts, all20 labels, horizontal/vertical torus boundaries, exact bitmap writes, independent original-terrain erasure, stale-smoke scratch and replaced-owner canary; natural gameplay remains separate.'))
    seal(out);print(f'Flag popup labels and erasure pass: {out}/report.json')


if __name__=='__main__':main()
