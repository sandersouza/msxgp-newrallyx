"""Detect persistent duplicate enemy markers in actual radar pattern memory."""
from .full_effects import RAM_BYTES,RECORD_BYTES,mask_pixel


def displayed_anchors(record,syms):
    state=record[:RAM_BYTES];patterns=record[RAM_BYTES:]
    def ram(name,size):
        at=syms[name]-0xc000;return state[at:at+size]
    published=ram('Radar_PublishedPoints',192)
    staged=ram('Radar_StagedPoints',192)
    pending=ram('Radar_PendingCell',1)[0]
    base=ram('Radar_Base',384);shown=[set() for _ in range(7)]
    for cell in range(12):
        points=(staged if cell==pending else published)[cell*16:cell*16+16]
        ox=cell%3*16;oy=cell//3*15+cell%3-2
        for i,(x,y) in enumerate(zip(points[2::2],points[3::2])):
            if x==255:continue
            pixels=[(px,py) for py in (y,y+1) for px in (x,x+1)
                    if ox<=px<ox+16 and oy<=py<oy+15 and 0<=py<58]
            if any(mask_pixel(patterns,px,py) and not mask_pixel(base,px,py) for px,py in pixels):
                shown[i].add((x,y))
    return shown


def duplicated(points):
    """Adjacent one-pixel fragments at a cell seam represent one moving dot."""
    return any(abs(x-a)>1 or abs(y-b)>1 for x,y in points for a,b in points)


def unattributed_bits(record,syms):
    """Pattern ink must belong to the frame/flags or a published actor pose."""
    state=record[:RAM_BYTES]
    def ram(name,size):
        at=syms[name]-0xc000;return state[at:at+size]
    known=bytearray(ram('Radar_Base',384));pending=ram('Radar_PendingCell',1)[0]
    published=ram('Radar_PublishedPoints',192);staged=ram('Radar_StagedPoints',192)
    def plot(cell,x,y):
        ox=cell%3*16;oy=cell//3*15+cell%3-2
        if ox<=x<ox+16 and oy<=y<oy+15 and 0<=y<58:
            rx=x-ox;known[cell*32+rx//8*16+y-oy]|=128>>(rx&7)
    for cell in range(12):
        points=(staged if cell==pending else published)[cell*16:cell*16+16]
        for x,y in zip(points[2::2],points[3::2]):
            if x!=255:
                for px in (x,x+1):
                    for py in (y,y+1):plot(cell,px,py)
        # Flag removal/blink is checked independently with its own deadline.
        for x,y in zip(state[0x1fd0:0x1fe4:2],state[0x1fd1:0x1fe4:2]):
            for px in (x,x+1):
                for py in (y,y+1):plot(cell,px,py)
    return {(i,bit) for i,(actual,expected) in enumerate(zip(record[RAM_BYTES:RAM_BYTES+384],known))
            for bit in range(8) if actual & ~expected & (1<<bit)}


def analyze(directory,syms,*,maximum_ghost_ms=200):
    times=[float(v) for v in (directory/'effects-times.tsv').read_text().splitlines()]
    data=(directory/'effects.bin').read_bytes()
    if not times or len(data)!=len(times)*RECORD_BYTES:raise ValueError('Incomplete radar motion trace')
    ages={};unknown_ages={};scope=None;maximum=unknown_max=0.0
    ghost_samples=unknown_samples=phase_mismatches=peak=active=0;counts={}
    for i,now in enumerate(times):
        record=data[i*RECORD_BYTES:(i+1)*RECORD_BYTES];state=record[:RAM_BYTES]
        board=(state[0x21b0],state[0x7ec])
        if board!=scope or state[0x7d0] or state[0x490] or state[0x724]:
            ages.clear();unknown_ages.clear();scope=board;continue
        active+=1
        count=state[0x224e];counts[count]=counts.get(count,0)+1
        normal=record[RAM_BYTES:RAM_BYTES+384]
        shifted=b''.join(b'\0'+normal[at:at+15] for at in range(0,384,16))
        phase_mismatches+=shifted!=record[RAM_BYTES+384:]
        shown=displayed_anchors(record,syms)
        peak=max(peak,max(map(len,shown)))
        for actor,points in enumerate(shown):
            if duplicated(points):
                ghost_samples+=1;start=ages.setdefault(actor,now)
                maximum=max(maximum,(now-start)*1000)
            elif actor in ages:
                maximum=max(maximum,(now-ages.pop(actor))*1000)
        unknown=unattributed_bits(record,syms)
        unknown_samples+=bool(unknown)
        for bit in unknown:
            start=unknown_ages.setdefault(bit,now);unknown_max=max(unknown_max,(now-start)*1000)
        for bit in set(unknown_ages)-unknown:
            unknown_max=max(unknown_max,(now-unknown_ages.pop(bit))*1000)
    return dict(active_samples=active,enemy_count_samples=counts,duplicate_actor_samples=ghost_samples,
        maximum_ghost_ms=maximum,maximum_allowed_ms=maximum_ghost_ms,
        unknown_ink_samples=unknown_samples,maximum_unknown_ink_ms=unknown_max,
        shifted_pattern_mismatches=phase_mismatches,
        maximum_displayed_positions_per_enemy=peak,
        passed=maximum<=maximum_ghost_ms and unknown_max<=maximum_ghost_ms and not phase_mismatches,
        scope='Actual radar pattern bits and per-cell committed/staged actor poses. One-pixel seam fragments are allowed; persistent distinct positions of one enemy are not.')
