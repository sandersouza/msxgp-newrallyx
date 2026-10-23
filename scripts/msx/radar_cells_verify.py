"""Execute every compact-radar marker clip and color-priority boundary."""
import os
import statistics
import subprocess

from scripts.scenes.bundle import digest,read_json,verify_manifest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .raster_scroll import index_for


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('hud_style',{}).get('radar_cells_only'):
        raise ValueError('Twelve-cell radar cartridge required')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym');cases=[]
    base_mode=bool(getattr(args,'radar_base',False))
    deferred_shift='Radar_EnsureCellShift' in syms
    separate_player=info['hud_style'].get('radar_player_sprite',False)
    map_slot=info['hud_style'].get('radar_map_first_slot',0)
    source_flags=read_json(bundle/'radar.json')['scenes'][0]['flags']
    for cell in range(12):
        ox,oy=cell%3*16,cell//3*15+cell%3-2
        for who in range(4):
            for ry in range(-2,16):
                for rx in range(-2,17):
                    points=[(255,255)]*3
                    if who<3:points[who]=((ox+rx)&255,(oy+ry)&255)
                    else:points=[((ox+rx+i)&255,(oy+ry+i)&255) for i in (2,0,1)]
                    cases.append(bytes((cell,*sum((list(p) for p in points),[]))))
    if base_mode:
        cases=[bytes((cell,255,255,255,255,255,255))+mask.to_bytes(2,'little')
               for cell in range(12) for mask in range(1<<len(source_flags))]
    else:cases=[c+b'\xff\xff' for c in cases]
    if deferred_shift:cases=[case for case in cases for _ in range(2)]
    base=bytes(((0x81 if row%2 else 0x42) ^ (half*0x18)) if row<15 else 0
               for half in range(2) for row in range(16))
    (out/'cases.bin').write_bytes(b''.join(cases));(out/'base.bin').write_bytes(base*12)
    entry=syms['hud_render_cell' if base_mode else 'Radar_RenderCell']
    code=[243,205,entry&255,entry>>8]
    if info['hud_style'].get('radar_ready_state_address'):
        publish=syms['Radar_PublishReady'];code.extend((205,publish&255,publish>>8))
    if deferred_shift:
        shift=syms['Radar_EnsureCellShift'];code.extend((205,shift&255,shift>>8))
    code=bytes(code+[195,64,199])
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set f [open [file join $out base.bin] rb];set base [read $f];close $f',
        'set results [open [file join $out msx.bin] wb];set costs [open [file join $out cycles.tsv] w];set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==[string length $::cases]/9} {if {[debug read_block VRAM 0 65536] ne $::scene || [debug read_block memory 0xe000 4096] ne $::native} {error "Radar changed maze/native state"};close $::results;close $::costs;exit 0;return}',
        ' binary scan [string range $::cases [expr {$::index*9}] [expr {$::index*9+8}]] cu* c',
        f' debug write memory {syms["hud_cell"]} [lindex $c 0]',
        f' debug write_block memory {syms["Radar_Last"]} [binary format c* [lrange $c 1 6]]',
        *([f' debug write_block memory 0xc704 [binary format c* [expr {{$::index%2?{{0 0 0}}:{{205 {publish&255} {publish>>8}}}}}]]'] if deferred_shift else []),
        *([f' set points {{{" ".join("{"+str(x)+" "+str(y)+"}" for x,y in source_flags)}}};set flags {{}};set mask [expr {{[lindex $c 7]+256*[lindex $c 8]}}];set bit 1',
           ' foreach point $points {if {$mask&$bit} {lappend flags {*}$point} else {lappend flags 255 255};set bit [expr {$bit<<1}]}',
           ' while {[llength $flags]<40} {lappend flags 255 255}',
           f' debug write_block memory {syms["hud_flags"]} [binary format c* $flags]'] if base_mode else []),
        ' set ::cell [lindex $c 0];set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc700','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::scene [debug read_block VRAM 0 65536];set ::native [debug read_block memory 0xe000 4096]',
        ' debug write {VDP regs} 0 6;debug write {VDP regs} 1 66',
        f' debug write memory {syms["Radar_Initializing"]} 0',
        f' debug write_block memory {syms["Radar_Base"]} $::base',
        *[f' debug write memory {0xc700+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc740 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Radar stack imbalance"}',
        f' foreach {{address count}} [list [expr {{129184+32*$::cell}}] 32 [expr {{129568+32*$::cell}}] 32 [expr {{128000+16*($::cell+{map_slot})}}] 16] {{puts -nonewline $::results [debug read_block VRAM $address $count]}}',
        ' puts $::costs [expr {round(([machine_info time]-$::begin)*3579545)}];incr ::index;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Radar VRAM timing violation";exit 2}',
        'after time 180 {puts stderr "Radar component timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    palette=(bundle/'palette.bin').read_bytes()
    white=index_for(palette,(222,222,222));red=index_for(palette,(255,0,0));black=info['sprites']['black']
    raw=(out/'msx.bin').read_bytes()
    if len(raw)!=len(cases)*80:raise ValueError('Incomplete radar component output')
    for n,case in enumerate(cases):
        cell,*coords=case[:7];points=list(zip(coords[::2],coords[1::2]))
        ox,oy=cell%3*16,(cell//3*15+cell%3-2)&255
        mask=bytearray(base);colors=bytearray([white|32])*16
        if base_mode:
            active=int.from_bytes(case[7:],'little');flags=[p for i,p in enumerate(source_flags) if active&(1<<i)]
            signed_oy=cell//3*15+cell%3-2
            mask=bytearray(sum(int(row<15 and 0<=signed_oy+row<58 and
                (ox+half+bit in (0,47) or signed_oy+row in (0,57) or
                 any(x<=ox+half+bit<x+2 and y<=signed_oy+row<y+2 for x,y in flags)))<<(7-bit)
                for bit in range(8)) for half in (0,8) for row in range(16))
        for who,color in ((1,red),(2,red),(0,black)):
            if who==0 and separate_player:continue
            px,py=points[who];rx=(px-ox)&255;ry=(py-oy)&255
            if px==255 or rx not in (*range(16),255) or ry not in (*range(15),255):continue
            rx=-1 if rx==255 else rx;ry=-1 if ry==255 else ry
            for y in range(ry,ry+2):
                for x in range(rx,rx+2):
                    if 0<=x<16 and 0<=y<15:mask[x//8*16+y]|=128>>(x%8)
            for row in range(ry,ry+3):
                if 0<=row<16:colors[row]=color|32
        shifted=b''.join(bytes((0,))+mask[h*16:h*16+15] for h in range(2))
        if raw[n*80:(n+1)*80]!=mask+shifted+colors:
            raise ValueError(f'Radar marker/mask/color mismatch case {n}, cell {cell}, points {points}')
    costs=[int(v) for v in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=len(cases) or bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Radar evidence/source changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),cases=len(cases),maze_unchanged=True,native_state_unchanged=True,
        elapsed_cycles=dict(median=statistics.median(costs),maximum=max(costs)),strict_vram_timing=True,
        scope=('Actual base-mask lookup across every flag subset/cell; independent pixel geometry' if base_mode else 'Actual compact-radar cell composition/upload: all marker clips, three producers, overlap/color priority and shifted sentinel masks')+'; isolated IRQ sources disabled, not moving display acceptance'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} executed radar cell cases: {out}/report.json')
