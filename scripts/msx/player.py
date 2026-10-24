"""Link selected native movement routines and unchanged car pixels from local ROMs."""
from pathlib import Path
import re
import subprocess

from .screen5 import expand, rgb333, packed
from .raster_scroll import sprite_pattern
from .display import PLAYER_SLOT
from scripts.scenes.storage import json_write

CODE = ((0x0069,0x0185),(0x0c6c,0x0cba),(0x0e63,0x0f11),
        (0x0f3e,0x0f5c),(0x1052,0x11bf),(0x14e0,0x150c),
        (0x1ddf,0x1e3d),(0x212b,0x2135))
ENEMY_CODE=((0x0010,0x0023),(0x022b,0x02eb),(0x038a,0x03c3),
            (0x04a0,0x04d7),(0x0ab5,0x0b0f),(0x0b63,0x0bd1),
            (0x0cd6,0x0e63),(0x1031,0x1052),(0x11bf,0x124f),
            (0x15bd,0x1685),(0x1885,0x18b1))
ROUND_CODE=((0x03fd,0x043e),(0x0472,0x0482),(0x08bf,0x08d4),(0x0f24,0x0f3e),(0x1343,0x1417),(0x141b,0x143d))


def clipped_masks(masks,clip):
    """Exact left clipping in the source's 16-row-per-half sprite layout."""
    if len(masks)!=64 or not 0<=clip<16:raise ValueError('Invalid enemy clipping input')
    left=255>>min(clip,8);right=255>>max(clip-8,0)
    return bytes(value&(right if (i//16)&1 else left) for i,value in enumerate(masks))


def palette(encoded, buffers, *, enemy=False):
    """Assign blue=3, pale yellow=9, black=11=3|9 for two mode-2 planes."""
    colors=[expand((encoded[i]>>4,encoded[i+1],encoded[i]&7)) for i in range(0,32,2)]
    desired=((3,(33,71,222)),(9,(255,255,151)))
    if enemy:desired+=((6,(255,0,0)),(10,(0,0,151)))
    order=list(range(16))
    for target,rgb in desired:
        source=colors.index(expand(rgb333(rgb)))
        previous=order.index(source)
        order[target],order[previous]=order[previous],order[target]
    if enemy and colors[order[14]]!=(0,0,0):
        raise ValueError('Enemy sprite OR color 6|10 must remain black')
    translation=bytes(order.index(i) if i<16 else i for i in range(256))
    return b''.join(encoded[i*2:i*2+2] for i in order),[b.translate(translation) for b in buffers]


def relocate(program, listing, *, rock_collision=False, scoring=False, score_tables=(), fuel=False, lives=False,enemies=False,enemy_count=1,smoke=False,smoke_notify=False,parameters=False,round_preparation=False,attract=False):
    """Relocate instruction operands, leaving fixed-point constants untouched."""
    bank=bytearray([255])*16384
    code_ranges=CODE+(((0x1774,0x17a6),) if rock_collision else ())
    if scoring:code_ranges+=((0x1aa4,0x1aca),(0x1e62,0x1e6b),(0x2064,0x20e5),(0x210f,0x212b))
    if fuel:code_ranges+=((0x0482,0x04a0),(0x1ecc,0x1f8e))
    if lives:code_ranges+=((0x08e7,0x0908),(0x18da,0x18e8))
    if enemies:code_ranges+=ENEMY_CODE
    if parameters:code_ranges+=((0x1b1f,0x1b9c),)
    if attract:code_ranges+=((0x1d9a,0x1ddf),)
    if round_preparation:
        if not parameters:raise ValueError('Round preparation requires original parameter dispatch')
        code_ranges+=ROUND_CODE
    if smoke:
        if not fuel or not enemies:raise ValueError('Original smoke requires fuel and enemy components')
        code_ranges+=((0x0185,0x01f0),(0x0f5c,0x1052))
    for first,last in code_ranges+((0x253a,0x2552),(0x3000,0x3400 if round_preparation else 0x30e0))+(((0x1417,0x141b),) if round_preparation else ())+tuple((p,p+8) for p in score_tables)+(((0x226f,0x227f),) if fuel else ())+(((0x2345,0x2505),) if parameters else ()):
        bank[first:last]=program[first:last]
    if attract:
        bank[0x3400:0x3500]=program[0x3400:0x3500]
    patches=[]
    for line in listing.splitlines():
        match=re.search(r';([0-9a-f]{4})\s+((?:[0-9a-f]{2}\s+)+)',line)
        if not match:continue
        address=int(match[1],16)
        if not any(a<=address<b for a,b in code_ranges):continue
        raw=bytes.fromhex(match[2]);text=line.split(';',1)[0].strip()
        if raw!=program[address:address+len(raw)]:raise ValueError('Disassembly bytes differ from pinned program')
        if text in ('di','ei'):
            bank[address]=0x00  # The embedding renderer owns interrupt windows.
            patches.append(dict(address=address,kind='renderer-interrupt-ownership'))
            continue
        if address in (0x0069,0x0c7d,0x03b6):
            bank[address:address+3]=bytes(3)  # Arcade output latch, not movement state.
            patches.append(dict(address=address,kind='arcade-output-latch'))
            continue
        if len(raw)<3:continue
        # Indexed displacements/immediates are bytes, not a 16-bit address.
        # In particular DD 36 00 88 must retain the enemy's $88 startup state.
        if re.search(r'\((?:ix|iy)(?:[+-]|\))',text):continue
        value=int.from_bytes(raw[-2:],'little');new=value
        if text.startswith(('call ','jp ')):
            new=value+0x8000
        elif text.startswith('ld ') and 0x8000<=value<0x9000:
            new=value+0x6000
        elif address in (0x0188,0x1b8f,0x1de5,0x1eec,0x1ef3,0x1f80):  # Original ROM tables, not velocity constants.
            new=value+0x8000
        elif round_preparation and address==0x13da:
            new=value+0x8000  # Original fixed flag-exclusion coordinate table.
        if new!=value:
            bank[address+len(raw)-2:address+len(raw)]=new.to_bytes(2,'little')
            patches.append(dict(address=address,original=value,relocated=new))
    bank[0x0c2c]=0xc9  # Return from the native main-loop continuation to our caller.
    if round_preparation:
        if program[0x08d4:0x08d9]!=bytes((0x3e,3,0x32,0x81,0xa1)):
            raise ValueError('Original round preparation hardware boundary changed')
        bank[0x043e]=0xc9
        patches.append(dict(address=0x043e,kind="round-phase-clock-return-before-arcade-io"))
        bank[0x08d4]=0xc9
        patches.append(dict(address=0x08d4,kind='round-preparation-return-before-hardware'))
    if parameters:
        if program[0x1b2f:0x1b34]!=bytes((0xf6,0x30,0x32,0x8f,0x82)):
            raise ValueError('Original parameter terrain-page instruction changed')
        # The original A is reused for wall color immediately after this store.
        # Relocate the stored page only, preserving the original A and flags.
        bank[0x1b2f:0x1b34]=bytes((0xcd,0x10,0xbf,0,0))
        bank[0x3f10:0x3f1a]=bytes((0xf6,0x30,0xf5,0xf6,0x80,0x32,0x8f,0xe2,0xf1,0xc9))
        patches.append(dict(address=0x1b2f,kind='terrain-page-store-only-relocation',target=0xbf10))
    if attract:
        if program[0x1dcf:0x1dd4]!=bytes((0x3e,0x34,0x32,0x8f,0x82)) or program[0x1dd9:0x1dde]!=bytes((0x3e,0x30,0x32,0x8f,0x82)):
            raise ValueError("Original attract geometry boundaries changed")
        bank[0x1dd0]=0xb4;bank[0x1dda]=0xb0
        patches.append(dict(address=0x1dcf,kind="attract-guide-and-restored-terrain-relocation"))
    if smoke:
        if program[0x1045:0x1047]!=bytes((0x26,0x21)) or program[0x1027:0x1029]!=bytes((0xf6,0x8c)):
            raise ValueError('Original smoke tile-buffer addressing changed')
        bank[0x1046]=0x39   # Two RL H operations form E400..E7ff instead of8400..87ff.
        bank[0x1028]=0xec   # Paired attribute ring is EC00..EFff.
        patches.extend((dict(address=0x1045,kind='smoke-code-buffer-relocation',target=0xe400),
                        dict(address=0x1027,kind='smoke-attribute-buffer-relocation',target=0xec00)))
        if smoke_notify:
            if program[0x1c9:0x1cc]!=bytes((6,3,0x54)):raise ValueError('Original smoke recovery hook changed')
            if program[0x1a0:0x1a4]!=bytes((0xdd,0x36,0x15,0)):raise ValueError('Original smoke stun-expiry hook changed')
            bank[0x1c9:0x1cc]=bytes((0xcd,0xb0,0xc7))
            bank[0x1a0:0x1a4]=bytes((0xcd,0xb3,0xc7,0))
            patches.append(dict(address=0x1c9,kind='notify-host-before-original-smoke-clear',target=0xc7b0))
            patches.append(dict(address=0x1a0,kind='notify-host-of-original-stun-expiry',target=0xc7b3))
    if rock_collision:
        bank[0x17a6]=0xc9  # Return the original contact cell; later systems stay absent.
        patches.append(dict(address=0x17a6,kind='contact-cell-return-before-flag-scan'))
    if scoring:
        bank[0x1aca]=0xc9  # Fuel conversion is a separate incremental component.
        bank[0x0b2f]=0xc9  # Source bonus-life count/bits retained; old bitmap HUD absent.
        patches.extend((dict(address=0x1aca,kind='score-return-before-lucky-fuel-conversion'),
                        dict(address=0x0b2f,kind='bonus-life-bitmap-interface-owned-by-host')))
    if lives:
        for at,kind in ((0x0908,'restart-ram-return-before-radar-and-redraw'),
                        (0x18e8,'life-loss-return-before-two-player-dispatch'),
                        (0x073d,'inactive-game-return'),(0x1bcd,'final-life-return-to-host-state')):
            bank[at]=0xc9
            patches.append(dict(address=at,kind=kind))
    if enemies:
        if program[0xafd:0xb01]!=bytes((0xd7,0x00,0x20,0x05)):
            raise ValueError('Enemy initialization RST-10 hook changed')
        # CALL the retained RST helper inside this bank, then take the same
        # source branch. No restart vector in the MSX BIOS is invoked.
        bank[0xafd:0xb00]=bytes((0xc3,0x00,0xbf))
        bank[0x3f00:0x3f09]=bytes((0xcd,0x10,0x80,0xc2,0x06,0x8b,0xc3,0x01,0x8b))
        for at in (0x02eb,0x03c3,0x0bd1,0x124f,0x1273,0x127e,0x12a8):bank[at]=0xc9
        bank[0x18c1:0x18c7]=bytes((0x3e,1,0x32,0xd0,0xc5,0xc9))
        if enemy_count>1:
            # HL identifies the exact colliding descriptor's Y coordinate.
            bank[0x18c1:0x18ca]=bytes((0x22,0x3c,0xc6,0x3e,1,0x32,0xd0,0xc5,0xc9))
        patches.extend((dict(address=0xafd,kind='bank-local-original-rst10-trampoline',target=0xbf00),
                        dict(address=0x18c1,kind='original-contact-return-to-host-event')))
        patches.extend(dict(address=at,kind='hardware-interface-return') for at in
                       (0x02eb,0x03c3,0x0bd1,0x124f,0x1273,0x127e,0x12a8))
    return bytes(bank),patches


def coordinates(ram):
    """World centre from native 24-pixel cells and signed intra-cell offsets."""
    signed=lambda value:value-256 if value&128 else value
    return (36+ram[0x70]*24+signed(ram[0x6d]),
            36+ram[0x72]*24-signed(ram[0x6f]))


def padded_world(world, width=816, height=1392, *, pad=256, flower=24):
    """Independent viewport oracle: outside the maze, repeat its flower tile.

    Linear array indexing across an edge would read an unrelated maze row.
    Retain the runtime's world-coordinate flower phase on both axes instead.
    """
    if len(world)!=width*height or min(width,height)<flower or pad<0 or flower<=0:
        raise ValueError('Invalid world/padding dimensions')
    stride=width+2*pad;rows=height+2*pad;result=bytearray(stride*rows)
    for y in range(rows):
        sy=y-pad
        for x in range(stride):
            sx=x-pad
            result[y*stride+x]=world[sy*width+sx] if 0<=sx<width and 0<=sy<height else world[sy%flower*width+sx%flower]
    return result,stride,rows


def atlas_with_tiles(world, extra_tiles=(),*,force_source_xy=False,grouped_rows=()):
    """Deduplicate exact 8x8 pixels; command copies never rescale the source."""
    unique=[];indices={};table=bytearray(128*174)
    for y in range(174):
        for x in range(102):
            tile=bytes(world[(y*8+r)*816+x*8+c] for r in range(8) for c in range(8))
            if tile not in indices:
                indices[tile]=len(unique);unique.append(tile)
            table[y*128+x]=indices[tile]
    extra_ids=[]
    grouped_rows=set(grouped_rows)
    if any(i<0 or i+3>len(extra_tiles) for i in grouped_rows) or any(i+1 in grouped_rows or i+2 in grouped_rows for i in grouped_rows):
        raise ValueError('Invalid grouped atlas rows')
    i=0
    while i<len(extra_tiles):
        if i in grouped_rows:
            row=extra_tiles[i:i+3]
            if any(len(tile)!=64 for tile in row):raise ValueError('Atlas tiles must contain exactly 8x8 pixels')
            while len(unique)%32>29:unique.append(bytes(64))
            extra_ids.extend(range(len(unique),len(unique)+3))
            unique.extend(row);i+=3
            continue
        tile=extra_tiles[i]
        if len(tile)!=64:raise ValueError('Atlas tiles must contain exactly 8x8 pixels')
        if tile not in indices:
            indices[tile]=len(unique);unique.append(tile)
        extra_ids.append(indices[tile])
        i+=1
    if len(unique)>64:raise ValueError('Command atlas exceeds its reserved 64 tiles')
    rows=8 if len(unique)<=32 and not force_source_xy else 16
    image=bytearray(256*rows)
    for n,tile in enumerate(unique):
        for y in range(8):
            start=(n//32*8+y)*256+(n%32)*8
            image[start:start+8]=tile[y*8:y*8+8]
    table.extend(bytes(32768-len(table)))
    if len(unique)>32 or force_source_xy:
        # Two source-address bytes per world tile. A 256-byte row permits
        # direct H/L addressing and four 64-row banks, with no runtime multiply.
        addresses=bytearray(65536)
        for y in range(174):
            for x in range(128):
                tile=table[y*128+x]
                at=y*256+x*2
                addresses[at:at+2]=bytes(((tile%32)*8,16+(tile//32)*8))
        return packed(image),[bytes(addresses[i:i+16384]) for i in range(0,65536,16384)],len(unique),extra_ids
    return packed(image),[bytes(table[:16384]),bytes(table[16384:])],len(unique),extra_ids


def uniform_source_tags(atlas, banks):
    """Tag exact solid terrain for HMMV; retain flag-owner and textured entries."""
    result=[]
    for bank in banks:
        data=bytearray(bank)
        for at in range(0,len(data),2):
            x,y=data[at:at+2]
            if x&1 or y not in (16,24):continue
            pixels=bytes(v for row in range(8)
                         for byte in atlas[((y-16)*128+row*128+x//2):][:4]
                         for v in (byte>>4,byte&15))
            if len(pixels)==64 and len(set(pixels))==1:
                data[at]=(pixels[0]<<4)|2
                data[at+1]=0
        result.append(bytes(data))
    return result


def merge_scenery_color(world,source,target,protected,*,width=816):
    """Recolor terrain only; restore complete original object rectangles."""
    if len(world)%width:raise ValueError('Incomplete scenery rows')
    translation=bytearray(range(256));translation[source]=target
    result=bytearray(world.translate(bytes(translation)))
    height=len(world)//width
    for x,y,w,h in protected:
        if min(x,y,w,h)<0 or x+w>width or y+h>height:
            raise ValueError('Protected scenery object is outside the world')
        for row in range(y,y+h):
            at=row*width+x;result[at:at+w]=world[at:at+w]
    return bytes(result)


def atlas(world):
    return atlas_with_tiles(world)[:3]


def build(output, program, native, assets, *, rock_collision=False, scoring=False, fuel=False, lives=False,enemies=False,enemy_count=1,smoke=False,smoke_notify=False,parameters=False,round_preparation=False,full_game=False):
    (output/'native-program.bin').write_bytes(program)
    listing=subprocess.check_output(['z80dasm','-a','-t','-g','0',str(output/'native-program.bin')],
                                    text=True,stderr=subprocess.DEVNULL)
    score_tables=[int.from_bytes(native[p:p+2],'little') for p in (0x1b3,0x1b9)] if scoring else []
    if any(not 0x2000<=p<0x2500 or p&255>247 for p in score_tables):
        raise ValueError('Unexpected original bonus-score table pointer/page boundary')
    code,patches=relocate(program,listing,rock_collision=rock_collision,scoring=scoring,score_tables=score_tables,fuel=fuel,lives=lives,enemies=enemies,enemy_count=enemy_count,smoke=smoke,smoke_notify=smoke_notify,parameters=parameters,round_preparation=round_preparation,attract=full_game)
    flags=list(dict.fromkeys(program[0x253a:0x2552]))
    if len(flags)!=12:raise ValueError('Unexpected native car animation cycle')
    lookup=bytes(flags.index(i) if i in flags else 255 for i in range(256))
    masks=bytearray();pixels=bytearray()
    for flag in flags:
        code_id=flag>>2;bitmap=[]
        for y in range(16):
            for x in range(16):
                sx=15-x if flag&1 else x;sy=15-y if flag&2 else y
                pen=assets.pixels['sprites'][code_id*256+sy*16+sx]
                color=assets.palette['lookup'][4+pen]
                bitmap.append({0:0,1:11,9:3,14:9}[color])
        pixels.extend(bitmap)
        for shift in (0,1):
            for plane in (3,9):
                mask=bytes(int(p in (plane,11)) for p in bitmap)
                # Full-height original sprites need a one-row bitmap patch when
                # avoiding SAT Y=216; retain that last row separately below.
                if shift:mask=mask[:240]+bytes(16)
                masks.extend(sprite_pattern(mask,shift))
    seed=bytearray(4096)
    seed[0x20]=1
    seed[0x27:0x29]=native[0x27:0x29]  # Original first-stage forward speed.
    seed[0x28f]=0xb0  # Original first-stage bitmap, relocated to native bank + $3000.
    seed[0x99e:0x9a0]=(0xe3f0).to_bytes(2,'little')
    seed[0x3f0]=255
    if scoring:
        seed[0x60:0x68]=native[0x60:0x68]
        seed[0xa0:0xa8]=native[0xa0:0xa8]
        seed[0x990:0x992]=(0xe0a0).to_bytes(2,'little')
        seed[0x988:0x98a]=(0xe00f).to_bytes(2,'little')
        seed[0xf]=native[0xf]
        seed[0x1aa]=native[0x1aa]
        for at,p in zip((0x1b3,0x1b9),score_tables):seed[at:at+2]=(p+0x8000).to_bytes(2,'little')
    if fuel:
        for at,size in ((0x21,1),(0x2b,2),(0x1b0,1),(0x26a,2),(0x26e,1),(0x28b,1)):
            seed[at:at+size]=native[at:at+size]
        for at,target in ((0x98a,0xe1b0),(0x98c,0xe271),(0x98e,0xe26a),(0x99a,0xe289),(0x99c,0xe28b)):
            seed[at:at+2]=target.to_bytes(2,'little')
    if lives:seed[0x25:0x2d]=native[0x25:0x2d]
    if parameters:
        for at in (0x28a,0x2d8):seed[at]=native[at]
        seed[0x2d2:0x2d4]=(int.from_bytes(native[0x2d2:0x2d4],'little')+0x8000).to_bytes(2,'little')
    if full_game:
        from .round_prepare_verify import relocated_seed
        seed=bytearray(relocated_seed(native))
        seed[0x20]=1
        seed[0x99e:0x9a0]=(0xe3f0).to_bytes(2,'little')
        seed[0x3f0]=255
    last_rows=b''.join(pixels[i*256+240:(i+1)*256] for i in range(len(flags)))
    data=bytes(masks)+last_rows+bytes(8192-len(masks)-len(last_rows))+seed+bytes(4096)
    (output/'player-flags.bin').write_bytes(lookup)
    (output/'player-pixels.bin').write_bytes(pixels)
    (output/'player-seed.bin').write_bytes(seed)
    if round_preparation:
        json_write(output/'round-preparation.json',dict(source_entry=0x08bf,source_boundary=0x08d4,
            native_entry=0x88bf,code_ranges=ROUND_CODE,terrain_pages=[0x30,0x31,0x32,0x33],
            object_build_entry=0xac00,object_lookup_entry=0xac03,object_scan_entry=0xac06,
            object_map_address=0xdc00,object_map_bytes=896,
            runtime_enabled=full_game,
            scope='Original preparation with dynamic runtime progression' if full_game else 'Isolated increment, parameter and object placement component; runtime round transition not enabled'))
    json_write(output/'player.json',dict(flags=flags,patches=patches,
        code_ranges=CODE+(((0x1774,0x17a6),) if rock_collision else ())+
                    (((0x1aa4,0x1aca),(0x1e62,0x1e6b),(0x2064,0x20e5),(0x210f,0x212b)) if scoring else ())+(((0x0482,0x04a0),(0x1ecc,0x1f8e)) if fuel else ())+(((0x08e7,0x0908),(0x18da,0x18e8)) if lives else ())+ (ENEMY_CODE if enemies else ())+(((0x0185,0x01f0),(0x0f5c,0x1052)) if smoke else ())+(((0x1b1f,0x1b9c),) if parameters else ())+(ROUND_CODE if round_preparation else ())+(((0x1d9a,0x1ddf),) if full_game else ()),
        rock_contact_geometry=rock_collision,scoring=scoring,fuel=fuel,lives=lives,enemies=enemies,score_tables=score_tables,native_ram=[0xe000,0xf000],input=0xe3f0,
        native_period_seconds=0.0165,speed_fixed=int.from_bytes(seed[0x27:0x29],'little'),
        palette=dict(blue=3,pale_yellow=9,black=11),slots=[PLAYER_SLOT,PLAYER_SLOT+1],pattern=180,
        coordinate_origin=[36,36],full_game=full_game,attract_guide_range=[0x3400,0x3500] if full_game else None,
        scope=('Selected original gameplay routines with complete progression/session adapter; arcade foreground/IRQ replaced' if full_game else 'Selected original movement and scoring routines for the bounded score adapter; no complete foreground loop'
            if scoring else 'Original player movement, walls and steering; no enemy/flag/Fuel rules')))
    return code,data
