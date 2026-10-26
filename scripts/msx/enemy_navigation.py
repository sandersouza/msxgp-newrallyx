"""Authored navigation policy; generated maze tables remain in ignored builds."""
DIRECTIONS=((0,-1),(1,0),(0,1),(-1,0))


def exits(walls,width=32,height=56):
    if len(walls)!=width*height or min(width,height)<1:raise ValueError('Invalid navigation grid')
    result=bytearray(len(walls))
    for y in range(height):
        for x in range(width):
            if walls[y*width+x]:continue
            for direction,(dx,dy) in enumerate(DIRECTIONS):
                nx,ny=x+dx,y+dy
                if 0<=nx<width and 0<=ny<height and not walls[ny*width+nx]:
                    result[y*width+x]|=1<<direction
    return bytes(result)


def original_maps(program):
    if len(program)!=16384:raise ValueError('Incomplete contributor program')
    return b''.join(exits(bytes(bool(program[0x3000+page*256+y*4+x//8]&(128>>(x&7)))
        for y in range(56) for x in range(32)))+bytes(256) for page in range(4))


def choose(exits_mask,heading,dx,dy,actor):
    """Pursue on alternate axis priorities; reverse only at a dead end."""
    if not 0<=exits_mask<16 or not 0<=heading<4:raise ValueError('Invalid direction policy input')
    if not exits_mask:return None
    allowed=exits_mask&~(1<<((heading+2)&3)) or exits_mask
    horizontal=1 if dx>=0 else 3;vertical=2 if dy>=0 else 0
    horizontal_first=(abs(dx)>=abs(dy)) ^ bool(actor&1)
    preferences=(horizontal,vertical) if horizontal_first else (vertical,horizontal)
    return next(d for d in (*preferences,heading,0,1,2,3) if allowed&(1<<d))
