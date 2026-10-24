"""Validate disjoint active buffers in the complete selected-routine runtime."""


def layout(symbols):
    from .full_enemy import pattern_plan
    pattern_plan(radar_pattern=symbols['RADAR_PLAYER_PATTERN'])
    regions=[]
    def add(name,start,size):
        address=symbols[start] if isinstance(start,str) else start
        regions.append(dict(name=name,start=address,end=address+size))
    add('actor hot code','Full_EnemyHotStart',symbols['Full_EnemyHotEnd']-symbols['Full_EnemyHotStart'])
    add('eight-digit numeric state','hud_score_pending',64)
    add('fuel publication','hud_fuel_payload',128)
    add('wall snapshot',0xd200,44)
    add('inactive player','Full_Shadow',120)
    add('stationary AI results','Full_AITable0',28)
    add('stationary AI input axes','Full_AIBefore',7)
    add('stationary AI tick','Full_AITick',1)
    add('IM2 trampoline',0xd2d2,3)
    add('smoke display','Smoke_Display',2048)
    add('smoke row counts','Smoke_DisplayRows',32)
    add('published radar points','Radar_PublishedPoints',192)
    add('dynamic object owners','Round_Objects',896)
    add('dynamic flag records','Flag_Records',60)
    add('round bank metadata','Full_IDBank',20)
    add('round radar flags','Full_RadarFlags',20)
    add('tile division table',0xe300,240)
    add('native input',0xe3f0,1)
    add('stationary AI keys','Full_AIValid',7)
    add('native smoke attributes',0xec00,1024)
    add('cold RAM code','Full_LoadStart',symbols['Full_LoadEnd']-symbols['Full_LoadStart'])
    for region in regions:
        if not 0xc000<=region['start']<region['end']<=0xf380:
            raise ValueError(f'Full-game RAM region exceeds its mapped workspace: {region["name"]}')
    ordered=sorted(regions,key=lambda r:r['start'])
    for left,right in zip(ordered,ordered[1:]):
        if left['end']>right['start']:
            raise ValueError(f'Full-game RAM overlap: {left["name"]} / {right["name"]}')
    if symbols['Full_EnemyHotEnd']>0xc700 or 0xf380-symbols['Full_LoadEnd']<128:
        raise ValueError('Full-game executable buffers leave insufficient smoke/stack space')
    return dict(regions=ordered,stack_top=0xf380,
        cold_code_stack_gap=0xf380-symbols['Full_LoadEnd'],ram_mapper_kb=128,vram_kb=128,
        native_borrowed_bytes=dict(tile_division=[0xe300,0xe3f0],ai_keys=[0xe3f1,0xe3f8]),
        scope='Additional full-game buffers; original selected-core/legacy renderer fields retain their existing contracts.')
