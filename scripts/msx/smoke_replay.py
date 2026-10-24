"""Replay observed keyboard smoke calls in the original contributor program."""
import os
import subprocess

from scripts.graphics.roms import input_records,load_metadata,validate_roms
from scripts.scenes.bundle import digest,read_json
from scripts.scenes.storage import json_write
from .smoke_verify import RECORD
from .smoke import anchor,ring_index
from .player import coordinates


def verify(root,bundle,out):
    before=(out/'smoke-before.bin').read_bytes();actual=(out/'smoke-after.bin').read_bytes()
    context=(out/'smoke-context.bin').read_bytes()
    if not before or len(before)%4096:raise ValueError('Incomplete live smoke input snapshots')
    count=len(before)//4096
    if len(actual)!=count*RECORD or len(context)!=count*17:raise ValueError('Incomplete live smoke output/context snapshots')
    seeds=bytearray();placed=prepared=0
    from .stage_one import acquire,tile
    program,reference=acquire(root);native=(reference/'video.bin').read_bytes()
    board=bytearray((root/'references/stage-one/rocks-v1/work.bin').read_bytes()[:1792])
    flags=read_json(bundle/'flags.json')['records']
    for n in range(count):
        state=bytearray(before[n*4096:(n+1)*4096]);ctx=context[n*17:(n+1)*17]
        result=actual[n*RECORD:(n+1)*RECORD]
        origin=coordinates(state)  # $0069 already advanced world and fine camera.
        expected=anchor(*origin,state[0x77])
        requested=bool(state[0x291] or not state[0x3f0]&2)
        if expected is not None and requested:
            x,y=expected
            if ctx[:2]!=bytes((x&255,y&255)):raise ValueError(f'Live smoke anchor differs from original physical geometry at {n}')
            at=ring_index(x,y);code,attr=state[0x400+at],state[0xc00+at]
            if 0<=x<102 and 0<=y<174:
                cells=bytearray(board)
                for i,f in enumerate(flags,1):
                    if not ctx[6+i]:cells[f['address']-0x9800]=0
                road,permission=tile(program,cells,x-3,y-3,native[0x2b1],native[0x2d6])
                allowed=road==0x81 and bool(permission&128)
            else:allowed=False
            if code==0x81 and attr&128 and not allowed:raise ValueError(f'Smoke granted non-road placement at {n}/{x},{y}')
            if code==0 and allowed:raise ValueError(f'Smoke failed to prepare original road at {n}/{x},{y}')
            prepared+=1
        if result[4]&16:
            if expected is None:raise ValueError('Smoke placed from a non-cardinal source pose')
            x,y=expected
            for dy in range(3):
                for dx in range(3):
                    at=ring_index(x+dx,y+dy)
                    if result[38+at]!=0xbd+dy*3+dx or result[1062+at]!=0x45:
                        raise ValueError(f'Original smoke 24x24 tile layout changed at {n}')
            placed+=1
        # These are the declared RAM pointer relocations, not byte filtering of
        # any compared rule output. The original consumes original addresses.
        for at in (0x988,0x98a,0x98c,0x98e,0x990,0x99a,0x99c):
            value=int.from_bytes(state[at:at+2],'little')
            if not 0xe000<=value<0xf000:raise ValueError('Unexpected live smoke native pointer')
            state[at:at+2]=(value-0x6000).to_bytes(2,'little')
        for at in (0x1b3,0x1b9):
            value=int.from_bytes(state[at:at+2],'little')
            state[at:at+2]=(value-0x8000).to_bytes(2,'little')
        for at in range(2,14,2):
            value=int.from_bytes(state[at:at+2],'little')
            if value:state[at:at+2]=(value-0x6000).to_bytes(2,'little')
        state[0x99e:0x9a0]=(0x9f40).to_bytes(2,'little');state[0x28f]=0x30
        seeds.extend(state)
    oracle=out/'smoke-original';oracle.mkdir();(oracle/'seeds.bin').write_bytes(seeds)
    inputs=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata()))
    version=subprocess.check_output(['mame','-version'],text=True).strip()
    if not version.startswith('0.289 '):raise ValueError('Live smoke replay requires MAME0.289')
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat','-rompath',str(root/'references/roms'),
        '-video','none','-sound','none','-nothrottle','-noautosave','-noautoframeskip','-frameskip','0',
        '-skip_gameinfo','-autoboot_delay','0','-autoboot_script',str(root/'scripts/msx/smoke_native.lua'),
        '-cfg_directory',str(oracle/'mame-cfg'),'-nvram_directory',str(oracle/'mame-nvram'),'-seconds_to_run','90']
    with (oracle/'mame.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,SMOKE_OUTPUT=str(oracle),SMOKE_REPLAY='1'),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    original=(oracle/'original.bin').read_bytes()
    if original!=actual:
        at=next((i for i,(a,b) in enumerate(zip(original,actual)) if a!=b),min(len(original),len(actual)))
        raise ValueError(f'Live smoke differs from original at call {at//RECORD}, byte {at%RECORD}')
    if inputs!=input_records(validate_roms(root/'references/roms/nrallyx',load_metadata())):raise ValueError('Original smoke inputs changed')
    report=dict(calls=count,placements=placed,prepared_cardinal_attempts=prepared,
        complete_ring_bytes_per_call=2048,byte_exact=True,
        original_script_sha256=digest(root/'scripts/msx/smoke_native.lua'),
        scope='Original F64 replay of every observed keyboard-call input; independent world/flag eligibility and physical placement geometry')
    json_write(oracle/'report.json',report)
    return report
