"""Lossless 1:1 HUD block packing and explicitly cropped maze proposals."""
from dataclasses import dataclass
from PIL import Image
from .render import Frame, Object

SOURCES = dict(score=[224,0,288,32],fuel=[224,56,288,72],
               radar=[224,80,288,192],lives=[224,192,288,208],round=[224,208,288,224])


@dataclass
class Layout:
    name: str
    maze: dict
    blocks: dict


@dataclass
class Preview:
    image: Image.Image
    background: bytes
    indices: bytes
    shadow: bytes
    objects: list[Object]
    transforms: dict


def proposals():
    def blocks(destinations):
        return {name:dict(source=source.copy(),destination=destinations[name])
                for name,source in SOURCES.items()}
    return [Layout('sidebar',dict(source=[16,6,208,218],destination=[0,0,192,212]),
        blocks(dict(score=[192,0,256,32],fuel=[192,40,256,56],
                    radar=[192,64,256,176],lives=[192,180,256,196],round=[192,196,256,212]))),
        Layout('wide',dict(source=[0,60,224,160],destination=[16,0,240,100]),
        blocks(dict(score=[0,100,64,132],fuel=[64,100,128,116],
                    radar=[192,100,256,212],lives=[0,140,64,156],round=[0,164,64,180]))),
        Layout('compact',dict(source=[12,6,212,218],destination=[0,0,200,212]),
        blocks(dict(score=[200,0,256,32],fuel=[200,40,256,56],
                    radar=[200,64,256,176],lives=[200,180,256,196],round=[200,196,256,212])))]


def compose(frame: Frame, capture, layout: Layout, assets=None) -> Preview:
    if capture.state['registers']['flip']:
        raise ValueError('Layout proposals currently require upright cabinet captures')
    if layout.name=='compact':
        from .compact import compose_compact
        if layout!=next(p for p in proposals() if p.name=='compact'):
            raise ValueError('Compact layout requires its declared source/destination geometry')
        if assets is None:
            raise ValueError('Compact layout needs source assets for marker and fuel reconstruction')
        return compose_compact(frame,capture,layout,assets)
    if set(layout.blocks) != set(SOURCES):
        raise ValueError('All required HUD blocks must be present exactly once')
    occupied=bytearray(256*212)
    segments=[('maze',layout.maze),*layout.blocks.items()]
    for name,segment in segments:
        source,dest=segment['source'],segment['destination']
        for rect,maximum in [(source,(288,224)),(dest,(256,212))]:
            if (not isinstance(rect,list) or len(rect)!=4 or any(type(v) is not int for v in rect)
                    or not 0<=rect[0]<rect[2]<=maximum[0]
                    or not 0<=rect[1]<rect[3]<=maximum[1]):
                raise ValueError('Rectangle outside native image or preview')
        if name!='maze' and source!=SOURCES[name]:
            raise ValueError('Required HUD source block cannot be cropped')
        if name=='maze' and source[2]>224:
            raise ValueError('Maze source crosses into HUD')
        if (source[2]-source[0],source[3]-source[1]) != (dest[2]-dest[0],dest[3]-dest[1]):
            raise ValueError('Scaling is not permitted')
        for y in range(dest[1],dest[3]):
            for x in range(dest[0],dest[2]):
                i=y*256+x
                if occupied[i]: raise ValueError('Layout rectangles overlap')
                occupied[i]=1
    image=Image.new('RGB',(256,212))
    background=bytearray(256*212); indices=bytearray(256*212); shadow=bytearray(256*212)
    objects=[]
    for _,segment in segments:
        s,d=segment['source'],segment['destination']
        dx,dy=d[0]-s[0],d[1]-s[1]
        image.paste(frame.image.crop(tuple(s)),(d[0],d[1]))
        for y in range(s[1],s[3]):
            for x in range(s[0],s[2]):
                dest=(y+dy)*256+x+dx; src=y*288+x
                background[dest]=frame.background[src]
                indices[dest]=frame.indices[src]; shadow[dest]=frame.shadow[src]
        for obj in frame.objects:
            x0,y0,x1,y1=obj.rect
            if x1<=s[0] or x0>=s[2] or y1<=s[1] or y0>=s[3]: continue
            colors=bytearray(obj.colors); w=x1-x0
            for iy in range(y1-y0):
                for ix in range(w):
                    if not (s[0]<=x0+ix<s[2] and s[1]<=y0+iy<s[3]):
                        colors[iy*w+ix]=255
            objects.append(Object(obj.kind,obj.id,obj.code,(x0+dx,y0+dy,x1+dx,y1+dy),bytes(colors)))
    s=layout.maze['source']; regs=capture.state['registers']
    transforms=dict(schema_version=1,status='proposal',name=layout.name,size=[256,212],
        maze=layout.maze,blocks=layout.blocks,
        tilemap_origin_mod256=[(s[0]+regs['scroll_x']-3)%256,(s[1]+16+regs['scroll_y'])%256],
        camera_note='tilemap addressing origin; simulation/world state remains unchanged',
        formula='preview = native PNG coordinate + destination origin - source origin')
    return Preview(image,bytes(background),bytes(indices),bytes(shadow),objects,transforms)
