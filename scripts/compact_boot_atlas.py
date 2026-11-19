"""Cold SCREEN5 atlas candidate; exact contributor pixels remain ignored.

Two hidden/display pages retain the old71-state timeline.8x8 pixel tiles live
only in boot VRAM pages2/3; their dictionary is loaded lazily. Tile code/LUTs
reuse main Page0 navigation RAM before the first game rebuild. No active-game
decode or extra mapper-RAM segment is introduced.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

PAGE=8192
PREFIX=0x2200


def prepare(rom,session,metadata):
    from renderer_image_build import replay
    at=session['banks']['SESSION_BOOT_BANK']*16384+4096
    table=rom[at:at+356];pages=[bytearray(27136),bytearray(27136)];frames=[];ticks=[]
    for i in range(71):
        p=i%2
        for dest,data,_ in replay(rom,table[i*5],int.from_bytes(table[i*5+1:i*5+3],'little')):
            pages[p][dest:dest+len(data)]=data
        frames.append(bytes(pages[p]));ticks.append(table[i*5+3:i*5+5])
    tiles=[bytes(32)];ids={tiles[0]:0};grid=[];palettes=set()
    for frame in frames:
        row=[]
        for y in range(0,212,8):
            for x in range(0,128,4):
                tile=b''.join(frame[(y+j)*128+x:(y+j)*128+x+4] for j in range(min(8,212-y))).ljust(32,b'\0')
                if tile not in ids:ids[tile]=len(tiles);tiles.append(tile)
                row.append(ids[tile])
        grid.append(row)
    status=metadata.get('hardware_status',{}).get('descriptor_index',-1);forced=set()
    for x,y,w,h in metadata.get('hardware_status',{}).get('rectangles',[]):
        forced.update(row*32+col for row in range(y//8,(y+h+7)//8) for col in range(x//8,(x+w+7)//8))
    previous=[[0]*864,[0]*864];last=[-1,-1];dirty=[];scores=Counter()
    for i,target in enumerate(grid):
        cells={j for j,v in enumerate(target) if v!=previous[i%2][j] or(last[i%2]==status and j in forced)}
        dirty.append(cells);previous[i%2]=target[:];last[i%2]=i
        j=0
        while j<864:
            if j not in cells:j+=1;continue
            n=1
            while j+n in cells and (j+n)//32==j//32 and target[j+n]==target[j]:n+=1
            if i>2 and n>1:scores[target[j]]+=n-1
            j+=n
    canonical_count=len(tiles);strip_base=(canonical_count+31)//32*32
    selected=sorted(scores,key=lambda v:(-scores[v],v))[:(2046-strip_base)//32]
    strips={v:strip_base+i*32 for i,v in enumerate(selected)}
    originals=tiles[:];tiles.extend([tiles[0]]*(strip_base-len(tiles)))
    for v in selected:tiles.extend([originals[v]]*32)
    for tile in tiles:
        colors=tuple(sorted({n for b in tile for n in (b>>4,b&15)}))
        if 1<len(colors)<=4:palettes.add(colors)
    palettes=sorted(palettes);assert len(palettes)<64 and len(tiles)<2047
    luts=bytearray()
    for colors in palettes:
        if len(colors)==2:
            for n in range(16):
                c=[colors[(n>>b)&1] for b in (3,2,1,0)]
                luts.extend((c[0]*16+c[1],c[2]*16+c[3]))
        else:
            c=colors+(colors[-1],)*(4-len(colors))
            luts.extend(bytes(c[n>>2]*16+c[n&3] for n in range(16))+bytes(16))
    packed=[]
    for tile in tiles:
        pixels=[n for b in tile for n in (b>>4,b&15)];colors=tuple(sorted(set(pixels)))
        if len(colors)==1:data=bytes((0xc0|colors[0],))
        elif len(colors)==2:
            masks=[sum(colors.index(pixels[y*8+x])<<(7-x) for x in range(8)) for y in range(8)]
            data=bytes((0x40|palettes.index(colors),*masks))
        elif len(colors)<=4:
            values=[sum(colors.index(pixels[i+j])<<(6-2*j) for j in range(4)) for i in range(0,64,4)]
            data=bytes((palettes.index(colors),*values))
        else:data=b'\xff'+tile
        # Decode via independently indexed palette LUTs, not the encoder's
        # original color/index arrays, before accepting any dictionary record.
        tag=data[0]
        if tag==255:actual=data[1:]
        elif tag>=0xc0:actual=bytes(((tag&15)*17,))*32
        else:
            lut=luts[(tag&63)*32:(tag&63)*32+32];actual=bytearray()
            for value in data[1:]:
                for n in (value>>4,value&15):
                    actual.extend(lut[n*2:n*2+2] if tag&64 else bytes((lut[n],)))
        assert actual==tile
        packed.append(data)
    commands=[]
    for i,target in enumerate(grid):
        cursor=0;words=[];cell=0
        while cell<864:
            if cell not in dirty[i]:cell+=1;continue
            tile=target[cell];n=1
            while (cell+n in dirty[i] and (cell+n)//32==cell//32 and
                   target[cell+n]==tile+n and (tile+n)//32==tile//32):n+=1
            repeat=1
            if i>2 and tile in strips:
                while cell+repeat in dirty[i] and (cell+repeat)//32==cell//32 and target[cell+repeat]==tile:repeat+=1
            if repeat>n:tile=strips[tile];n=repeat
            skip=cell-cursor
            while skip>=32:
                steps=min(skip//32,32);words.append(2047|((steps-1)<<11));cursor+=steps*32;skip-=steps*32
            if n>1:words.append(2046|((n-2)<<11))
            words.append(tile|(skip<<11));cursor=cell+n;cell+=n
        data=len(words).to_bytes(2,'little')+b''.join(w.to_bytes(2,'little') for w in words)
        assert len(data)<=PAGE
        commands.append(data)
    # Independent full hidden-page reconstruction, including8x8 bottom padding.
    actual=[bytearray(32768),bytearray(32768)]
    for i,data in enumerate(commands):
        cursor=0;run=1
        for at in range(2,len(data),2):
            word=int.from_bytes(data[at:at+2],'little');tile=word&2047;skip=word>>11
            if tile==2047:cursor+=(skip+1)*32;continue
            if tile==2046:run=skip+2;continue
            cursor+=skip;y,x=divmod(cursor,32);cursor+=1
            for k in range(run):
                for row in range(8):actual[i%2][(y*8+row)*128+(x+k)*4:(y*8+row)*128+(x+k)*4+4]=tiles[tile+k][row*4:row*4+4]
            cursor+=run-1;run=1
        assert actual[i%2][:27136]==frames[i],(i,next(j for j,(a,b) in enumerate(zip(actual[i%2],frames[i])) if a!=b))
    return dict(tiles=packed,luts=bytes(luts),commands=commands,ticks=ticks,
        report=dict(frames=71,tiles=len(tiles),canonical_tiles=canonical_count,repeat_strips=len(strips),prime_count=max(grid[1])+1,palettes=len(palettes),tile_bytes=sum(map(len,set(packed))),
            pointer_bytes=len(tiles)*3,lut_bytes=len(luts),command_bytes=sum(map(len,commands)),
            all_dictionary_records_and_full_frames_exact=True,frame_hashes=[hashlib.sha256(f).hexdigest() for f in frames]))


def allocate(root,bundle,rom,session,cases,records,out):
    """Pack hot code into declared data holes freed by the new cold codec."""
    from renderer_image_build import free_ranges,compile_map_chunk
    boot=prepare(rom,session,json.loads((bundle/'session-boot.json').read_text()))
    removed=set(range(4,68))|set(session['edge_banks'])|set(session['map_banks'])|{2,3,68,69,70,124}
    raw_banks=[n for n in range(len(rom)//16384) if n not in removed]
    mapping={bank:n*2 for n,bank in enumerate(raw_banks)}
    image=bytearray(b''.join(rom[n*16384:(n+1)*16384] for n in raw_banks))
    start=mapping[1]*PAGE+4096;image[start:start+PREFIX]=rom[124*16384:124*16384+PREFIX]
    base=len(image)//PAGE;image.extend(b'\xff'*(48*PAGE))
    occupied=bytearray(b'\1'*(base*PAGE))+bytearray(48*PAGE)
    occupied[mapping[1]*PAGE+4096+PREFIX:(mapping[1]+2)*PAGE]=b'\0'*(16384-4096-PREFIX)
    for n,r in enumerate(records):
        at=base*PAGE+n*4096;image[at:at+4096]=r['data'];occupied[at:at+4096]=r['occupied']
    holes=[[n,a,b] for n in range(1,len(image)//PAGE) for a,b in free_ranges(occupied[n*PAGE:(n+1)*PAGE])]
    def place(data):
        choices=[(b-a-len(data),i) for i,(_,a,b) in enumerate(holes) if b-a>=len(data)]
        if not choices:
            p=len(image)//PAGE;image.extend(b'\xff'*PAGE);holes.append([p,0,PAGE]);choices=[(PAGE-len(data),len(holes)-1)]
        _,i=min(choices);p,a,b=holes[i];image[p*PAGE+a:p*PAGE+a+len(data)]=data;holes[i][1]+=len(data)
        return p,0x8000+a
    table_page,table_address=place(bytes(len(boot['tiles'])*3))
    map_tables=[place(bytes(3072)) for _ in session['map_banks']]
    ring=json.loads((bundle/'ring-refresh.json').read_text());at=ring['mapper_bank']*16384+ring['entry']-0x8000
    ring_location=place(rom[at:at+ring['bytes']]);dictionary={};constructors=[]
    maps=session['map_banks'];descriptors=[]
    for chunk in sorted({rom[b*16384+i:b*16384+i+16] for b in maps for i in range(0,16384,16)}):
        code=compile_map_chunk(chunk);p,a=place(code);dictionary[chunk]=(p,a+8192);constructors.append((p,a+8192,len(code)))
    for n,b in enumerate(maps):
        raw=rom[b*16384:(b+1)*16384];table=b''.join(bytes((dictionary[raw[i:i+16]][0],))+dictionary[raw[i:i+16]][1].to_bytes(2,'little') for i in range(16368,-1,-16))
        p,a=map_tables[n];at=p*PAGE+a-0x8000;image[at:at+len(table)]=table
        descriptors.append(dict(old_bank=b,entry=(p,a),kind='stack16',bytes=16384,sha256=hashlib.sha256(raw).hexdigest()))
    tile_ptrs=bytearray();tile_locations={}
    for tile in boot['tiles']:
        if tile not in tile_locations:tile_locations[tile]=place(tile)
        p,a=tile_locations[tile];tile_ptrs.extend(bytes((p,))+(a+8192).to_bytes(2,'little'))
    at=table_page*PAGE+table_address-0x8000;image[at:at+len(tile_ptrs)]=tile_ptrs
    pointers={n:place(data) for n,data in enumerate(boot['commands'])}
    locations={}
    for code in sorted({r['code'] for r in cases},key=lambda c:(-len(c),c)):
        p,a=place(code);locations[hashlib.sha256(code).hexdigest()]=(p,a+8192)
    for row in cases:
        r=records[row['record']];p,a=locations[hashlib.sha256(row['code']).hexdigest()]
        at=base*PAGE+row['record']*4096+r['pointer_offset']+row['index']*3
        image[at:at+3]=bytes((p,))+a.to_bytes(2,'little')
    table=b''.join(bytes((pointers[i][0],))+pointers[i][1].to_bytes(2,'little')+boot['ticks'][i] for i in range(71))+b'\xff'
    at=mapping[1]*PAGE+8192;image[at:at+len(table)]=table
    (out/'allocation.bin').write_bytes(image);(out/'atlas-luts.bin').write_bytes(boot['luts'])
    layout=dict(raw_bank_pages=mapping,data_base=base,code_base=base+48,code_locations=locations,
        maps=descriptors,map_backend='stack16',map_storage_optimized=True,map_constructors=constructors,
        map_constructor_bytes=sum(r[2] for r in constructors),map_table_bytes=len(maps)*3072,
        boot_pointers=pointers,boot_codec='atlas8',boot_prefix_bytes=PREFIX,
        atlas_table=(table_page,table_address+8192),atlas=boot['report'],ring=ring_location,reserved=None)
    (out/'layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    report=dict(allocated_bytes=len(image),pages_8k=len(image)//PAGE,below_768k=len(image)<=768*1024,
        atlas=boot['report'],status='Allocation only; native atlas worker and whole game require qualification')
    print(json.dumps({k:v for k,v in report.items() if k!='atlas'},indent=2));return report
