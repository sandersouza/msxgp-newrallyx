"""Original-size cast reveal units and authored session/challenge presentation."""
from .screen5 import packed

CAST_ROWS=((44,52,16,16,56,'MY CAR'),(44,68,16,16,72,'RED CAR'),
           (44,84,16,16,88,'CHECK POINT'),(44,100,16,16,104,'SPECIAL CHECK POINT'),
           (44,116,16,16,120,'LUCKY CHECK POINT'),(40,136,24,24,144,'ROCK ( DANGER ! )'),
           (40,160,24,24,168,'SMOKE SCREEN'))


def cast_reveal(image,background):
    blank=bytearray(image);units=[]
    def unit(x,y,w,h,delay):
        pixels=bytes(image[(y+dy)*256+x+dx] for dy in range(h) for dx in range(w))
        units.append((x,y,w,h,delay,packed(pixels)))
        for dy in range(h):blank[(y+dy)*256+x:(y+dy)*256+x+w]=bytes([background])*w
    for x,y,w,h,label_y,label in CAST_ROWS:
        unit(x,y,w,h,12)
        for i in range(len(label)):unit(76+i*8,label_y,8,8,4)
    return blank,units


def font(assets):
    result=bytearray()
    for code in range(128):
        source=code-48 if 48<=code<=57 else code
        glyph=assets.pixels['tiles'][source*64:(source+1)*64]
        result.extend(sum((128>>x) for x in range(8)
            if assets.palette['lookup'][38*4+glyph[y*8+x]]) for y in range(8))
    # New credits use a small authored lower-case alphabet and copyright mark.
    lower={
        'a':('00000','00000','01110','00001','01111','10001','01111'),
        'c':('00000','00000','01111','10000','10000','10000','01111'),
        'e':('00000','00000','01110','10001','11111','10000','01111'),
        'k':('10000','10000','10010','10100','11000','10100','10010'),
        'm':('00000','00000','11010','10101','10101','10101','10101'),
        'n':('00000','00000','11110','10001','10001','10001','10001'),
        'o':('00000','00000','01110','10001','10001','10001','01110'),
        'r':('00000','00000','10110','11001','10000','10000','10000'),
        't':('01000','01000','11100','01000','01000','01001','00110'),
        'w':('00000','00000','10001','10001','10101','10101','01010'),
        '@':('01110','10001','10111','10100','10111','10001','01110'),
    }
    for char,rows in lower.items():
        result[ord(char)*8:ord(char)*8+8]=bytes([0]+[int(row,2)<<2 for row in rows])
    result[32*8:33*8]=bytes(8)
    return bytes(result)


def build(root,out,assets,palette):
    from .attract import cast
    image,background=cast(root,palette)
    _,units=cast_reveal(image,background)
    (out/'ui-font.bin').write_bytes(font(assets))
    parts=['UI_CastReveal:']
    for i,(x,y,w,h,delay,pixels) in enumerate(units):
        parts.extend((f'    dw UI_Reveal{i},{y*128+x//2}',f'    db {w//2},{h},{delay}'))
        (out/f'ui-reveal-{i}.bin').write_bytes(pixels)
    parts.append('UI_CastRevealEnd:')
    for i in range(len(units)):parts.extend((f'UI_Reveal{i}:',f'    INCBIN "ui-reveal-{i}.bin"'))
    parts.extend(('UI_Font:','    INCBIN "ui-font.bin"'))
    for name,index in [('Rock',5),('RedCar',1)]:
        x,y,w,h,*_=CAST_ROWS[index]
        data=packed(bytes(image[(y+dy)*256+x+dx] for dy in range(h) for dx in range(w)))
        (out/f'ui-{name.lower()}.bin').write_bytes(data)
        parts.extend((f'UI_{name}:',f'    INCBIN "ui-{name.lower()}.bin"'))
    (out/'full-ui-data.inc').write_text('\n'.join(parts)+'\n')
    return dict(cast_units=len(units),cast_background=background,source_scale='1:1',
                selection_credits=['@ namco 1981 2ST','@ retrowork 2026'])
