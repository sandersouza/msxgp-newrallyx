"""Two-color 8x8 scenery codec and independent SCREEN 4 cache decoding."""
from collections import Counter
from .raster_scroll import palette_rgb


def encode(world,palette,*,width=816,height=1392):
    if len(world)!=width*height or width%8 or height%8:
        raise ValueError('Tile scenery needs complete 8x8 cells')
    rgb=palette_rgb(palette);adapted=bytearray(world);patterns=[];colors=[]
    ids=bytearray(32768);unique={};changed=0
    for ty in range(height//8):
        for tx in range(width//8):
            bits=bytearray();inks=bytearray()
            for row in range(8):
                at=(ty*8+row)*width+tx*8;original=world[at:at+8]
                kept=[color for color,_ in Counter(original).most_common(2)]
                bg=kept[0];fg=kept[-1]
                selected=bytes(color if color in kept else min(kept,key=lambda k:
                    sum((a-b)**2 for a,b in zip(rgb[color],rgb[k]))) for color in original)
                changed+=sum(a!=b for a,b in zip(original,selected))
                adapted[at:at+8]=selected
                bits.append(sum(int(color==fg)<<(7-x) for x,color in enumerate(selected)))
                inks.append(fg*16+bg)
            key=(bytes(bits),bytes(inks))
            if key not in unique:
                unique[key]=len(patterns);patterns.append(key[0]);colors.append(key[1])
            ids[ty*128+tx]=unique[key]
    if len(patterns)>256:raise ValueError('SCREEN 4 scenery exceeds 256 tile patterns')
    pg=b''.join(patterns)+bytes(2048-len(patterns)*8)
    ct=b''.join(colors)+bytes(2048-len(colors)*8)
    return dict(world=bytes(adapted),patterns=pg*4,colors=ct*4,
                banks=[bytes(ids[:16384]),bytes(ids[16384:])],tiles=len(patterns),changed_pixels=changed)


class CacheDecoder:
    """Validate immutable pattern/color tables, then decode changed name entries."""
    def __init__(self,patterns,colors):
        if len(patterns)!=8192 or len(colors)!=8192:raise ValueError('Four tile groups required')
        self.patterns,self.colors=patterns,colors
        self.previous=None;self.bitmap=bytearray(65536)
        self.rows={}
        for group in range(4):
            for tile in range(256):
                for row in range(8):
                    at=group*2048+tile*8+row;bits=patterns[at];ink=colors[at]
                    values=[ink>>4 if bits&(128>>x) else ink&15 for x in range(8)]
                    self.rows[group,tile,row]=bytes(values[x]*16+values[x+1] for x in range(0,8,2))

    def decode(self,vram):
        if vram[:8192]!=self.patterns or vram[0x4000:0x6000]!=self.colors:
            raise ValueError('SCREEN 4 scenery pattern/color tables changed')
        names=vram[0x2000:0x2400]+vram[0xa000:0xa400]
        if len(names)!=2048:raise ValueError('Incomplete SCREEN 4 cache capture')
        for n,tile in enumerate(names):
            if self.previous is not None and tile==self.previous[n]:continue
            page,entry=divmod(n,1024);ty,tx=divmod(entry,32)
            for row in range(8):
                at=page*32768+(ty*8+row)*128+tx*4
                self.bitmap[at:at+4]=self.rows[ty//8,tile,row]
        self.previous=names
        return self.bitmap
