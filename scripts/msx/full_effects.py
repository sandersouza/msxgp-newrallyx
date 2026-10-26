"""Observe native collection/smoke through their actual display publication."""
from .smoke import published_tiles
from . import sprite_radar as radar

RAM_BYTES = 12288
PATTERN_BYTES = 768
RECORD_BYTES = RAM_BYTES + PATTERN_BYTES


def trace(syms):
    return [
        'set effects_state [open [file join $out effects.bin] wb]',
        'set effects_times [open [file join $out effects-times.tsv] w]',
        'set effects_uploads [open [file join $out effects-uploads.tsv] w]',
        'debug set_watchpoint write_mem 0xc000 {$wp_last_value==2 && $::phase eq "game"} {',
        ' puts $::effects_times [machine_info time]',
        ' puts -nonewline $::effects_state [debug read_block memory 0xc000 12288]',
        ' puts -nonewline $::effects_state [debug read_block VRAM 0x1f8a0 768]',
        '}',
        f'debug set_bp {syms["Radar_UploadCell"]} {{[info exists ::phase] && $::phase eq "game" && ![debug read memory {syms["Radar_Initializing"]}]}} {{',
        f' puts $::effects_uploads "[machine_info time] [debug read memory {syms["ticks"]}] [debug read memory {syms["Radar_Scanned"]}]"',
        '}',
    ]


def visible_smoke(state):
    """Live native tiles inside the presented maze; ring coordinates wrap at 256."""
    left,top=state[0x702:0x704]
    wx=int.from_bytes(state[0xb0:0xb2],'little',signed=True)//8
    wy=int.from_bytes(state[0xb2:0xb4],'little',signed=True)//8
    for at,code in enumerate(state[0x2400:0x2800]):
        if not 189<=code<198:continue
        x=(left+((at%32+3-left)&31))&255
        y=(top+((at//32+10-top)&31))&255
        if x<102 and y<174 and ((x-wx)&255)<32 and ((y-wy)&255)<26:
            yield x,y,code-189


def mask_pixel(data,x,y):
    column=x//16;band=(y-column+2)//15
    cell=band*3+column;rx=x%16;ry=y-(band*15+column-2)
    if not (0<=column<3 and 0<=band<4 and 0<=ry<15):return False
    return bool(data[cell*32+rx//8*16+ry] & (128>>(rx&7)))


def analyze(directory,syms,*,maximum_flag_ms=250,maximum_smoke_ms=200):
    times=[float(v) for v in (directory/'effects-times.tsv').read_text().splitlines()]
    raw=(directory/'effects.bin').read_bytes()
    if not times or len(raw)!=len(times)*RECORD_BYTES:raise ValueError('Incomplete effects trace')
    flags_pending={};smoke_pending={};seen_flags=set();seen_smoke=set();scope=None
    flag_max=smoke_max=0.0;pixel_checks=0;retired_unpublished=0
    for i,now in enumerate(times):
        record=raw[i*RECORD_BYTES:(i+1)*RECORD_BYTES];state=record[:RAM_BYTES]
        if state[0x7d0] or state[0x490] or state[0x724]:
            flags_pending.clear();smoke_pending.clear();continue
        board=(state[0x21b0],state[0x7ec],state[0x1fd0:0x1fe4])
        if board!=scope:
            flags_pending.clear();smoke_pending.clear();scope=board
        def ram(name,size):
            at=syms[name]-0xc000;return state[at:at+size]
        points=list(zip(board[2][::2],board[2][1::2]))
        active=state[0x501:0x50b]
        base=ram('Radar_Base',384);hud=ram('hud_flags',20)
        published=ram('Radar_PublishedPoints',192)
        staged=ram('Radar_StagedPoints',192)
        # White frame/remaining flags can legitimately share the same pixels.
        remaining=radar.bitmap([p for j,p in enumerate(points) if active[j]])
        for j,(x,y) in enumerate(points):
            if active[j]:continue
            seen_flags.add((board,j));bad=hud[j*2:j*2+2]!=b'\xff\xff'
            for py in (y,y+1):
                for px in (x,x+1):
                    if remaining[py*radar.WIDTH+px]:continue
                    bad |= mask_pixel(base,px,py)
                    cell=(py-px//16+2)//15*3+px//16
                    # A red enemy may cover a removed white flag. Pending and
                    # committed snapshots straddle the last publication cell.
                    enemy_points=published[cell*16+2:cell*16+16]+staged[cell*16+2:cell*16+16]
                    if any(ex<=px<ex+2 and ey<=py<ey+2 for ex,ey in zip(enemy_points[::2],enemy_points[1::2]) if ex!=255):continue
                    bad |= mask_pixel(record[RAM_BYTES:],px,py)
                    pixel_checks+=1
            if bad:
                start=flags_pending.setdefault(j,now);flag_max=max(flag_max,(now-start)*1000)
            elif j in flags_pending:
                flag_max=max(flag_max,(now-flags_pending.pop(j))*1000)
        actual=set(published_tiles(state[0x1300:0x1b00]));live=set(visible_smoke(state))
        current={}
        for tile in live:
            seen_smoke.add((board,tile))
            if tile in actual:
                if tile in smoke_pending:smoke_max=max(smoke_max,(now-smoke_pending[tile])*1000)
                continue
            start=smoke_pending.get(tile,now);current[tile]=start
            smoke_max=max(smoke_max,(now-start)*1000)
        retired_unpublished+=len(set(smoke_pending)-live-actual)
        smoke_pending=current
    result=dict(samples=len(times),collected_flags=len(seen_flags),radar_pixel_checks=pixel_checks,
        visible_smoke_tiles=len(seen_smoke),maximum_flag_lag_ms=flag_max,
        maximum_smoke_lag_ms=smoke_max,unpublished_tiles_leaving_view=retired_unpublished,
        maximum_flag_ms=maximum_flag_ms,maximum_smoke_ms=maximum_smoke_ms,
        smoke_observed=bool(seen_smoke),
        passed=bool(seen_flags) and flag_max<=maximum_flag_ms and smoke_max<=maximum_smoke_ms,
        scope='Natural native flags versus HUD/base/actual radar masks; live visible smoke versus published tiles. Enemy-overlapped radar pixels excluded. Durations are sampled foreground observations, not physical frame latency.')
    if (directory/'effects-uploads.tsv').exists():
        uploads=[line.split() for line in (directory/'effects-uploads.tsv').read_text().splitlines()]
        invalid=sum(int(row[2]) not in (1,2,3) for row in uploads)
        duplicate=sum(a[1]==b[1] and float(b[0])-float(a[0])<0.02 for a,b in zip(uploads,uploads[1:]))
        result.update(radar_publications=len(uploads),unsafe_publications=invalid,
                      repeated_publications_in_refresh=duplicate)
        result['passed'] &= not (invalid or duplicate)
    return result
