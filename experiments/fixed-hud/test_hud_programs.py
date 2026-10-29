"""Native exact HUD transitions, every physical set, VRAM guards and IRQs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import unittest

from hud_programs import compile_packet, writes, transition_packet

ROOT = Path(__file__).resolve().parents[2]


class ProgramTests(unittest.TestCase):
    def test_inactive_previous_slots_are_unknown_even_when_source_bytes_match(self):
        arrays=(bytes([7])*24,bytes([0xaa])*24)
        packet=transition_packet(arrays,arrays,(0x300,0x4300),{0},{1})
        self.assertEqual(list(writes(packet)),[(0x308,bytes([7])*8),(0x4308,bytes([0xaa])*8)])
        self.assertEqual(list(writes(transition_packet(arrays,arrays,(0x300,0x4300),{1},{1}))),[])

    def test_sources_are_in_same_page_and_relocations_are_explicit(self):
        packet = bytes((0,3,3,1,2,3,0,67,32))+bytes(range(32))+bytes(3)
        code, relocs = compile_packet(packet,0x9000)
        self.assertEqual([name for _,name in relocs],['GamePacketFast_Transfer','hud_upload.done'])
        self.assertEqual(list(writes(packet)),[(0x300,bytes((1,2,3))),(0x4300,bytes(range(32)))])
        self.assertTrue(code.endswith(bytes(range(32))))
        self.assertEqual(code.count(bytes((0xed,0xa3))),3)
        for offset,_ in relocs:
            self.assertEqual(code[offset:offset+2],bytes(2))


def verify(bundle, out):
    sys.path.insert(0,str(ROOT))
    from scripts.msx.emulator import reference_machine,tcl
    bundle,out=Path(bundle).resolve(),Path(out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    rom=(bundle/'fixed-hud.rom').read_bytes()
    (out/'measured.rom').write_bytes(rom)
    banks=(bundle/'banks.bin').read_bytes()
    syms={n:int(v,16) for n,v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)',(bundle/'lab.sym').read_text())}
    table=bytearray()
    for phase in range(64):
        page=banks[(3+phase)*16384:(4+phase)*16384]
        table.extend(bytes((page[0x900],))+page[0x100:0x300]+page[0x500:0x700]+page[:256])
    (out/'phases.bin').write_bytes(table)
    layout=bundle/'hud-layout.json'
    active=json.loads(layout.read_text())['active_slots'] if layout.exists() else [list(range(table[n*1281])) for n in range(64)]
    pattern_back=syms.get("pattern_back",syms["back"])
    phase_base=syms.get("pattern_phases",syms["loaded_phase"])
    sets=4 if "pattern_back" in syms else 2
    # All directed transitions and cold starts, every physical R14 set.
    cases=[(back,old,new) for back in range(sets) for old in list(range(64))+[255] for new in range(64)]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
           f'filepool add -path {tcl(ROOT/"references/msxbios")} -types system_rom -position 1',
           reference_machine(ROOT,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
           'set limitsprites true','set z80_freq 3579545','set z80_freq_locked false',
           f'cart {tcl(out/"measured.rom")} -romtype ASCII16','reset',f'set out {tcl(out)}',
           'set f [open [file join $out phases.bin] rb];set phases [read $f];close $f',
           'set poison [binary format c* [lrepeat 131072 238]]',
           'set cases {'+' '.join('{'+f'{b} {a} {c}'+'}' for b,a,c in cases)+'}',
           'set started 0;set index 0;set fast 0;set irqs 0',
           'set active {'+' '.join('{'+ ' '.join(map(str,row))+'}' for row in active)+'}',
           'proc fail {message} {puts stderr $message;exit 3}',
           'set timing [open [file join $out cycles.txt] w]',
           'set VDP.too_fast_vram_access_callback {if {$::started} {incr ::fast}}',
           'proc place {memory phase back} {',
           ' set at [expr {$phase*1281}];binary scan [string index $::phases $at] cu count',
           ' set length [expr {$count*8}]',
           ' foreach {source target} {1 768 513 17152} {',
           '  set dest [expr {$back*32768+$target}]',
           '  set data [string range $::phases [expr {$at+$source}] [expr {$at+$source+$length-1}]]',
           '  for {set slot 0} {$slot<$count} {incr slot} {if {$slot ni [lindex $::active $phase]} {set data [string replace $data [expr {$slot*8}] [expr {$slot*8+7}] [string repeat "\xee" 8]]}}',
           '  set memory [string replace $memory $dest [expr {$dest+$length-1}] $data]',
           ' };return $memory','}',
           'proc issue {} {',
           f' if {{$::index=={len(cases)}}} {{close $::timing;set f [open [file join $::out checks.json] w];puts $f [format {{{{"strict_callbacks":%d,"irqs":%d}}}} $::fast $::irqs];close $f;exit 0;return}}',
           ' lassign [lindex $::cases $::index] back previous current',
           ' set initial $::poison;if {$previous!=255} {set initial [place $initial $previous $back]}',
           ' set ::initial $initial',
           ' debug write_block VRAM 0 $initial',
           f' debug write memory {pattern_back} $back;debug write memory {syms["phase"]} $current',
           f' binary scan [string index $::phases [expr {{$current*1281}}]] cu count;debug write memory {syms["count"]} $count',
           f' debug write memory [expr {{{phase_base}+$back}}] $previous',
           ' debug write memory 0x7000 [expr {$current+4}]',
           f' set p 0xd110;foreach v [list 251 205 {syms["hud_upload"]&255} {syms["hud_upload"]>>8} 0 243 195 64 209] {{debug write memory $p $v;incr p}}',
           ' reg SP 0xf380;reg PC 0xd110;set ::begin [machine_info time]',
           '}',
           f'debug set_bp {syms["Game_Prepare"]} {{!$::started}} {{set ::started 1;issue}}',
           f'debug set_bp {syms["clock_irq"]} {{$::started}} {{incr ::irqs}}',
           'debug set_bp 0xd114 {$::started} {if {!([reg IFF]&1)} {error "HUD changed interrupt ownership"}}',
           'debug set_bp 0xd140 {$::started} {',
           ' lassign [lindex $::cases $::index] back previous current',
           ' set actual [debug read_block VRAM 0 131072];set expected $::initial',
           ' set phase_base [expr {$current*1281}];binary scan [string index $::phases $phase_base] cu count;set length [expr {$count*8}]',
           ' foreach {source target} {1 768 513 17152} {',
           '  set at [expr {$back*32768+$target}];set data [string range $::phases [expr {$phase_base+$source}] [expr {$phase_base+$source+$length-1}]]',
           '  for {set slot 0} {$slot<$count} {incr slot} {if {$slot ni [lindex $::active $current]} {',
           '   set offset [expr {$slot*8}];set physical [expr {$at+$offset}]',
           '   binary scan [string range $actual $physical [expr {$physical+7}]] cu* values',
           '   binary scan [string range $::initial $physical [expr {$physical+7}]] cu* old',
           '   binary scan [string range $data $offset [expr {$offset+7}]] cu* new',
           '   foreach a $values b $old c $new {if {$a!=$b && $a!=$c} {fail "Inactive HUD byte contains neither prior nor current source case=$::index"}}',
           '   set data [string replace $data $offset [expr {$offset+7}] [string range $actual $physical [expr {$physical+7}]]]',
           '  }}',
           '  set expected [string replace $expected $at [expr {$at+$length-1}] $data]',
           ' }',
           ' if {$actual ne $expected} {fail "HUD active bytes or full VRAM guard mismatch case=$::index"}',
           ' set at [expr {$current*1281+1025}]',
           ' if {[debug read_block memory 0x8000 256] ne [string range $::phases $at [expr {$at+255}]]} {error "HUD failed to restore current phase mapping"}',
           ' puts $::timing [expr {round(([machine_info time]-$::begin)*3579545)}]',
           ' incr ::index;issue','}',
           'after time 300 {puts stderr "HUD program probe timeout case=$::index started=$::started PC=[reg PC] SP=[reg SP]";exit 2}']
    (out/'session.tcl').write_text(('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n').replace('{error "','{fail "'))
    with (out/'emulator.log').open('w') as log:
        subprocess.run(['openmsx','-script',str(out/'session.tcl')],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180,
                       env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    checks=json.loads((out/'checks.json').read_text())
    assert checks['strict_callbacks']==0 and checks['irqs']>0,checks
    cycles=[int(v) for v in (out/'cycles.txt').read_text().split()]
    assert len(cycles)==len(cases)
    assert min(cycles)>0 and max(cycles)<100000, 'Invalid isolated wrapper timing'
    report=dict(complete=True,cases=len(cases),rom_sha256=hashlib.sha256(rom).hexdigest(),checks=checks,
                cpu_hz=3579545,machine='Panasonic_FS-A1WSX_NR128',screen4_display_on=True,
                mean_cycles=statistics.mean(cycles),max_cycles=max(cycles),
                scope='All64x64 known transitions and64 cold starts, all physical pattern sets. Previous inactive slots seeded unknown. Exact current active glyph bytes and full128KiB VRAM guards; inactive HUD bytes may retain old or receive current source during gap merging. Current phase mapping/IFF preserved. IRQs enabled/exercised across probe, not inside every call. Wrapper timing includes IRQs; no gameplay FPS claim.')
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    if '--bundle' in sys.argv:
        p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--out',required=True)
        a=p.parse_args();verify(a.bundle,a.out)
    else:unittest.main()
