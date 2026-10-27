"""Validate disjoint active buffers in the complete selected-routine runtime."""


def irq_image(bundle,symbols):
    if 'Full_RadarIRQStart' not in symbols:return b''
    offset=symbols['PLAYER_BANK']*16384+0x2800
    offset+=symbols['Full_LoadEnd']-symbols['Full_LoadStart']
    offset+=symbols['Full_EnemyHotEnd']-symbols['Full_EnemyHotStart']
    size=symbols['Full_RadarIRQEnd']-symbols['Full_RadarIRQStart']
    return (bundle/'raster-scroll.rom').read_bytes()[offset:offset+size]


def presentation_image(bundle,symbols):
    if 'Full_PresentStart' not in symbols:return b''
    offset=symbols['FULL_TERRAIN_BANK']*16384+0x1000
    size=symbols['Full_PresentEnd']-symbols['Full_PresentStart']
    return (bundle/'raster-scroll.rom').read_bytes()[offset:offset+size]


def layout(symbols):
    from .full_enemy import pattern_plan
    pattern_plan(radar_pattern=symbols['RADAR_PLAYER_PATTERN'])
    regions=[]
    def add(name,start,size):
        address=symbols[start] if isinstance(start,str) else start
        regions.append(dict(name=name,start=address,end=address+size))
    add('actor hot code','Full_EnemyHotStart',symbols['Full_EnemyHotEnd']-symbols['Full_EnemyHotStart'])
    add('fixed radar IRQ code','Full_RadarIRQStart',symbols['Full_RadarIRQEnd']-symbols['Full_RadarIRQStart'])
    add('collision identity','Enemy_HitAddress',2)
    add('packet readiness already sealed',symbols.get('Full_SealedFrame',symbols['Full_RegisteredMask']),1)
    add('terrain queue preference','Stage_PreferRows',1)
    add('terrain deadline flag','Stage_GuardClosed',1)
    add('compact actor SAT cursor','Full_EnemySATCursor',1)
    add('actor destination invalidation','Full_EnemySATDirty',1)
    add('current actor registration','Full_RegisteredCurrent',1)
    add('world coordinate keys',0xdb20,28)
    add('world coordinate change flag',0xc67e,1)
    add('shared cache window pattern',0xc675,1)
    add('bounded idle prefetch flag',0xc67f,1)
    add('wide terrain strip metadata',0xd2d8,9)
    add('terrain mapper and native clock workspace',0xd2e1,31)
    add('eight-digit numeric state','hud_score_pending',64)
    add('conservative native smoke rows',0xd160,32)
    add('fuel publication','hud_fuel_payload',128)
    add('wall snapshot',0xd200,44)
    add('inactive player','Full_Shadow',120)
    add('enemy decision cells','Full_AITable0',14)
    add('camera candidate centres',symbols['Full_AITable0']+14,4)
    add('camera publication epoch',symbols['Full_AITable0']+18,2)
    add('presentation mailboxes',symbols['Full_AITable0']+20,8)
    add('enemy decision scratch','Full_AIBefore',7)
    add('current enemy index','Full_AITick',1)
    add('latched vertical scroll and validity',0xd2cc,2)
    add('stream-local rejected cell',0xd2ce,3)
    add('cell source kind and physical spans',0xd2d1,1)
    add('IM2 trampoline',0xd2d2,3)
    add('smoke display','Smoke_Display',2048)
    add('smoke row counts','Smoke_DisplayRows',32)
    add('published radar points','Radar_PublishedPoints',192)
    if 'Radar_Urgent' in symbols:
        add('radar flag visibility snapshots',0xce00,24)
        add('radar content publication priority','Radar_Urgent',2)
    if 'Radar_Cleanup' in symbols:
        add('departed enemy radar cells','Radar_Cleanup',2)
        add('prepared enemy records','Full_EnemyRecords',224)
    add('dynamic object owners','Round_Objects',896)
    add('dynamic flag records','Flag_Records',60)
    add('round bank metadata','Full_IDBank',20)
    add('round radar flags','Full_RadarFlags',20)
    add('tile division table',0xe300,240)
    add('native input',0xe3f0,1)
    if 'Full_FrameOriginX' in symbols:
        add('render restart','Full_RenderRestart',1)
        add('packet origin centres','Full_FrameOriginX',4)
        add('shared complete-mask cache fault','Full_PoolFault',1)
    else:
        add('legacy stationary AI keys and valid masks','Full_AIValid',8)
    add('native smoke attributes',0xec00,1024)
    if 'Full_PresentStart' in symbols:
        start,end=symbols['Full_PresentStart'],symbols['Full_PresentEnd']
        if start!=0xea00 or end>0xec00:
            raise ValueError('Presentation code must preserve native E988/E9F4 pointers and smoke attributes')
        add('presentation code in unused sound workspace',start,end-start)
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
    overlay=None
    if 'Full_CacheEngineStart' in symbols:
        start,end=symbols['Full_CacheEngineStart'],symbols['Full_CacheEngineEnd']
        if not 0x1000<=start<end<=0x2000:
            raise ValueError('Terrain overlay code exceeds reserved mapper space')
        overlay=dict(code=[start,end],tile_owners=[0x2000,0x3000],
            presentation_packets=[0,0x384],navigation=[0x3000,0x3700],
            segment='Page3 RAM mapper segment XOR 1; distinct spare segment on the required 128KB mapper',
            mapping='Temporary page0 overlay; restore original primary, secondary and mapper selection; no BIOS calls while mapped')
    return dict(regions=ordered,stack_top=0xf380,terrain_mapper=overlay,
        cold_code_stack_gap=0xf380-symbols['Full_LoadEnd'],ram_mapper_kb=128,vram_kb=128,
        native_borrowed_bytes=dict(tile_division=[0xe300,0xe3f0],render_scratch=[0xe3f1,0xe3f9]),
        scope='Additional full-game buffers; original selected-core/legacy renderer fields retain their existing contracts.')
