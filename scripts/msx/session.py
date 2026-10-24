"""Bounded single-player session screens, using unscaled original font pixels."""
from .screen5 import packed


STATUS_Y=96
CODE_OFFSET=0x3800


def resources(assets,black,white,*,full_game=False,root=None,palette=None):
    def text(image,value,x,y):
        for column,char in enumerate(value):
            if char==' ':continue
            code=int(char) if char.isdigit() else ord(char)
            glyph=assets.pixels['tiles'][code*64:(code+1)*64]
            for row in range(8):
                for px in range(8):
                    if assets.palette['lookup'][38*4+glyph[row*8+px]]:
                        image[(y+row)*256+x+column*8+px]=white
    background=black
    if full_game:
        from .attract import cast
        image,background=cast(root,palette)
        text(image,'HIGH SCORE',16,0)
        text(image,'5 COIN  1 START  2 TWO PLAYERS',8,184)
        text(image,'CREDIT',72,192)
    else:
        image=bytearray([black])*(256*212)
    for value,y in (() if full_game else (('NEW RALLY-X',32),('5: CREDIT   1: START',128))):
        text(image,value,(256-len(value)*8)//2,y)
    if not full_game:
        text(image,'HIGH SCORE',40,56);text(image,'SCORE',80,80);text(image,'CREDIT',72,152)
    statuses=[]
    for value in ('INSERT COIN','GAME OVER','FIRST ROUND CLEAR'):
        line=bytearray([background])*(256*8)
        text(line,value,(256-len(value)*8)//2,0)
        statuses.append(packed(line))
    font=bytearray()
    for digit in range(10):
        line=bytearray([background])*(256*8);text(line,str(digit),0,0)
        font.extend(packed(bytes(line[y*256+x] for y in range(8) for x in range(8))))
    bitmap=packed(image)
    second=bitmap[16384:]+b''.join(statuses)+font
    if full_game:
        black_font=bytearray()
        for digit in range(10):
            line=bytearray([black])*(256*8);text(line,str(digit),0,0)
            black_font.extend(packed(bytes(line[y*256+x] for y in range(8) for x in range(8))))
        second=bytearray(second)
        second[0x3200:0x3200+len(black_font)]=black_font
    if len(second)>CODE_OFFSET:raise ValueError('Session image resources overlap code')
    second+=bytes([255])*(16384-len(second))
    return bitmap[:16384],bytes(second)
