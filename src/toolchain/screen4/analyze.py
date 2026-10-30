"""Compare complete emulator images with a camera/HUD oracle, including borders."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
from collections import Counter
from pathlib import Path
import sys
import hashlib
import statistics
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from src.toolchain.msx.raster_scroll import palette_rgb
from edge import SCENE_WIDTH, EDGE_WIDTH

BASE=ROOT/'references/experiments/fixed-hud'
PROBE=Path(sys.argv[1]) if len(sys.argv)>1 else Path((BASE/'last-probe.txt').read_text().strip())
metadata=json.loads((PROBE/'metadata.json').read_text())
assert metadata['rom_sha256']==hashlib.sha256((BASE/'fixed-hud.rom').read_bytes()).hexdigest(), 'ROM changed since probe'
palette=palette_rgb((BASE/'palette.bin').read_bytes())
world=Image.open(BASE/'maze.png').convert('RGB')
hud=Image.new('RGB',(48,212))
hud.putdata([palette[c] for c in (BASE/'hud.bin').read_bytes()])
states={}
logic={}
times=[]
for line in (PROBE/'frames.tsv').read_text().splitlines():
    n,t,x,y,speed,elapsed,tick,keys=line.split()
    states[int(n)]=(int(x),int(y),int(speed))
    logic[int(n)]=(int(elapsed),int(tick),int(keys))
    times.append(float(t))
def oracle(x,y):
    expected=Image.new('RGB',(320,240),palette[11])
    expected.paste(world.crop((x,y,x+SCENE_WIDTH,y+212)),(32,14))
    expected.paste(hud,(240,14))
    expected.putpixel((240+8+(x+100)*32//816,14+70+(y+106)*106//1392),palette[12])
    # This screen-space band applies in EVERY phase. Never choose scene colors
    # from the HUD palette or exempt the reset frame from the edge policy.
    boundary_changes=0
    phase=x%8
    for yy in range(212):
        for xx in range(SCENE_WIDTH-EDGE_WIDTH,SCENE_WIDTH):
            tile_x=(x+xx)//8*8
            row=[world.getpixel((tile_x+i,y+yy)) for i in range(8)]
            dominant=Counter(row).most_common(1)[0][0]
            boundary_changes+=dominant!=world.getpixel((x+xx,y+yy))
            expected.putpixel((32+xx,14+yy),dominant)
    # User-authorized fixed V9958 mask, including fine phase zero/reset.
    for yy in range(212):
        for xx in range(8):
            expected.putpixel((32+xx,14+yy),palette[11])
    return expected,boundary_changes


results=[]
for path in sorted(PROBE.glob('frame-*.png'),key=lambda p:int(p.stem.split('-')[1])):
    n=int(path.stem.split('-')[1]);x,y,_=states[n]
    actual=Image.open(path).convert('RGB')
    candidates=[n,n-1] if metadata['mode']=='continuous' else [n]
    choices=[]
    for candidate in candidates:
        xx,yy,_=states[candidate]
        image,changed=oracle(xx,yy)
        if metadata['mode']=='continuous': image.save(PROBE/f'oracle-{candidate}.png')
        mismatch=sum(a!=b for a,b in zip(actual.get_flattened_data(),image.get_flattened_data()))
        choices.append((mismatch,candidate,image,changed))
    mismatch,presented,expected,boundary_changes=min(choices,key=lambda item:item[0])
    if actual.size!=expected.size:
        raise ValueError(f'Unexpected raw frame size: {actual.size}')
    hud_mismatch=sum(actual.getpixel((xx,yy))!=expected.getpixel((xx,yy))
                     for yy in range(14,226) for xx in range(32+SCENE_WIDTH,288))
    expected.save(PROBE/f'expected-{n}.png')
    ImageChops.difference(actual,expected).save(PROBE/f'diff-{n}.png')
    results.append(dict(frame=n,camera=[x,y],presented=presented,mismatch_pixels=mismatch,
                        boundary_color_changes=boundary_changes,hud_mismatch_pixels=hud_mismatch))
normal=[];fast=[]
for n in range(2,len(states)+1):
    x,y,speed=states[n]; px,py,_=states[n-1]
    elapsed,tick,keys=logic[n]
    if metadata['mode'] in ('keyboard','continuous'):
        step=speed*elapsed
        expected_x=max(0,min(816-SCENE_WIDTH,px+bool(keys&128)*step-bool(keys&16)*step))
        expected_y=max(0,min(1180,py+bool(keys&64)*step-bool(keys&32)*step))
        assert (x,y)==(expected_x,expected_y), ('Clock-driven input',n,(x,y),(expected_x,expected_y))
        assert elapsed==max(1,(tick-logic[n-1][1])%65536), ('Tick accounting',n)
    distance=max(abs(x-px),abs(y-py))/elapsed
    if distance==speed: (fast if speed==2 else normal).append(distance)
if metadata['mode'] in ('keyboard','continuous'):
    assert set(normal)=={1} and set(fast)=={2}, (normal,fast)
intervals=[(b-a)*1000 for a,b in zip(times,times[1:])]
work=[sum(float(v) for v in line.split()[2:]) for line in (PROBE/'render.tsv').read_text().splitlines()[1:]]
traffic=json.loads((PROBE/'traffic.json').read_text())
assert traffic['vdp_commands']==0 and not traffic['sprites_enabled']
if metadata['mode']=='matrix':
    expected_cases={tuple(v) for v in metadata['cases']}
    assert expected_cases <= {tuple(r['camera']) for r in results}, 'Missing requested matrix cases'
if metadata['mode']=='continuous':
    assert len(results)==305, 'Incomplete continuous capture sequence'
    assert all(a['presented']<=b['presented'] for a,b in zip(results,results[1:])), 'Presentation moved backwards'
    assert traffic['full_cache_rebuilds']==0, 'Keyboard movement rebuilt the world window'
    assert traffic['max_world_ids_per_update']<=128, 'World streaming exceeded edge budget'
report=dict(images=results, normal_step_pixels=sorted(set(normal)),shift_step_pixels=sorted(set(fast)),
            movement_clock='VBlank ticks; values are pixels per refresh, not per presentation',
            mode=metadata['mode'],rom_sha256=metadata['rom_sha256'],
            traffic=traffic,strict_vram_timing=True,
            main_work_ms=dict(min=min(work),max=max(work),mean=statistics.mean(work)),
            refresh_intervals=dict(one=sum(t<25 for t in intervals),two=sum(25<=t<45 for t in intervals),
                                   three_or_more=sum(t>=45 for t in intervals)),
            frame_interval_ms=dict(min=min(intervals),max=max(intervals),mean=sum(intervals)/len(intervals)),
            hud_complete=all(r['hud_mismatch_pixels']==0 for r in results),
            complete=all(r['mismatch_pixels']==0 for r in results))
(PROBE/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='images'} | dict(
    images_checked=len(results), image_failures=[r for r in results if r['mismatch_pixels']]),indent=2))
sys.exit(0 if report['complete'] else 1)
