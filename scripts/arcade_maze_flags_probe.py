"""Research original-ROM maze/flag behavior without changing the MSX game.

Contributor ROM bytes, full boards and traces stay ignored. The durable result
contains hashes, counts and algorithm metadata, not original tables or payloads.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.toolchain.graphics.roms import load_metadata,validate_roms,input_records
from scripts.extract_graphics import _region
from src.toolchain.msx.stage_one import cells_from_rom


def advance(state):
    """Original0F24:16-bit rotate then conditional4080 addition; no new PRNG."""
    state=((state<<1)&65535)|(state>>15)
    if not state&0x49:state=(state+0x4080)&65535
    return state


def place_objects(program,state,page,rock_count=0):
    """Model original1343/1379 rejection placement with original ROM inputs.

    Return final PRNG state, number of advances, flag cell IDs and rock cell IDs.
    Fixed exclusion coordinates/candidate pools are read, never embedded here.
    """
    geometry=cells_from_rom(program,page);flags=[];rocks=[];calls=0
    excluded=[tuple(program[0x1417+2*i:0x1419+2*i]) for i in range(2)]
    def blocked(x,y,points,distance):
        return any(abs(x-a)<distance and abs(y-b)<distance for a,b in points)
    for kind,count in [('rock',rock_count),('flag',10)]:
        for _ in range(count):
            # Fail a diagnostic that cannot terminate; never invent a guest
            # placement fallback or change the original rejection sequence.
            while True:
                state=advance(state);calls+=1
                if calls>1000000:raise AssertionError('Original candidate sequence did not terminate')
                if kind=='rock':
                    at=page*256+0xe0+(state&30);x,y=program[at:at+2]
                else:
                    x=state&31;y=(state>>8)&63
                    if y>=56 or geometry[y*32+x]:continue
                if blocked(x,y,flags,4) or blocked(x,y,rocks,3) or blocked(x,y,excluded,5):continue
                (rocks if kind=='rock' else flags).append((x,y));break
    encode=lambda points:b''.join((0x9800+y*32+x).to_bytes(2,'little') for x,y in points)
    return state,calls,encode(flags),encode(rocks)


def matrix(program):
    from src.toolchain.msx.stage_one import acquire
    _,cache=acquire(ROOT)
    out=ROOT/'references/build/game-issue42/arcade-matrix';out.mkdir(parents=True,exist_ok=True)
    (out/'complete').unlink(missing_ok=True)
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat',
        '-rompath',str(ROOT/'references/roms'),'-video','none','-sound','none',
        '-nothrottle','-noautosave','-skip_gameinfo','-autoboot_delay','0',
        '-autoboot_script',str(ROOT/'src/toolchain/screen4/arcade-maze-matrix.lua'),
        '-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','240']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,check=True,timeout=90,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,NRX42_OUTPUT=str(out),NRX42_SEED=str(cache/'video.bin')))
    assert (out/'complete').exists(),out
    cases=list(csv.DictReader((out/'cases.tsv').open(),delimiter='\t'))
    states=(out/'states.bin').read_bytes();boards=(out/'boards.bin').read_bytes()
    assert len(cases)==64 and len(states)==4096*64 and len(boards)==1792*64
    results=[]
    for i,case in enumerate(cases):
        snapshot=states[i*4096:(i+1)*4096];actual=boards[i*1792:(i+1)*1792]
        seed=int(case['seed']);page=int(case['layout']);count=int(case['rocks'])
        state,calls,flags,rocks=place_objects(program,seed,page,count)
        fp=int.from_bytes(snapshot[0x992:0x994],'little')-0x8000
        rp=int.from_bytes(snapshot[0x996:0x998],'little')-0x8000
        assert flags==snapshot[fp:fp+20] and rocks==snapshot[rp:rp+2*count],case
        assert state==int(case['rng_after']),case
        expected=bytearray(cells_from_rom(program,page))
        for j in range(10):expected[int.from_bytes(flags[j*2:j*2+2],'little')-0x9800]=1 if j<8 else 4 if j==8 else 2
        for j in range(count):expected[int.from_bytes(rocks[j*2:j*2+2],'little')-0x9800]=3
        assert actual==expected,case
        results.append(dict(round=int(case['round']),seed=seed,layout=page,rocks=count,
            prng_advances=calls,rng_after=state,flags_sha256=hashlib.sha256(flags).hexdigest(),
            board_sha256=hashlib.sha256(actual).hexdigest(),exact_original_objects_and_board=True))
    return dict(cases=results,passed=True,
        scope='Controlled RAM seed and original08BF/08E7 entry, DI,32 rounds x2 seeds. No original ROM patches. Full1792-byte boards, flag/rock tables and PRNG compared; not natural course/lifecycle progression.')


def run(delay,repeat):
    out=ROOT/f'references/build/game-issue42/arcade-delay{delay}-repeat{repeat}'
    out.mkdir(parents=True,exist_ok=True)
    (out/'complete').unlink(missing_ok=True)
    command=['mame','nrallyx','-noreadconfig','-noplugins','-nocheat',
        '-rompath',str(ROOT/'references/roms'),'-video','none','-sound','none',
        '-nothrottle','-noautosave','-skip_gameinfo','-autoboot_delay','0',
        '-autoboot_script',str(ROOT/'src/toolchain/screen4/arcade-maze-flags.lua'),
        '-cfg_directory',str(out/'cfg'),'-nvram_directory',str(out/'nvram'),'-seconds_to_run','60']
    with (out/'mame.log').open('w') as log:
        subprocess.run(command,check=True,timeout=90,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,NRX42_OUTPUT=str(out),NRX42_START_DELAY=str(delay)))
    assert (out/'complete').exists(),out
    rows=list(csv.DictReader((out/'events.tsv').open(),delimiter='\t'))
    return out,rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--delays',default='0,1,2,7,60,180')
    args=parser.parse_args();delays=list(map(int,args.delays.split(',')))
    metadata=load_metadata();inputs=validate_roms(ROOT/'references/roms/nrallyx',metadata)
    program=_region(inputs,metadata,'maincpu',16384)
    results=[]
    for delay,repeat in [(d,0) for d in delays]+[(delays[0],1)]:
        out,rows=run(delay,repeat)
        start=next(r for r in rows if r['event']=='flags_begin')
        end=next(r for r in rows if r['event']=='flags_end')
        board=next(r for r in rows if r['event']=='board_ready')
        raw=(out/'board.bin').read_bytes();assert len(raw)==1792
        geometry=cells_from_rom(program,int(board['layout']))
        assert all(a==b if a not in (1,2,3,4) else b==0 for a,b in zip(raw,geometry))
        assert raw.count(1)==8 and raw.count(4)==1 and raw.count(2)==1
        flags=bytes.fromhex(end['flags']);assert len(flags)==20
        for i in range(10):
            cell=int.from_bytes(flags[2*i:2*i+2],'little')-0x9800
            assert 0<=cell<1792 and raw[cell]==(1 if i<8 else 4 if i==8 else 2)
        calls=int(end['rng_calls'])-int(start['rng_calls']);state=int(start['rng'])
        for _ in range(calls):state=advance(state)
        assert state==int(end['rng']),(state,end)
        model_state,model_calls,model_flags,_=place_objects(program,int(start['rng']),int(board['layout']))
        assert model_state==state and model_calls==calls and model_flags==flags
        results.append(dict(start_delay_frames=delay,repeat=repeat,round=int(board['round']),
            layout=int(board['layout']),rng_before=int(start['rng']),rng_after=int(end['rng']),
            placement_rng_calls=calls,background_rng_calls=int(start['background_calls']),
            flag_positions_sha256=hashlib.sha256(flags).hexdigest(),
            board_sha256=hashlib.sha256(raw).hexdigest(),geometry_matches_rom=True,
            counts=dict(normal=raw.count(1),special=raw.count(4),lucky=raw.count(2)),
            evidence=str(out.relative_to(ROOT))))
    assert results[0]['flag_positions_sha256']==results[-1]['flag_positions_sha256']
    report=dict(program_sha256=hashlib.sha256(program).hexdigest(),program_bytes=len(program),
        inputs=input_records(inputs),emulator=subprocess.check_output(['mame','-version'],text=True).strip(),
        source_files={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
            ['scripts/arcade_maze_flags_probe.py','src/toolchain/screen4/arcade-maze-flags.lua','src/toolchain/screen4/arcade-maze-matrix.lua']},
        natural_runs=results,distinct_placements=len({r['flag_positions_sha256'] for r in results}),
        controlled_matrix=matrix(program),
        scope='Natural runs use real cold boots and keyboard credit/start with read-only observers, first round only. The separately labeled controlled matrix supplies RAM seed/PC/IFF and executes original code. No original ROM patches. Geometry, object placement and exact PRNG progression independently checked.')
    target=ROOT/'docs/measurements/cartridge/issue42-arcade-maze-flags.json'
    target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
