"""Dirty-cell lookup and independent row-color oracle for the twelve-sprite radar."""
from . import sprite_radar as radar


def base_variants(flags,*,border=True,square=True):
    """Four exact base masks per cell; this board has at most two flags/cell."""
    variants=bytearray();offsets=bytearray()
    for cell in range(12):
        ox,oy=cell%3*16,cell//3*15+cell%3-2
        ids=[i for i,(x,y) in enumerate(flags) if -1<=x-ox<16 and -1<=y-oy<15]
        if len(ids)>2:raise ValueError('Compact radar base table needs more than two flag bits for a cell')
        offsets.extend([i*2 for i in ids]+[255]*(2-len(ids)))
        for mask in range(4):
            selected=[flags[i] for bit,i in enumerate(ids) if mask&(1<<bit)]
            patterns=radar.patterns(radar.bitmap(selected,border=border,square=square))
            variants.extend(patterns[cell*32:(cell+1)*32])
    return bytes(variants),bytes(offsets)


def dirty_table():
    result=bytearray()
    for y in range(64):
        for x in range(64):
            mask=0
            for dy in (0,1):
                for dx in (0,1):
                    px,py=x+dx,y+dy;column=px//16
                    relative=py-column+2
                    if px<radar.WIDTH and py<radar.HEIGHT and 0<=column<3 and 0<=relative<60:
                        mask|=1<<(relative//15*3+column)
            result.extend(mask.to_bytes(2,'little'))
    return bytes(result)


def published_cells(ram,flags,style):
    quantum=style.get('radar_marker_quantum',1)
    if quantum==2:
        for point,source in enumerate((0x93,0x95,0x638)):
            if point==0 and style.get('radar_player_sprite'):continue
            original=ram[source:source+2]
            expected=original if original[0]==255 else bytes(value//2*2 for value in original)
            if ram[0xf00+point*2:0xf02+point*2]!=expected:
                raise ValueError('Radar point differs from the declared one-pixel quantization bound')
    at=style.get('radar_marker_state_address')
    if at is None:return None
    marker=at-0xc000;visibility=style['radar_flag_state_address']-0xc000;result=[]
    for cell in range(12):
        ox,oy=cell%3*16,cell//3*15+cell%3-2
        ids=[i for i,(x,y) in enumerate(flags) if -1<=x-ox<16 and -1<=y-oy<15]
        mask=ram[visibility+cell]
        if mask>>len(ids):raise ValueError('Invalid displayed radar flag subset')
        points=ram[marker+cell*6:marker+(cell+1)*6]
        if style.get('radar_player_sprite') and points[:2]!=b'\xff\xff':
            raise ValueError('Separate player leaked into a composite radar cell')
        result.append(dict(flags=[flags[i] for bit,i in enumerate(ids) if mask&(1<<bit)],
                           player=points[:2],enemies=[points[2:4],points[4:6]]))
    return result


def queue_metrics(path,frames,limit,words=2):
    raw=path.read_bytes()
    size=words*2
    if len(raw)!=frames*size:raise ValueError('Incomplete continuous radar queue trace')
    ages=[0]*12;longest=peak=pending_frames=0
    for at in range(0,len(raw),size):
        mask=0
        for offset in range(0,size,2):mask|=int.from_bytes(raw[at+offset:at+offset+2],'little')
        if mask>>12:raise ValueError('Invalid radar dirty-cell mask')
        pending_frames+=bool(mask);peak=max(peak,mask.bit_count())
        ages=[age+1 if mask&(1<<cell) else 0 for cell,age in enumerate(ages)]
        longest=max(longest,max(ages))
        if longest>limit:raise ValueError(f'Radar cell backlog did not drain within {limit} refreshes')
    return dict(frames=frames,pending_frames=pending_frames,peak_pending_cells=peak,maximum_pending_refreshes=longest,limit_refreshes=limit)


def paint(pixels,flags,player,enemies,white,red,black,scroll,*,square=True,cells=None):
    """Compose complete cells in screen coordinates, including allowed recoloring.

    Marker colors cover three sprite rows so either sentinel phase retains the
    exact 2x2 footprint. Other white pixels sharing those rows take that color.
    """
    base=radar.bitmap(flags,square=square)
    markers=[(p,red) for p in enemies]+[(player,black)]
    for band in range(4):
        for column in range(3):
            if cells is not None:
                state=cells[band*3+column]
                base=radar.bitmap(state['flags'],square=square)
                markers=[(p,red) for p in state['enemies']]+[(state['player'],black)]
            ox,oy=column*16,band*15+column-2
            phase=int((radar.Y+oy+scroll-1)&255==216)
            colors=[white]*16
            visible=[]
            for (px,py),color in markers:
                if px==255:continue
                if -1<=px-ox<16 and -1<=py-oy<15:
                    visible.append((px,py))
                    for row in range(py-oy,py-oy+3):
                        if 0<=row<16:colors[row]=color
            for row in range(15):
                py=oy+row
                if not 0<=py<radar.HEIGHT:continue
                for sx in range(16):
                    px=ox+sx
                    if base[py*radar.WIDTH+px] or any(ax<=px<ax+2 and ay<=py<ay+2 for ax,ay in visible):
                        pixels[(radar.Y+py)*256+radar.X+px]=colors[row+phase]
