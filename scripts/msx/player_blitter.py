"""Conservative static-road certificates for exact opaque player copies."""
from .screen5 import packed


def road_tiles(world,color,*,width=816,height=1392,flags=()):
    if len(world)!=width*height or width%8 or height%8 or width>1024 or height>2048:
        raise ValueError('Road certificates require complete world tiles within128x256 cells')
    table=bytearray(32768)
    for y in range(height//8):
        for x in range(width//8):
            table[y*128+x]=int(all(world[(y*8+row)*width+x*8+col]==color
                                  for row in range(8) for col in range(8)))
    for owner,flag in enumerate(flags,1):
        if owner>10:raise ValueError('Only the original ten collected flag cells are supported')
        for y in range(flag['tile_y'],flag['tile_y']+3):
            for x in range(flag['tile_x'],flag['tile_x']+3):table[y*128+x]=owner+1
    return bytes(table)


def opaque_atlas(cars,color):
    if len(cars)!=12*256 or not 0<=color<16:
        raise ValueError('Twelve original16x16 player poses required')
    return b''.join(packed(bytes(cars[frame*256+y*16+x-phase] or color
                         if phase<=x<phase+16 else color
                         for frame in range(12) for x in range(18)))
                    for phase in (0,1) for y in range(16))
