#!/usr/bin/env python3
"""Check dynamic natural-route VRAM against independent source-pixel oracles."""
import argparse
from pathlib import Path
import sys
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.full_game_probe import world
from scripts.msx.player import padded_world
from scripts.msx.player_verify import check_cache
from scripts.msx.raster_scroll import header
from scripts.msx.screen5 import packed
from scripts.msx.stage_one import acquire
from scripts.msx.smoke import paint,verify_publication_counts
from scripts.scenes.bundle import digest,load_assets,read_json,verify_manifest
from scripts.scenes.storage import require_ignored,json_write,seal
from scripts.msx.build import destination
from scripts.msx.hud_verify import symbols
from scripts.msx.full_memory import irq_image


def number(data):
    if len(data)!=8 or any(v>9 for v in data):raise ValueError('Invalid eight-digit HUD snapshot')
    return int(''.join(map(str,data)))


def actors(state,vram,pixels,scroll,compact=False):
    visible=0;candidates=[0]*212
    count=state[0x224e]
    for i in range(count):
        record=state[0xe20+i*32:0xe40+i*32]
        if not record[0]:continue
        slot=state[0xe20+i*32+30]//4 if compact else 18+i*2
        if compact and slot!=18+visible*2:raise ValueError('Visible actor order changed during SAT compaction')
        visible+=1
        sat=vram[0x1f600+slot*4:0x1f600+slot*4+8]
        if any(vram[0x1f600+s*4]==216 for s in range(slot+2)):
            raise ValueError('SAT terminator hides a visible natural enemy')
        x=int.from_bytes(record[6:8],'little',signed=True)
        y=int.from_bytes(record[8:10],'little',signed=True)
        expected_y=(scroll+y-1)&255
        if sat[0]!=expected_y or sat[4]!=expected_y:
            raise ValueError('Natural enemy SAT Y differs from prepared pose')
        ec=128 if x<0 else 0
        if sat[1]!=((x+(32 if ec else 0))&255) or sat[5]!=sat[1]:raise ValueError('Natural enemy SAT X differs from prepared pose')
        colors=vram[0x1f400+slot*16:0x1f400+slot*16+32]
        if colors!=bytes([0x26|ec])*16+bytes([0x6a|ec])*16:raise ValueError('Natural enemy OR colors differ')
        car=pixels[record[19]*256:][:256]
        expected=bytes(sum(int(car[py*16+px+bit] in plane and x+px+bit>=8 and py+y!=11)<<(7-bit)
            for bit in range(8)) for plane in ((3,11),(9,11)) for px in (0,8) for py in range(16))
        actual=b''.join(vram[0x1f800+(p&252)*8:0x1f800+(p&252)*8+32] for p in (sat[2],sat[6]))
        if actual!=expected:raise ValueError(f'Natural enemy {i} masks differ from complete source drawing')
        for row in range(max(11,y),min(212,y+16)):candidates[row]+=2
    return visible,max(candidates,default=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];bundle=args.rom.resolve().parent
    verify_manifest(bundle);verify_manifest(args.capture)
    if read_json(args.capture/'report.json')['rom_sha256']!=digest(args.rom):raise ValueError('Natural route used another cartridge')
    out=destination(root,args.output);require_ignored(root,[out/'report.json']);out.mkdir(parents=True)
    program,_=acquire(root);assets=load_assets(root/'references/assets/nrallyx');palette=(bundle/'palette.bin').read_bytes()
    death=(bundle/'death-pixels.bin').read_bytes();smoke=(bundle/'smoke-pixels.bin').read_bytes()
    pixels=(bundle/'player-pixels.bin').read_bytes();flags=read_json(bundle/'player.json')['flags']
    syms=symbols(bundle/'raster-scroll.sym');scroll_address=syms['scroll_y']-0xc000
    irq=irq_image(bundle,syms);irq_at=syms.get('Full_RadarIRQStart',0)-0xc000
    frames=sorted(args.capture.glob('*.state'),key=lambda p:int(p.stem));visible=maximum=0
    for path in frames:
        state=path.read_bytes();vram=path.with_suffix('.vram').read_bytes()
        if irq and state[irq_at:irq_at+len(irq)]!=irq:raise ValueError('Natural scene overwrote raster IRQ code')
        image=world(program,state[0x2000:0x3000],state[0x534:0x53f],assets,palette)
        image,width,_=padded_world(image)
        display=state[0x1300:0x1b00]
        verify_publication_counts(display,state[0x1b00:0x1b20])
        paint(image,width,256,display,smoke)
        if state[0x49a]==1:
            ax,ay=state[0x492:0x494]
            for n in range(9):
                for y in range(8):
                    at=(ay*8+n//3*8+y+256)*width+ax*8+n%3*8+256
                    image[at:at+8]=death[n*64+y*8:n*64+y*8+8]
        bitmap=bytearray(packed(image))
        if state[0x418]:
            px=int.from_bytes(state[0x405:0x407],'little');py=int.from_bytes(state[0x407:0x409],'little')
            car=pixels[flags.index(state[0x409])*256:][:256]
            for x,color in enumerate(car[240:]):
                if not color:continue
                at=(py+7+256)*(width//2)+(px-8+x+256)//2
                bitmap[at]=bitmap[at]&15|color<<4 if (px-8+x)%2==0 else bitmap[at]&240|color
        wx=int.from_bytes(state[0xb0:0xb2],'little',signed=True);wy=int.from_bytes(state[0xb2:0xb4],'little',signed=True)
        check_cache(vram,bitmap,width,wx,wy,path.stem)
        v,c=actors(state,vram,pixels,state[scroll_address],'Full_EnemySATCursor' in syms);visible+=v;maximum=max(maximum,c)
        expected=packed(header(assets,palette,number(state[0x1120:0x1128]),number(state[0x1128:0x1130]),
            player=state[0x7ec]+1,full_game=True,round_=(state[0x21b0]-1)&255))
        if vram[0x10000:0x10400]!=expected:raise ValueError(f'Natural eight-digit header differs from published values: {path.stem}')
    rows=[list(map(int,line.split())) for line in (args.capture/'events.tsv').read_text().splitlines()]
    held=run=longest=0
    for old,new in zip(rows,rows[1:]):
        delta=new[7]-old[7]
        if 0<delta<=1:held+=delta;run+=1;longest=max(longest,run)
        else:run=0
    verify_manifest(bundle);verify_manifest(args.capture)
    json_write(out/'report.json',dict(rom_sha256=digest(args.rom),natural_samples=len(frames),
        complete_enemy_images_checked=visible,maximum_enemy_planes_per_scanline=maximum,
        cache_held_refreshes=held,observed_refreshes=len(rows),hold_percentage=100*held/len(rows),
        longest_consecutive_hold=longest,
        scope='Independent visible cache, published smoke and row counters, death/player patch, complete enemy masks/OR colors and eight-digit HUD VRAM. SAT/VRAM proof; rendered scanout and physical hardware are separate.'))
    require_ignored(root,[f for f in out.rglob('*') if f.is_file()]);seal(out)
    print(f'{len(frames)} natural cache/HUD/car snapshots pass: {out}/report.json')


if __name__=='__main__':main()
