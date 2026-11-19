"""Account for compact renderer, all other bank owners and cold payloads.

This creates an ignored, NON-BOOTABLE allocation image: consumers and native
16 KiB bank constants still need relinking. No bytes in dist/ are modified.
Padding comes from declared record fields, never a search for FF/zero runs.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/toolchain/screen4'),str(ROOT)]
from renderer_window_probe import probe
from disk_package import compress_bank, decompress_bank
from rom_pack import pack_replay

PAGE=8192


def replay(rom, bank, address, bank_bytes=16384):
    """Independently expand one old/new command stream into literal/fill spans."""
    spans=[]
    for _ in range(20000):
        at=bank*bank_bytes+address-0x8000
        assert 0x8000<=address<0x8000+bank_bytes
        op=rom[at]
        if op==0:return spans
        if op==3:
            bank=rom[at+1];address=int.from_bytes(rom[at+2:at+4],'little')
            continue
        assert op in (1,2,4)
        dest=int.from_bytes(rom[at+1:at+3],'little');size=rom[at+3] or 256
        if op==1:
            raw=rom[at+4:at+4+size];address+=4+size
        elif op==2:
            raw=bytes([rom[at+4]])*size;address+=5
        else:
            source=int.from_bytes(rom[at+4:at+6],'little')
            assert 0x8000<=source and source+size<=0x8000+bank_bytes
            p=bank*bank_bytes+source-0x8000
            raw=rom[p:p+size];address+=6
        assert len(raw)==size
        spans.append((dest,raw,op==2))
    raise ValueError('Replay chain does not terminate')


def free_ranges(mask):
    begin=None
    for n,busy in enumerate(mask+b'\x01'):
        if not busy and begin is None:begin=n
        if busy and begin is not None:
            yield begin,n
            begin=None


def compile_map_chunk(chunk, continuation=0, *, optimize=True):
    """Compile16 bytes into eight reverse-order word pushes and a tail JP.

    Runtime owns a DI-protected Page0 data stack. Clobbers HL/SP only; no
    CALL/RET or source read can use that stack. The linker supplies resident JP.
    HL survives PUSH: equal words share a load; one-byte changes use LD H/L,n.
    The first word always loads HL: entry HL contains the constructor address.
    optimize=False reproduces the measured35-byte Issue41/early42 fixture.
    """
    if len(chunk)!=16 or not 0<=continuation<=65535:
        raise ValueError('Expected16 bytes and a16-bit continuation')
    program=bytearray();previous=None
    for at in range(14,-1,-2):
        word=chunk[at:at+2]
        if not optimize or previous is None or (word[0]!=previous[0] and word[1]!=previous[1]):
            program.extend(b'\x21'+word)
        elif word[0]!=previous[0]:program.extend((0x2e,word[0]))
        elif word[1]!=previous[1]:program.extend((0x26,word[1]))
        previous=word
        program.append(0xe5)
    program.extend(b'\xc3'+continuation.to_bytes(2,'little'))
    return bytes(program)


def build(integrated=False, bundle=None, *, optimize_maps=True,fast_transfers=False,boot_atlas=False):
    out=ROOT/'references/build'/('game-compact-runtime-allocation' if integrated else 'game-compact-allocation')
    out.mkdir(parents=True,exist_ok=True)
    bundle=Path(bundle or ROOT/'references/build/game').resolve()
    rom=(bundle/'newrallyx.rom').read_bytes()
    assert len(rom)==125*16384, 'Compact source layout requires the125-bank full-session linker'
    session=json.loads((bundle/'session-build.json').read_text())
    cases=[];records=[];probe(4096,cases,records,integrated=integrated,bundle=bundle,fast_transfers=fast_transfers)
    if boot_atlas:
        assert integrated and optimize_maps
        from compact_boot_atlas import allocate
        return allocate(ROOT,bundle,rom,session,cases,records,out)
    maps=session['map_banks'] if integrated else [2,3]+session['map_banks']
    removed=set(range(4,68))|set(session['edge_banks'])|set(maps)|{2,3,124}
    if integrated:removed.update((68,69,70))
    raw_banks=[n for n in range(len(rom)//16384) if n not in removed]
    image=bytearray(b''.join(rom[n*16384:(n+1)*16384] for n in raw_banks))
    mapping={bank:n*2 for n,bank in enumerate(raw_banks)}
    # The boot bank has only its declared1536-byte worker and356-byte table.
    # Preserve the whole4452-byte prefix inside the initial terrain bank's
    # generator-declared12 KiB reservation. Consumers still need source rebinding.
    assert rom[16384+4096:32768]==b'\xff'*12288
    at=mapping[1]*PAGE+4096
    image[at:at+4452]=rom[124*16384:124*16384+4452]
    data_base=len(image)//PAGE
    image.extend(b'\xff'*(48*PAGE))
    occupied=bytearray(b'\x01'*(data_base*PAGE))+bytearray(48*PAGE)
    codes=[];locations={}
    for code in sorted({r['code'] for r in cases},key=lambda c:(-len(c),c)):
        choices=[(PAGE-len(p)-len(code),n) for n,p in enumerate(codes) if len(p)+len(code)<=PAGE]
        n=min(choices)[1] if choices else len(codes)
        if n==len(codes):codes.append(bytearray())
        locations[code]=(data_base+48+n,0xa000+len(codes[n]))
        codes[n].extend(code)
    for row in cases:
        record=records[row['record']]
        page,address=locations[row['code']]
        at=record['pointer_offset']+row['index']*3
        record['data'][at:at+3]=bytes((page,address&255,address>>8))
    for n,record in enumerate(records):
        at=data_base*PAGE+n*4096
        image[at:at+4096]=record['data']
        occupied[at:at+4096]=record['occupied']
    for code in codes:
        image.extend(bytes(code).ljust(PAGE,b'\xff'))
        occupied.extend(b'\x01'*len(code)+b'\0'*(PAGE-len(code)))
    cold_pages=0 if integrated else 2
    image.extend(b'\xff'*(cold_pages*PAGE))
    occupied.extend(b'\0'*(cold_pages*PAGE))
    fixed_tables=[]
    if integrated:
        if not optimize_maps:
            # Diagnostic reproduction only: former four fixed descriptor pages.
            start=len(image)//PAGE
            image.extend(b'\xff'*(4*PAGE));occupied.extend(b'\0'*(4*PAGE))
            for n in range(8):
                at=start*PAGE+n*4096;occupied[at:at+3072]=b'\x01'*3072
                fixed_tables.append((start+n//2,0x8000+(n%2)*4096))
        # Initial terrain and the rehomed boot prefix are the complete live
        # owners of this raw bank; the declared remaining tail is reusable.
        at=mapping[1]*PAGE+8548
        occupied[at:(mapping[1]+2)*PAGE]=b'\0'*((mapping[1]+2)*PAGE-at)
    holes=[[n,a,b] for n in range(1,len(image)//PAGE)
           for a,b in free_ranges(occupied[n*PAGE:(n+1)*PAGE])]
    def place(raw):
        choices=[(b-a-len(raw),i) for i,(_,a,b) in enumerate(holes) if b-a>=len(raw)]
        if not choices:raise ValueError(f'No contiguous hole for {len(raw)} bytes')
        _,i=min(choices);page,a,b=holes[i]
        image[page*PAGE+a:page*PAGE+a+len(raw)]=raw
        holes[i][1]+=len(raw)
        return page,0x8000+a

    # Ring worker uses local relative branches and absolute RAM addresses only.
    # Its raw body therefore relocates without instruction/operand changes.
    ring=json.loads((bundle/'ring-refresh.json').read_text())
    start=ring['mapper_bank']*16384+ring['entry']-0x8000
    ring_location=place(rom[start:start+ring['bytes']])
    reserve=place(bytes(1024))  # Explicit space, not yet an implemented runtime.
    # Keep each1024-entry table contiguous for the unchanged three-byte hot
    # dispatch, but consume declared holes before reserving another whole page.
    # These placements precede small constructors and boot replay packing.
    map_tables=list(fixed_tables)
    if integrated and optimize_maps:
        for _ in maps:
            if not any(b-a>=3072 for _,a,b in holes):
                page=len(image)//PAGE
                image.extend(b'\xff'*PAGE);holes.append([page,0,PAGE])
            map_tables.append(place(bytes(3072)))
    descriptors=[]
    constructors=[]
    if integrated:
        chunks={rom[b*16384+at:b*16384+at+16] for b in maps for at in range(0,16384,16)}
        dictionary={}
        for chunk in sorted(chunks):
            program=compile_map_chunk(chunk,optimize=optimize_maps)
            page,address=place(program);dictionary[chunk]=(page,address+8192)
            constructors.append((page,address+8192,len(program)))
        for n,bank in enumerate(maps):
            raw=rom[bank*16384:(bank+1)*16384];table=bytearray()
            for at in range(16368,-1,-16):
                page,address=dictionary[raw[at:at+16]]
                table.extend((page,address&255,address>>8))
            page,address=map_tables[n];at=page*PAGE+address-0x8000
            image[at:at+3072]=table
            descriptors.append(dict(old_bank=bank,entry=(page,address),kind='stack16',bytes=16384,
                                    sha256=hashlib.sha256(raw).hexdigest()))
            # Independent execution-language model: every PUSH writes its
            # little-endian word below SP; descriptor order is part of proof.
            actual=bytearray(16384);sp=16384
            for cursor in range(0,3072,3):
                p=table[cursor];pc=int.from_bytes(table[cursor+1:cursor+3],'little')
                at=p*PAGE+pc-0xa000;word=None;pushes=0
                while image[at]!=0xc3:
                    op=image[at];at+=1
                    if op==0x21:word=bytearray(image[at:at+2]);at+=2
                    elif op in (0x26,0x2e):
                        assert word is not None
                        word[1 if op==0x26 else 0]=image[at];at+=1
                    else:
                        assert op==0xe5 and word is not None
                        sp-=2;actual[sp:sp+2]=word;pushes+=1
                assert pushes==8
            assert sp==0 and actual==raw
    for bank in ([] if integrated else maps):
        raw=rom[bank*16384:(bank+1)*16384];packed=compress_bank(raw)
        assert decompress_bank(packed)==raw
        # Fragment header: remaining count, next page, next address (5 bytes).
        # Chunks are linked after placement; no chunk crosses an8 KiB window.
        fragments=[];cursor=0
        while cursor<len(packed):
            choices=[(b-a,i) for i,(_,a,b) in enumerate(holes) if b-a>=6]
            _,i=max(choices);page,a,b=holes[i]
            count=min(b-a-5,len(packed)-cursor)
            address=0x8000+a
            image[page*PAGE+a:page*PAGE+a+5+count]=count.to_bytes(2,'little')+b'\xff\0\0'+packed[cursor:cursor+count]
            holes[i][1]+=5+count
            fragments.append((page,address,count));cursor+=count
        for current,nxt in zip(fragments,fragments[1:]):
            page,address,_=current;np,na,_=nxt
            at=page*PAGE+address-0x8000+2
            image[at:at+3]=bytes((np,na&255,na>>8))
        recovered=bytearray()
        for page,address,count in fragments:
            at=page*PAGE+address-0x8000
            recovered.extend(image[at+5:at+5+count])
        assert decompress_bank(recovered)==raw
        descriptors.append(dict(old_bank=bank,entry=fragments[0][:2],fragments=len(fragments),
                                compressed_bytes=len(packed),sha256=hashlib.sha256(raw).hexdigest()))
    # Decode the actual linked boot descriptors, not regenerated/re-sampled video.
    old_table=rom[session['banks']['SESSION_BOOT_BANK']*16384+0x1000:][:356]
    assert old_table[-1]==255 and len(old_table)==356
    frames=[];ticks=[];expected=[]
    for at in range(0,355,5):
        bank=old_table[at];address=int.from_bytes(old_table[at+1:at+3],'little')
        spans=replay(rom,bank,address);raw=bytearray()
        for dest,data,fill in spans:
            for offset in range(0,len(data),256 if fill else 128):
                part=data[offset:offset+(256 if fill else 128)]
                target=dest+offset
                raw.extend(bytes((2 if fill else 1,target&255,target>>8,len(part)&255)))
                raw.extend(part[:1] if fill else part)
        raw.append(0);frames.append(dict(data=bytes(raw)));expected.append(spans)
        ticks.append(old_table[at+3:at+5])
    tail=image[PAGE:]
    pointers,packing=pack_replay(frames,tail,[h for h in holes if h[1]<h[2]],bank_bytes=PAGE,
                                reuse_across_holes=True)
    image[PAGE:]=tail
    if integrated:
        table=bytearray()
        for n in range(71):
            bank,address=pointers[n]
            table.extend(bytes((bank,address&255,address>>8))+ticks[n])
        table.append(255)
        at=mapping[1]*PAGE+8192
        image[at:at+len(table)]=table
    def written(spans):
        result={}
        for dest,raw,_ in spans:
            result.update(enumerate(raw,dest))
        return result
    for n,(bank,address) in pointers.items():
        assert written(replay(image,bank,address,PAGE))==written(expected[n])
    (out/'allocation.bin').write_bytes(image)
    # Exact target addresses are original-derived metadata and remain ignored.
    (out/'layout.json').write_text(json.dumps(dict(raw_bank_pages=mapping,data_base=data_base,
        code_base=data_base+48,maps=descriptors,boot_pointers=pointers,
        map_backend='stack16' if integrated else 'lz',map_constructors=constructors,
        map_storage_optimized=bool(integrated and optimize_maps),
        map_constructor_bytes=sum(r[2] for r in constructors),map_table_bytes=len(maps)*3072 if integrated else 0,
        ring=ring_location,reserved=reserve),indent=2)+'\n')
    report=dict(source_sha256=hashlib.sha256(rom).hexdigest(),allocation_sha256=hashlib.sha256(image).hexdigest(),allocated_bytes=len(image),pages_8k=len(image)//PAGE,
        below_1mib=len(image)<1048576,raw_banks_preserved=len(raw_banks),raw_allocated_bytes=len(raw_banks)*16384,
        hot_allocated_bytes=(48+len(codes))*PAGE,map_banks=len(maps),map_compressed_bytes=sum(x.get('compressed_bytes',0) for x in descriptors),
        boot_frames=len(frames),boot_encoded_bytes=packing['encoded_bytes'],boot_chains=packing['chains'],
        ring_bytes=ring['bytes'],runtime_reservation_bytes=1024,all_maps_host_roundtrip=True,
        boot_prefix_rehomed_bytes=4452,extra_cold_pages_8k=cold_pages,
        all_boot_frame_final_bytes_independently_equal=True,
        source_files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ['scripts/renderer_image_build.py','scripts/renderer_window_probe.py','scripts/disk_package.py','src/toolchain/screen4/rom_pack.py']},
        caveat='NON-BOOTABLE allocation experiment. Remaining raw bank and caller addresses are not relinked; omitted legacy atlas liveness is unproven; 1024-byte runtime reserve is not an implemented backend. No full-game or performance acceptance.')
    if not integrated:
        (ROOT/'docs/measurements/cartridge/issue41-allocation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':build()
