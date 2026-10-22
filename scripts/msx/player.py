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


def palette(encoded, buffers):
    """Assign blue=3, pale yellow=9, black=11=3|9 for two mode-2 planes."""
    colors=[expand((encoded[i]>>4,encoded[i+1],encoded[i]&7)) for i in range(0,32,2)]
    desired=((3,(33,71,222)),(9,(255,255,151)))
    order=list(range(16))
    for target,rgb in desired:
        source=colors.index(expand(rgb333(rgb)))
        previous=order.index(source)
        order[target],order[previous]=order[previous],order[target]
    translation=bytes(order.index(i) if i<16 else i for i in range(256))
    return b''.join(encoded[i*2:i*2+2] for i in order),[b.translate(translation) for b in buffers]


def relocate(program, listing):
    """Relocate instruction operands, leaving fixed-point constants untouched."""
    bank=bytearray([255])*16384
    for first,last in CODE+((0x253a,0x2552),(0x3000,0x30e0)):
        bank[first:last]=program[first:last]
    patches=[]
    for line in listing.splitlines():
        match=re.search(r';([0-9a-f]{4})\s+((?:[0-9a-f]{2}\s+)+)',line)
        if not match:continue
        address=int(match[1],16)
        if not any(a<=address<b for a,b in CODE):continue
        raw=bytes.fromhex(match[2]);text=line.split(';',1)[0].strip()
        if raw!=program[address:address+len(raw)]:raise ValueError('Disassembly bytes differ from pinned program')
        if text in ('di','ei'):
            bank[address]=0x00  # The embedding renderer owns interrupt windows.
            patches.append(dict(address=address,kind='renderer-interrupt-ownership'))
            continue
        if address in (0x0069,0x0c7d):
            bank[address:address+3]=bytes(3)  # Arcade output latch, not movement state.
            patches.append(dict(address=address,kind='arcade-output-latch'))
            continue
        if len(raw)<3:continue
        value=int.from_bytes(raw[-2:],'little');new=value
        if text.startswith(('call ','jp ')):
            new=value+0x8000
        elif text.startswith('ld ') and 0x8000<=value<0x9000:
            new=value+0x6000
        elif address==0x1de5:  # Native animation table, not a velocity constant.
            new=value+0x8000
        if new!=value:
            bank[address+len(raw)-2:address+len(raw)]=new.to_bytes(2,'little')
            patches.append(dict(address=address,original=value,relocated=new))
    bank[0x0c2c]=0xc9  # Return from the native main-loop continuation to our caller.
    return bytes(bank),patches


def coordinates(ram):
    """World centre from native 24-pixel cells and signed intra-cell offsets."""
    signed=lambda value:value-256 if value&128 else value
    return (36+ram[0x70]*24+signed(ram[0x6d]),
            36+ram[0x72]*24-signed(ram[0x6f]))


def atlas(world):
    """Deduplicate exact 8x8 pixels; command copies never rescale the source."""
    unique=[];indices={};table=bytearray(128*174)
    for y in range(174):
        for x in range(102):
            tile=bytes(world[(y*8+r)*816+x*8+c] for r in range(8) for c in range(8))
            if tile not in indices:
                indices[tile]=len(unique);unique.append(tile)
            table[y*128+x]=indices[tile]
    if len(unique)>32:raise ValueError('First-stage command atlas exceeds its reserved 32 tiles')
    image=bytearray(256*8)
    for n,tile in enumerate(unique):
        for y in range(8):image[y*256+n*8:y*256+n*8+8]=tile[y*8:y*8+8]
    table.extend(bytes(32768-len(table)))
    return packed(image),[bytes(table[:16384]),bytes(table[16384:])],len(unique)


def build(output, program, native, assets):
    (output/'native-program.bin').write_bytes(program)
    listing=subprocess.check_output(['z80dasm','-a','-t','-g','0',str(output/'native-program.bin')],
                                    text=True,stderr=subprocess.DEVNULL)
    code,patches=relocate(program,listing)
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
    last_rows=b''.join(pixels[i*256+240:(i+1)*256] for i in range(len(flags)))
    data=bytes(masks)+last_rows+bytes(8192-len(masks)-len(last_rows))+seed+bytes(4096)
    (output/'player-flags.bin').write_bytes(lookup)
    (output/'player-pixels.bin').write_bytes(pixels)
    (output/'player-seed.bin').write_bytes(seed)
    json_write(output/'player.json',dict(flags=flags,patches=patches,
        code_ranges=CODE,native_ram=[0xe000,0xf000],input=0xe3f0,
        native_period_seconds=0.0165,speed_fixed=int.from_bytes(seed[0x27:0x29],'little'),
        palette=dict(blue=3,pale_yellow=9,black=11),slots=[PLAYER_SLOT,PLAYER_SLOT+1],pattern=180,
        coordinate_origin=[36,36],scope='Original player movement, walls and steering; no enemy/flag/Fuel rules'))
    return code,data
