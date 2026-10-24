"""Real-display, stationary stress proof for the flicker experiment."""
import os
import statistics
import subprocess
from PIL import Image,ImageChops

from scripts.scenes.bundle import digest,read_json,verify_manifest,load_assets
from scripts.scenes.storage import json_write,require_ignored,seal
from .build import destination
from .emulator import reference_machine,tcl
from .hud_verify import symbols
from .player import padded_world
from .raster_scroll import compose,header,bordered
from .sprite_flicker import permutation,paint,selected


def verify(root,args):
    bundle=args.rom.parent;verify_manifest(bundle);info=read_json(bundle/'build.json')
    if not (info.get('sprite_flicker') or {}).get('stationary_stress_fixture'):
        raise ValueError('Stationary flicker stress cartridge required')
    out=destination(root,args.output);require_ignored(root,[out/'frames.bin']);out.mkdir(parents=True)
    syms=symbols(bundle/'raster-scroll.sym');slots=info['sprites']['total_slots'];frames=120
    outline=bool(info.get('outline_flicker'))
    sat_address='[expr {128512-2048*[debug read memory 0xc7c1]}]' if outline else '128512'
    lines=['set save_settings_on_exit false','set sound_driver null',
        f'filepool add -path {tcl(args.bios.resolve())} -types system_rom -position 1',reference_machine(root,args.machine),
        'set firmwareswitch off','set throttle on','set speed 100','set vsync off','set pause_on_lost_focus false',
        'set z80_freq 3579545','set z80_freq_locked false','set cmdtiming real','set limitsprites true',
        'set minframeskip 0','set maxframeskip 0','set gamma 1','set brightness 0','set contrast 0',
        'set color_matrix {{1 0 0} {0 1 0} {0 0 1}}','set blur 0','set noise 0','set scanline 0',
        f'cart {tcl(args.rom.resolve())} -romtype ASCII16','reset',f'set out {tcl(out)}',
        'set n 0;set started 0;set stress_done 0;set stress_samples [open [file join $out frames.bin] wb];set times [open [file join $out times.tsv] w]',
        f'debug set_bp {syms["main"]} {{!$::started}} {{set ::started 1}}',
        'proc capture {n} {screenshot -raw -size auto [file join $::out "$n.png"]}',
        'proc footer {} {',
        ' incr ::n',
        f' if {{[debug read {{VDP regs}} 9]!={info["timing"]["vdp_r9"]}}} {{error "VDP frequency changed"}}',
        ' if {![debug read memory 0xc009] || [debug read memory 0xc440] || [debug read memory 0xc441]} {error "Stress fixture is not frozen"}',
        ' puts -nonewline $::stress_samples [debug read_block memory 0xc000 12288]',
        f' puts -nonewline $::stress_samples [debug read_block VRAM {sat_address} {slots*4+1}]',
        ' if {$::n<=8 || $::n>=119} {',
        '  foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072]] {set f [open [file join $::out "$::n.$ext"] wb];puts -nonewline $f $data;close $f}',
        '  after frame [list capture $::n]',' }',
        f' if {{$::n=={frames}}} {{set ::stress_done 1;close $::stress_samples;close $::times;after frame {{exit 0}}}}','}',
        'debug set_watchpoint write_mem 0xc03c {$::started && !$::stress_done && $wp_last_value in {2 4 6}} {puts $::times "$wp_last_value $::n [machine_info time]";if {$wp_last_value==6} {if {[catch {footer} problem]} {puts stderr $problem;exit 2}}}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Flicker stress VRAM timing violation";exit 2}',
        'after time 20 {puts stderr "Flicker stress timeout";exit 2}']
    (out/'session.tcl').write_text('if {[catch {\n'+'\n'.join(lines)+'\n} problem]} {puts stderr $problem;exit 2}\n')
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'session.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=40,
            env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    raw=(out/'frames.bin').read_bytes();size=12288+slots*4+1
    if len(raw)!=frames*size:raise ValueError('Incomplete stress frames')
    phases=[];full=[0,0];bodies=[0,0];peak=0;native=None
    for n in range(frames):
        r=raw[n*size:(n+1)*size];ram=r[:12288];actual=r[12288:];phase=ram[0x7ca if outline else 0x7c0];phases.append(phase)
        state=ram[0x2000:0x3000]
        if native is None:native=state
        elif state!=native:raise ValueError('Stress test changed original native state')
        canonical=ram[0x100:0x144]+ram[0x410:0x418]+ram[0x600:0x608]+ram[0x610:0x618]
        if slots==24:canonical+=ram[0x620:0x624]
        order=permutation(slots,phase,outline)
        attrs=bytearray(b''.join(canonical[i*4:i*4+4] for i in order)+bytes((216,)))
        attrs[14*4:17*4]=ram[0x290:0x29c]
        if actual!=attrs:raise ValueError(f'Published flicker attributes/phase mismatch {n}')
        for y in range(64,80):
            chosen,count=selected(attrs,ram[0x1c],y);chosen={s for s,dy in chosen};peak=max(peak,count)
            for actor in range(2):
                full[actor]+=all(order.index(slot) in chosen for slot in (19+2*actor,20+2*actor))
                bodies[actor]+=order.index(19+2*actor) in chosen
    if any(a==b for a,b in zip(phases[2:],phases[3:])):raise ValueError('Priority rotation skipped/froze a refresh')
    if peak<=8 or min(full)<frames*16//2:raise ValueError('Stress did not demonstrate bounded actor starvation under overflow')
    if outline and min(bodies)!=frames*16:raise ValueError('A priority body was lost to scanline overflow')
    assets=load_assets(args.assets);palette=(bundle/'palette.bin').read_bytes();world,width,_=padded_world((bundle/'stage-world.bin').read_bytes())
    fuel=(bundle/'sprite-colors.bin').read_bytes()[14*16:17*16];images=0
    for path in out.glob('*.state'):
        ram=path.read_bytes();vram=path.with_suffix('.vram').read_bytes();wx=int.from_bytes(ram[0xb0:0xb2],'little',signed=True);wy=int.from_bytes(ram[0xb2:0xb4],'little',signed=True)
        numeric=header(assets,palette,int(''.join(map(str,ram[0x30c:0x312]))),int(''.join(map(str,ram[0x312:0x318]))))
        expected=compose(world,numeric,(bundle/'life.bin').read_bytes(),palette,wx+256,wy+256,width=width)
        expected=bordered(paint(expected,ram,vram,info,palette,fuel),palette)
        with Image.open(path.with_suffix('.png')) as image:actual=image.convert('RGB')
        diff=ImageChops.difference(actual,expected)
        if diff.getbbox():
            expected.save(path.with_name(path.stem+'-expected.png'));diff.save(path.with_name(path.stem+'-diff.png'))
            raise ValueError(f'Stress RGB mismatch {path.stem}: {diff.getbbox()}')
        images+=1
    periods={};target=info['timing']['frame_seconds']*1000
    rows=[r.split() for r in (out/'times.tsv').read_text().splitlines()]
    for kind in ('2','4','6'):
        values=[float(r[2]) for r in rows if r[0]==kind and int(r[1])>=3];delta=[(b-a)*1000 for a,b in zip(values,values[1:])]
        if not delta or max(abs(d-target) for d in delta)>.6:raise ValueError(f'Stress refresh missed {kind}: {max(delta,default=0):.3f}ms')
        periods[kind]=dict(median_ms=statistics.median(delta),minimum_ms=min(delta),maximum_ms=max(delta))
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:raise ValueError('BIOS changed')
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),display_frames=frames,rgb_images=images,
        nominal_hz=info['timing']['nominal_hz'],candidate_line_peak=peak,actual_limit=8,
        full_two_plane_enemy_scanline_fraction=[v/(frames*16) for v in full],periods=periods,
        enemy_body_scanline_fraction=[v/(frames*16) for v in bodies],
        setup_writes_native_positions=True,native_simulation_frozen=True,strict_vram_timing=True,
        scope=('Paused sprite-overflow stress: independent body/black masks, four buffered priorities, complete RGB and EC, bodies never culled. No moving gameplay acceptance.' if outline else
               'Paused sprite-overflow stress: original graphics, two actual SAT orders, complete RGB, fixed maze, CC/EC and bounded flicker. No moving gameplay acceptance.')))
    verify_manifest(bundle);require_ignored(root,[p for p in out.rglob('*') if p.is_file()]);seal(out)
    print(f'{frames} flicker stress frames and {images} full RGB: {out}/report.json')
