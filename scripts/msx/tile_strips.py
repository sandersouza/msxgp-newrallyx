"""Exact three-tile SCREEN5 strips for the original 24-pixel world cells."""
from .screen5 import packed


def encode(world,*,width=816,height=1392,origins=(544,768),cells=1):
    if len(world)!=width*height or width%24 or height%24 or cells not in (1,2):
        raise ValueError('Strip atlas requires complete 24-pixel cells')
    result={}
    for axis in ('horizontal','vertical'):
        horizontal=axis=='horizontal'
        columns,rows=(width//24-cells+1,height//8) if horizontal else (width//8,height//24-cells+1)
        tw,th=(24*cells,8) if horizontal else (8,24*cells)
        unique=[];indices={};ids=[]
        for row in range(rows):
            for column in range(columns):
                x,y=(column*24,row*8) if horizontal else (column*8,row*24)
                tile=b''.join(world[(y+r)*width+x:(y+r)*width+x+tw] for r in range(th))
                if tile not in indices:indices[tile]=len(unique);unique.append(tile)
                ids.append(indices[tile])
        per_row=256//tw
        atlas_height=((len(unique)+per_row-1)//per_row)*th
        atlas=bytearray(256*atlas_height)
        for n,tile in enumerate(unique):
            for r in range(th):
                start=(n//per_row*th+r)*256+n%per_row*tw
                atlas[start:start+tw]=tile[r*tw:(r+1)*tw]
        stride=128 if horizontal else 256
        table=bytearray(32768 if horizontal else 16384)
        origin=origins[0 if horizontal else 1]
        if origin+atlas_height>(768 if horizontal else 1000):
            raise ValueError('Strip atlas exceeds reserved VRAM')
        for row in range(rows):
            for column in range(columns):
                n=ids[row*columns+column];at=row*stride+column*2
                table[at:at+2]=bytes((n%per_row*tw,(origin+n//per_row*th)&255))
        result[axis]=dict(table=bytes(table),pixels=packed(atlas),unique=len(unique),
                          vram=origin*128,height=atlas_height)
    return result


def candidates(banks, *, columns=102, rows=174):
    """Tag aligned mixed strips; a solid three-tile fill keeps the cheaper HMMV.

    Source-X bit2 is horizontal eligibility; source-Y bit0 is vertical.
    Owner entries and the exact source pixels remain untouched.
    """
    data=bytearray(b''.join(banks))
    if len(data)!=65536 or columns%3 or rows%3:
        raise ValueError('Strip candidates require the complete XY table')
    def eligible(offsets):
        values=[data[at] for at in offsets]
        return not any(v&1 for v in values) and not (
            all(v&2 for v in values) and len({v>>4 for v in values})==1)
    for y in range(rows):
        for x in range(columns):
            at=y*256+x*2
            if data[at]&1:continue
            if x%3==0 and eligible((at,at+2,at+4)):data[at]|=4
            if y%3==0 and eligible((at,at+256,at+512)):data[at+1]|=1
    return [bytes(data[i:i+16384]) for i in range(0,65536,16384)]


def encode_cells(world,*,width=816,height=1392,origin=584):
    """Exact complete original cells, indexed on a 128-byte row stride."""
    if len(world)!=width*height or width%24 or height%24:
        raise ValueError('Complete-cell atlas requires complete 24-pixel cells')
    unique=[];indices={};ids=[]
    for y in range(0,height,24):
        for x in range(0,width,24):
            image=b''.join(world[(y+r)*width+x:(y+r)*width+x+24] for r in range(24))
            if image not in indices:indices[image]=len(unique);unique.append(image)
            ids.append(indices[image])
    rows=(len(unique)+9)//10*24
    if origin+rows>768:raise ValueError('Complete-cell atlas exceeds reserved VRAM')
    atlas=bytearray(256*rows);table=bytearray(32768)
    for n,image in enumerate(unique):
        for r in range(24):
            at=(n//10*24+r)*256+n%10*24;atlas[at:at+24]=image[r*24:r*24+24]
    for y in range(height//24):
        for x in range(width//24):
            n=ids[y*(width//24)+x];at=y*128+x*2
            image=unique[n]
            table[at:at+2]=(bytes((1,image[0]*17)) if image.count(image[:1])==len(image) else
                bytes((n%10*24,(origin+n//10*24)&255)))
    return dict(table=bytes(table),pixels=packed(atlas),height=rows,unique=len(unique),vram=origin*128)
