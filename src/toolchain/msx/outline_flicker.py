"""Independent car ink planes and body-first SAT orders for the experiment."""
from .raster_scroll import sprite_pattern


def resources(pixels):
    if len(pixels)!=12*256 or set(pixels)-{0,3,9,11}:
        raise ValueError('Twelve native blue/yellow/black car poses required')
    masks=bytearray();colors=bytearray()
    for pose in range(12):
        image=pixels[pose*256:(pose+1)*256]
        for y in range(16):
            row=image[y*16:y*16+16]
            colors.append((9 if row.count(9)>row.count(3) else 3)|32)
        for shift in (0,1):
            for ink in ((3,9),(11,)):
                mask=bytes(int(p in ink) for p in image)
                if shift:mask=mask[:240]+bytes(16)
                masks.extend(sprite_pattern(mask,shift))
    return bytes(masks),bytes(colors)


def order(phase):
    if phase not in range(4):raise ValueError('Four outline priority phases required')
    outlines=[18,20,22]
    if phase&2:outlines.reverse()
    radar=list(range(14))+[23]
    if phase&2:radar.reverse()
    moving=[17,19,21]+(radar+outlines if phase&1 else outlines+radar)
    # ISR-owned shared fuel/life entries keep their hardware slots.
    result=moving[:14]+[14,15,16]+moving[14:]
    if sorted(result)!=list(range(24)):raise ValueError('Lost a canonical SAT entry')
    return result
