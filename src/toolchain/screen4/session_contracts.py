"""Independent full-session active VRAM, world, HUD and complete-car oracle."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib,json,struct
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from edge import edge_tiles
from game_hud import display_keys,prepare_reference as hud_reference
from game_sprites import prepare_reference as car_reference


def validate(folder,bundle):
    folder,bundle=map(Path,(folder,bundle))
    digits=(bundle/'game-hud-digits.bin').read_bytes();life=(bundle/'game-hud-life.bin').read_bytes()
    cars=(bundle/'game-sprite-templates.bin').read_bytes();hud=(bundle/'hud.bin').read_bytes()
    module=json.loads((bundle/'hud-module.json').read_text());small_round=module['small_round']
    results=[]
    for snapshot in sorted(folder.glob('*.ram')):
        regs=snapshot.with_suffix('.regs').read_bytes()
        if regs[0]&14!=4:continue
        ram=snapshot.read_bytes();vram=snapshot.with_suffix('.vram').read_bytes()
        if ram[0xc7d0]!=0 or ram[0xc00c]!=1:continue
        word=lambda a:int.from_bytes(ram[a:a+2],'little')
        cx,cy=word(0xc000),word(0xc002);col,row=ram[0xc009],ram[0xc008]
        assert (col,row)==(cx//8,cy//8),(snapshot.name,'camera epoch')
        front=ram[0xc006]^1;pb=ram[0xc028]*16384;nb=0x0800+front*1024
        assert regs[4]*2048==pb and regs[2]*1024==nb,(snapshot.name,'published table bases')
        assert regs[10]*16384+(regs[3]&128)*64==pb+0x2000,(snapshot.name,'published color base')
        layout=ram[0xdfc9];resource=(bundle/f'session-terrain-{layout}.bin').read_bytes()
        patterns,colors=resource[:2048],resource[2048:4096];objects=resource[4096:4132]
        terrain=(bundle/f'session-map-{layout}.bin').read_bytes()
        assert vram[pb:pb+512]==patterns[:512],(snapshot.name,'terrain patterns')
        assert vram[pb+0x2000:pb+0x2200]==colors[:512],(snapshot.name,'terrain colors')
        flags=[ram[0xdf80+i*6:0xdf86+i*6] for i in range(10)]
        stones=[];stone_cells=set();at=word(0xe996)
        for i in range(ram[0xe251]):
            cell=word(at+i*2)-0x9800;stone_cells.add(cell);stones.append((3+cell%32*3,3+cell//32*3))
        navigation=(bundle/'game-navigation.bin').read_bytes()[layout*2048:(layout+1)*2048]
        assert len(navigation)==2048
        assert ram[0x3000:0x3800]==bytes(v|(16 if i in stone_cells else 0) for i,v in enumerate(navigation)),(snapshot.name,'stone navigation tags altered exits')
        for y in range(28):
            for x in range(1,24):
                wx,wy=col+x,row+y;expected=terrain[wy*128+wx]
                for i,r in enumerate(flags):
                    dx,dy=wx-r[4],wy-r[5]
                    if 0<=dx<3 and 0<=dy<3:expected=objects[(r[2]-1)*9+dy*3+dx] if ram[0xc501+i] else 37
                for sx,sy in stones:
                    if 0<=wx-sx<3 and 0<=wy-sy<3:expected=objects[18+(wy-sy)*3+wx-sx]
                if ram[0xdfe4] and 1<=ram[0xdfe6]-col<22 and wy==ram[0xdfe7] and 0<=wx-ram[0xdfe6]<3:
                    expected=92+wx-ram[0xdfe6]
                if ram[0xc701] and 0<=wx-ram[0xc702]<32 and 0<=wy-ram[0xc703]<32:
                    code=ram[0xe400+((wy-10)&31)*32+((wx-3)&31)]
                    if 0xbd<=code<0xc6:expected=38+code-0xbd
                if ram[0xc490]==1 and 0<=wx-ram[0xc492]<3 and 0<=wy-ram[0xc493]<3:
                    expected=28+(wy-ram[0xc493])*3+wx-ram[0xc492]
                cache=((wy&31)*32+(wx&31))
                assert ram[0xd800+cache]==expected,(snapshot.name,'world',wx,wy,ram[0xd800+cache],expected)
                assert vram[nb+cache]==expected,(snapshot.name,'names',wx,wy)
        def pixel(tile,y,x):
            a=pb+tile*8+y;c=vram[a+0x2000]
            return c>>4 if vram[a]&(128>>x) else c&15
        for y in range(28):
            for which in range(2):
                at=((row+y)&31)*32+((col+24+which)&31);source=ram[0xd800+at]
                assert source<64,(snapshot.name,'effect entered mixed edge',source)
                original=bytes(colors[source*8+yy]>>4 if patterns[source*8+yy]&(128>>xx) else colors[source*8+yy]&15 for yy in range(8) for xx in range(8))
                wanted=edge_tiles(original,cx&7)[which];tile=vram[nb+at]
                actual=bytes(pixel(tile,yy,xx) for yy in range(8) for xx in range(8))
                assert actual==wanted,(snapshot.name,'boundary',which,y,source,tile)
        wanted=bytearray(hud)
        if ram[0xc7ec]:
            from src.toolchain.scenes.bundle import load_assets
            from prepare import ROOT
            assets=load_assets(ROOT/'assets/arcade/nrallyx');glyph=assets.pixels['tiles'][128:192]
            for y in range(8):
                for x in range(8):wanted[(24+y)*48+x]=8 if assets.palette['lookup'][152+glyph[y*8+x]] else 11
        for i,r in enumerate(flags):
            if ram[0xc501+i] and not(i==9 and ram[0xc0f6]):
                cell=r[0]+r[1]*256-0x9800;wanted[(70+(cell//32)*106//56)*48+8+cell%32]=12
        for actor in range(min(7,ram[0xe24e]),-1,-1):
            p=0xe068+actor*32;x,y=ram[p+8],ram[p+10]
            if x<32 and y<56:
                yy=70+y*106//56;xx=8+x;group=(xx+(cx&7))//8
                cells=[col for col in range(48) if (col+(cx&7))//8==group]
                ink=(11 if ram[0xc0f6] else 8) if actor==0 else (12 if any(wanted[yy*48+col]==12 for col in cells) else 6)
                for col in cells:
                    if wanted[yy*48+col]!=10:wanted[yy*48+col]=ink
                wanted[yy*48+xx]=ink
        for y in range(212):
            yy=(cy+y)&255
            for x in range(200,256):
                xx=(cx+x)&255;tile=vram[nb+(yy//8)*32+xx//8]
                expected=11 if x<208 else wanted[y*48+x-208]
                assert pixel(tile,yy%8,xx%8)==expected,(snapshot.name,'HUD',x,y,pixel(tile,yy%8,xx%8),expected)
        keys=display_keys(ram[0xe060:0xe068],ram[0xe0a0:0xe0a8],ram[0xe1b0],ram[0xe00f],ram[0xe26b],arcade=True)
        sat,pg=hud_reference(digits,life,keys,cy&255,arcade=True,small_round=small_round,symmetric_gauge=module['symmetric_gauge'])
        assert vram[0x1a00:0x1a38]==sat,(snapshot.name,'HUD SAT')
        for slot in range(14):
            if 7<=slot<=10 and not keys[slot]:continue
            at=0x2800+sat[slot*4+2]*8
            assert vram[at:at+32]==pg[slot*32:slot*32+32],(snapshot.name,'HUD glyph',slot)
        actors=[struct.unpack_from('<hhBB',ram,0xc800+i*6) for i in range(8)]
        car=car_reference(cars,actors,cy&255,ram[0xcd40])
        for slot in range(18):
            actual=vram[0x1a38+slot*4:0x1a3c+slot*4];expected=car['sat'][slot*4:slot*4+4]
            assert (actual[:2]==expected[:2] and actual[3]==expected[3] and (actual[2]==expected[2] or actual[2]>=200)) if car['colors'][slot*16]&15 else actual[0]==expected[0],(snapshot.name,'car SAT',slot)
            if not car['colors'][slot*16]&15:continue
            at=0x2800+actual[2]*8;group=expected[2]//4-ram[0xcd40]*18
            assert vram[at:at+32]==car['patterns'][group*32:(group+1)*32],(snapshot.name,'complete car',slot)
            assert vram[0x18e0+slot*16:0x18f0+slot*16]==car['colors'][slot*16:(slot+1)*16],(snapshot.name,'car colors',slot)
        results.append(dict(snapshot=snapshot.stem,layout=layout,native_round=ram[0xe1b0],player=ram[0xc7ec]+1,enemies=ram[0xe24e],stones=len(stones),flags=ram[0xc50b]))
    assert results,'No stable active-mode snapshots'
    report=dict(passed=True,rom_sha256=hashlib.sha256((folder/'measured.rom').read_bytes()).hexdigest(),snapshots=results,scope='Independent dynamic world, all fixed HUD background pixels, numeric/life SAT and complete car patterns on stable commit snapshots. Not a full human-course proof.')
    (folder/'graphics-contracts.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(validate(args.folder,args.bundle),indent=2))
