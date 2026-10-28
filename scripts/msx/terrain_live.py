"""Observe terrain throughout a route, including transient cache corruption."""
STATE = 12288
POINTS = tuple((x, y) for y in range(4, 201, 8) for x in range(4, 248, 8))
STRIDE = STATE + len(POINTS)


def camera_bounds(path):
    """Check the visible rectangle, including the original 24-pixel border."""
    from .stage_one import WIDTH, HEIGHT
    from .display import VIEWPORT_WIDTH
    count = violations = 0; first = []
    with path.open('rb') as source:
        while row := source.read(STRIDE):
            if len(row) != STRIDE:
                raise ValueError('Incomplete live terrain observation')
            x = int.from_bytes(row[0xb0:0xb2], 'little', signed=True)
            y = int.from_bytes(row[0xb2:0xb4], 'little', signed=True)
            if not (0 <= x <= WIDTH-VIEWPORT_WIDTH and 0 <= y <= HEIGHT-201):
                violations += 1
                if len(first) < 10: first.append(dict(sample=count, camera=[x, y]))
            count += 1
    return dict(passed=count > 0 and violations == 0, samples=count,
                violations=violations, first_failures=first,
                limits=[0, WIDTH-VIEWPORT_WIDTH, 0, HEIGHT-201])


def observer():
    return [
        'set terrain_live_out [open [file join $out terrain-live.bin] wb]',
        'set terrain_latch_out [open [file join $out terrain-latch.bin] wb]',
        'proc terrain_observe {} {',
        ' set wx [u16 0xc0b0];if {$wx>=32768} {incr wx -65536}',
        ' set wy [u16 0xc0b2];if {$wy>=32768} {incr wy -65536}',
        ' terrain_capture $wx $wy $::terrain_live_out',
        '}',
        'proc terrain_capture {wx wy stream} {',
        ' if {[debug read memory 0xc7d0]!=0 || [debug read memory 0xc490] || [debug read memory 0xc49a] || [debug read memory 0xc50e] || [debug read memory 0xc70e]} {return}',
        ' set image [debug read_block VRAM 0 65536];set samples ""',
        ' for {set y 4} {$y<201} {incr y 8} {for {set x 4} {$x<248} {incr x 8} {',
        '  set px [expr {($wx+$x)&511}];set py [expr {($wy+$y)&255}]',
        '  append samples [string index $image [expr {($px/256)*32768+$py*128+($px%256)/2}]]',
        ' }}',
        ' set state [debug read_block memory 0xc000 12288]',
        ' set state [string replace $state 176 179 [binary format c* [list [expr {$wx&255}] [expr {($wx>>8)&255}] [expr {$wy&255}] [expr {($wy>>8)&255}]]]]',
        ' puts -nonewline $stream $state',
        ' puts -nonewline $stream $samples',
        ' flush $stream',
        '}',
    ]


def analyze(root, bundle, path):
    from scripts.full_game_probe import world
    from scripts.msx.player import padded_world
    from scripts.msx.stage_one import acquire
    from scripts.scenes.bundle import load_assets
    program, _ = acquire(root)
    assets = load_assets(root/'references/assets/nrallyx')
    palette = (bundle/'palette.bin').read_bytes()
    from .hud_verify import symbols
    syms=symbols(bundle/'raster-scroll.sym') if (bundle/'raster-scroll.sym').exists() else {}
    popup_data=(bundle/'flag-popup-pixels.bin').read_bytes() if syms.get('FLAG_POPUPS') else b''
    images = {}; count = checked = ignored = failed = maximum = 0; failures = []
    with path.open('rb') as source:
        while row := source.read(STRIDE):
            if len(row) != STRIDE:
                raise ValueError('Incomplete live terrain observation')
            state = row[:STATE]; video = state[0x2000:]
            def table(offset, length):
                address = int.from_bytes(video[offset:offset+2], 'little')-0xe000
                if not 0 <= address <= 4096-length:
                    raise ValueError('Live terrain object pointer is invalid')
                return video[address:address+length]
            key = (video[0x28f], video[0x2b1], video[0x2d6],
                   state[0x534:0x53f], table(0x992, 20), table(0x996, video[0x251]*2))
            if key not in images:
                images[key] = padded_world(world(program, video, state[0x534:0x53f], assets, palette))
            image, width, _ = images[key]
            wx = int.from_bytes(state[0xb0:0xb2], 'little', signed=True)
            wy = int.from_bytes(state[0xb2:0xb4], 'little', signed=True)
            px = int.from_bytes(state[0x405:0x407], 'little')
            py = int.from_bytes(state[0x407:0x409], 'little')
            mismatches = []
            for (x, y), actual in zip(POINTS, row[STATE:]):
                xx, yy = wx+x, wy+y
                smoke = state[0x1300+(yy//8 % 32)*64+(xx//8 % 64)] & 15
                if smoke or state[0x418] and px-8 <= xx < px+8 and py-8 <= yy < py+8:
                    ignored += 1; continue
                expected = image[(yy+256)*width+xx+256]
                actual = actual & 15 if xx & 1 else actual >> 4
                checked += 1
                # A cached tile can be repainted before the label expires. Accept
                # either exact original terrain or the exact authored label,
                # only inside its world rectangle. Never exclude a whole region.
                if popup_data and state[0x1fe4] and actual!=expected:
                    lx=xx-state[0x1fe6]*8;ly=yy-state[0x1fe7]*8
                    popup_source=int.from_bytes(state[0x1feb:0x1fed],'little')-syms['Popup_Pixels']
                    if 0<=lx<24 and 0<=ly<8 and 0<=popup_source<=len(popup_data)-96:
                        value=popup_data[popup_source+ly*12+lx//2]
                        label=(value&15) if lx&1 else value>>4
                        if actual==label:continue
                if actual != expected:
                    mismatches.append((x, y, actual, expected))
            if mismatches:
                failed += 1;maximum = max(maximum, len(mismatches))
                if len(failures) < 20:
                    failures.append(dict(sample=count, camera=[wx, wy], mismatches=len(mismatches), first=mismatches[:5]))
            count += 1
    if not count:
        raise ValueError('No live terrain observations')
    return dict(passed=not failures, frames=count, checked_pixels=checked,
                failed_frames=failed, maximum_mismatches=maximum,
                ignored_dynamic_pixels=ignored, first_failures=failures,
                scope='Every eligible foreground packet: an 8-pixel grid over the full maze cache, '
                      'independent original scenery oracle; exact active flag-label pixels accepted; published smoke/player patch pixels excluded. '
                      'This samples terrain VRAM, not physical scanout or every pixel.')
