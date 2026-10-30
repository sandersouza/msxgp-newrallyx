"""Compile exact HUD transition writes into bounded ROM-resident programs.

Programs execute from the same mapper page as their immutable source bytes.
Address pairs are serialized with DI/EI, unchanged R14 groups are shared, and
short spans use OUTI directly. Longer spans use the existing measured helper.
The resident return remaps the current phase after execution has left the page.
"""
import json
from pathlib import Path
import re


def transition_packet(old, new, bases, old_active=None, current_active=None,merge_gap=12):
    result=bytearray()
    for base,previous,current in zip(bases,old,new):
        different=[i for i,value in enumerate(current) if
            (current_active is None or i//8 in current_active) and
            (i>=len(previous) or previous[i]!=value or (old_active is not None and i//8 not in old_active))]
        while different:
            start=different[0];end=start+1;used=1
            while used<len(different) and different[used]-end<=merge_gap and different[used]-start<255:
                end=different[used]+1;used+=1
            at=base+start
            result.extend((at&255,at>>8,end-start));result.extend(current[start:end])
            different=different[used:]
    result.extend(bytes(3))
    return bytes(result)


def writes(packet):
    at = 0
    while packet[at+2]:
        length = packet[at+2]
        yield int.from_bytes(packet[at:at+2], 'little'), bytes(packet[at+3:at+3+length])
        at += 3+length
    assert at+3 == len(packet)


def compile_packet(packet, origin, *, back_address=0xc006, packed8=False, source_tables=None):
    """Compile inline literals, or alias byte-verified tables in the same bank.

    source_tables contains (unpacked VDP destination, CPU ROM address, bytes).
    Alias mode emits exactly the same instructions; only LD HL operands change.
    """
    code = bytearray((0x0e, 0x98))  # LD C,98; preserved by every transfer.
    sources, relocations = [], []
    prior_page = None
    for destination, data in writes(packet):
        source = None
        if source_tables is not None:
            matches = [(address+destination-base, raw[destination-base:destination-base+len(data)])
                       for base,address,raw in source_tables
                       if base <= destination and destination+len(data) <= base+len(raw)]
            if len(matches) != 1 or matches[0][1] != data:
                raise ValueError('Transfer does not match exactly one source table')
            source = matches[0][0]
            if not 0x8000 <= source or source+len(data) > 0xc000:
                raise ValueError('Transfer source crosses the mapped ROM page')
        if packed8:
            destination=(destination&0x7ff)|(0x2000 if destination&0x4000 else 0)
        page = destination >> 14
        code.append(0xf3)
        if page != prior_page:
            # R14 = back*2 + target14bitpage. No mapper write while executing.
            code.extend((0x3a,back_address&255,back_address>>8))
            code.extend((0xf6,0) if packed8 else (0x87,0xf6,page))
            code.extend((0xd3,0x99,0x3e,0x8e,0xd3,0x99))
            prior_page = page
        code.extend((0x3e,destination&255,0xd3,0x99))
        code.extend((0x3e,(destination>>8)|0x40))
        code.extend((0xd3,0x99,0xfb,0x21))
        if source is None:
            sources.append((len(code), data))
        code.extend((0, 0) if source is None else source.to_bytes(2,'little'))
        if len(data) <= 15:
            code.extend((0xed, 0xa3)*len(data))
        else:
            code.extend((0x06, len(data), 0xcd))
            relocations.append((len(code), 'GamePacketFast_Transfer'))
            code.extend((0, 0))
    code.append(0xc3)
    relocations.append((len(code), 'hud_upload.done'))
    code.extend((0, 0))
    for at, data in sources:
        address = origin+len(code)
        assert address+len(data) <= 0xc000
        code[at:at+2] = address.to_bytes(2, 'little')
        code.extend(data)
    if not 0x8000 <= origin or origin+len(code) > 0xc000:
        raise ValueError('Compiled transfer crosses the mapped ROM page')
    return bytes(code), relocations


def link(banks, assembly, out):
    """Resolve resident addresses only after the normal resident assembly."""
    report_path = Path(out)/'hud-programs.json'
    report = json.loads(report_path.read_text())
    symbols = {n: int(v, 16) for n, v in re.findall(r'(?m)^(\S+): EQU 0x([0-9a-fA-F]+)',
                                                  (Path(assembly)/'lab.sym').read_text())}
    for row in report['relocations']:
        assert 0x4000 <= symbols[row['symbol']] < 0x8000
        at = row['offset']
        banks[at:at+2] = symbols[row['symbol']].to_bytes(2, 'little')
    report['linked_symbols'] = {n: symbols[n] for n in ('GamePacketFast_Transfer','hud_upload.done')}
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    return banks
