"""Live HUD alerts, real Space/P keys and explicitly seeded fuel boundaries."""
import os
import subprocess

from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal
from .build import destination
from .emulator import reference_machine, scanout_recording_tcl, tcl
from .hud_verify import symbols
from .death_verify import verify_images


def verify_blink(rows, cells, flags, slot, half_period):
    """Allow the existing publication budget, while requiring every stable phase."""
    visible=[]
    phase_age=0
    previous=None
    settled=0
    for age, clock, encoded in rows:
        phase=int(clock)//half_period & 1
        phase_age=phase_age+1 if phase==previous else 0
        previous=phase
        masks=bytes.fromhex(encoded)
        bits=[(masks[cell] >> bit) & 1 for cell,bit in cells]
        if len(set(bits))!=1:
            raise ValueError('S radar cells disagree')
        visible.append(bits[0])
        if int(age)<=24:
            continue
        for cell in range(12):
            ox,oy=cell%3*16,cell//3*15+cell%3-2
            ids=[i for i,(x,y) in enumerate(flags) if -1<=x-ox<16 and -1<=y-oy<15]
            if any(not masks[cell]&(1<<bit) for bit,i in enumerate(ids) if i!=slot):
                raise ValueError('An ordinary flag blinked with the S flag')
        if phase_age>=16:
            if bits[0] != 1-phase:
                raise ValueError('S radar blink exceeded the publication budget')
            settled+=1
    if len(rows)!=128 or set(visible[24:])!={0,1} or settled<16:
        raise ValueError('S radar marker did not blink in live gameplay')
    return settled


def verify(root, args):
    bundle = args.rom.parent
    verify_manifest(bundle)
    info = read_json(bundle/'build.json')
    style = info['hud_style']
    slot = style.get('radar_special_flag_slot')
    if slot is None or not style.get('fuel_color_state_address'):
        raise ValueError('HUD alerts require the stage12 session build')
    out = destination(root, args.output)
    out.mkdir(parents=True)
    require_ignored(root, [out/'alerts.tcl'])
    syms = symbols(bundle/'raster-scroll.sym')
    flags = read_json(bundle/'radar.json')['scenes'][0]['flags']
    # Independent geometry: locate the S dot among each cell's flag bits.
    cells = []
    for cell in range(12):
        ox, oy = cell % 3*16, cell//3*15+cell % 3-2
        ids = [i for i, (x, y) in enumerate(flags) if -1 <= x-ox < 16 and -1 <= y-oy < 15]
        if slot in ids:
            cells.append((cell, ids.index(slot)))
    lines = [
        'set save_settings_on_exit false', 'set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',
        reference_machine(root, args.machine), 'set firmwareswitch off',
        'set throttle on', 'set speed 100', 'set vsync off', 'set pause_on_lost_focus false',
        'set z80_freq 3579545', 'set z80_freq_locked false', 'set cmdtiming real',
        'set limitsprites true', 'set minframeskip 0', 'set maxframeskip 0',
        'set gamma 1', 'set brightness 0', 'set contrast 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        'set blur 0', 'set noise 0', 'set scanline 0',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16', 'reset',
        f'set out {tcl(out)};set phase boot;set age 0;set shots 0;set cases {{60 6 5 0 60}}',
        'set blink [open [file join $out blink.tsv] w];set header [string repeat [binary format c 0] 12]',
        'proc poll {} {if {[catch {menu} p]} {puts stderr $p;exit 2};if {$::phase in {boot coin release start}} {after time 0.02 poll}}',
        'proc menu {} {incr ::age;set state [debug read memory 0xc7d0];set ready [debug read memory 0xc7dd];switch $::phase {',
        ' boot {if {$state==1 && $ready} {keymatrixdown 0 32;set ::phase coin;set ::age 0}}',
        ' coin {if {$::age==3} {keymatrixup 0 32;set ::phase release;set ::age 0}}',
        ' release {if {$::age==3} {keymatrixdown 0 2;set ::phase start;set ::age 0}}',
        ' start {if {$state==0} {keymatrixup 0 2;set ::phase blink;set ::age 0}}','}}',
        'proc step {} {',
        ' if {$::phase in {boot coin release start done}} {return};incr ::age',
        ' switch $::phase {',
        ' blink {',
        f'  puts $::blink "$::age [debug read memory {syms["radar_clock"]}] [binary encode hex [debug read_block memory 0xcfa8 12]]"',
        '  if {$::age==128} {keymatrixdown 8 1;set ::placements [debug read memory 0xc711];set ::phase smoke;set ::age 0}',
        ' }',
        ' smoke {',
        '  if {[debug read memory 0xc009]} {error "Space paused gameplay"}',
        '  if {$::age==4} {keymatrixup 8 1}',
        '  if {$::age==12} {if {[debug read memory 0xc711]<=$::placements} {error "Space did not place smoke"};keymatrixdown 4 32;set ::phase pause;set ::age 0}',
        ' }',
        ' pause {',
        '  if {$::age==4} {keymatrixup 4 32;if {![debug read memory 0xc009]} {error "P did not pause"};set ::native [debug read_block memory 0xe000 4096]}',
        '  if {$::age==12} {if {[debug read_block memory 0xe000 4096] ne $::native} {error "Paused native state moved"};set ::phase fuel;set ::age 0}',
        ' }',
        ' fuel {',
        '  if {$::age==1} {set ::amount [lindex $::cases 0];debug write memory 0xe26a 0;debug write memory 0xe26b $::amount;debug write memory 0xc5b6 1}',
        f'  if {{$::age==8}} {{set want [expr {{$::amount<6?{info["sprites"]["red"]}|32:{info["sprites"]["yellow"]}|32}}];if {{[debug read memory 0xc39b]!=$want || [debug read memory 0xc325]!=min($::amount,54)*30/54}} {{error "Fuel alert boundary mismatch"}};set ::capture 1}}',
        '  if {$::age==12} {set ::cases [lrange $::cases 1 end];if {![llength $::cases]} {close $::blink;set ::phase done;after frame {record stop;exit 0}};set ::age 0}',
        ' }',' }','}',
        'debug set_watchpoint write_mem 0xc000 {$wp_last_value==2} {if {[catch {step} p]} {puts stderr $p;exit 2}}',
        'debug set_watchpoint write_mem 0xc03c {$wp_last_value==2} {set ::header [debug read_block memory 0xc30c 12]}',
        'debug set_watchpoint write_mem 0xc03c {$wp_last_value==6 && [info exists ::capture] && $::capture} {',
        ' set ::capture 0;set n [incr ::shots];foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] header $::header] {set f [open [file join $::out "$n.$ext"] wb];puts -nonewline $f $data;close $f}',
        ' after frame [list after time 0.001 [list screenshot -raw -size auto [file join $::out "$n.png"]]]','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "HUD alert VRAM timing violation";exit 2}',
        'after time 60 {puts stderr "HUD alert timeout";exit 2}',
        scanout_recording_tcl(out, syms['startup_mode']), 'after time 0.02 poll',
    ]
    (out/'alerts.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} p]} {puts stderr $p;exit 2}\n')
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx, '-script', str(out/'alerts.tcl')], check=True, timeout=90,
                       stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, OPENMSX_HOME=str(out/'home'), OPENMSX_USER_DATA=str(out/'userdata')))
    rows = [line.split() for line in (out/'blink.tsv').read_text().splitlines()]
    settled=verify_blink(rows,cells,flags,slot,style['radar_special_flag_blink_ticks'])
    images = verify_images(args, out)
    verify_manifest(bundle)
    json_write(out/'report.json', dict(rom_sha256=digest(args.rom), full_rgb_images=images,
        live_special_flag_refreshes=len(rows), special_flag_cells=cells,
        special_flag_settled_phase_checks=settled,ordinary_flags_remain_visible=True,
        keyboard_space_places_smoke=True, keyboard_p_pauses=True,
        fuel_boundary_units=[60, 6, 5, 0, 60], fuel_inputs_explicitly_seeded=True,
        scope='Live S radar blink and real keyboard controls; isolated fuel color boundaries with the complete HUD'))
    require_ignored(root, [p for p in out.rglob('*') if p.is_file()])
    seal(out)
    print(f'HUD alerts: {images} RGB,128 live S refreshes, Space smoke/P pause: {out}/report.json')
