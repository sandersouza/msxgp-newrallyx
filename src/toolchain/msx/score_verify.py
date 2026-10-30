"""Independent original scoring/carry/high-score/bonus-life component oracle."""
import os
import statistics
import subprocess
from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .stage_one import acquire

DIGITS=(4,5,6,7,0,1,2,3)


def packet(value):
    """Canonical original score glyphs: leading spaces, decimal digits, fixed ones."""
    if value%10 or not 0<=value<100000000:raise ValueError('Score fixture must fit eight digits in tens')
    digits=f'{value:08d}';leading=True;out=bytearray(8)
    for offset,char in zip(DIGITS,digits):
        if char!='0':leading=False
        out[offset]=64 if leading and offset not in (2,3) else int(char)
    out[3]=0x30
    if value==0:out[2]=0x30
    return bytes(out)


def cases_for():
    cases=[]
    for order in ([1]*8+[4,2],[2]+[1]*8+[4],[4,2]+[1]*8):
        for i,kind in enumerate(order,1):
            cases.extend([(int(i==1),i,kind,0,0,3,packet(0),packet(20000)),
                          (0,i,kind,0,0,3,packet(0),packet(20000))])
    for value in (0,90,990,9990,19950,19990,20000,20050,69990,79990,80000,99990,999990,99999990):
        for high in sorted({0,20000,value,min(value+50,99999990),min(value+100,99999990)}):
            for ordinal in (1,9,10):
                for kind in (1,2,4):
                    for mode in (0,1):
                        cases.append((1,ordinal,kind,mode,0,3,packet(value),packet(high)))
    for value in (19990,79990):
        for ordinal in (1,10):
            for kind in (1,2):
                for mode in (0,1):
                    for awarded in (2,8,10):
                        cases.append((1,ordinal,kind,mode,awarded,3,packet(value),packet(20000)))
    return cases


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle)
    if read_json(bundle/'build.json').get('incremental_stage') not in (5,6):raise ValueError('Score proof requires stage 05 or 06')
    out=destination(root,args.output);require_ignored(root,[out/'cases.bin']);out.mkdir(parents=True)
    cases=cases_for();data=b''.join(bytes(c[:6])+c[6]+c[7] for c in cases)
    (out/'cases.bin').write_bytes(data)
    _,source=acquire(root);native=(source/'video.bin').read_bytes()
    linked=(bundle/'player-seed.bin').read_bytes();seed=bytearray(linked)
    for at in (0x988,0x990):seed[at:at+2]=(int.from_bytes(linked[at:at+2],'little')-0x6000).to_bytes(2,'little')
    for at in (0x1b3,0x1b9):
        seed[at:at+2]=native[at:at+2]
        if int.from_bytes(linked[at:at+2],'little')!=int.from_bytes(native[at:at+2],'little')+0x8000:
            raise ValueError('Bonus table relocation differs from original')
    if linked[0x60:0x68]!=native[0x60:0x68] or linked[0xa0:0xa8]!=native[0xa0:0xa8]:raise ValueError('Score initialization changed')
    (out/'source-seed.bin').write_bytes(seed)
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Score oracle requires MAME 0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'src/toolchain/msx/score_native.lua'),
        '-cfg_directory',str(out/'mame-cfg'),'-nvram_directory',str(out/'mame-nvram'),'-seconds_to_run','60']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,SCORE_OUTPUT=str(out)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    syms=symbols(bundle/'raster-scroll.sym');call=syms['Score_Update'];init=syms['Score_Init']
    code=[0xf3,0x3e,syms['PLAYER_BANK'],0x32,0,0x70,0xcd,call&255,call>>8,0x76]
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        f'set f [open {tcl(bundle/"player-seed.bin")} rb];set seed [read $f];close $f',
        'set f [open [file join $out cases.bin] rb];set cases [read $f];close $f',
        'set result [open [file join $out msx.bin] wb];set pending [open [file join $out pending.bin] wb];set times [open [file join $out cycles.tsv] w];set index 0;set started 0',
        'proc next_case {} {',
        ' if {$::index==[string length $::cases]/22} {if {[debug read_block VRAM 0 131072] ne $::saved_vram} {error "Score producer changed VRAM"};close $::result;close $::pending;close $::times;exit 0;return}',
        ' set p [expr {$::index*22}];set c [string range $::cases $p [expr {$p+21}]];binary scan $c cu* v',
        ' lassign $v reset ordinal kind mode awards lives',
        ' if {$reset} {',
        '  debug write_block memory 0xe000 $::seed;debug write memory 0xc540 0;debug write memory 0xc54f 0',
        '  debug write_block memory 0xe0a0 [string range $c 6 13];debug write_block memory 0xe060 [string range $c 14 21]',
        '  foreach {a v} [list 0xe023 $mode 0xe1b2 $awards 0xe00f $lives] {debug write memory $a $v}',
        ' }',
        ' debug write memory 0xc50b $ordinal;debug write memory 0xc50d $kind',
        ' set ::saved_player [debug read_block memory 0xe068 24]',
        ' reg SP 0xc7f0;reg PC 0xc600','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{',
        'set ::started 1;set ::saved_vram [debug read_block VRAM 0 131072]',
        *[f'debug write memory {0xc600+i} {v}' for i,v in enumerate(code)],
        'next_case','}',
        f'debug set_bp {call} {{$::started}} {{set ::begin [machine_info time]}}',
        'debug set_bp 0xc609 {$::started} {',
        ' if {[reg SP]!=0xc7f0 || [debug read_block memory 0xe068 24] ne $::saved_player} {error "Score producer changed movement/stack"}',
        ' puts -nonewline $::result [debug read_block memory 0xe0a0 8];puts -nonewline $::result [debug read_block memory 0xe060 8]',
        ' foreach a {0xe00f 0xe1b2 0xe023 0xe2d0 0xe250 0xc540} {puts -nonewline $::result [binary format c [debug read memory $a]]}',
        ' puts -nonewline $::pending [debug read_block memory 0xc300 12]',
        ' puts $::times "$::index [expr {round(([machine_info time]-$::begin)*3579545)}]"',
        ' incr ::index;next_case','}',
        'after time 180 {puts stderr "Score microprobe timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    original=(out/'original.bin').read_bytes();actual=(out/'msx.bin').read_bytes()
    if len(original)!=len(cases)*22 or len(actual)!=len(original):raise ValueError('Incomplete score proof')
    for i in range(len(cases)):
        a,b=actual[i*22:(i+1)*22],original[i*22:(i+1)*22]
        if a!=b:raise ValueError(f'Original score mismatch at {i}: {a.hex()} / {b.hex()}')
    if read_json(bundle/'build.json')['hud_enabled']:
        pending=(out/'pending.bin').read_bytes()
        expected=bytes(original[i*22+base+j]&15 for i in range(len(cases)) for base in (0,8) for j in (6,7,0,1,2,3))
        if pending!=expected:raise ValueError('HUD pending score/high score differs from original values')
    costs=[int(r.split()[1]) for r in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=len(cases):raise ValueError('Incomplete score timing proof')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    verify_manifest(bundle);verify_manifest(source)
    json_write(out/'report.json',dict(cases=len(cases),rom_sha256=digest(args.rom),mame_version=version,
        median_cycles=statistics.median(costs),max_cycles=max(costs),vram_unchanged=True,movement_unchanged=True,
        scope='Original flag points, special/lucky request bits, digit carry, high-score and bonus-life accounting; fuel conversion excluded'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{len(cases)} exact original score/high-score/bonus-life cases: {out}/report.json')
    return out
