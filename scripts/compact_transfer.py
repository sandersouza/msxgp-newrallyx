"""Lossless transfer specialization; no contributor bytes are embedded here.

Input is the linked compile_packet vocabulary. Output aliases the same source
bytes, preserves ordered VDP operations and final HL/BC/DE/IX/IY/IFF, with AF
scratch at long calls. Long marker0100+N returns B=0; short marker0200+N keeps
the original OUTI decrement. The linker replaces markers with exact workers.
Budgets include MSX M1 waits; no shorter VDP write interval is introduced.
"""
LONG=0x100
SHORT=0x200


def old_long_cycles(n):
    """LD B,n + CALL + old helper; linked emulator verifies19 cycles/OUTI.

    Both old/new models include the same MSX prefixed-instruction waits, so
    correcting an earlier18-cycle estimate leaves every saved-cycle budget
    and selected instruction byte unchanged.
    """
    q,r=divmod(n,16)
    assert q and n<=255
    return 8+18+21+(q-1)*330+325+(17 if not r else 24*r+17)


def exact_long_cycles(n):return 19*n+37+(11 if n>64 else 0)


def tokens(code):
    out=[];at=0
    while at<len(code):
        op=code[at]
        if op==0xed:
            end=at
            while code[end:end+2]==b'\xed\xa3':end+=2
            if end==at:raise ValueError('Unknown ED transfer opcode')
            out.append(('short',end//2-at//2,code[at:end]));at=end;continue
        if op==6:
            if at+5>len(code) or code[at+2]!=0xcd:raise ValueError('Count without original helper')
            n=code[at+1]
            if n<16:raise ValueError('Unexpected original short helper call')
            out.append(('long',n,code[at:at+5]));at+=5;continue
        width=3 if op in (0x3a,0x21,0xc3) else 2 if op in (0x0e,0x3e,0xf6,0xe6,0xd3) else 1
        if op not in (0x3a,0x21,0xc3,0x0e,0x3e,0xf6,0xe6,0xd3,0xf3,0xfb,0x87,0x0f):raise ValueError(f'Unknown transfer opcode {op:02x}')
        if at+width>len(code):raise ValueError('Truncated transfer')
        out.append(('load' if op==0x21 else 'raw',None,code[at:at+width]));at+=width
    if not out or out[-1][2][0]!=0xc3:raise ValueError('Missing transfer tail jump')
    return out


def optimize(code):
    """Specialize long calls, then spend only earned cycles on smaller short calls.

    First LD HL is mandatory: entry HL points to code. Subsequent source loads
    may reuse the known post-transfer pointer or change one byte. All address
    setup/DI/EI order remains intact. Smaller short calls are selected by saved
    bytes only when the complete program retains a nonnegative cycle gain.
    """
    rows=tokens(code);known=None;gain=0;loads={};candidates=[]
    for i,(kind,n,raw) in enumerate(rows):
        if kind=='load':
            value=int.from_bytes(raw[1:],'little');new=raw;saved=0
            if known==value:new=b'';saved=11
            elif known is not None and known>>8==value>>8:new=bytes((0x2e,value&255));saved=3
            elif known is not None and known&255==value&255:new=bytes((0x26,value>>8));saved=3
            loads[i]=new;gain+=saved;known=value
        elif kind in ('short','long'):
            if known is None:raise ValueError('Transfer without a source')
            known=(known+n)&65535
            if kind=='long':gain+=old_long_cycles(n)-exact_long_cycles(n)
            elif n>=2:candidates.append((-(2*n-3),i))
    selected=set()
    for _,i in sorted(candidates):
        if gain<29:break
        selected.add(i);gain-=29
    result=bytearray()
    for i,(kind,n,raw) in enumerate(rows):
        if kind=='load':result.extend(loads[i])
        elif kind=='long' or i in selected:
            result.append(0xcd);result.extend(((LONG if kind=='long' else SHORT)+n).to_bytes(2,'little'))
        else:result.extend(raw)
    assert len(result)<=len(code) and gain>=0
    return bytes(result),dict(bytes_saved=len(code)-len(result),cycles_saved=gain,short_calls=len(selected))


def events(code):
    """Independent instruction decoder: ordered control/data source events + HL/B.

    B is symbolic until a long copy resets it. No literal pixels are required;
    source addresses identify the exact immutable bytes copied by the caller.
    """
    at=0;hl=None;count=None;events=[];b=('input',0)
    while at<len(code):
        op=code[at];at+=1
        if op==0x21:hl=int.from_bytes(code[at:at+2],'little');at+=2
        elif op in (0x26,0x2e):
            if hl is None:raise ValueError('Partial source before initialization')
            hl=((hl&255)|(code[at]<<8)) if op==0x26 else ((hl&0xff00)|code[at]);at+=1
        elif op==6:count=code[at];at+=1
        elif op==0xed:
            assert code[at]==0xa3;at+=1;events.append(('data',hl));hl=(hl+1)&65535
            b=(b[0],(b[1]-1)&255)
        elif op==0xcd:
            target=int.from_bytes(code[at:at+2],'little');at+=2
            marker=target&0xff00
            n=target&255 if marker in (LONG,SHORT) else count
            assert n and hl is not None
            events.extend(('data',(hl+i)&65535) for i in range(n));hl=(hl+n)&65535
            b=('zero',0) if marker!=SHORT else (b[0],(b[1]-n)&255)
        elif op==0xc3:events.append(('exit',));at+=2
        else:
            width=3 if op==0x3a else 2 if op in (0x0e,0x3e,0xf6,0xe6,0xd3) else 1
            events.append(('control',bytes((op,))+code[at:at+width-1]));at+=width-1
    return events,hl,b
