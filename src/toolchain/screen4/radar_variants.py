"""Exact phase-local flag visibility tiles and native Z80 name-store programs.

This changes character allocation, not one displayed pixel. All generated
patterns and contributor-derived tables remain in ignored references outputs.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
from prepare import encode_tile


def prepare_phase(payload, records, phase, blue):
    names=payload[:224]
    count=(len(payload)-224)//16
    patterns=bytearray(payload[224:224+count*8])
    colors=bytearray(payload[224+count*8:])
    unique={bytes(patterns[i*8:i*8+8]+colors[i*8:i*8+8]):i for i in range(count)}
    points={}
    fx,fy=phase%8,phase//8
    for slot,record in enumerate(records):
        cell=record['address']-0x9800
        x,y=8+cell%32+fx,70+(cell//32)*106//56+fy
        entry=(y//8)*7+x//8
        points.setdefault(entry,[]).append((slot,(y%8)*8+x%8))
    groups=[]
    for entry,members in sorted(points.items()):
        tile=names[entry]
        pixels=bytes(colors[tile*8+y]>>4 if patterns[tile*8+y]&(128>>x)
                     else colors[tile*8+y]&15 for y in range(8) for x in range(8))
        ids=[]
        for mask in range(1<<len(members)):
            variant=bytearray(pixels)
            for bit,(slot,at) in enumerate(members):
                if not mask&(1<<bit):variant[at]=blue
            p,c=encode_tile(variant)
            key=p+c
            if key not in unique:
                unique[key]=len(unique);patterns.extend(p);colors.extend(c)
            ids.append(96+unique[key])
        groups.append(dict(entry=entry,slots=[slot for slot,_ in members],ids=ids))
    assert len(unique)<=64,'Flag variants overlap boundary character allocation'
    return names+patterns+colors,groups


def name_program(groups, *, origin=0xa700, names=0xd400):
    code=bytearray();fixups=[]
    for group in groups:
        slots=group['slots']
        address=0xc501+slots[-1]
        code.extend((0x3a,address&255,address>>8))  # LD A,(last active byte)
        for slot in reversed(slots[:-1]):
            address=0xc501+slot
            code.extend((0x87,0x47,0x3a,address&255,address>>8,0xb0))
        code.extend((0x6f,0x26,0,0x11))  # L=A,H=0,DE=lookup
        fixups.append((len(code),bytes(group['ids'])))
        code.extend((0,0,0x19,0x7e))
        row,column=divmod(group['entry'],7)
        at=names+row*32+26+column
        code.extend((0x32,at&255,at>>8))
    code.append(0xc9)
    for at,table in fixups:
        pointer=origin+len(code)
        code[at:at+2]=pointer.to_bytes(2,'little');code.extend(table)
    assert origin+len(code)<0xc000
    return bytes(code)
