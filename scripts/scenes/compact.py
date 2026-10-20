"""Experimental 56-pixel HUD: copy glyphs; reproject radar anchors, not bitmaps."""
from collections import Counter
from itertools import combinations
from PIL import Image
from .layout import Preview
from .render import Object


def project_x(x,width):
    """Project a glyph centre by 7/8, preserving its integer pixel footprint."""
    return 200+(14*(x-224)-width+8)//16


def components(buffer,rect,backdrop):
    """Find connected marker ink in a tile-layer region, without resizing it."""
    remaining={(x,y) for y in range(rect[1],rect[3]) for x in range(rect[0],rect[2])
               if buffer[y*288+x]!=backdrop}
    result=[]
    while remaining:
        start=min(remaining,key=lambda p:(p[1],p[0]))
        remaining.remove(start); pending=[start]; pixels={}
        while pending:
            x,y=pending.pop(); pixels[x,y]=buffer[y*288+x]
            for neighbour in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
                if neighbour in remaining:
                    remaining.remove(neighbour); pending.append(neighbour)
        x0=min(x for x,y in pixels); x1=max(x for x,y in pixels)+1
        y0=min(y for x,y in pixels); y1=max(y for x,y in pixels)+1
        result.append(((x0,y0,x1,y1),pixels))
    return result


class Canvas:
    def __init__(self,frame,assets,factor):
        self.frame=frame; self.assets=assets; self.factor=factor
        self.image=Image.new('RGB',(256,212))
        self.background=bytearray(256*212); self.indices=bytearray(256*212)
        self.shadow=bytearray(256*212); self.objects=[]; self.fragments=[]

    def plot(self,x,y,index,background=True,shadow=0):
        offset=y*256+x
        if background: self.background[offset]=index
        self.indices[offset]=index; self.shadow[offset]=shadow
        rgb=self.assets.palette['rgb'][index]
        self.image.putpixel((x,y),tuple(int(c*self.factor) if shadow else c for c in rgb))

    def copy(self,name,source,destination):
        sx,sy,x1,y1=source; dx,dy=destination
        width,height=x1-sx,y1-sy
        self.fragments.append(dict(name=name,source=list(source),
            destination=[dx,dy,dx+width,dy+height]))
        self.image.paste(self.frame.image.crop(tuple(source)),(dx,dy))
        for y in range(height):
            for x in range(width):
                original=(sy+y)*288+sx+x; target=(dy+y)*256+dx+x
                self.background[target]=self.frame.background[original]
                self.indices[target]=self.frame.indices[original]
                self.shadow[target]=self.frame.shadow[original]
        for obj in self.frame.objects:
            ox,oy,ox1,oy1=obj.rect
            if ox1<=sx or ox>=x1 or oy1<=sy or oy>=y1: continue
            colors=bytearray(obj.colors); w=ox1-ox
            for iy in range(oy1-oy):
                for ix in range(w):
                    if not (sx<=ox+ix<x1 and sy<=oy+iy<y1): colors[iy*w+ix]=255
            self.objects.append(Object(obj.kind,obj.id,obj.code,
                (ox+dx-sx,oy+dy-sy,ox1+dx-sx,oy1+dy-sy),bytes(colors)))


def overlaps(markers):
    pairs=[]; pixels=set()
    for (id1,ink1),(id2,ink2) in combinations(markers,2):
        common=ink1 & ink2
        if common:
            pairs.append([id1,id2]); pixels.update(common)
    return pairs,len(pixels)


def compact_radar(canvas):
    frame=canvas.frame
    source=[224,80,288,192]; destination=[200,64,256,176]
    backdrop=Counter(frame.background[y*288+x] for y in range(80,192) for x in range(224,288)).most_common(1)[0][0]
    for y in range(64,176):
        for x in range(200,256): canvas.plot(x,y,backdrop)
    original=[]; projected=[]; mobile_original=[]; mobile_projected=[]; markers=[]; clipped=[]
    # Flags are tile-layer marks, typically 2x2. Their pixels remain unchanged.
    for number,(rect,ink) in enumerate(components(frame.background,source,backdrop)):
        x,y,x1,y1=rect; width=x1-x
        if width>56:
            raise ValueError('Radar background contains a feature wider than the compact panel')
        tx=project_x(x,width); ty=y-16; identity=f'flag-{number}'
        target={(tx+px-x,ty+py-y):color for (px,py),color in ink.items()}
        if any(not (200<=px<256 and 64<=py<176) for px,py in target):
            raise ValueError('A radar background marker would be clipped')
        for (px,py),color in target.items(): canvas.plot(px,py,color)
        original.append((identity,set(ink))); projected.append((identity,set(target)))
        markers.append(dict(id=identity,source=list(rect),destination=[tx,ty,tx+width,ty+y1-y]))
    # Dynamic dots stay 4x4. Tile flags stay below the hardware-dot layer.
    for obj in frame.objects:
        x,y,x1,y1=obj.rect
        if obj.kind!='dot' or x1<=224 or x>=288 or y1<=80 or y>=192: continue
        tx=project_x(x,4); ty=y-16; colors=bytearray([255]*16)
        old_ink=set(); new_ink=set(); lost=[]
        source_pens=canvas.assets.pixels['dots'][obj.code*16:(obj.code+1)*16]
        for iy in range(4):
            for ix in range(4):
                pen=source_pens[iy*4+ix]
                if pen==3: continue
                sx,sy=x+ix,y+iy; px,py=tx+ix,ty+iy
                if not (224<=sx<288 and 80<=sy<192): continue
                old_ink.add((sx,sy))
                if 200<=px<256 and 64<=py<176:
                    canvas.plot(px,py,16+pen,background=False,shadow=1)
                    colors[iy*4+ix]=16+pen; new_ink.add((px,py))
                else: lost.append([sx,sy])
        if lost: clipped.append(dict(id=obj.id,pixels=lost))
        identity=f'dot-{obj.id}'
        original.append((identity,old_ink)); projected.append((identity,new_ink))
        mobile_original.append((identity,old_ink)); mobile_projected.append((identity,new_ink))
        canvas.objects.append(Object('dot',obj.id,obj.code,(tx,ty,tx+4,ty+4),bytes(colors)))
        markers.append(dict(id=identity,source=list(obj.rect),destination=[tx,ty,tx+4,ty+4]))
    old_pairs,old_count=overlaps(original); new_pairs,new_count=overlaps(projected)
    old_mobile,old_mobile_count=overlaps(mobile_original)
    new_mobile,new_mobile_count=overlaps(mobile_projected)
    return dict(source=source,destination=destination,anchor_scale=[7,8],
        formula='x = 200 + floor((14*(native_x-224) - glyph_width + 8)/16); y = native_y-16',
        glyphs_resized=False,markers=markers,clipped_markers=clipped,
        source_overlap_pixels=old_count,projected_overlap_pixels=new_count,
        new_overlap_pairs=[p for p in new_pairs if p not in old_pairs],
        source_mobile_overlap_pixels=old_mobile_count,projected_mobile_overlap_pixels=new_mobile_count,
        new_mobile_overlap_pairs=[p for p in new_mobile if p not in old_mobile],
        policy='Tile-layer flags and hardware dots are reprojected; full-size arcade car sprites are represented by their radar dots.')


def compose_compact(frame,capture,layout,assets):
    # Cropping is permitted only for visually empty margins, never score/life data.
    trimmed=dict(score=[(224,8,232,16),(280,16,288,24),(224,24,232,32)],
                 fuel=[(224,56,228,62),(284,56,288,62)],
                 lives=[(280,192,288,208)],round=[(264,208,272,224)])
    for name,rects in trimmed.items():
        if any(frame.image.crop(r).getbbox() is not None for r in rects):
            raise ValueError(f'Compact {name} would discard nonblank information; needs a different packing')
    canvas=Canvas(frame,assets,capture.state['shadow_factor'])
    canvas.copy('maze',layout.maze['source'],[0,0])
    for name,source,dest in [
        ('HI',[224,0,240,8],[200,0]),('SCORE',[248,0,288,8],[216,0]),
        ('high-score',[232,8,288,16],[200,8]),('player',[224,16,280,24],[200,16]),
        ('player-score',[232,24,288,32],[200,24]),('fuel-label',[228,56,284,62],[200,40]),
        ('lives',[224,192,280,208],[200,180]),
        ('ROUND',[224,208,264,224],[200,196]),('round-number',[272,208,288,224],[240,196])]:
        canvas.copy(name,source,dest)
    for rect,ink in components(frame.background,[224,62,288,64],0):
        x,y,x1,y1=rect; tx=project_x(x,x1-x)
        for (px,py),index in ink.items(): canvas.plot(tx+px-x,py-16,index)
    rows=[]
    for y in range(64,72):
        filled=[x for x in range(224,288) if frame.background[y*288+x]!=0]
        if not filled: continue
        left,right=filled[0],filled[-1]+1
        colors={frame.background[y*288+x] for x in filled}
        if (len(colors)!=1 or filled!=list(range(left,right)) or left<226 or right>286):
            raise ValueError('Compact fuel gauge requires a contiguous fill within its 60-pixel track')
        start=202+((left-226)*52+30)//60; end=202+((right-226)*52+30)//60
        for x in range(start,end): canvas.plot(x,y-16,next(iter(colors)))
        rows.append(dict(source=[left,y,right,y+1],destination=[start,y-16,end,y-15]))
    radar=compact_radar(canvas)
    regs=capture.state['registers']; source=layout.maze['source']
    transforms=dict(schema_version=1,status='approved',name='compact',size=[256,212],
        maze=layout.maze,blocks=layout.blocks,
        tilemap_origin_mod256=[(source[0]+regs['scroll_x']-3)%256,(source[1]+16+regs['scroll_y'])%256],
        camera_note='Tilemap addressing origin; simulation/world state remains unchanged',
        formula='Copies use preview = native + destination origin - source origin; radar anchors have a separate 7/8 projection.',
        compact=dict(panel_width=56,maze_width=200,title='HISCORE',glyphs_resized=False,
            removed_title_cell=[240,0,248,8],fragments=canvas.fragments,
            fuel=dict(source_inner_width=60,destination_inner_width=52,rows=rows),radar=radar))
    return Preview(canvas.image,bytes(canvas.background),bytes(canvas.indices),bytes(canvas.shadow),canvas.objects,transforms)
