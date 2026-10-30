"""Independent native-state/active-VRAM contracts for the first-stage cartridge.

Checks coherent terrain names, effect priority/restoration, native HUD glyphs,
complete selected car masks, exact effect patterns and real scanline candidates.
This does not equate a RAM snapshot with uninterrupted video scanout proof.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
from pathlib import Path
import struct
import sys
from game_hud import display_keys, prepare_reference as hud_reference
from game_sprites import prepare_reference as car_reference
from edge import edge_tiles

BASE=Path(__file__).resolve().parents[3]/'references/experiments/stage-one'


def analyze(path, bundle=None):
    global BASE
    if bundle is not None:
        BASE=Path(bundle)
    info=json.loads((BASE/'prepare.json').read_text())
    pattern=(BASE/'terrain-patterns.bin').read_bytes()
    colors=(BASE/'terrain-colors.bin').read_bytes()
    terrain=(BASE/'map.bin').read_bytes()
    flags=(BASE/'flag-records.bin').read_bytes()
    digits=(BASE/'game-hud-digits.bin').read_bytes()
    life=(BASE/'game-hud-life.bin').read_bytes()
    cars=(BASE/'game-sprite-templates.bin').read_bytes()
    hud=(BASE/'hud.bin').read_bytes()
    snapshots=[]
    for snapshot in sorted(path.glob('*.ram')):
        ram=snapshot.read_bytes();vram=snapshot.with_suffix('.vram').read_bytes()
        word=lambda at:ram[at]+256*ram[at+1]
        cy=word(0xc002);col=ram[0xc009];row=ram[0xc008]
        front=ram[0xc006]^1
        pattern_front=ram[0xc028] if 'pattern_front:' in (BASE/'lab.sym').read_text() else front
        pbase=pattern_front*0x8000
        count=info['scenery_tiles']*8
        assert vram[pbase:pbase+count]==pattern[:count],(snapshot.name,'terrain patterns')
        assert vram[pbase+0x4000:pbase+0x4000+count]==colors[:count],(snapshot.name,'terrain colors')
        visible_smoke=visible_death=0
        for y in range(28):
            for x in range(1,24):
                wx,wy=col+x,row+y
                at=(wy&31)*32+(wx&31)
                expected=terrain[wy*128+wx]
                for i in range(10):
                    fx,fy=flags[i*6+4:i*6+6]
                    if not ram[0xc501+i] and 0<=wx-fx<3 and 0<=wy-fy<3:
                        expected=info['effects']['empty'][0]
                if ram[0xc701] and 0<=wx-ram[0xc702]<32 and 0<=wy-ram[0xc703]<32:
                    code=ram[0xe400+((wy-10)&31)*32+((wx-3)&31)]
                    if 0xbd<=code<=0xc5:
                        expected=info['effects']['smoke'][code-0xbd];visible_smoke+=1
                if ram[0xc490]==1 and 0<=wx-ram[0xc492]<3 and 0<=wy-ram[0xc493]<3:
                    expected=info['effects']['death'][(wy-ram[0xc493])*3+wx-ram[0xc492]];visible_death+=1
                assert ram[0xd800+at]==expected,(snapshot.name,'world cache',wx,wy,ram[0xd800+at],expected)
                assert vram[0x2000+front*0x400+at]==expected,(snapshot.name,'active names',wx,wy,vram[0x2000+front*0x400+at],expected)
        # Decode the active edge characters independently of dictionary IDs.
        # This checks stable-color packet skipping on the published VRAM, not
        # merely equality of the offline atlas generator's source pixels.
        for y in range(28):
            for which in range(2):
                at = ((row+y)&31)*32+((col+24+which)&31)
                source = ram[0xd800+at]
                pixels = bytes(colors[source*8+dy] >> 4 if pattern[source*8+dy] & (128 >> dx)
                               else colors[source*8+dy] & 15 for dy in range(8) for dx in range(8))
                expected = edge_tiles(pixels, word(0xc000)&7)[which]
                name = vram[0x2000+front*0x400+at]
                address = pbase+name*8
                actual = bytes(vram[address+0x4000+dy] >> 4 if vram[address+dy] & (128 >> dx)
                               else vram[address+0x4000+dy] & 15 for dy in range(8) for dx in range(8))
                assert actual == expected, (snapshot.name, 'active boundary pixels', which, y, source, name)
        # Decode the entire fixed background panel independently of dictionary
        # allocation. Numeric/life/fuel sprites are checked separately below.
        expected_hud=bytearray(hud)
        blue=info['palette_translation'][1]
        yellow=info['palette_translation'][12]
        black=info['palette_translation'][11]
        for i in range(10):
            if not ram[0xc501+i]:
                cell=flags[i*6]+256*flags[i*6+1]-0x9800
                x,y=8+cell%32,70+(cell//32)*106//56
                expected_hud[y*48+x]=blue
        for actor in range(min(8,ram[0xe24e]+1)):
            address=0xe068+actor*32
            if ram[address+8]>=32 or ram[address+10]>=56:continue
            x,y=8+ram[address+8],70+ram[address+10]*106//56
            expected_hud[y*48+x]=yellow
        for y in range(212):
            physical_y=(cy+y)&255
            for x in range(200,256):
                physical_x=(word(0xc000)+x)&255
                entry=(physical_y//8)*32+physical_x//8
                tile=vram[0x2000+front*0x400+entry]
                address=pbase+tile*8+physical_y%8
                ink=vram[address+0x4000]
                actual=ink>>4 if vram[address]&(128>>(physical_x%8)) else ink&15
                expected=black if x<208 else expected_hud[y*48+x-208]
                assert actual==expected,(snapshot.name,'fixed HUD background pixel',x,y,actual,expected)
        keys=display_keys(ram[0xe060:0xe068],ram[0xe0a0:0xe0a8],ram[0xe1b0],ram[0xe00f],ram[0xe26b])
        sat,expected_patterns=hud_reference(digits,life,keys,cy&255)
        assert vram[0x1a00:0x1a38]==sat,(snapshot.name,'HUD SAT')
        for slot in range(14):
            if 7<=slot<=10 and not keys[slot] or slot>=11 and not keys[slot]:continue
            address=0x2800+sat[slot*4+2]*8
            assert vram[address:address+32]==expected_patterns[slot*32:slot*32+32],(snapshot.name,'HUD pattern',slot)
        actors=[struct.unpack_from('<hhBB',ram,0xc800+i*6) for i in range(8)]
        active_set=ram[0xcd40]
        car=car_reference(cars,actors,cy&255,active_set)
        for slot in range(18):
            actual=vram[0x1a38+slot*4:0x1a3c+slot*4]
            expected=car['sat'][slot*4:slot*4+4]
            if car['colors'][slot*16]&15:
                assert actual==expected,(snapshot.name,'active car SAT',slot)
            else:
                assert actual[0]==expected[0],(snapshot.name,'inactive car must stay hidden',slot)
        for slot in range(18):
            if not car['colors'][slot*16]&15:continue
            assert vram[0x18e0+slot*16:0x18f0+slot*16]==car['colors'][slot*16:(slot+1)*16],(snapshot.name,'car colors',slot)
            pid=car['sat'][slot*4+2]
            group=pid//4-active_set*18
            assert vram[0x2800+pid*8:0x2820+pid*8]==car['patterns'][group*32:(group+1)*32],(snapshot.name,'full native car',slot)
        candidates=[]
        for y in range(212):
            slots=0
            for slot in range(32):
                sy=vram[0x1a00+slot*4]
                assert sy!=216,(snapshot.name,'early sprite terminator',slot)
                if ((y+cy-sy-1)&255)<16:slots+=1
            candidates.append(slots)
        snapshots.append(dict(name=snapshot.stem,smoke_tiles=visible_smoke,death_tiles=visible_death,
            flags=ram[0xc50b],lives=ram[0xe00f],state=ram[0xc040],
            maximum_scanline_candidates=max(candidates),sentinel_whole_car_culling=car['culled']))
    assert snapshots,'Missing captured RAM/VRAM'
    report=dict(complete=True,snapshots=snapshots,
        limitations='Active VRAM/state contracts; not an uninterrupted scanout or physical hardware oracle.')
    (path/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(path,len(snapshots),'snapshots checked')
    return report

if __name__=='__main__':
    for arg in sys.argv[1:]:analyze(Path(arg))
