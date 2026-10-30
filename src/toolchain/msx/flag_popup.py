"""Small authored flag-award inscriptions over the original collected road."""
from .screen5 import packed

GLYPHS=('111101101101111','010110010010111','111001111100111',
        '111001111001111','101101111001001','111100111001111',
        '111100111101111','111001001001001','111101111101111',
        '111101111001111','000101010101000')


def image(ordinal,multiplier,road,white):
    if ordinal not in range(1,11) or multiplier not in (1,2):
        raise ValueError('Flag awards require ordinal1..10 and multiplier1/2')
    text=f'{ordinal*100}'+('x2' if multiplier==2 else '')
    pixels=bytearray(road[y*8+x%8] for y in range(8) for x in range(24))
    left=(24-len(text)*4)//2
    for i,char in enumerate(text):
        glyph=GLYPHS[10 if char=='x' else int(char)]
        for y in range(5):
            for x in range(3):
                if glyph[y*3+x]=='1':pixels[(y+1)*24+left+i*4+x]=white
    return text,packed(pixels)


def build(out,road,white):
    parts=['Popup_Images:'];data=bytearray()
    for multiplier in (1,2):
        for ordinal in range(1,11):
            _,pixels=image(ordinal,multiplier,road,white)
            parts.append(f'    dw Popup_Pixels+{len(data)}')
            data.extend(pixels)
    (out/'flag-popup-pixels.bin').write_bytes(data)
    parts.extend(('Popup_Pixels:','    INCBIN "flag-popup-pixels.bin"'))
    (out/'flag-popup-data.inc').write_text('\n'.join(parts)+'\n')


def trace(symbols):
    s=symbols
    return ['set nr_popup_out [open [file join $out popups.tsv] w]',
        f'debug set_bp {s["Full_PopupFrame.exit"]} {{[info exists ::phase] && $::phase eq "game" && [debug read memory {s["Popup_Active"]}]==1 && [debug read memory {s["Popup_Age"]}]==0}} {{',
        f' set x [debug read memory {s["Popup_X"]}];set y [debug read memory {s["Popup_Y"]}]',
        f' set source [expr {{[debug read memory {s["Popup_Source"]}]+256*[debug read memory {s["Popup_Source"]+1}]-{s["Popup_Pixels"]}}}]',
        ' set pixels "";for {set r 0} {$r<8} {incr r} {for {set c 0} {$c<3} {incr c} {set xx [expr {$x+$c}];set at [expr {($xx/32%2)*32768+($y%32*8+$r)*128+($xx%32)*4}];append pixels [debug read_block VRAM $at 4]}}',
        ' puts $::nr_popup_out "[machine_info time] $x $y $source [binary encode hex $pixels]";flush $::nr_popup_out',
        '}']


def analyze(bundle,path,*,required=True):
    data=(bundle/'flag-popup-pixels.bin').read_bytes();rows=path.read_text().splitlines()
    labels=[]
    for row in rows:
        when,x,y,offset,pixels=row.split();offset=int(offset)
        if offset%96 or not 0<=offset<=len(data)-96 or bytes.fromhex(pixels)!=data[offset:offset+96]:
            raise ValueError('Natural flag popup does not match its exact award bitmap')
        ordinal=offset//96%10+1;multiplier=offset//960+1
        labels.append(f'{ordinal*100}'+('x2' if multiplier==2 else ''))
    if required and not labels:raise ValueError('Natural route painted no flag popups')
    return dict(passed=True,painted=len(labels),labels=sorted(set(labels)),
        scope='Exact24x8 VRAM pixels observed immediately after production painting on the keyboard-driven route; expiry/torus ownership have separate component gates.')
