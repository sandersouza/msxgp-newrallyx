"""Prove visible name publication using synthetic terrain, HUD and dirty queues.

Executes the original and candidate Z80 uploaders with display enabled at 60Hz.
Every selected 32x28 name view is independently reconstructed from the current
CPU terrain cache and HUD names. Hidden VRAM may retain a different history.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HEADER = 4218
RAM_BYTES = 2763
RECORD_BYTES = RAM_BYTES+2048


def candidate_source(original):
    start = original.index('Ring_UploadNames:\n')
    before, names = original[:start], original[start:]
    needle = '    cp 3\n    jr nc,.full\n'
    assert names.count(needle) == 2
    names = names.replace(needle, '    cp 3\n    jp nc,GameNameStream_Wide\n')
    # Publish the row actually entering the visible28-row view.
    needle = '    add a,31\n.row:\n    call Ring_UploadRow\n'
    assert names.count(needle) == 1
    names = names.replace(needle, '    add a,27\n.row:\n    call Ring_UploadRow\n')
    return before+names


def terrain(col, row, overrides):
    result = bytearray(1024)
    for y in range(row, row+32):
        for x in range(col, col+32):
            result[(y&31)*32+(x&31)] = overrides.get((x,y), ((x*37+y*19)^((x+y)>>3))&255)
    return bytes(result)


def hud(index):
    return bytes((0xc0+(r*7+c*3+index*11)%64) for r in range(32) for c in range(32))


def full_names(world, names, col, row):
    result = bytearray(world)
    for y in range(28):
        for x in (0, *range(24,32)):
            result[((row+y)&31)*32+((col+x)&31)] = names[y*32+x]
    return bytes(result)


def visible(world, names, col, row):
    return bytes(names[y*32+x] if x == 0 or x >= 24 else
                 world[((row+y)&31)*32+((col+x)&31)]
                 for y in range(28) for x in range(32))


def actual_visible(table, col, row):
    return bytes(table[((row+y)&31)*32+((col+x)&31)]
                 for y in range(28) for x in range(32))


def fixtures():
    cases = []
    def add(col, row, back, reset=False, seen=None, seed=None, marks=(), overrides=None, label='route'):
        index = len(cases)
        world = terrain(col,row,overrides or {})
        names = hud(index)
        ptrs = b''.join((0x2000+((row+y)&31)*32+(col&31)).to_bytes(2,'little')+
                        (0x2000+((row+y)&31)*32+((col+24)&31)).to_bytes(2,'little')
                        for y in range(28))
        cases.append(dict(col=col,row=row,back=back,reset=reset,seen=bytes(seen or (255,0,255,0)),
                          seed=seed or bytes([0x5a])*2048,world=world,names=names,ptrs=ptrs,
                          marks=tuple(marks),label=label))
    for phase in range(32):
        for dx in range(-4,5):
            for dy in range(-4,5):
                for back in range(2):
                    col,row = 32+phase,64+phase
                    oldcol,oldrow = col-dx,row-dy
                    old = full_names(terrain(oldcol,oldrow,{}),hud(0),oldcol,oldrow)
                    add(col,row,back,True,(oldcol,oldrow)*2,old*2,
                        label=f'unit-dx{dx}-dy{dy}')
    rng = random.Random(0x4e414d45)
    for scenario in ('horizontal-reversal','vertical-reversal','diagonal','mixed','hidden-reveal'):
        overrides = {}
        col,row = 32,64
        for frame in range(192):
            reset = frame in (0,111)
            if reset:
                col,row = 32,64
                overrides = {}
            elif scenario == 'horizontal-reversal':
                col += 1 if (frame//24)&1 == 0 else -1
            elif scenario == 'vertical-reversal':
                row += 1 if (frame//32)&1 == 0 else -1
            elif scenario == 'diagonal':
                col += 1 if (frame//24)&1 == 0 else -1
                row += 1 if (frame//32)&1 == 0 else -1
            elif scenario == 'hidden-reveal':
                row += (0,1,1,2,0,-1,-2,-1)[frame%8]
                col += (1,0,1,0,-1,0,-1,0)[frame%8]
            else:
                col = max(4,min(72,col+rng.choice((-2,-1,0,1,2))))
                row = max(4,min(143,row+rng.choice((-2,-1,0,1,2))))
            marks=[]
            if frame%7 == 3:
                for rx,ry in ((5,5),(12,29),(29,15)):
                    x,y = col+rx,row+ry
                    overrides[(x,y)] = ((frame*23+rx*11+ry)^0x7f)&255
                    marks.append((y&31)*32+(x&31))
            if frame%41 == 7:
                for i in range(28):
                    x,y = col+1+i%23,row+i%28
                    overrides[(x,y)] = (frame+i*13)&255
                    marks.append((y&31)*32+(x&31))
            add(col,row,frame&1,reset,marks=marks,overrides=overrides,label=scenario)
    return cases


def probe_source():
    lab = (HERE/'lab.asm').read_text()
    definitions = lab[lab.index('cx EQU '):lab.index('    ORG $4000')].replace('names EQU $c400','names EQU $d400')
    io = lab[lab.index('address:\n'):lab.index('palette:\n')]
    ring = (HERE/'game-ring.inc').read_text()
    ring = re.sub(r'    IFDEF GAMEPLAY_CONFIGURED\n    IF GAME_RENDER_OPT\n    jp nc,GameNameStream_Wide\n    ELSE\n    jr nc,\.full\n    ENDIF\n    ELSE\n    jr nc,\.full\n    ENDIF\n', '    jr nc,.full\n', ring)
    ring = re.sub(r'    IFDEF GAMEPLAY_CONFIGURED\n    IF GAME_RENDER_OPT\n    add a,27\n    ELSE\n    add a,31\n    ENDIF\n    ELSE\n    add a,31\n    ENDIF\n', '    add a,31\n', ring)
    start = ring.index('Ring_UploadNames:\n')
    end = ring.index('    MACRO game_ring_hud_rows',start)
    baseline = ring[start:end].replace('Ring_UploadNames:', 'Baseline_Ring_UploadNames:',1)
    return ''' OUTPUT "probe.rom"
 MACRO reg number,value
 ld a,value
 out ($99),a
 ld a,$80+number
 out ($99),a
 ENDM
'''+definitions+'''Probe_MarkCount EQU $e100
Probe_Marks EQU $e200
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 in a,($a8)
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
 ld a,4
 out ($fc),a
 reg 0,4
 reg 1,$42
 reg 8,$28
 reg 9,$80
main:
 jp main
Probe_RunMarks:
 ld bc,(Probe_MarkCount)
 ld a,b
 or c
 ret z
 ld ix,Probe_Marks
.loop:
 ld l,(ix+0)
 ld h,(ix+1)
 inc ix
 inc ix
 call GameDirty_Mark
 dec bc
 ld a,b
 or c
 jr nz,.loop
 ret
Probe_Baseline:
 di
 call Probe_RunMarks
 call GameDirty_Plan
 call Baseline_Ring_UploadNames
Probe_Baseline_AfterRing:
 call GameDirty_Upload
 jp Probe_Done
Probe_Candidate:
 di
 call Probe_RunMarks
 call GameDirty_Plan
 call Ring_UploadNames
Probe_Candidate_AfterRing:
 call GameDirty_Upload
Probe_Done:
 jp main
'''+(HERE/'game-dirty.inc').read_text()+candidate_source(ring)+baseline+f'''
 INCLUDE "{HERE/'game-name-stream.inc'}"
'''+io+'''
Probe_End:
 ASSERT $ < $8000
 defs $8000-$,$ff
'''


def stats(values):
    ordered=sorted(values)
    return dict(calls=len(values),mean=statistics.mean(values),
                p95=ordered[(len(values)*95+99)//100-1],maximum=max(values))


def verify(bios, out=None):
    sys.path.insert(0,str(ROOT))
    from scripts.msx.emulator import reference_machine,tcl
    out=Path(out or ROOT/'outputs/fixed-hud/name-stream-synthetic').resolve()
    out.mkdir(parents=True,exist_ok=True)
    cases=fixtures()
    packed,offsets=bytearray(),[]
    for case in cases:
        offsets.append(len(packed))
        packed.extend(bytes((case['col'],case['row'],case['back'],case['reset']))+len(case['marks']).to_bytes(2,'little'))
        packed.extend(case['world']+case['names']+case['ptrs']+case['seen']+case['seed'])
        assert len(packed)-offsets[-1] == HEADER
        for cell in case['marks']:
            packed.extend((0xd800+cell).to_bytes(2,'little'))
    (out/'cases.bin').write_bytes(packed)
    (out/'probe.asm').write_text(probe_source())
    assembled=subprocess.run([str(ROOT/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo','--sym=probe.sym','probe.asm'],cwd=out,capture_output=True,text=True)
    if assembled.returncode:
        raise AssertionError(assembled.stdout+assembled.stderr)
    syms={n:int(v,16) for n,v in re.findall(r'^([\w.]+): EQU 0x([0-9a-fA-F]+)',(out/'probe.sym').read_text(),re.M)}
    results={}
    for version in ('baseline','candidate'):
        target=out/version
        target.mkdir(exist_ok=True)
        lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
               f'filepool add -path {tcl(Path(bios).resolve())} -types system_rom -position 1',
               reference_machine(ROOT,'Panasonic_FS-A1WSX'),'set firmwareswitch off','set throttle off',
               'set z80_freq 3579545','set z80_freq_locked true','set limitsprites true',
               f'cart {tcl(out/"probe.rom")} -romtype Normal','reset',f'set target {tcl(target)}',
               f'set f [open {tcl(out/"cases.bin")} rb];set data [read $f];close $f',
               f'set offsets [list {" ".join(map(str,offsets))}]',
               'set actual [open [file join $target actual.bin] wb];set timing [open [file join $target cycles.txt] w]',
               'set index 0;set started 0;set strict 0',
               'set VDP.too_fast_vram_access_callback {if {$::started} {incr ::strict}}',
               'proc issue {} {',
               f' if {{$::index=={len(cases)}}} {{close $::actual;close $::timing;set f [open [file join $::target strict.txt] w];puts $f $::strict;close $f;exit 0;return}}',
               ' set at [lindex $::offsets $::index];binary scan [string range $::data $at [expr {$at+5}]] cu* fields',
               ' lassign $fields col row back reset low high;set count [expr {$low+256*$high}]',
               ' if {$reset} {',
               '  debug write_block memory 0xc000 [string repeat "\0" 256]',
               '  debug write_block memory 0x2600 [string repeat "\0" 512]',
               '  debug write_block memory 0xc018 [string range $::data [expr {$at+2166}] [expr {$at+2169}]]',
               '  debug write_block VRAM 0x2000 [string range $::data [expr {$at+2170}] [expr {$at+4217}]]',
               ' }',
               ' debug write_block memory 0xd800 [string range $::data [expr {$at+6}] [expr {$at+1029}]]',
               ' debug write_block memory 0xd400 [string range $::data [expr {$at+1030}] [expr {$at+2053}]]',
               ' debug write_block memory 0xce00 [string range $::data [expr {$at+2054}] [expr {$at+2165}]]',
               ' debug write_block memory 0xc920 [string repeat "\xa5" 84]',
               ' debug write memory 0xc009 $col;debug write memory 0xc008 $row;debug write memory 0xc006 $back',
               ' debug write memory 0xe100 $low;debug write memory 0xe101 $high',
               ' debug write_block memory 0xe200 [string range $::data [expr {$at+4218}] [expr {$at+4217+2*$count}]]',
               f' reg SP 0xf380;reg PC {syms["Probe_"+version.title()]}','}',
               f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;issue}}',
               f'debug set_bp {syms["Baseline_Ring_UploadNames" if version=="baseline" else "Ring_UploadNames"]} {{$::started}} {{set ::begin [machine_info time]}}',
               f'debug set_bp {syms["Probe_"+version.title()+"_AfterRing"]} {{$::started}} {{set ::cycles [expr {{round(([machine_info time]-$::begin)*3579545)}}]}}',
               f'debug set_bp {syms["Probe_Done"]} {{$::started}} {{',
               ' if {[reg SP]!=62336} {error "Name streamer unbalanced stack"}',
               ' foreach {at len} {0xd800 1024 0xd400 1024 0xce00 112 0xc018 4 0xc096 2 0x2600 256 0x2700 256 0xc099 1 0xc920 84} {puts -nonewline $::actual [debug read_block memory $at $len]}',
               ' puts -nonewline $::actual [debug read_block VRAM 0x2000 2048]',
               ' puts $::timing $::cycles;incr ::index;issue','}',
               'after time 600 {puts stderr "Name stream proof timeout";exit 2}']
        (target/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
        with (target/'emulator.log').open('w') as log:
            subprocess.run(['openmsx','-script',str(target/'session.tcl')],check=True,stdout=log,stderr=subprocess.STDOUT,
                           timeout=180,env=dict(os.environ,OPENMSX_HOME=str(target/'home'),OPENMSX_USER_DATA=str(target/'userdata')))
        raw=(target/'actual.bin').read_bytes()
        assert len(raw)==len(cases)*RECORD_BYTES,(version,len(raw),len(cases)*RECORD_BYTES)
        timing=[int(v) for v in (target/'cycles.txt').read_text().split()]
        mismatches=[]
        last=None
        for index,case in enumerate(cases):
            record=raw[index*RECORD_BYTES:(index+1)*RECORD_BYTES]
            assert record[:2160] == case['world']+case['names']+case['ptrs'],(version,index,'RAM/cache changed')
            table=record[RAM_BYTES:]
            before=case['seed'] if case['reset'] else last
            other=1-case['back']
            assert table[other*1024:(other+1)*1024] == before[other*1024:(other+1)*1024],(version,index,'other table changed')
            selected=table[case['back']*1024:(case['back']+1)*1024]
            expected=visible(case['world'],case['names'],case['col'],case['row'])
            if actual_visible(selected,case['col'],case['row']) != expected:
                mismatches.append(index)
                if version == 'candidate':
                    at=next(i for i,(a,b) in enumerate(zip(actual_visible(selected,case['col'],case['row']),expected)) if a!=b)
                    raise AssertionError((version,index,case['label'],'visible mismatch',divmod(at,32)))
            last=table
        results[version]=dict(strict_vram_callbacks=int((target/'strict.txt').read_text()),visible_mismatch_cases=mismatches,
                              workloads={label:stats([timing[i] for i,c in enumerate(cases) if c['label']==label])
                                         for label in sorted({c['label'] for c in cases})})
    a=(out/'baseline/actual.bin').read_bytes()
    b=(out/'candidate/actual.bin').read_bytes()
    narrow_equal=0
    for index,case in enumerate(cases):
        aa=a[index*RECORD_BYTES:(index+1)*RECORD_BYTES]
        bb=b[index*RECORD_BYTES:(index+1)*RECORD_BYTES]
        assert aa[:RAM_BYTES] == bb[:RAM_BYTES],(index,'cache/metadata/dirty queues differ')
        if case['label'].startswith('unit-'):
            dx=case['col']-case['seen'][case['back']*2]
            dy=case['row']-case['seen'][case['back']*2+1]
            if abs(dx)<=1 and dy in (-1,0):
                assert aa == bb,(index,'unchanged narrow path differs')
                narrow_equal+=1
    assert results['candidate']['strict_vram_callbacks']==0,results['candidate']['strict_vram_callbacks']
    report=dict(complete=True,cases=len(cases),independent_visible_names_per_case=896,
                unchanged_narrow_full_byte_cases=narrow_equal,
                cpu_hz=3579545,video_hz_nominal=60,machine='Panasonic_FS-A1WSX_NR128',hardware_sprite_limits=True,
                display_enabled=True,calls_per_case=1,synchronization_waits=0,
                method='Inclusive uploader entry-to-immediate-return guest elapsed time times CPU Hz, including MSX memory/IO wait states. VDP interrupts disabled in this callable-boundary probe.',
                helper_bytes=syms['GameNameStream_End']-syms['GameNameStream_Wide'],
                rom_sha256=hashlib.sha256((out/'probe.rom').read_bytes()).hexdigest(),
                helper_sha256=hashlib.sha256((HERE/'game-name-stream.inc').read_bytes()).hexdigest(),
                scope='Display-on SCREEN4 strict callback; exact current 32x28 visible terrain/HUD/left names compared to independent FULL view over unit deltas and continuous two-buffer routes, reversals, diagonal movement, dirty hidden changes, reveals and restarts. Both raw terrain cache/HUD/pointers/seen/dirty metadata exact, other buffer untouched. Hidden VRAM and private ring scratch may differ. Positive narrow row changes from 31 to 27 repair entering visible rows at identical instruction cost.',
                limitations='Synthetic CPU cache bytes and original upload helpers. Ring_Prepare, native gameplay, IRQ/synchronization, physical hardware and complete presentation cadence are not measured here; integration acceptance requires the canonical cartridge route.',
                results=results)
    (out/'cycle-ledger.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out)
    print(json.dumps({key:{label:value for label,value in result['workloads'].items() if label in ('unit-dx2-dy0','unit-dx0-dy2','unit-dx3-dy0','unit-dx0-dy3')} for key,result in results.items()},indent=2))
    print(json.dumps(dict(cases=len(cases),helper_bytes=report['helper_bytes'],baseline_visible_mismatches=len(results['baseline']['visible_mismatch_cases']),candidate_visible_mismatches=len(results['candidate']['visible_mismatch_cases']))))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bios',type=Path,default=ROOT/'references/msxbios')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    verify(args.bios,args.out)
