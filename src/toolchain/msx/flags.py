"""Original flag records and compact persistent collection address encoding."""


def records(video, cells):
    pointer=int.from_bytes(video[0x992:0x994],'little')-0x8000
    if not 0<=pointer<=4096-20:raise ValueError('Invalid original flag table')
    addresses=[int.from_bytes(video[pointer+i:pointer+i+2],'little') for i in range(0,20,2)]
    if len(set(addresses))!=10 or any(not 0x9800<=a<0x9f00 for a in addresses):
        raise ValueError('Invalid original flag addresses')
    kinds=[cells[a-0x9800] for a in addresses]
    if kinds!=[1]*8+[4,2]:raise ValueError('Original flag type/order changed')
    ordered=sorted(addresses)
    return [dict(address=a,kind=kind,hud_slot=ordered.index(a),
                 tile_x=(a-0x9800)%32*3+3,tile_y=(a-0x9800)//32*3+3)
            for a,kind in zip(addresses,kinds)]


def encode_owners(banks, flags):
    """Mark only flag tiles: source-X bit0, source-Y high nibble = slot+1.

    Exact source Y is recovered from its low nibble plus the fixed atlas origin
    16. Ordinary tiles retain their existing addresses and take one cheap test.
    """
    if len(banks)!=4:raise ValueError('Flag owners require the two-row XY atlas')
    data=bytearray(b''.join(banks));occupied=set()
    for index,flag in enumerate(flags,1):
        for dy in range(3):
            for dx in range(3):
                x,y=flag['tile_x']+dx,flag['tile_y']+dy
                if not 0<=x<102 or not 0<=y<174 or (x,y) in occupied:
                    raise ValueError('Flag tile ownership is out of bounds or overlaps')
                occupied.add((x,y));at=y*256+x*2
                if data[at]&7 or data[at+1] not in (16,24):raise ValueError('Invalid atlas source coordinates')
                data[at]|=1;data[at+1]=(index<<4)|(data[at+1]&15)
    return [bytes(data[i:i+16384]) for i in range(0,len(data),16384)]


def verify_display_snapshots(logical,display,ticks):
    """Require exactly the preceding logical snapshot, including reset boundaries."""
    if len(logical)!=len(display) or len(logical)!=len(ticks)*11 or not ticks:
        raise ValueError('Incomplete flag presentation snapshots')
    for i,tick in enumerate(ticks):
        source=i if i==0 or tick<ticks[i-1] else i-1
        if display[i*11:(i+1)*11]!=logical[source*11:(source+1)*11]:
            raise ValueError(f'Flag presentation exceeded one refresh at frame {i}')
