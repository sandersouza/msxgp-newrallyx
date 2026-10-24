"""Four original terrain profiles and placement-independent command atlases."""
from . import stage_one
from .screen5 import packed, rgb333
from .raster_scroll import palette_rgb, index_for


def complete_palette(encoded):
    """Use the spare third black for orange; retain both car OR-plane blacks."""
    colors = palette_rgb(encoded)
    if colors[11] != (0,0,0) or colors[14] != (0,0,0) or colors[15] != (0,0,0):
        raise ValueError('Expected approved spare black palette slot')
    result = bytearray(encoded)
    r,g,b = rgb333((255,104,0))
    result[30:32] = bytes((r<<4|b,g))
    if palette_rgb(result)[:15] != colors[:15]:
        raise ValueError('Existing colors changed while extending terrain coverage')
    return bytes(result)


def pixels(pair, assets, palette):
    code,attr = pair
    result = bytearray()
    for y in range(8):
        for x in range(8):
            sx=x if attr&64 else 7-x; sy=7-y if attr&128 else y
            pen=assets.pixels['tiles'][code*64+sy*8+sx]
            rgb=assets.palette['rgb'][assets.palette['lookup'][(attr&63)*4+pen]]
            result.append(index_for(palette,rgb))
    return bytes(result)


def profile(program, page, assets, palette, death_tiles, smoke_tiles):
    """Fixed object/effect slots; only the terrain suffix differs by map."""
    if page not in range(0x30,0x34) or len(death_tiles)!=9 or len(smoke_tiles)!=9:
        raise ValueError('Incomplete original round scenery inputs')
    wall=page-0x23;flower=0x53+(page-0x30+1)*9
    geometry=stage_one.cells_from_rom(program,page)
    atlas=[];sources={}
    decoded={}
    def image(pair):
        if pair not in decoded:decoded[pair]=pixels(pair,assets,palette)
        return decoded[pair]

    def group(name, tiles):
        ids=[]
        for start in range(0,len(tiles),3):
            while len(atlas)%32>29:atlas.append(bytes(64))
            ids.extend(range(len(atlas),len(atlas)+len(tiles[start:start+3])))
            atlas.extend(tiles[start:start+3])
        sources[name]=bytes(v for n in ids for v in ((n%32)*8,16+n//32*8))

    for kind in range(1,5):
        cell=bytearray(1792);cell[0]=kind
        group(f'object{kind}',[image(stage_one.tile(program,cell,x,y,wall,flower))
                                 for y in range(3) for x in range(3)])
    group('death',death_tiles);group('smoke',smoke_tiles)
    road=image(stage_one.tile(program,bytes(1792),0,0,wall,flower))
    group('empty',[road]*3)
    flowers=[image(stage_one.tile(program,geometry,x-3,y-3,wall,flower))
             for y in range(3) for x in range(3)]
    group('flower',flowers)
    # Every fixed source has identical position across all four profiles.
    if len(atlas)>96:raise ValueError('Fixed objects/effects exceed three atlas rows')
    atlas.extend([bytes(64)]*(96-len(atlas)))
    unique={tile:i for i,tile in enumerate(atlas)}
    ids=bytearray(65536)
    pairs=[]
    for y in range(stage_one.TILE_ROWS):
        for x in range(stage_one.TILE_COLUMNS):
            pair=stage_one.tile(program,geometry,x-3,y-3,wall,flower)
            pairs.append(pair);tile=image(pair)
            if tile not in unique:
                unique[tile]=len(atlas);atlas.append(tile)
            n=unique[tile];at=y*256+x*2
            if len(set(tile))==1:
                ids[at:at+2]=bytes((tile[0]<<4|2,0))
            else:
                ids[at:at+2]=bytes(((n%32)*8,16+n//32*8))
    if len(atlas)>128:raise ValueError('Original round atlas exceeds 128 exact tiles')
    image=bytearray(256*32)
    for n,tile in enumerate(atlas):
        for y in range(8):
            at=(n//32*8+y)*256+n%32*8;image[at:at+8]=tile[y*8:y*8+8]
    world=stage_one.bitmap(pairs,assets,palette)
    return dict(page=page,wall=wall,flower=flower,geometry=geometry,world=world,
                atlas=packed(image),ids=[bytes(ids[i:i+16384]) for i in range(0,65536,16384)],
                sources=sources,tiles=len(atlas))
