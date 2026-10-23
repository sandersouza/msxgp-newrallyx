"""Independent priority permutation and mode-2 eight-sprite scanline model."""
from .display import DISPLAY_SHIFT
from .raster_scroll import palette_rgb


def permutation(slots,phase):
    if slots not in (23,24) or phase not in (0,1):raise ValueError('Unsupported flicker layout/phase')
    order=list(range(slots))
    if phase:order[6:10],order[19:23]=order[19:23],order[6:10]
    return order


def selected(attrs,scroll,y):
    """Transparent patterns and CC planes consume slots, irrespective of ink."""
    visible=[]
    for slot in range(len(attrs)//4):
        ay=attrs[slot*4]
        if ay==216:break
        dy=(y+scroll-ay-1)&255
        if dy<16:visible.append((slot,dy))
    return visible[:8],len(visible)


def paint(image,ram,vram,info,palette,body_fuel_colors):
    """Overlay actual SAT/pattern scanout on an independently generated maze.

    The caller captures VRAM at the footer; recover body fuel attrs/colors from
    canonical RAM/resources because the footer reuses those same three slots.
    """
    slots=info['sprites']['total_slots'];fuel=info['sprites']['life_reuses_fuel_slots'][0]
    footer=bytearray(vram[0x1f600:0x1f600+slots*4]);body=bytearray(footer)
    if info['hud_enabled']:body[fuel*4:(fuel+3)*4]=ram[0x280:0x28c]
    colors=bytearray(vram[0x1f400:0x1f400+slots*16]);body_colors=bytearray(colors)
    if info['hud_enabled']:body_colors[fuel*16:(fuel+3)*16]=body_fuel_colors
    rgb=palette_rgb(palette);scroll=ram[0x1c]
    for y in range(info.get('enemy_logic',{}).get('sprite_body_top',12),212):
        attrs,row_colors=(footer,colors) if y>=176 else (body,body_colors)
        chosen,_=selected(attrs,scroll,y);groups=[]
        for slot,dy in chosen:
            ax,pattern=attrs[slot*4+1:slot*4+3];color=row_colors[slot*16+dy]
            if not color&64:groups.append([])
            if groups:groups[-1].append((ax-(32 if color&128 else 0),pattern,dy,color&15))
        for group in reversed(groups):
            ink={}
            for ax,pattern,dy,color in group:
                if not color:continue
                base=0x1f800+(pattern&252)*8
                for dx in range(16):
                    if 8<=ax+dx<256 and vram[base+dy+(16 if dx>=8 else 0)]&(128>>(dx&7)):
                        ink[ax+dx]=ink.get(ax+dx,0)|color
            for x,color in ink.items():
                sx=x+DISPLAY_SHIFT
                if 0<=sx<256:image.putpixel((sx,y),rgb[color])
    return image
