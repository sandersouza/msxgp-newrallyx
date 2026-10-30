"""Execute every compact-HUD coordinate phase and verify independent geometry."""
import os
import statistics
import subprocess

from src.toolchain.scenes.bundle import digest,read_json,verify_manifest
from src.toolchain.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not info.get('hud_style',{}).get('radar_cells_only'):raise ValueError('Compact HUD required')
    out=destination(root,args.output);require_ignored(root,[out/'results.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym');code=[243]
    separate=info['hud_style'].get('radar_player_sprite',False)
    cases=512 if separate else 256
    attr_bytes=64 if separate else 60
    record_bytes=84+attr_bytes+(7 if separate else 0)
    calls=('HUD_PrepareCoordinates',) if 'HUD_PrepareCoordinates' in syms else ('update_fuel_sat','update_life_sat','update_lives')
    for name in calls:code.extend((205,syms[name]&255,syms[name]>>8))
    if separate:
        entry=syms['Radar_UpdatePoints'];code.extend((205,entry&255,entry>>8))
    code.extend((195,64,199))
    lines=['set save_settings_on_exit false','set renderer none','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle off','set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set results [open [file join $out results.bin] wb];set costs [open [file join $out cycles.tsv] w];set n 0;set started 0',
        'proc issue {} {',
        f' if {{$::n=={cases}}} {{if {{[debug read_block VRAM 0 65536] ne $::scene || [debug read_block memory 0xe000 4096] ne $::native}} {{error "Coordinates changed maze/native state"}};close $::results;close $::costs;exit 0;return}}',
        f' debug write memory {syms["scroll_y"]} [expr {{$::n&255}}]',
        *([f' debug write memory {syms["hud_player_x"]} [expr {{$::n<256?2+$::n%44:255}}]',
           f' debug write memory {syms["hud_player_y"]} [expr {{$::n<256?2+$::n%54:255}}]',
           f' debug write memory {syms["player_native_ticks"]} [expr {{$::n&255}}]',
           f' debug write memory {syms["hud_enemy_x"]} 255',
           f' debug write memory {syms["hud_enemy_y"]} 255',
           *([f' debug write memory {syms["Enemy2_PointX"]} 255',f' debug write memory {syms["Enemy2_PointY"]} 255'] if 'Enemy2_PointX' in syms else []),
           f' debug write_block memory {syms["Radar_Last"]} [binary format c* {{255 255 255 255 255 255}}]',
           f' debug write_block memory {syms["Radar_Dirty"]} [binary format c* {{0 0}}]'] if separate else []),
        ' set ::begin [machine_info time];reg SP 0xc7f0;reg PC 0xc700','}',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1;set ::scene [debug read_block VRAM 0 65536];set ::native [debug read_block memory 0xe000 4096]',
        *([f' set f [open [file join $::out dot-patterns.bin] wb];puts -nonewline $f [debug read_block VRAM {129024+info["hud_style"]["radar_player_pattern"]*8} 64];close $f'] if separate else []),
        ' debug write {VDP regs} 0 6;debug write {VDP regs} 1 66',
        *[f' debug write memory {0xc700+i} {v}' for i,v in enumerate(code)],'issue','}',
        'debug set_bp 0xc740 {$::started} {',
        ' if {[reg SP]!=0xc7f0} {error "Coordinates stack imbalance"}',
        f' puts -nonewline $::results [debug read_block memory 0xc100 60];puts -nonewline $::results [debug read_block memory 0xc280 12];puts -nonewline $::results [debug read_block memory 0xc290 12];puts -nonewline $::results [debug read_block VRAM 128512 {attr_bytes}]',
        *([' puts -nonewline $::results [debug read_block VRAM 128000 3];puts -nonewline $::results [debug read_block memory 0xcf38 4]',
           f' if {{[debug read memory {syms["Radar_Dirty"]}] || [debug read memory {syms["Radar_Dirty"]+1}] || [debug read memory {syms["Radar_Last"]}]!=255 || [debug read memory {syms["Radar_Last"]+1}]!=255}} {{error "Independent player dirtied the radar map"}}'] if separate else []),
        ' puts $::costs [expr {round(([machine_info time]-$::begin)*3579545)}];incr ::n;issue','}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Coordinates VRAM timing violation";exit 2}',
        'after time 30 {puts stderr "Coordinates timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],check=True,timeout=60,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'results.bin').read_bytes()
    if len(raw)!=cases*record_bytes:raise ValueError('Incomplete coordinate evidence')
    for case in range(cases):
        scroll=case&255
        attrs=bytearray()
        if separate:
            visible=case<256;px=2+scroll%44 if visible else 255;py=2+scroll%54 if visible else 255
            y=(scroll+(20+py-1 if visible else 211))&255
            phase=int(visible and y==216)
            if not visible and y==216:y+=1
            attrs.extend((y-phase,(204+px)&255,info['hud_style']['radar_player_pattern']+4*phase,0))
        for cell in range(12):
            column,band=cell%3,cell//3;y=(scroll+20+band*15+column-3)&255;phase=int(y==216)
            attrs.extend((y-phase,204+column*16,20+4*cell+48*phase,0))
        y=(scroll+81)&255;phase=int(y==216)
        fuel=bytes(v for x,p in ((204,132+4*phase),(220,140+8*phase),(236,144+8*phase)) for v in (y-phase,x,p,0))
        attrs.extend(fuel)
        y=(scroll+193)&255;phase=int(y==216)
        life=bytes(v for x,p in ((220,156+8*phase),(220,160+8*phase),(238,172+4*phase)) for v in (y-phase,x,p,0))
        if info.get('hud_style',{}).get('static_fuel_life_colors'):
            hidden=(scroll+211)&255
            if hidden==216:hidden+=1
            life=bytes((y-phase,238,172+4*phase,0,y-phase,220,156+8*phase,0,
                        hidden,220,156+8*phase,0))
        shadow=raw[:60] if info['hud_style'].get('coordinates_direct_rom') else attrs
        expected=shadow+fuel+life+attrs
        if separate:
            color=info['sprites']['black' if scroll&8 else 'white']
            expected+=bytes([color|32])*3+bytes((px,py,int(visible),color))
        if raw[case*record_bytes:(case+1)*record_bytes]!=expected:
            raise ValueError(f'Coordinate geometry/SAT mismatch case {case}, scroll {scroll}')
    if separate and (out/'dot-patterns.bin').read_bytes()!=bytes((192,192))+bytes(30)+bytes((0,192,192))+bytes(29):
        raise ValueError('Resident player dot masks differ from the original 2x2 footprint')
    costs=[int(v) for v in (out/'cycles.tsv').read_text().splitlines()]
    if len(costs)!=cases or bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('Coordinate evidence/source changed')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(phases=256,cases=cases,rom_sha256=digest(args.rom),cpu_hz=3579545,
        min_cycles=min(costs),median_cycles=statistics.median(costs),max_cycles=max(costs),
        maze_unchanged=True,native_state_unchanged=True,strict_vram_timing=True,
        independent_player_no_map_dirty=separate,independent_player_blink_native_ticks=8 if separate else None,
        scope='Actual compact HUD coordinates/body SAT/fuel/footer RAM across all256 scroll values; isolated VDP IRQ sources disabled, independent screen geometry; not complete display acceptance'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'256 exact compact HUD coordinate phases: {out}/report.json')
    return out
