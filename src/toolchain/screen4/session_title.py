"""Cold title composition and optional MSX label; native game assets stay local."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib,json,os,re
from pathlib import Path
from PIL import Image

CAPTION='[5] insert coin - [1/2] start player(s)'
BRAND='namco'

def pack(pixels):
    return bytes(a*16+b for a,b in zip(pixels[::2],pixels[1::2]))

def shift_reveal(source):
    def move(match):
        address=int(match[2]);assert address//128>=8
        return match[1]+str(address-8*128)
    return re.sub(r'(dw UI_Reveal\d+,)(\d+)',move,source)

def import_brand(image):
    """Copy native PNG alpha one-to-one; only the ink color is palette-mapped."""
    image=image.convert('RGBA');width,height=image.size
    if width>256 or height>14:raise ValueError('Signature does not fit the footer at1:1; resizing is forbidden')
    alpha=bytes(image.getchannel('A').get_flattened_data())
    if not set(alpha)<={0,255}:raise ValueError('Signature must have binary pixel-art alpha; smoothing is forbidden')
    mask=bytes(a==255 for a in alpha)
    return mask,dict(x=(256-width)//2,y=212-height-4,width=width,height=height,
        source_size=[width,height],uniform_scale=1,bottom_margin=4,
        method='Exact approved PNG alpha at1:1; horizontal centering and4px bottom margin; foreground mapped to the existing red palette entry')

def brand_reference(root):
    from title_reference import ensure
    source=ensure(root)
    with Image.open(source) as image:mask,meta=import_brand(image)
    assert (meta['width'],meta['height'])==(56,8),'Original arcade wordmark dimensions changed'
    meta['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    return mask,meta

def compose(original,font,colors,brand):
    """Move the cast up8px and compose the exact supplied wordmark mask."""
    assert len(original)==256*212 and len(font)==2048
    red,white=colors['RED'],colors['WHITE'];background=original[0]
    pixels=bytearray([background])*(256*212)
    pixels[:176*256]=original[8*256:184*256]
    mask,brand_width,brand_height,bx,by=brand
    assert len(mask)==brand_width*brand_height and 0<=bx<bx+brand_width<=256 and 0<=by<by+brand_height<=212
    for y in range(brand_height):
        for x in range(brand_width):
            if mask[y*brand_width+x]:pixels[(by+y)*256+bx+x]=red
    caption_width=len(CAPTION)*6-1;cx=(256-caption_width)//2;cy=186
    blink_pixels=[]
    ranges=[(CAPTION.index('5'),1),(CAPTION.index('1/2'),3)]
    blinking={i for at,count in ranges for i in range(at,at+count)}
    for i,c in enumerate(CAPTION):
        if c==' ':continue
        for y,row in enumerate(font[ord(c)*8:ord(c)*8+8]):
            assert not row&3,'Terminal glyph exceeds6px cell'
            for x in range(6):
                if row&(128>>x):
                    at=(cy+y)*256+cx+i*6+x;pixels[at]=white
                    if i in blinking:blink_pixels.append(at)
    patches=[]
    for at,count in ranges:
        left=(cx+at*6)//2*2;right=(cx+(at+count)*6+1)//2*2
        on=bytes(pixels[(cy+y)*256+left+x] for y in range(8) for x in range(right-left));off=bytearray(on)
        for p in blink_pixels:
            yy,xx=divmod(p,256)
            if left<=xx<right:off[(yy-cy)*(right-left)+xx-left]=background
        patches.append(dict(rect=[left,cy,right-left,8],on=on,off=bytes(off)))
    return pixels,dict(caption=CAPTION,caption_y=cy,caption_x=cx,brand=BRAND,brand_y=by,
        brand_x=bx,brand_width=brand_width,brand_height=brand_height,shift_y=-8,
        brand_source='Original arcade tiles 0x19..0x1f; native pixels without resampling',
        blink_pixels=blink_pixels,blink_keys=['5','1/2'],blink_half_period_refreshes=32,inverted_keys=[]),patches

def logo_enabled():
    text=source_path('session-ui-options.inc').read_text()
    return os.environ.get('NRX_MSX_LOGO','1')!='0' and bool(re.search(r'^\s*INCLUDE "session-msx-logo.inc"\s*$',text,re.M))

def import_logo(source,colors):
    """Import the approved final-size monochrome artwork without resampling.

    The existing cold blitter owns a54x20 rectangle. Reject incompatible input
    rather than silently crop, quantize or resize an artist-supplied bitmap.
    Only binary black/white values are mapped to the existing SCREEN5 palette.
    """
    if source.mode!='1':raise ValueError('MSX logo must be a1-bit bitmap; automatic quantization is forbidden')
    if source.size!=(54,20):raise ValueError('MSX logo must be54x20 at1:1; resizing is forbidden')
    pixels=bytes(colors['WHITE'] if value else colors['BLACK'] for value in source.get_flattened_data())
    return pixels,dict(source_size=[54,20],source_crop=[0,0,54,20],scale_divisor=1,
        rect=[194,8,54,20],colors='Exact1-bit black/white artwork mapped to the existing palette',
        method='Copy every source pixel at1:1; no crop, resize, smoothing or quantization')

def prepare(root,out,image,colors,font):
    original=bytearray(v for byte in image[:27136] for v in (byte>>4,byte&15))
    mask,brand=brand_reference(root)
    pixels,meta,patches=compose(original,font,colors,(mask,brand['width'],brand['height'],brand['x'],brand['y']))
    meta['brand_artwork']=brand
    (out/'session-title-brand-mask.bin').write_bytes(mask)
    (out/'session-title-base.bin').write_bytes(pack(pixels))
    lines=[];workers=[]
    for i,patch in enumerate(patches):
        for state in ('on','off'):
            name=f'session-title-key-{i}-{state}.bin';(out/name).write_bytes(pack(patch[state]))
            lines.extend((f'UI_CastKey{i}_{state}:',f'    INCBIN "{name}"'))
        meta.setdefault('blink_rects',[]).append(patch['rect'])
        x,y,w,h=patch['rect']
        workers.extend((f'UI_CastFooter_Key{i}:',f'    ld de,{y*128+x//2}', '    ld (Full_UIDestination),de',f'    ld a,{w//2}', '    ld (Full_UIWidth),a',f'    ld a,{h}', '    ld (Full_UIRows),a','    jp Full_UIBlit'))
    (out/'session-title-blit.inc').write_text('\n'.join(workers)+'\n')
    (out/'session-title-data.inc').write_text('\n'.join(lines)+'\n')
    logo=dict(enabled=logo_enabled(),include='session-msx-logo.inc')
    if logo['enabled']:
        source=root/'assets/msxlogo.bmp'
        # The frozen module-layout proof may supply its committed historical
        # artwork as a temporary1-bit bitmap. Normal delivery always uses assets/.
        if os.environ.get('NRX_BASELINE_LOGO'):source=Path(os.environ['NRX_BASELINE_LOGO'])
        with Image.open(source) as im:lp,details=import_logo(im,colors)
        logo.update(details,source=str(source.relative_to(root)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        (out/'session-msx-logo.bin').write_bytes(pack(lp))
    meta['logo']=logo
    (out/'session-title.json').write_text(json.dumps(meta,indent=2)+'\n')
    return pack(pixels)+image[27136:],meta
