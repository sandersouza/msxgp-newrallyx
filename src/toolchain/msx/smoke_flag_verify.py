"""Execute flag/smoke overlap against original four-tile clearing and RAM canaries."""
import os
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .fuel_verify import source_seed
from .smoke_verify import RANGES,RECORD
from .smoke import ring_index


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not (info.get('smoke_component') or {}).get('runtime_enabled'):raise ValueError('Flag/smoke proof requires stage10')
    out=destination(root,args.output);out.mkdir(parents=True);require_ignored(root,[out/'seeds.bin'])
    flags=read_json(bundle/'flags.json')['records'];seed=(bundle/'player-seed.bin').read_bytes()
    cases=[];native_seeds=bytearray();original_seeds=bytearray();wanted_queue=[]
    for f in flags:
        x,y=f['tile_x'],f['tile_y']
        for dy in range(-3,4):
            for dx in range(-3,4):
                state=bytearray(seed);state[0x400:0x800]=bytes([129])*1024;state[0xc00:]=bytes([149])*1024
                state[0x70]=(x-3)//3;state[0x72]=(y-3)//3;state[0x6d]=state[0x6f]=0
                state[0x74]=112;state[0x76]=116
                state[0x4d]=(x*8+12-112-28)&255;state[0x4f]=(80-y*8-12-116-8)&255
                for sy in range(3):
                    for sx in range(3):state[0x400+ring_index(x+dx+sx,y+dy+sy)]=189+sy*3+sx
                wanted_queue.append(any(189<=state[0x400+ring_index(x+sx,y+sy)]<198 for sy in range(3) for sx in range(3)))
                native_seeds.extend(state)
                original=bytearray(source_seed(bundle))
                for at,n in ((0x400,1024),(0xc00,1024),(0x4d,1),(0x4f,1),(0x70,1),(0x72,1),(0x6d,1),(0x6f,1),(0x74,1),(0x76,1)):
                    original[at:at+n]=state[at:at+n]
                original_seeds.extend(original);cases.append((x,y,(x-12)&255,(y-12)&255))
    (out/'seeds.bin').write_bytes(original_seeds);(out/'native-seeds.bin').write_bytes(native_seeds)
    (out/'cases.bin').write_bytes(bytes(v for case in cases for v in case))
    rows=[(x,y,valid) for x in (0,30,31,63,100) for y in (0,31,32,173) for valid in (0,1)]
    (out/'rows.bin').write_bytes(bytes(v for case in rows for v in case))
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Flag/smoke oracle requires MAME0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/msx/smoke_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','90']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,SMOKE_OUTPUT=str(out),SMOKE_FLAG_REPLAY='1'),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    syms=symbols(bundle/'raster-scroll.sym');bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'foreach name {cases native-seeds rows} {set f [open [file join $out "$name.bin"] rb];set data($name) [read $f];close $f}',
        'foreach name {msx queue published published-counts} {set result($name) [open [file join $out "$name.bin"] wb]}',
        f'set native_count {len(cases)};set total {len(cases)+len(rows)};set index 0;set started 0',
        'proc issue {} {',
        ' if {$::index==$::total} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {error "Flag/smoke RAM adapter changed VRAM"};foreach name {msx queue published published-counts} {close $::result($name)};exit 0;return}',
        ' if {$::index<$::native_count} {',
        '  binary scan [string range $::data(cases) [expr {$::index*4}] [expr {$::index*4+3}]] cu* c;lassign $c ::x ::y left top',
        '  debug write_block memory 0xe000 [string range $::data(native-seeds) [expr {$::index*4096}] [expr {($::index+1)*4096-1}]]',
        '  foreach {a v} [list 0xc701 1 0xc702 $left 0xc703 $top 0xc50f $::x 0xc510 $::y 0xc70c 0 0xc70d 0 0xc70e 0 0xc70f 0] {debug write memory $a $v}',
        f'  set target {syms["Smoke_CollectedFlag"]}',
        ' } else {',
        '  set at [expr {($::index-$::native_count)*3}];binary scan [string range $::data(rows) $at [expr {$at+2}]] cu* c;lassign $c ::x ::y valid',
        '  debug write_block memory 0xd300 [string repeat [binary format c 17] 2048]',
        '  debug write_block memory 0xdb00 [string repeat [binary format c 64] 32]',
        '  foreach {a v} [list 0xc701 $valid 0xc0bc $::x 0xc0bd $::y 0xc710 192] {debug write memory $a $v}',
        f'  set target {syms["Smoke_ClearPublishedRow"]}',' }',
        ' set p 0xd110;foreach v [list 243 205 [expr {$target&255}] [expr {$target>>8}] 195 64 209] {debug write memory $p $v;incr p}',
        ' foreach {name value} {AF 4660 BC 13398 DE 30874 HL 48350 IX 9029 IY 17767 SP 51184 PC 53520} {reg $name $value}','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::saved_vram [debug read_block VRAM 0 131072];issue}}',
        'debug set_bp 0xd140 {$::started} {',
        ' foreach {name value} {AF 4660 BC 13398 DE 30874 HL 48350 IX 9029 IY 17767 SP 51184} {if {[reg $name]!=$value} {error "Flag/smoke adapter changed $name"}}',
        ' if {$::index<$::native_count} {',
        *[f'  puts -nonewline $::result(msx) [debug read_block memory {0xe000+a} {n}]' for a,n in RANGES],
        '  puts -nonewline $::result(queue) [binary format c [debug read memory 0xc70e]];puts -nonewline $::result(queue) [debug read_block memory 0xc740 3]',
        ' } else {',
        '  if {[debug read memory 0xc0bc]!=$::x || [debug read memory 0xc0bd]!=$::y || [debug read memory 0xc710]!=192} {error "Flag row metadata changed its caller state"}',
        '  puts -nonewline $::result(published) [debug read_block memory 0xd300 2048]',' }',
        ' if {$::index>=$::native_count} {puts -nonewline $::result(published-counts) [debug read_block memory 0xdb00 32]}',
        ' incr ::index;issue','}','after time 90 {puts stderr "Flag/smoke adapter timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    actual=(out/'msx.bin').read_bytes();original=(out/'original.bin').read_bytes()
    if len(actual)!=len(cases)*RECORD or original!=actual:
        at=next((i for i,(a,b) in enumerate(zip(original,actual)) if a!=b),min(len(original),len(actual)))
        raise ValueError(f'Flag/smoke differs from original at case{at//RECORD}, byte{at%RECORD}')
    queue=(out/'queue.bin').read_bytes()
    if len(queue)!=4*len(cases):raise ValueError('Incomplete flag repaint queue evidence')
    for i,(x,y,_,_) in enumerate(cases):
        r=queue[i*4:i*4+4]
        if r[0]!=wanted_queue[i] or r[0] and r[1:]!=bytes((x,y,0)):raise ValueError('Flag/smoke repaint queue changed')
    published=(out/'published.bin').read_bytes()
    counted=bool(info['smoke_component'].get('publication_counts_address'))
    counts=(out/'published-counts.bin').read_bytes()
    if len(published)!=len(rows)*2048:raise ValueError('Incomplete flag row canaries')
    for i,(x,y,valid) in enumerate(rows):
        expected=bytearray([17])*2048
        if valid:
            for dx in range(3):expected[(y&31)*64+((x+dx)&63)]=0
        if published[i*2048:(i+1)*2048]!=expected:raise ValueError('Flag/smoke row touched unrelated display cells')
        if counted:
            from .smoke import verify_publication_counts
            verify_publication_counts(expected,counts[i*32:(i+1)*32])
    from .smoke_queue_verify import verify as verify_queue
    queue_cases=verify_queue(root,args,out/'queue-proof',syms)
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Flag/smoke BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),original_flag_overlap_cases=len(cases),
        publication_row_canaries=len(rows),queue_wrap_dedup_full_cases=queue_cases,original_bytes_per_case=RECORD,caller_registers_preserved=True,vram_unchanged=True,
        scope='Original 19d9..1a32 four-tile clearing preserves other cloud tiles and all attributes; row metadata preserves neighboring cells and caller ABI'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} original flag/smoke overlaps and {len(rows)} row canaries: {out}/report.json')
    return out
