"""Original smoke geometry, terrain permission and bitmap publication oracle."""


def eligibility(original,cleared,*,width=102,height=174,stride=128):
    """Two bits/tile: original road, then road after collecting its flag."""
    if len(original)!=width*height or len(cleared)!=len(original) or width>stride or stride%4:
        raise ValueError('Invalid smoke terrain-permission geometry')
    result=bytearray(stride*height//4)
    for y in range(height):
        for x in range(width):
            at=y*width+x
            bits=sum(int(code==0x81 and bool(attr&128))<<n
                for n,(code,attr) in enumerate((original[at],cleared[at])))
            result[y*(stride//4)+x//4]|=bits<<((x&3)*2)
    return bytes(result)


def anchor(x,y,facing):
    """Tile origin from the source's physical-coordinate placement offsets."""
    offsets={0xf0:(-9,16),0xf2:(-9,-24),0xfc:(-33,-8),0xfd:(15,-8)}
    if facing not in offsets:return None
    dx,dy=offsets[facing]
    return (x+dx)//8,(y+dy)//8


def ring_index(x,y):
    return ((y-10)&31)*32+((x-3)&31)


def published_tiles(data):
    """Decode cached tile identity and smoke ink without reading VRAM pixels.

    One byte per64x32 cache tile: low nibble=smoke tile1..9, high nibble=
    world Y high three bits and world X high bit. Zero denotes no smoke.
    """
    if len(data)!=2048:raise ValueError('Incomplete smoke display-state plane')
    result=[]
    for at,v in enumerate(data):
        code=v&15
        if not code:continue
        if code>9:raise ValueError('Invalid published smoke tile')
        x=(at&63)|((v>>1)&64);y=(at//64)|((v&112)<<1)
        if not 0<=x<102 or not 0<=y<174:raise ValueError('Published smoke outside the maze')
        result.append((x,y,code-1))
    return result


def verify_publication_counts(data,counts):
    if len(data)!=2048 or len(counts)!=32:raise ValueError('Incomplete smoke publication counts')
    expected=bytes(sum(bool(v&15) for v in data[y*64:(y+1)*64]) for y in range(32))
    if expected!=counts:raise ValueError('Smoke publication row counts differ from actual tile state')


def verify_logical_rows(codes,rows):
    """Conservative positives may outlive clears; no live cloud may be skipped."""
    if len(codes)!=1024 or len(rows)!=32 or any(v not in (0,1) for v in rows):
        raise ValueError('Invalid smoke logical row presence')
    for y in range(32):
        if not rows[y] and any(189<=v<198 for v in codes[y*32:(y+1)*32]):
            raise ValueError(f'Smoke logical row {y} hides live original cloud ink')


def held_refresh_metrics(counts,motion,record_bytes):
    """A held simulation must retain native ticks and complete car motion state."""
    frames=len(counts)//2
    if len(counts)!=frames*2 or len(motion)!=frames*record_bytes or not frames:
        raise ValueError('Incomplete cache backpressure evidence')
    held=run=longest=0
    for i in range(1,frames):
        old=int.from_bytes(counts[(i-1)*2:i*2],'little')
        new=int.from_bytes(counts[i*2:(i+1)*2],'little')
        previous=motion[(i-1)*record_bytes:i*record_bytes]
        current=motion[i*record_bytes:(i+1)*record_bytes]
        if new>old:
            if new!=old+1 or current[4160:4162]!=previous[4160:4162] or current[0x68:0x80]!=previous[0x68:0x80]:
                raise ValueError(f'Cache backpressure advanced native motion at frame {i}')
            held+=1;run+=1;longest=max(longest,run)
        else:run=0
    return dict(observed_refreshes=frames,held_refreshes=held,
                percentage=100*held/frames,longest_consecutive_refreshes=longest,
                native_motion_and_tick_counter_frozen=True)


def paint(world,width,pad,data,tiles):
    """Overlay exact original 8x8 smoke tiles onto the independent world."""
    if len(tiles)!=9*64:raise ValueError('Incomplete original smoke pixels')
    for x,y,code in published_tiles(data):
        for row in range(8):
            at=(pad+y*8+row)*width+pad+x*8
            world[at:at+8]=tiles[code*64+row*8:code*64+row*8+8]
