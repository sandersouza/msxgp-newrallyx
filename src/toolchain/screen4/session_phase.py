"""Offline transfer-cost estimates for safe inactive pattern-set selection."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
from pathlib import Path
from hud_programs import writes


def compiled_cycles(image, bank, address):
    """Count the bounded instruction vocabulary emitted by compile_packet."""
    at=(bank-1)*16384+address-0x8000
    total=0;count=0
    while True:
        op=image[at];at+=1
        if op==0xc3:return total+10
        if op in (0xf3,0xfb,0x87,0x0f):total+=4
        elif op in (0x0e,0x3e,0xf6,0xe6):at+=1;total+=7
        elif op==0xd3:at+=1;total+=11
        elif op==0x3a:at+=2;total+=13
        elif op==0x21:at+=2;total+=10
        elif op==0xed:
            assert image[at]==0xa3;at+=1;total+=16
        elif op==0x06:count=image[at];at+=1;total+=7
        elif op==0xcd:
            at+=2
            # Resident burst helper:16 OUTI per full group, OTIR only for tail.
            full,tail=divmod(count,16)
            total+=17+7+7+7+full*(16*16+4+7+7)
            total+=(tail*21-5+10 if tail else 4+11)
        else:raise ValueError(f'Unexpected compiled HUD opcode {op:02x}')


def packet_cycles(packet):
    # Includes address/setup/mapper overhead. Used only to rank candidates;
    # the actual routine timings remain in the measured cycle ledger.
    return sum(16*len(data)+180 for _,data in writes(packet))


def append_costs(image, edge_costs, out):
    """Use unused phase-bank ROM space; no VRAM, RAM segment or graphic change."""
    image=bytearray(image);costs=[]
    for current in range(64):
        base=(3+current)*16384
        hud=[]
        for old in range(65):
            bank,lo,hi=image[base+0x2600+(old if old<64 else 0)*3:base+0x2603+(old if old<64 else 0)*3]
            if old<64 and bank:cost=compiled_cycles(image,bank,lo+256*hi)
            else:cost=image[base+0x900]*16*17+250
            hud.append(cost)
        for layout in range(4):
            row=[hud[old]+edge_costs[layout][old%8 if old<64 else 8][current%8]
                 for old in range(65)]
            assert max(row)<65535
            target=base+0x3800+layout*256
            assert image[target:target+130]==bytes([255])*130,'Phase cost table overlaps resources'
            image[target:target+65]=bytes(min(254,(v+128)//256) for v in row)
            costs.append(dict(layout=layout,current=current,costs=row))
    Path(out,'session-phase-costs.json').write_text(json.dumps(dict(
        method='Estimated instruction/transfer cycles; actual timing verified separately',
        active_set_excluded=True,new_ram_bytes=0,new_rom_banks=0,rows=costs),indent=2)+'\n')
    return image
