"""Package placement-independent terrain data; original payloads stay local."""
from .round_scenery import profile
from .tile_strips import encode, candidates
from .smoke import eligibility
from .stage_one import tile, TILE_COLUMNS, TILE_ROWS
from scripts.scenes.storage import json_write


def package(root, output, banks, program, assets, palette, death_tiles, smoke_tiles):
    metadata=[];records=[];profiles=[]
    for page in range(0x30,0x34):
        p=profile(program,page,assets,palette,death_tiles,smoke_tiles)
        profiles.append(p)
        strips=encode(p['world'],origins=(560,768))
        resource=len(banks)+1
        pairs=[tile(program,p['geometry'],x-3,y-3,p['wall'],p['flower'])
               for y in range(TILE_ROWS) for x in range(TILE_COLUMNS)]
        permission=eligibility(pairs,pairs)
        data=p['atlas']+permission
        banks.append(data+bytes(16384-len(data)))
        id_bank=len(banks)+1
        banks.extend(candidates(p['ids']))
        hbank=len(banks)+1
        htable=bytearray(strips['horizontal']['table'])
        hdata=strips['horizontal']['pixels'];vdata=strips['vertical']['pixels']
        offset=0x1800;voffset=offset+len(hdata)
        if voffset+len(vdata)+256>16384:
            raise ValueError('Full round strip graphics exceed their lookup bank')
        htable[16384+offset:16384+offset+len(hdata)]=hdata
        htable[16384+voffset:16384+voffset+len(vdata)]=vdata
        htable[16384+voffset+len(vdata):16384+voffset+len(vdata)+256]=bytes(i//3 for i in range(256))
        banks.extend((bytes(htable[:16384]),bytes(htable[16384:])))
        vbank=len(banks)+1;banks.append(strips['vertical']['table'])
        records.append(bytes((id_bank,resource,hbank,vbank))+
                       len(hdata).to_bytes(2,'little')+len(vdata).to_bytes(2,'little')+
                       voffset.to_bytes(2,'little')+(0x8000+voffset+len(vdata)).to_bytes(2,'little'))
        for name,value in [('world',p['world']),('geometry',p['geometry']),('atlas',p['atlas'])]:
            (output/f'round-{page-0x30}-{name}.bin').write_bytes(value)
        metadata.append(dict(page=page,id_bank=id_bank,resource_bank=resource,
                             horizontal_bank=hbank,vertical_bank=vbank,atlas_tiles=p['tiles'],
                             horizontal_bytes=len(hdata),vertical_bytes=len(vdata),vertical_offset=voffset))
    p=profiles[0]
    if any(q['sources']!=p['sources'] for q in profiles[1:]):
        raise ValueError('Round object/effect source positions differ across terrain profiles')
    (output/'full-profiles.bin').write_bytes(b''.join(records))
    (output/'full-flag-radar-x.bin').write_bytes(bytes(2+(x*24+36)*44//816 for x in range(32)))
    (output/'full-flag-radar-y.bin').write_bytes(bytes(2+(y*24+36)*54//1392 for y in range(56)))
    (output/'full-object-sources.bin').write_bytes(b''.join(p['sources'][f'object{k}'] for k in range(1,5)))
    for name in ('death','smoke'):(output/f'{name}-sources.bin').write_bytes(p['sources'][name])
    (output/'flower-sources.bin').write_bytes(bytes(v for i in range(0,18,6) for v in p['sources']['flower'][i:i+2]))
    # Full rounds use the ordinary exact strip lookup for flowers as well.
    (output/'flower-vertical-sources.bin').write_bytes(strips['vertical']['table'][:6])
    json_write(output/'full-rounds.json',dict(profiles=metadata,object_map=0xdc00,object_map_bytes=896,
        flag_records=0xdf80,scope='Dynamic original objects over four exact terrain profiles'))
    return profiles[0]


def cold_source(root):
    def section(path,start,end):
        text=(root/path).read_text();body=text.split(start,1)[1].split(end,1)[0]
        # Each original definition is gated out of the resident bank for FULL_GAME.
        body=body.rsplit('    ENDIF',1)[0]
        return start+body
    return ('    DISP $f000\nFull_LoadStart:\n'+
            section('src/raster-scroll.asm','show_scene:\n','    IF !HUD_ENABLED\n; Preserve')+
            section('src/hud.inc','HUD_Init:\n','; Reusable SCREEN')+
            section('src/stage-one-stream.inc','stage_load:\n','stage_tile:\n')+
            (root/'src/full-strip-load.inc').read_text()+
            '\nFull_ObjectSources:\n    INCBIN "full-object-sources.bin"\n'+
            (root/'src/full-enemy-records.inc').read_text()+
            '    ASSERT $ <= $f300\nFull_LoadEnd:\n    ENT\n'+
            '    DISP $c680\nFull_EnemyHotStart:\n'+(root/'src/full-enemy-hot.inc').read_text()+
            '    ASSERT $ <= $c700\nFull_EnemyHotEnd:\n    ENT\n')
