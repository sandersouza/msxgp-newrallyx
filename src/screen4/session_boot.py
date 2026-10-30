"""Replay original cold-boot states losslessly on the arcade timeline."""
import hashlib,json,os,subprocess,re
from pathlib import Path
from PIL import Image
from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.msx.screen5 import rgb333

def enabled(source=None,setting=None):
    if source is None:source=Path(__file__).with_name('session-startup-options.inc').read_text()
    if setting is None:setting=os.environ.get('NRX_HARDWARE_CHECK','1')
    assert setting in ('0','1'),'HARDWARE_CHECK must be0 or1'
    return setting=='1' and bool(re.search(r'^\s*INCLUDE "session-boot.inc"\s*$',source,re.M))

def capture(root):
    out=root/'references/experiments/arcade-boot-video';out.mkdir(parents=True,exist_ok=True)
    version=subprocess.check_output(['mame','-version'],text=True).strip();assert version.startswith('0.289 ')
    key=dict(emulator=version,roms=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())),sample_step=12,seconds=14)
    marker=out/'reference.json';old=json.loads(marker.read_text()) if marker.exists() else {}
    if old.get('inputs')!=key or not all((out/n).exists() and hashlib.sha256((out/n).read_bytes()).hexdigest()==h for n,h in old.get('hashes',{}).items()) or not old.get('hashes'):
        command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),'-video','none','-sound','none',
          '-aviwrite',str(out/'boot.avi'),'-nothrottle','-noautosave','-skip_gameinfo','-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','14']
        with (out/'mame.log').open('w') as log:subprocess.run(command,check=True,timeout=90,stdout=log,stderr=subprocess.STDOUT)
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(out/'boot.avi'),'-vf','select=not(mod(n\\,12))','-fps_mode','vfr',str(out/'frame-%03d.png')],check=True,timeout=30)
    images=[]
    for i,p in enumerate(sorted(out.glob('frame-*.png'))):
        im=Image.open(p).convert('RGB');assert im.size==(288,224)
        colors=im.getcolors(288*224);grid=len(colors)==2 and sum(n for n,c in colors if c!=(0,0,0))>3000
        images.append((i*12,im,grid))
    grids=[i for i,(_,_,grid) in enumerate(images) if grid];assert grids
    end=images[grids[-1]+1][0];start_grid=images[grids[0]][0]
    # Preserve stage progression/timing, sampling moving artifact states at60
    # original refreshes. Identical ROM-OK and matrix states need one upload.
    selected=[];last=None
    for n,im,grid in images:
        if n>=end:break
        if n%60 and n not in (12,start_grid):continue
        h=hashlib.sha256(im.tobytes()).hexdigest()
        if h==last:continue
        selected.append((n,im));last=h
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('frame-*.png')}
    meta=dict(inputs=key,hashes=hashes,native_end_frame=end,matrix_frame=start_grid,sample_frames=[n for n,im in selected],
              scope='Untouched original cold boot recorded from the first video frame. No Lua delay, guest writes or injected test flags. Matrix endpoint is sampled within12 original refreshes.')
    marker.write_text(json.dumps(meta,indent=2)+'\n');return selected,meta

def encode_rows(raw):
    """Packed128-byte rows; zero repeats a row,128 is a literal row."""
    assert len(raw)%128==0
    data=bytearray();previous=None
    for y in range(len(raw)//128):
        row=raw[y*128:(y+1)*128]
        if row==previous:data.append(0);continue
        pairs=bytearray();i=0
        while i<128:
            j=i+1
            while j<128 and row[j]==row[i]:j+=1
            pairs.extend((j-i,row[i]));i=j
        if len(pairs)<128:data.append(len(pairs)//2);data.extend(pairs)
        else:data.append(128);data.extend(row)
        previous=row
    return bytes(data)

CPU_HZ=3579545
REFRESH_CYCLES=59736
ARCADE_HZ=2000/33

def encode_delta(old,new):
    """Lossless byte spans: opcode, addressLE, count(0=256), payload.

    Literal and constant spans go directly from the banked ROM to the VDP.
    The deliberately conservative planning cost includes address setup,
    per-command skip checks, interrupts and repeat-loop overhead.
    """
    assert len(old)==len(new)==27136
    dirty=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    if not dirty:return b'\0',600
    spans=[];start=last=dirty[0]
    for i in dirty[1:]:
        if i-last>5:spans.append((start,last+1));start=i
        last=i
    spans.append((start,last+1))
    data=bytearray();cost=600
    def emit(op,at,raw):
        nonlocal cost
        data.extend((op,at&255,at>>8,len(raw)&255))
        data.extend(raw[:1] if op==2 else raw)
        cost+=520+len(raw)*(38 if op==2 else 28)
    for start,end in spans:
        i=start
        while i<end:
            j=i+1
            while j<end and j-i<256 and new[j]==new[i]:j+=1
            if j-i>=5:emit(2,i,new[i:j]);i=j;continue
            j=i+1
            while j<end and j-i<256:
                k=j+1
                while k<end and k-j<5 and new[k]==new[j]:k+=1
                if k-j>=5:break
                j+=1
            emit(1,i,new[i:j]);i=j
    data.append(0)
    return bytes(data),round(cost*1.40+3000)

def decode_delta(old,data):
    result=bytearray(old);i=0
    while data[i]:
        op=data[i];at=data[i+1]+256*data[i+2];n=data[i+3] or 256;i+=4
        assert op in (1,2) and at+n<=len(result)
        result[at:at+n]=data[i:i+n] if op==1 else data[i:i+1]*n
        i+=n if op==1 else 1
    assert i==len(data)-1
    return bytes(result)

def plan_frames(frames,end):
    """Prepare hidden-page deltas, then publish on the original timeline.

    Select the earliest native state whose preparation fits after the previous
    publication. Selection is temporal only: every published pixel is exact.
    Original RGB333 mapping and the established 1:1 crop remain unchanged.
    """
    pages=[bytes(27136),bytes(27136)];records=[];last_tick=0;last=None
    for n,new in enumerate(frames[:end]):
        if new==last:continue
        data,cost=encode_delta(pages[len(records)%2],new)
        tick=round(n*(CPU_HZ/REFRESH_CYCLES)/ARCADE_HZ)
        if n and cost>(tick-last_tick)*REFRESH_CYCLES:continue
        records.append(dict(native_frame=n,tick=tick,data=data,planned_cycles=cost))
        pages[(len(records)-1)%2]=new;last=new;last_tick=tick
    return records

def append(root,out,page,*,image=None,holes=None):
    if not enabled():
        for name in ('data','palette'):(out/f'session-boot-{name}.inc').write_text('; Hardware-check module omitted.\n')
        (out/'session-boot.json').write_text(json.dumps(dict(enabled=False,frame_count=0,compressed_bytes=0,scope='Module omitted at build time; shared HUD/test workers remain independent.'),indent=2)+'\n')
        return
    _,meta=capture(root)
    video=root/'references/experiments/arcade-boot-video'
    frames_dir=video/'all';frames_dir.mkdir(exist_ok=True)
    if not (frames_dir/'frame-0850.png').exists():
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(video/'boot.avi'),'-fps_mode','passthrough',str(frames_dir/'frame-%04d.png')],check=True,timeout=60)
    paths=sorted(frames_dir.glob('frame-*.png'))
    colors=sorted({c for p in paths for count,c in Image.open(p).convert('RGB').getcolors(288*224)})
    assert len(colors)<=16
    palette_image=Image.new('P',(1,1));palette_image.putpalette([v for c in colors for v in c]+[0]*(768-len(colors)*3))
    frames=[];grids=[]
    for n,p in enumerate(paths):
        im=Image.open(p).convert('RGB')
        counts=im.getcolors(288*224)
        if len(counts)==2 and sum(k for k,c in counts if c!=(0,0,0))>3000:grids.append(n)
        cropped=Image.new('RGB',(256,212));cropped.paste(im.crop((0,0,200,212)),(0,0));cropped.paste(im.crop((232,0,288,212)),(200,0))
        pix=cropped.quantize(palette=palette_image,dither=Image.Dither.NONE).tobytes()
        frames.append(bytes(a*16+b for a,b in zip(pix[::2],pix[1::2])))
    assert grids and all(b==a+1 for a,b in zip(grids,grids[1:])),grids
    end=grids[-1]+1;records=plan_frames(frames,end)
    # Existing opcodes support arbitrary bank/address chains. Reuse only
    # explicitly reserved graphics-bank holes; no new decoder or RAM buffer.
    if image is not None:
        from rom_pack import pack_replay
        pointers,packing=pack_replay(records,image,holes)
        compressed_bytes=packing['encoded_bytes']
        report=json.loads((out/'rom-packing.json').read_text())
        report['boot']=packing
        (out/'rom-packing.json').write_text(json.dumps(report,indent=2)+'\n')
    else:
        chunks=[];storage=bytearray();locations={};literals={}
        for i,r in enumerate(records):
            data=r['data'];at=0;first=True
            while at<len(data):
                op=data[at]
                size=1 if op==0 else 5 if op==2 else 4+(data[at+3] or 256)
                raw=data[at+4:at+size] if op==1 else None
                reused=raw is not None and len(raw)>2 and raw in literals
                wire_size=6 if reused else size
                if len(storage)+wire_size+4>16384:
                    chunks.append(storage);storage=bytearray();literals={};reused=False
                if first:locations[i]=(len(chunks),0x8000+len(storage));first=False
                if reused:
                    pointer=literals[raw]
                    storage.extend((4,data[at+1],data[at+2],data[at+3],pointer&255,pointer>>8))
                else:
                    if raw is not None:literals.setdefault(raw,0x8000+len(storage)+4)
                    storage.extend(data[at:at+size])
                at+=size
        chunks.append(storage);physical={}
        for i in range(len(chunks)-1,-1,-1):
            if i+1<len(chunks):chunks[i].extend((3,physical[i+1],0,128))
            physical[i]=page(chunks[i])
        pointers={i:(physical[k],address) for i,(k,address) in locations.items()}
        compressed_bytes=sum(len(chunk) for chunk in chunks)
    rgb=[rgb333(c) for c in colors]
    palette=bytes(v for r,g,b in rgb for v in ((r<<4)|b,g)).ljust(32,b'\0')
    lines=['GameSession_BootPalette:','    db '+','.join(map(str,palette))]
    (out/'session-boot-palette.inc').write_text('\n'.join(lines)+'\n')
    lines=['GameSession_BootFrames:']
    for i,r in enumerate(records):
        bank,address=pointers[i];lines.extend((f'    db {bank}',f'    dw {address}',f"    dw {r['tick']}"))
    ticks=round(end*(CPU_HZ/REFRESH_CYCLES)/ARCADE_HZ)
    lines.extend(('    db 255',f'GameSession_BootDeadline EQU {ticks}','GameSession_BootTableEnd:'))
    (out/'session-boot-data.inc').write_text('\n'.join(lines)+'\n')
    meta.update(enabled=True,border_color_index=0,border_rgb=[0,0,0],native_end_frame=end,matrix_frame=grids[0],sample_frames=[r['native_frame'] for r in records],
        frame_paths=[str(paths[r['native_frame']].resolve()) for r in records],speed_multiplier=1.0,
        physical_deadline_ticks=ticks,seconds=ticks*REFRESH_CYCLES/CPU_HZ,compressed_bytes=compressed_bytes,unshared_stream_bytes=sum(len(r['data']) for r in records),
        frame_count=len(records),native_changed_states=1+sum(a!=b for a,b in zip(frames[:end-1],frames[1:end])),
        planned_cycles=[r['planned_cycles'] for r in records],publication_ticks=[r['tick'] for r in records],
        geometry='1:1 pixels; original columns0..199 and232..287, rows0..211; no scaling',palette=colors,
        scope='Untouched original cold boot, all source refreshes inspected. Lossless hidden-page deltas; bandwidth-limited temporal selection on the original 60.606Hz timeline, mapped to MSX refreshes. Matrix endpoint detected at the exact native refresh; no1.5x acceleration.')
    (out/'session-boot.json').write_text(json.dumps(meta,indent=2)+'\n')
