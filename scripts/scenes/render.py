"""Pinned Rally-X tile/object mixer, including pen-level shadow semantics."""
from dataclasses import dataclass
from PIL import Image
from .bundle import Assets, Capture

WIDTH, HEIGHT = 288, 224


@dataclass
class Object:
    kind: str
    id: int
    code: int
    rect: tuple[int,int,int,int]
    colors: bytes  # indirect indices; 255 is transparent


@dataclass
class Frame:
    image: Image.Image
    indices: bytes
    background: bytes
    shadow: bytes
    priority: bytes
    objects: list[Object]


def render(capture: Capture, assets: Assets) -> Frame:
    ram, radar = capture.video, capture.radar
    regs = capture.state['registers']
    flip = regs['flip']
    lookup, rgb = assets.palette['lookup'], assets.palette['rgb']
    pens = [0]*(WIDTH*HEIGHT)
    priority = bytearray(WIDTH*HEIGHT)
    tiledata = assets.pixels['tiles']
    for y in range(HEIGHT):
        native_y = y+16
        for x in range(WIDTH):
            foreground = x < 64 if flip else x >= 224
            tw = 64 if foreground else 256
            sx = 0 if foreground else regs['scroll_x']
            sy = 0 if foreground else regs['scroll_y']
            dx = 0 if foreground else 3
            if flip:
                # tilemap effective_scroll uses visible-area centre extents 288,256,
                # then the flipped pixmap addresses reverse both axes.
                px = (x-(288-tw-dx+sx)) % tw
                py = (native_y-sy) % 256
                px,py = tw-1-px,255-py
            else:
                px,py = (x+sx-dx)%tw,(native_y+sy)%256
            address = (py//8)*32 + px//8 + (0 if foreground else 0x400)
            attr, code = ram[address+0x800], ram[address]
            tx,ty = px%8,py%8
            if not attr & 0x40:
                tx = 7-tx
            if attr & 0x80:
                ty = 7-ty
            offset = y*WIDTH+x
            pens[offset] = (attr & 0x3f)*4+tiledata[code*64+ty*8+tx]
            priority[offset] = (attr>>5)&1
    background = bytes(lookup[p] for p in pens)
    objects = []
    dots = []
    for offset in range(0x14,0x20):
        attr = radar[offset & 15]
        x = ram[0x20+offset]+((~attr & 1)<<8)-(3 if flip else 0)
        y = 253-ram[0x820+offset]-16
        code = ((attr & 14)>>1)^7
        source = assets.pixels['dots'][code*16:(code+1)*16]
        colors = bytes(255 if p==3 else 16+p for p in source)
        obj = Object('dot',offset,code,(x,y,x+4,y+4),colors)
        objects.append(obj); dots.append((obj,source))
        for iy in range(4):
            for ix in range(4):
                pen=source[iy*4+ix]; ox,oy=x+ix,y+iy
                if pen != 3 and 0<=ox<WIDTH and 0<=oy<HEIGHT:
                    pens[oy*WIDTH+ox]=256+pen
    for offset in range(0x1e,0x13,-2):
        flags,attr=ram[offset],ram[0x801+offset]
        x=ram[offset+1]+((attr & 0x80)<<1)
        y=241-ram[0x800+offset]-16
        code=flags>>2
        source=assets.pixels['sprites'][code*256:(code+1)*256]
        colors=bytearray([255]*256)
        for iy in range(16):
            for ix in range(16):
                tx=15-ix if flags&1 else ix
                ty=15-iy if flags&2 else iy
                pen=(attr&63)*4+source[ty*16+tx]
                color=lookup[pen]
                if color == 0:
                    continue
                colors[iy*16+ix]=color
                ox,oy=x+ix,y+iy
                if 0<=ox<WIDTH and 0<=oy<HEIGHT:
                    index=oy*WIDTH+ox
                    if priority[index] not in (1,31):
                        pens[index]=pen
                    priority[index]=31
        objects.append(Object('sprite',offset,code,(x,y,x+16,y+16),bytes(colors)))
    for obj,source in dots:
        x,y,_,_=obj.rect
        for iy in range(4):
            for ix in range(4):
                ox,oy=x+ix,y+iy
                if source[iy*4+ix] != 3 and 0<=ox<WIDTH and 0<=oy<HEIGHT:
                    index=oy*WIDTH+ox
                    pen=pens[index]
                    # Overrides in video_start_common, otherwise default MAME shadow bank.
                    if pen < 16:
                        pens[index]=pen+16
                    elif pen < 32:
                        pass
                    elif pen < 260:
                        pens[index]=pen+260
    indices,shadow=bytearray(),bytearray()
    pixels=bytearray()
    factor=capture.state['shadow_factor']
    for pen in pens:
        shaded=pen>=260
        base=pen-260 if shaded else pen
        color=lookup[base] if base<256 else 16+base-256
        indices.append(color); shadow.append(int(shaded))
        pixels.extend(int(channel*factor) if shaded else channel for channel in rgb[color])
    return Frame(Image.frombytes('RGB',(WIDTH,HEIGHT),bytes(pixels)),bytes(indices),
                 background,bytes(shadow),bytes(priority),objects)
