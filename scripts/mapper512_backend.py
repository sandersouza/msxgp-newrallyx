"""Experimental16KiB RAM-mapper packet backend; never replaces public outputs.

The current cartridge packet pointers differ for paired source bases. This
backend supplies D/E as source high-byte bases, so programs can be shared across
all eight2KiB source slots of a16KiB mapper page. Packet code executes from a
separate Page1 mapper page; Page3 owns dispatch/return and Page0 exact tails.
This module implements the packet/source allocation, not whole-game takeover.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
from compact_transfer import tokens,optimize,old_long_cycles,exact_long_cycles,LONG,SHORT


def spans(mask):
    start=None
    for i,bit in enumerate(bytes(mask)+b'\0'):
        if bit and start is None:start=i
        if not bit and start is not None:yield start,i;start=None


def table_layout(record):
    """Map fixed original source arrays to page-aligned2KiB slot fields."""
    if record['kind']=='hud':return [(0x100,0,328),(0x300,0x200,328)]
    a,b=record['data'][0xa00:0xa02]
    return [(0x200,0,a*8),(0x400,0x200,a*8),(0x600,0x400,b*8),(0x800,0x600,b*8)]


def source_offset(address,record,paired_base):
    offset=address-paired_base
    matches=[new+offset-old for old,new,size in table_layout(record) if old<=offset<old+size]
    if len(matches)!=1:raise ValueError(f'Unowned source{address:04x}')
    return matches[0]


def pack_record(record, ranking_layout=None):
    """Keep every live source/metadata byte; locations are explicit, never FF scans.

    Metadata's internal pointers still need whole-game relocation. It counts
    toward the capacity probe but is not executed by the packet component test.
    Optional ranking_layout retains only that family's65-byte victim costs at
    slot+400; the other three tables need cold backing/rebuild before a change
    of family. Pixel offsets and2KiB slot size stay identical. Default keeps all
    four tables byte-for-byte and preserves the historical component format.
    """
    if ranking_layout is not None and ranking_layout not in range(4):raise ValueError('Invalid layout')
    data=bytearray(b'\xff'*2048);busy=bytearray(2048);rest=bytearray(record['occupied']);locations=[]
    for old,new,size in table_layout(record):
        assert size<=512
        data[new:new+size]=record['data'][old:old+size];busy[new:new+size]=b'\1'*size;rest[old:old+size]=b'\0'*size
        locations.append((old,new,size))
    removed=0
    if ranking_layout is not None and record['kind']=='hud':
        for layout in range(4):rest[0x800+layout*256:0x841+layout*256]=b'\0'*65
        old=0x800+ranking_layout*256
        assert not any(busy[0x400:0x441])
        data[0x400:0x441]=record['data'][old:old+65];busy[0x400:0x441]=b'\1'*65
        locations.append((old,0x400,65));removed=3*65
    for old,end in sorted(spans(rest),key=lambda p:(-(p[1]-p[0]),p[0])):
        size=end-old;holes=list(spans(bytes(1-x for x in busy)))
        choices=[(b-a-size,a) for a,b in holes if b-a>=size]
        if not choices:raise ValueError(f'Live metadata does not fit2KiB:{record["bank"]}/{size}')
        _,at=min(choices);data[at:at+size]=record['data'][old:end];busy[at:at+size]=b'\1'*size;locations.append((old,at,size))
    assert sum(busy)==sum(record['occupied'])-removed
    return bytes(data),bytes(busy),locations


def compile_relative(code,record,index):
    """Compile packet with D/E high-byte sources; original packet postconditions.

    D/E are inputs and survive; HL is scratch/advanced, AF/flags scratch.
    C becomes98; B retains original long-reset/short-decrement semantics;
    IX/IY survive. Nonempty packets returnEI, empty packets keep entry IFF.
    D=slot-high (patterns0/1), E=slot-high+2(HUD) or+4(edges).
    Source/data mapper ownership remains with the Page3 caller. All short OUTI
    stay inline, reclaiming the29-cycle calls spent by the cartridge compactor.
    No active decompression, pixel mutation or count dispatch is introduced.
    """
    result=bytearray();known=None;base=0x8000+(index%2)*4096
    bases=(0,2 if record['kind']=='hud' else 4)
    for kind,n,raw in tokens(code):
        if kind=='load':
            offset=source_offset(int.from_bytes(raw[1:],'little'),record,base)
            if offset!=known:
                if known is None or offset>>8!=known>>8:
                    which=min(range(2),key=lambda i:abs((offset>>8)-bases[i]))
                    result.append(0x62 if which==0 else 0x63) # LD H,D/E
                    delta=(offset>>8)-bases[which]
                    result.extend(bytes((0x24 if delta>=0 else 0x25,))*abs(delta))
                if known is None or offset&255!=known&255:result.extend((0x2e,offset&255))
            known=offset
        elif kind in ('long','short'):
            if known is None:raise ValueError('Transfer before source setup')
            if kind=='long':result.extend(b'\xcd'+(LONG+n).to_bytes(2,'little'))
            else:result.extend(raw)
            known=(known+n)&65535
        else:result.extend(raw)
    return bytes(result)


def cycles(code,prefixes=()):
    """Independent straight-line decoder; includes actual MSX instruction waits."""
    at=0;total=0
    while at<len(code):
        op=code[at];at+=1
        if op==0xed:
            assert code[at]==0xa3;at+=1;total+=19
        elif op==0x06:
            n=code[at];assert code[at+1]==0xcd;at+=4;total+=old_long_cycles(n)
        elif op==0xcd:
            target=int.from_bytes(code[at:at+2],'little');at+=2
            assert target&0xff00 in (LONG,SHORT,0x300)
            n=target&255
            total+=(sum({0x0e:8,0xf3:5,0x3a:14,0xf6:8,0xd3:13,0x3e:8,0xfb:5}[i[0]] for i in instructions(prefixes[n]))+29 if target&0xff00==0x300 else exact_long_cycles(n) if target&0xff00==LONG else 19*n+29)
        elif op==0x21:total+=11;at+=2
        elif op in (0x26,0x2e,0x0e,0x3e,0xf6,0xe6):total+=8;at+=1
        elif op==0x3a:total+=14;at+=2
        elif op==0xd3:total+=13;at+=1
        elif op==0xc3:total+=11;at+=2
        elif op in (0x62,0x63,0x24,0x25,0x87,0x0f,0xf3,0xfb):total+=5
        else:raise ValueError(f'Unexpected opcode{op:02x}')
        if at>len(code):raise ValueError('Truncated instruction')
    return total


def events(code,d,e):
    """Decode relative source operations independently of the compiler."""
    at=0;hl=None;b=('input',0);result=[]
    while at<len(code):
        op=code[at];at+=1
        if op in (0x62,0x63):hl=((d if op==0x62 else e)<<8)|(0 if hl is None else hl&255)
        elif op in (0x24,0x25):hl=(((hl>>8)+(1 if op==0x24 else -1))&255)*256+(hl&255)
        elif op==0x2e:hl=(hl&0xff00)|code[at];at+=1
        elif op==0xed:
            assert code[at]==0xa3;at+=1;result.append(('data',hl));hl=(hl+1)&65535;b=(b[0],(b[1]-1)&255)
        elif op==0xcd:
            target=int.from_bytes(code[at:at+2],'little');at+=2;assert target&0xff00==LONG
            n=target&255;result.extend(('data',(hl+i)&65535) for i in range(n));hl=(hl+n)&65535;b=('zero',0)
        elif op==0xc3:result.append(('exit',));at+=2
        else:
            width=3 if op==0x3a else 2 if op in (0x0e,0x3e,0xf6,0xe6,0xd3) else 1
            result.append(('control',bytes((op,))+code[at:at+width-1]));at+=width-1
    return result,hl,b


def instructions(code):
    """Split only the validated straight-line packet language at opcode boundaries."""
    at=0;out=[]
    while at<len(code):
        op=code[at]
        width=3 if op in (0x21,0x3a,0xcd,0xc3) else 2 if op in (0xed,0x0e,0x3e,0x26,0x2e,0xf6,0xe6,0xd3) else 1
        if at+width>len(code):raise ValueError('Truncated packet')
        out.append(code[at:at+width]);at+=width
    return tuple(out)


def suffix_graph(programs,origin=0x4000,exit_address=None):
    """Merge immutable instruction suffixes; each join adds one11-cycle JP.

    Every closure stays in a single16KiB Page1 mapping. No bank-crossing JP,
    interpreter, decompression, CALL/data-stack use or hidden dispatcher exists.
    Identical tails preserve the original incoming register/flag context.
    """
    nodes=[];intern={};roots={}
    for code in sorted(programs):
        tail=None
        for ins in reversed(instructions(code)):
            key=ins,tail
            if key not in intern:intern[key]=len(nodes);nodes.append(key)
            tail=intern[key]
        roots[code]=tail
    incoming=[0]*len(nodes)
    for ins,next_ in nodes:
        if next_ is not None:incoming[next_]+=1
    starts=set(roots.values())|{i for i,n in enumerate(incoming) if n!=1}
    blocks={}
    for start in sorted(starts):
        ids=[];current=start
        while True:
            ids.append(current);next_=nodes[current][1]
            if next_ is None or next_ in starts:break
            current=next_
        blocks[start]=(ids,next_)
    # A jump to a shared terminal JP costs one extra jump without saving a
    # byte. Inline that terminal in each predecessor and drop the dead node.
    terminals={i for i,(ins,next_) in enumerate(nodes) if next_ is None and ins[0]==0xc3}
    for start,(ids,next_) in list(blocks.items()):
        if next_ in terminals:blocks[start]=(ids+[next_],None)
    for i in terminals-set(roots.values()):blocks.pop(i,None)
    addresses={};image=bytearray()
    for start,(ids,next_) in blocks.items():
        addresses[start]=origin+len(image)
        for i in ids:
            ins=nodes[i][0]
            image.extend(b'\xc3'+exit_address.to_bytes(2,'little') if exit_address is not None and ins[0]==0xc3 else ins)
        if next_ is not None:image.extend(b'\xc3\0\0')
    if origin+len(image)>65536:
        # Oversize binary-search trial: length only, never an executable window.
        return bytes(image),{},{}
    cursor=0
    for start,(ids,next_) in blocks.items():
        cursor+=sum(len(nodes[i][0]) for i in ids)
        if next_ is not None:image[cursor+1:cursor+3]=addresses[next_].to_bytes(2,'little');cursor+=3
    entries={code:addresses[r] for code,r in roots.items()};jumps={}
    for code,root in roots.items():
        n=0;node=root
        while blocks[node][1] is not None:n+=1;node=blocks[node][1]
        jumps[code]=n
    return bytes(image),entries,jumps


def suffix_windows(programs,limit=0x3e40,exit_address=None):
    """Group similar reversed instruction streams; duplicate tails at bank edges."""
    unique=sorted(set(programs),key=lambda c:tuple(reversed(instructions(c))))
    windows=[];group=[]
    # Monotonic byte lengths allow a bounded binary search for each closure.
    first=0
    while first<len(unique):
        low=first+1;high=len(unique)+1
        while low+1<high:
            mid=(low+high)//2
            if len(suffix_graph(unique[first:mid])[0])<=limit:low=mid
            else:high=mid
        data,entries,jumps=suffix_graph(unique[first:low],exit_address=exit_address)
        if len(data)>limit:raise ValueError('One suffix closure exceeds Page1')
        windows.append(dict(data=data,entries=entries,jumps=jumps));first=low
    return windows


def compact_programs(cases):
    """Smaller measured tradeoff: all short workers plus shared23-byte headers."""
    prefixes=sorted({c['relative'][:23] for c in cases if c['relative'][:2]==b'\x0e\x98' and len(c['relative'])>23})
    assert len(prefixes)*24<=0x340
    for c in cases:
        code=c['relative'];result=bytearray();at=0
        if len(code)>23:result.extend(b'\xcd'+(0x300+prefixes.index(code[:23])).to_bytes(2,'little'));at=23
        parts=instructions(code[at:]);i=0
        while i<len(parts):
            if parts[i]==b'\xed\xa3':
                end=i
                while end<len(parts) and parts[end]==b'\xed\xa3':end+=1
                n=end-i
                if n>=2:result.extend(b'\xcd'+(SHORT+n).to_bytes(2,'little'))
                else:result.extend(parts[i])
                i=end
            else:
                result.extend(parts[i]);i+=1
        c['compact']=bytes(result);c['compact_cycles']=cycles(c['compact'],prefixes)
    return prefixes


def hoisted_programs(cases):
    """Move the identical14-byte header into Page3 dispatch, without a CALL.

    Its original instruction order/cost is retained immediately before JP(HL).
    Empty packets retain their original no-VDP/no-EI behavior. This saves bytes
    without the extra29-cycle header CALL used by the aggressive variant.
    """
    headers={c['relative'][:14] for c in cases if len(c['relative'])>23}
    assert len(headers)==1
    header=headers.pop()
    for c in cases:c['hoisted']=c['relative'][14:] if len(c['relative'])>23 else c['relative']
    return header


def absolute_programs(cases, records):
    """Cold-link absolute source operands for eight2KiB slots, then hoist14 bytes.

    Source tables move by page multiples, preserving the existing load/count
    optimizations and body cost. No D/E source-base ABI or active relocation is
    needed: D/E/IX/IY survive unchanged. Header execution stays before the body
    in the Page3 caller, with the original DI/EI/VDP ordering. The caller owns
    Page1 code, Page2 source, Page0 exact tails and stack; AF/HL/B are scratch.
    Suffix-linker joins remain a separate, measured cost, never a free saving.
    """
    from compact_transfer import events as absolute_events
    headers=set()
    for c in cases:
        record=records[c['record']];base=0x8000+(c['record']%2)*4096
        relocated=bytearray()
        for kind,n,raw in tokens(c['code']):
            if kind=='load':
                address=0x8000+c['slot']*2048+source_offset(int.from_bytes(raw[1:],'little'),record,base)
                relocated.extend(b'\x21'+address.to_bytes(2,'little'))
            else:relocated.extend(raw)
        code,_=optimize(bytes(relocated))
        assert cycles(code)==c['baseline_cycles'],'Absolute relocation changed body cost'
        decoded,hl,b=absolute_events(code)
        expected,relative_hl,relative_b=events(c['relative'],0x80+c['slot']*8,0x80+c['slot']*8+(2 if record['kind']=='hud' else 4))
        assert decoded==expected and b==relative_b and hl==relative_hl
        if len(code)>23:
            headers.add(code[:14]);c['absolute']=code[14:]
        else:c['absolute']=code
        c['absolute_cycles']=c['baseline_cycles']
    assert len(headers)==1
    return headers.pop()


def flat_windows(programs, limit=0x3e40, exit_address=None):
    """Cold first-fit link with zero suffix joins and no added body cycles.

    Returns the same closure interface as suffix_windows, but each terminal JP
    targets the caller's Page3 exit directly. Each immutable body is contiguous
    in one Page1 window. Register/IFF and mapping contracts are unchanged.
    """
    if not 0<limit<=16384:raise ValueError('Invalid code window size')
    windows=[]
    for code in sorted(set(programs),key=lambda c:(-len(c),c)):
        if len(code)>limit:raise ValueError('Packet exceeds code window')
        choices=[(limit-len(w['data'])-len(code),i) for i,w in enumerate(windows) if len(w['data'])+len(code)<=limit]
        i=min(choices)[1] if choices else len(windows)
        if i==len(windows):windows.append(dict(data=bytearray(),entries={},jumps={}))
        w=windows[i];w['entries'][code]=0x4000+len(w['data']);w['jumps'][code]=0
        body=code
        if exit_address is not None:
            assert code[-3]==0xc3
            body=code[:-2]+exit_address.to_bytes(2,'little')
        w['data'].extend(body)
    return windows


def prepare():
    from renderer_window_probe import probe
    from compact_transfer import events as old_events
    records=[];cases=[];probe(4096,cases,records,integrated=True,fast_transfers=False)
    packed=[pack_record(r) for r in records]
    for c in cases:
        record=records[c['record']];baseline,optim=optimize(c['code']);relative=compile_relative(c['code'],record,c['record'])
        slot=c['record']%8;d=0x80+slot*8;e=d+(2 if record['kind']=='hud' else 4)
        actual,_,b=events(relative,d,e);expected,_,old_b=old_events(baseline)
        translated=[]
        for event in expected:
            if event[0]=='data':translated.append(('data',0x8000+slot*2048+source_offset(event[1],record,0x8000+(c['record']%2)*4096)))
            else:translated.append(event)
        expected=translated
        assert actual==expected and b==old_b
        c.update(baseline=baseline,relative=relative,baseline_cycles=cycles(baseline),relative_cycles=cycles(relative),slot=slot)
    return cases,records,packed


def analyze(out=None):
    cases,records,packed=prepare();unique={c['relative'] for c in cases}
    # Code/data are separate16KiB windows; code may consume declared source
    # holes because Page1 and Page2 can map the same physical RAM segment.
    image=bytearray(b''.join(p[0] for p in packed));busy=bytearray(b''.join(p[1] for p in packed));locations={}
    holes=[]
    for page in range(len(image)//16384):
        holes.extend([page,a,b] for a,b in spans(bytes(1-x for x in busy[page*16384:(page+1)*16384])))
    for code in sorted(unique,key=lambda c:(-len(c),c)):
        choices=[(b-a-len(code),i) for i,(_,a,b) in enumerate(holes) if b-a>=len(code)]
        if not choices:
            page=len(image)//16384;image.extend(b'\xff'*16384);holes.append([page,0,16384]);choices=[(16384-len(code),len(holes)-1)]
        _,i=min(choices);page,a,b=holes[i];image[page*16384+a:page*16384+a+len(code)]=code;holes[i][1]+=len(code)
        locations[hashlib.sha256(code).hexdigest()]=(page,0x4000+a)
    deltas=[c['relative_cycles']-c['baseline_cycles'] for c in cases]
    windows=suffix_windows(unique)
    jump_counts={code:n for w in windows for code,n in w['jumps'].items()}
    suffix_deltas=[c['relative_cycles']+11*jump_counts[c['relative']]-c['baseline_cycles'] for c in cases]
    prefixes=compact_programs(cases);compact_windows=suffix_windows([c['compact'] for c in cases],limit=0x3b00)
    compact_jumps={code:n for w in compact_windows for code,n in w['jumps'].items()}
    compact_deltas=[c['compact_cycles']+11*compact_jumps[c['compact']]-c['baseline_cycles'] for c in cases]
    header=hoisted_programs(cases);hoisted_windows=suffix_windows([c['hoisted'] for c in cases])
    hoisted_jumps={code:n for w in hoisted_windows for code,n in w['jumps'].items()}
    hoisted_deltas=[c['relative_cycles']+11*hoisted_jumps[c['hoisted']]-c['baseline_cycles'] for c in cases]
    report=dict(status='Packet backend only; no complete512KiB executable',source_rom_sha256=hashlib.sha256((ROOT/'dist/newrallyx.rom').read_bytes()).hexdigest(),
        references=len(cases),records=len(records),slot_bytes=2048,data_live_bytes=sum(sum(p[1]) for p in packed),
        unique_programs=len(unique),unique_code_bytes=sum(map(len,unique)),hot_physical_segments=len(image)//16384,
        hot_bytes=len(image),main_work_segments=4,uncompressed_hot_owner_segments=5,
        current_expanded_cache_work_segments=6,
        provisional_bytes_before_cold_resources=len(image)+9*16384,
        slots_verified=list(range(8)),ordered_source_control_and_final_b_verified=True,
        packet_only_delta_cycles=dict(mean=sum(deltas)/len(deltas),min=min(deltas),max=max(deltas),slower=sum(v>0 for v in deltas),unchanged=sum(v==0 for v in deltas)),
        suffix=dict(code_windows=len(windows),code_live_bytes=sum(len(w['data']) for w in windows),
            code_window_sizes=[len(w['data']) for w in windows],
            hot_bytes=(12+len(windows))*16384,provisional_total_before_cold=(21+len(windows))*16384,
            extra_jumps=dict(mean=sum(jump_counts[c['relative']] for c in cases)/len(cases),max=max(jump_counts.values())),
            packet_only_delta_cycles=dict(mean=sum(suffix_deltas)/len(suffix_deltas),min=min(suffix_deltas),max=max(suffix_deltas),slower=sum(v>0 for v in suffix_deltas))),
        compact_suffix=dict(code_windows=len(compact_windows),code_live_bytes=sum(len(w['data']) for w in compact_windows),header_workers=len(prefixes),
            hot_bytes=(12+len(compact_windows))*16384,
            provisional_total_with_64k_work_and_native_audio_resident=(19+len(compact_windows))*16384,
            provisional_total_with_current_expanded_cache=(21+len(compact_windows))*16384,
            packet_only_delta_cycles=dict(mean=sum(compact_deltas)/len(compact_deltas),min=min(compact_deltas),max=max(compact_deltas),slower=sum(v>0 for v in compact_deltas))),
        hoisted_suffix=dict(code_windows=len(hoisted_windows),code_live_bytes=sum(len(w['data']) for w in hoisted_windows),common_header_bytes=len(header),header_call_overhead_cycles=0,
            hot_bytes=(12+len(hoisted_windows))*16384,provisional_total_with_64k_work_and_native_audio_resident=(19+len(hoisted_windows))*16384,
            provisional_total_with_current_expanded_cache=(21+len(hoisted_windows))*16384,
            packet_only_delta_cycles=dict(mean=sum(hoisted_deltas)/len(hoisted_deltas),min=min(hoisted_deltas),max=max(hoisted_deltas),slower=sum(v>0 for v in hoisted_deltas))),
        limits='No dispatch/mapping/D-E setup cost included. Full metadata relocations, cold-resource backing, loader/OS lifetimes, IRQ restoration and whole-game performance remain unqualified. Compressed file size is not resident usage.')
    out=Path(out or ROOT/'references/build/game-mapper512');out.mkdir(parents=True,exist_ok=True)
    (out/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'packet-locations.json').write_text(json.dumps(locations,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':analyze()
