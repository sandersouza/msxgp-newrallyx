"""Keyboard session UI proof with explicitly seeded terminal-state component cases."""
import os
import subprocess
from PIL import Image,ImageChops
from scripts.scenes.bundle import read_json,verify_manifest,digest
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl,scanout_recording_tcl
from .hud_verify import symbols
from .score_verify import packet
from .raster_scroll import palette_rgb
from .display import DISPLAY_SHIFT


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('session'):raise ValueError('Session proof requires stage12')
    out=destination(root,args.output);out.mkdir(parents=True);require_ignored(root,[out/'session.tcl'])
    syms=symbols(bundle/'raster-scroll.sym');high=packet(123450)
    natural=bool(getattr(args,'natural_game_over',False))
    if natural:
        from .stage_one import acquire,reconstruct
        from .completion_route_verify import navigation
        program,reference=acquire(root);board,_,_=reconstruct(program,reference)
        (out/'chase-nav.bin').write_bytes(navigation(board,[dict(address=0x9800+i) for i in range(1792)]))
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle on','set speed 100','set vsync off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set minframeskip 0','set maxframeskip 0','set gamma 1','set brightness 0','set contrast 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','set blur 0','set noise 0','set scanline 0',
        'activate_input_layer -blocking session_proof',f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',
        f'set out {tcl(out)};set phase boot;set held 0;set shots 0;set polls 0;set started 0',
        f'debug set_bp {syms["startup_mode"]} {{!$::started}} {{set ::started 1}}',
        f'set high [binary format c* {{{" ".join(map(str,high))}}}]',
        'proc key {m} {keymatrixup 0 255;if {$m} {keymatrixdown 0 $m}}',
        'proc shot {} {',
        ' set n [incr ::shots];set f [open [file join $::out "$n.state"] wb];puts -nonewline $f [debug read_block memory 0xc000 12288];close $f',
        ' after frame [list after frame [list after time 0.001 [list screenshot -raw -size auto [file join $::out "$n.png"]]]]','}',
        'proc terminal {which} {',
        ' if {$which==2} {foreach {a v} {0xe00f 0 0xe020 0 0xc490 2 0xc494 0 0xc5c0 2} {debug write memory $a $v}} else {debug write memory 0xc724 3}','}',
        'proc poll {} {',
        ' if {[catch {step} p]} {puts stderr $p;exit 2};if {$::phase ne "done"} {after time 0.02 poll}','}',
        'proc step {} {',
        f' incr ::polls;if {{$::polls>{9000 if natural else 3000}}} {{error "Session UI timeout: $::phase"}}',
        ' if {!$::started} {return}',
        ' set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd];set credit [debug read memory 0xc7d2]',
        ' switch $::phase {',
        ' boot {if {$state==1 && $ready} {if {$credit} {error "Boot credit nonzero"};shot;key 2;set ::held 0;set ::phase no_credit}}',
        ' no_credit {incr ::held;if {$state!=1 || $credit} {error "Start without credit"};if {$::held==8} {key 0;set ::phase release;set ::held 0}}',
        ' release {incr ::held;if {$::held==3} {key 32;set ::phase coin;set ::held 0}}',
        ' coin {incr ::held;if {$::held>2 && $credit!=1} {error "Held coin repeated or disappeared"};if {$::held==12} {key 0;shot;set ::phase start_release;set ::held 0}}',
        ' start_release {incr ::held;if {$::held==3} {key 2;set ::phase start;set ::held 0}}',
        ' start {incr ::held;if {$::held==4} {key 0};if {$state==0} {',
        '  if {$credit || [debug read memory 0xe00f]!=3 || [debug read memory 0xc50b]} {error "First-game initialization changed"};set ::phase game;set ::held 0',' }}',
        (' game {incr ::held;chase;if {$::held==5} {key 32};if {$::held==10} {key 0};if {$state==2 && $ready} {set ::phase over}}' if natural else
         ' game {incr ::held;if {$::held==5} {key 32};if {$::held==10} {key 0};if {$::held==20} {terminal 2;set ::phase over}}'),
        ' over {if {$state==2 && $ready} {if {$credit!=1} {error "Live-game credit was lost or repeated"};shot;set ::phase seed;set ::held 0}}',
        ' seed {incr ::held;if {$::held==3} {',
        '  debug write memory 0xc7d2 254;debug write memory 0xe024 254;debug write_block memory 0xe060 $::high;debug write memory 0xc7d1 0;debug write memory 0xc7dd 0;set ::phase seed_ready',' }}',
        ' seed_ready {if {$ready} {key 32;set ::phase saturation;set ::held 0}}',
        ' saturation {incr ::held;if {$::held>2 && $credit!=255} {error "Credit saturation changed"};if {$::held==12} {key 0;shot;set ::phase saturation_release;set ::held 0}}',
        ' saturation_release {incr ::held;if {$::held==3} {key 32;set ::phase saturated_again;set ::held 0}}',
        ' saturated_again {incr ::held;if {$credit!=255} {error "Credit wrapped"};if {$::held==5} {key 0;set ::phase restart_release;set ::held 0}}',
        ' restart_release {incr ::held;if {$::held==3} {key 2;set ::phase restart;set ::held 0}}',
        ' restart {incr ::held;if {$::held==4} {key 0};if {$state==0} {',
        '  if {$credit!=254 || [debug read memory 0xe024]!=254 || [debug read memory 0xe00f]!=3 || [debug read memory 0xc50b] || [debug read_block memory 0xe060 8] ne $::high} {error "Restart lost credits/high score or initial state"};set ::phase second_game;set ::held 0',' }}',
        ' second_game {incr ::held;if {$::held==20} {terminal 3;set ::phase clear}}',
        ' clear {if {$state==3 && $ready} {shot;set ::phase finish;set ::held 0}}',
        ' finish {incr ::held;if {$::held==5} {set ::phase done;if {[info exists ::life_ticks]} {close $::life_ticks};after frame {record stop;exit 0}}}',' }',
        ' if {$ready && $state && !([debug read {VDP regs} 8]&2)} {error "Sprites leaked: phase=$::phase state=$state ready=$ready R1=[debug read {VDP regs} 1] R8=[debug read {VDP regs} 8]"}','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Session VRAM timing violation";exit 2}',
        f'after time {200 if natural else 90} {{puts stderr "Session proof timeout";exit 2}}',
        scanout_recording_tcl(out,syms['startup_mode']),'after time 0.02 poll']
    if natural:
        lines.extend([
            'set f [open [file join $::out chase-nav.bin] rb];set chase_nav [read $f];close $f;set chase_x 396;set chase_y 1236;set chase_mask 0;set chase_deaths 0',
            'proc u16 {a} {expr {[debug read memory $a]+256*[debug read memory [expr {$a+1}]]}}',
            'proc chase {} {',
            ' keymatrixup 8 255;set deaths [debug read memory 0xc5c2]',
            ' if {$deaths!=$::chase_deaths} {set ::chase_deaths $deaths;set ::chase_x 396;set ::chase_y 1236;set ::chase_mask 0}',
            ' if {[debug read memory 0xc490]} {return}',
            ' set x [u16 0xc405];set y [u16 0xc407]',
            ' if {abs($::chase_x-$x)<=6 && abs($::chase_y-$y)<=6} {',
            '  set cx [expr {int(($::chase_x-36)/24)}];set cy [expr {int(($::chase_y-36)/24)}];set gx [debug read memory 0xe090];set gy [debug read memory 0xe092]',
            '  if {$gx>=32 || $gy>=56} {error "Enemy outside chase board"}',
            '  binary scan [string index $::chase_nav [expr {($gy*32+$gx)*1792+$cy*32+$cx}]] cu mask',
            '  if {$mask==255} {error "Enemy chase is unreachable"}',
            '  if {$mask} {set ::chase_mask $mask;set ::chase_x [expr {36+24*($cx+($mask==128)-($mask==16))}];set ::chase_y [expr {36+24*($cy+($mask==64)-($mask==32))}]}',' }',
            ' if {$::chase_mask} {keymatrixdown 8 $::chase_mask}','}',
            'set life_ticks [open [file join $::out life-ticks.tsv] w]',
            f'debug set_bp {syms["Player_CountTick"]} {{[reg IM]==2 && $::phase eq "game" && [debug read memory 0xc490]}} {{',
            ' puts $::life_ticks "[debug read memory 0xc5c2] [debug read memory 0xc490] [debug read memory 0xc491] [debug read memory 0xe00f] [debug read memory 0xc496]"','}'])
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240 if natural else 120,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    images=verify_images(bundle,out)
    if images!=5:raise ValueError('Missing title/game-over/completion images')
    natural_lives=None
    if natural:
        ticks=[list(map(int,line.split())) for line in (out/'life-ticks.tsv').read_text().splitlines()]
        for death,limit in ((1,120),(2,120),(3,96)):
            rows=[r for r in ticks if r[0]==death]
            if {r[2] for r in rows}!=set(range(limit+1)) or any(r[3]!=3-death or r[4]!=limit or r[1]!=(1 if r[2]<limit else 2) for r in rows):
                raise ValueError(f'Natural death{death} original life/wait mismatch')
        natural_lives=dict(keyboard_only_before_game_over=True,deaths=3,remaining_lives=[2,1,0],original_hold_ticks=[120,120,96])
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Session BIOS changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),full_rgb_images=images,keyboard_credit_and_start=True,
        credit_saturation=255,high_score_preserved=123450,
        natural_game_over=natural_lives,
        scope='Isolated UI transitions: terminal states/high score/credit edge seeded explicitly; real-keyboard all-flag integration is separate'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'Session UI: {images} RGB, credits/start/saturation/high score: {out}/report.json')


def verify_images(bundle,out):
    info=read_json(bundle/'build.json');palette=(bundle/'palette.bin').read_bytes();rgb=palette_rgb(palette)
    image_bank=info['session']['image_bank'];bank=(bundle/f'bank-{image_bank+1}.bin').read_bytes()
    base=(bundle/f'bank-{image_bank}.bin').read_bytes()+bank[:0x2a00]
    count=0
    for path in out.glob('*.state'):
        ram=path.read_bytes();state=ram[0x7d0];credit=ram[0x7d2]
        bitmap=bytearray(base);bitmap[96*128:104*128]=bank[0x2a00+(state-1)*1024:0x2a00+state*1024]
        def number(value,y):
            for digit,char in enumerate(value):
                font=bank[0x3600+int(char)*32:0x3620+int(char)*32]
                for row in range(8):bitmap[(y+row)*128+80+digit*4:(y+row)*128+84+digit*4]=font[row*4:row*4+4]
        for start,y in ((0x2060,56),(0x20a0,80)):
            number(''.join(str(ram[start+j]&15) for j in (6,7,0,1,2,3)),y)
        number(f'{credit:03d}',152)
        from .raster_scroll import index_for
        expected=Image.new('RGB',(320,240),rgb[index_for(palette,(0,0,0))]);screen=Image.new('RGB',(256,212))
        screen.putdata([rgb[v] for byte in bitmap for v in (byte>>4,byte&15)])
        expected.paste(screen,(32+DISPLAY_SHIFT,14))
        with Image.open(path.with_suffix('.png')) as opened:actual=opened.convert('RGB')
        diff=ImageChops.difference(actual,expected)
        if diff.getbbox():
            expected.save(path.with_name(path.stem+'-expected.png'));diff.save(path.with_name(path.stem+'-diff.png'))
            raise ValueError(f'Session RGB mismatch at {path.stem}: {diff.getbbox()}')
        count+=1
    return count
