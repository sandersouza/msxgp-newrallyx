"""Live four-way keyboard rollover and original-maze wall safety regression."""
import os
import subprocess

from scripts.scenes.bundle import digest, read_json, verify_manifest
from scripts.scenes.storage import json_write, require_ignored, seal
from .build import destination
from .emulator import tcl
from .hud_verify import symbols
from .stage_one import acquire, reconstruct
from .completion_route_verify import verify_header_reservations


def smoke_capture(syms):
    """Observe the first 1,200 stress refreshes, without writing guest state."""
    return '\n'.join([
        'set throttle on;set speed 100',
        'set minframeskip 0;set maxframeskip 0;set vsync off;set pause_on_lost_focus false',
        'set gamma 1;set brightness 0;set contrast 0;set color_matrix {{1 0 0} {0 1 0} {0 0 1}}',
        'set blur 0;set noise 0;set scanline 0',
        'foreach name {motion cache presentation smoke-display smoke-counts smoke-native-rows flag-display} {set files($name) [open [file join $out "$name.bin"] wb]}',
        'set shots 0;set settled_smoke {};set settled_frames 0;set header [string repeat [binary format c 0] 12]',
        'set hudflags [binary format c* {0 1 1 1 1 1 1 1 1 1 1}]',
        'proc snapshot {} {',
        ' foreach {address length} {0xe000 4096 0xc400 96 0xc0b0 4 0xc500 11 0xc490 5 0xc5c0 3} {puts -nonewline $::files(motion) [debug read_block memory $address $length]}',
        ' foreach {name address length} {presentation 0xc49a 1 smoke-display 0xd300 2048 smoke-counts 0xdb00 32 smoke-native-rows 0xdb20 32 flag-display 0xc534 11} {puts -nonewline $::files($name) [debug read_block memory $address $length]}',
        ' puts -nonewline $::files(cache) [debug read_block VRAM 0 65536]',
        '}',
        'debug set_watchpoint write_mem 0xc000 {$::phase eq "game" && !$::skip_headers && $::n<1200 && $wp_last_value==2} {snapshot}',
        'debug set_watchpoint write_mem 0xc000 {$::n==1208 && $wp_last_value==2} {set throttle off;set renderer none}',
        f'debug set_bp {syms["Player_Radar"]} {{$::phase eq "game"}} {{set ::hudflags [debug read_block memory 0xc500 11]}}',
        'debug set_watchpoint write_mem 0xc03c {$::phase eq "game" && $wp_last_value==2} {set ::header [debug read_block memory 0xc30c 12]}',
        'proc capture {n} {screenshot -raw -size auto [file join $::out "$n.png"]}',
        'debug set_watchpoint write_mem 0xc03c {$::phase eq "game" && !$::skip_headers && $::n<1200 && $wp_last_value==6} {',
        # Clouds intentionally publish by rows. Full-image comparisons use a
        # settled publication; all refreshes still face the strict header check.
        ' set published [debug read_block memory 0xd300 2048]',
        ' if {$published eq $::settled_smoke} {incr ::settled_frames} else {set ::settled_frames 0};set ::settled_smoke $published',
        ' if {$::n%8==0 && $::settled_frames>=2 && ![debug read memory 0xc70e]} {',
        '  set shot [incr ::shots]',
        '  foreach {ext data} [list state [debug read_block memory 0xc000 12288] vram [debug read_block VRAM 0 131072] hudflags $::hudflags header $::header] {set f [open [file join $::out "$shot.$ext"] wb];puts -nonewline $f $data;close $f}',
        '  after frame [list after time 0.001 [list capture $shot]]',
        ' }',
        '}',
        'set VDP.too_fast_vram_access_callback {puts stderr "Smoke stress VRAM timing violation";exit 2}',
    ])


def verify(root, args):
    bundle=args.rom.parent
    verify_manifest(bundle)
    info=read_json(bundle/'build.json')
    if not info.get('session') or not info['hud_enabled']:
        raise ValueError('Steering regression requires the full stage12 HUD')
    out=destination(root,args.output)
    out.mkdir(parents=True)
    require_ignored(root,[out/'board.bin'])
    program,reference=acquire(root)
    board,_,_=reconstruct(program,reference)
    (out/'board.bin').write_bytes(board)
    syms=symbols(bundle/'raster-scroll.sym')
    script=(root/'scripts/msx/steering_probe.tcl').read_text()
    for key,value in dict(BIOS=tcl(args.bios.resolve()), MAPPER=tcl(root/'scripts/msx/mapper_reference.tcl'),
                          ROM=tcl(args.rom.resolve()), OUTPUT=tcl(out),
                          AFTER_ROCK=str(syms['Player_AfterRock']), SHOW_SCENE=str(syms['show_scene']),
                          SMOKE_STRESS=str(int(args.smoke_stress))).items():
        script=script.replace('@'+key+'@',value)
    if args.smoke_stress and not args.headless:
        script=script.replace('set renderer none\n','')+'\n'+smoke_capture(syms)+'\n'
    (out/'steering.tcl').write_text(script)
    bios={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}
    with (out/'emulator.log').open('w') as log:
        subprocess.run([args.openmsx,'-script',str(out/'steering.tcl')],check=True,timeout=120,
                       stdout=log,stderr=subprocess.STDOUT,
                       env=dict(os.environ,OPENMSX_HOME=str(out/'home'),OPENMSX_USER_DATA=str(out/'userdata')))
    frames,checked,games,blocks,key_checks=map(int,(out/'summary.tsv').read_text().split())
    rows=[list(map(int,l.split())) for l in (out/'movement.tsv').read_text().splitlines()]
    if frames!=16000 or len(rows)!=checked or checked<8000 or games<1 or blocks<1 or key_checks<20:
        raise ValueError('Incomplete steering/wall exercise')
    if any(len(r)!=10 or not 0<=r[2]<1792 or board[r[2]]!=r[3] or r[3]&248 for r in rows):
        raise ValueError('A native player contact cell entered the original maze wall')
    poses=len({tuple(r[4:8]) for r in rows if r[0]>5000})
    if poses<100:
        raise ValueError('The car stopped exploring after its first corner protection')
    smoke_rows=[list(map(int,l.split())) for l in (out/'smoke.tsv').read_text().splitlines()]
    placements=sum(max(0,b[1]-a[1]) for a,b in zip(smoke_rows,smoke_rows[1:]))
    if args.smoke_stress and placements<20:
        raise ValueError('Missing repeated real-keyboard smoke placements')
    headers=verify_header_reservations(out/'headers.tsv',info['timing']['frame_seconds'])
    cache_frames=images=smoke_images=0
    if args.smoke_stress and not args.headless:
        from .lives_route_verify import check_cache_frames
        from .death_verify import verify_images
        cache_frames=check_cache_frames(root,bundle,out)
        images=verify_images(args,out)
        smoke_images=sum(any(p.read_bytes()[0x1300:0x1b00]) for p in out.glob('*.state'))
        if cache_frames<1000 or images<25 or smoke_images<20:
            raise ValueError('Incomplete smoke bitmap/RGB observation window')
    if bios!={str(p):digest(p) for p in args.bios.rglob('*') if p.is_file()}:
        raise ValueError('Steering proof changed BIOS files')
    verify_manifest(bundle)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),keyboard_only=True,
        msx_game_state_writes=False,hud_enabled=True,refreshes=frames,
        original_maze_contact_checks=checked,played_games=games,blocked_corner_steps=blocks,
        explicit_newest_direction_checks=key_checks,
        repeated_space_smoke=bool(args.smoke_stress),smoke_placements=placements,
        complete_visible_cache_frames=cache_frames,full_rgb_images=images,
        settled_smoke_rgb_images=smoke_images,
        header_reservations=headers,
        distinct_poses_after_refresh5000=poses,
        scope='Real keyboard16-way combinations and rapid reversals; exactly one native direction; no wall-center entry or frozen corner; standard guest Z80/VDP timing'))
    require_ignored(root,[p for p in out.rglob('*') if p.is_file()])
    seal(out)
    print(f'Steering: {frames} refreshes,{checked} maze checks,{blocks} protected steps: {out}/report.json')
