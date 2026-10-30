"""Link original stage-one rules to the isolated SCREEN4 hardware adapter.

All contributor bytes and generated sources stay in ignored references/.
The original production build and the free-camera laboratory are independent.
"""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import hashlib
import json
import shutil
from pathlib import Path

from prepare import encode_tile, shifted_hud
from src.toolchain.msx import stage_one, player, death, smoke, flags, enemy_navigation
from src.toolchain.msx.inputs import load_huds, background_zero
from src.toolchain.scenes.bundle import load_assets
from src.toolchain.msx.round_prepare_verify import relocated_seed
from src.toolchain.msx.raster_scroll import index_for
import game_sprites
import game_audio
from effect_codec import adapt


def inputs(root):
    program,capture=stage_one.acquire(root)
    video=(capture/'video.bin').read_bytes()
    cells,pairs,_=stage_one.reconstruct(program,capture)
    assets=load_assets(root/'assets/arcade/nrallyx')
    return program,video,cells,pairs,assets


def prepare_inputs(root,out,*,full_session=False):
    program,video,cells,pairs,assets=inputs(root)
    palette=(out/'palette.bin').read_bytes()
    contract=game_sprites.palette_contract(palette)
    trans=contract['translation']+bytes(range(16,256))
    (out/'palette.bin').write_bytes(contract['palette'])
    colors=(out/'terrain-colors.bin').read_bytes()
    colors=bytes(trans[c>>4]*16+trans[c&15] for c in colors)
    patterns=bytearray((out/'terrain-patterns.bin').read_bytes())
    colors=bytearray(colors)
    report=json.loads((out/'prepare.json').read_text())
    count=report['scenery_tiles']
    effects={}
    dp,_,_=death.acquire(root)
    empty=[stage_one.tile(program,bytes(1792),x,y,0,0) for y in range(3) for x in range(3)]
    sources={'death':death.pixels(dp,assets,palette),
             'empty':death.pixels(empty[:1],assets,palette),
             'smoke':death.pixels([(program[0xfec]+i,program[0xff4]) for i in range(9)],assets,palette)}
    effect_adaptation={}
    for kind,tiles in sources.items():
        if kind in ('death','smoke'):
            tiles,changed=adapt(tiles,palette)
            effect_adaptation[kind]=dict(changed_pixels=changed,total_pixels=576,
                dimensions=[24,24],authorized='2026-10-28',
                scope='Smoke and explosion only; this experiment; final visual acceptance pending')
        ids=[]
        for tile in tiles:
            p,c=encode_tile(tile.translate(trans))
            ids.append(count)
            patterns[count*8:count*8+8]=p
            colors[count*8:count*8+8]=c
            count+=1
        effects[kind]=ids
    if count>64:raise ValueError('Game effects overlap radar characters')
    (out/'terrain-patterns.bin').write_bytes(patterns)
    (out/'terrain-colors.bin').write_bytes(colors)
    hud=bytearray((out/'hud.bin').read_bytes().translate(trans))
    black=trans[index_for(palette,(0,0,0))]
    blue=trans[index_for(palette,(0,0,151))]
    for y0,y1,x0,x1 in ((8,16,0,48),(32,40,0,48),(60,64,0,48),
                        (184,200,0,48),(204,212,32,48)):
        for y in range(y0,y1):hud[y*48+x0:y*48+x1]=bytes([black])*(x1-x0)
    (out/'hud.bin').write_bytes(hud)
    if full_session:
        for record in flags.records(video,cells):
            address=record['address']-0x9800
            x=8+address%32;y=70+(address//32)*106//56
            hud[y*48+x]=blue
        (out/'hud.bin').write_bytes(hud)
    counts=[]
    radar_variants={}
    from radar_variants import prepare_phase
    flag_records=[] if full_session else flags.records(video,cells)
    for fy in range(8):
        for fx in range(8):
            n,p,c,count_hud=shifted_hud(hud,fx,fy,black)
            if count_hud>64:raise ValueError('Static HUD exceeds64chars')
            phase=fy*8+fx
            payload,groups=prepare_phase(n+p+c,flag_records,phase,blue)
            (out/f'hud-{phase:02d}.bin').write_bytes(payload)
            radar_variants[str(phase)]=groups
            counts.append((len(payload)-224)//16)
    assert effect_adaptation['death']['changed_pixels']==23
    assert effect_adaptation['smoke']['changed_pixels']==37
    report.update(scenery_tiles=count,effects=effects,effect_adaptation=effect_adaptation,
                  palette_translation=list(trans),
                  hud_unique_tiles=dict(min=min(counts),max=max(counts)))
    (out/'radar-variants.json').write_text(json.dumps(radar_variants,indent=2)+'\n')
    (out/'prepare.json').write_text(json.dumps(report,indent=2)+'\n')


def append_resources(root,out,banks,*,enemies=1,legacy_render=False,full_session=False):
    import game_core
    program,video,cells,pairs,assets=inputs(root)
    code,data=player.build(out,program,video,assets,rock_collision=True,scoring=True,
        fuel=True,lives=True,enemies=True,enemy_count=7,smoke=True,smoke_notify=True,
        parameters=True,round_preparation=True,full_game=full_session)
    code=game_core.patch_native(code,program)
    data=bytearray(data)
    seed=bytearray(relocated_seed(video))
    seed[0x99e:0x9a0]=(0xe3f0).to_bytes(2,'little');seed[0x3f0]=255
    data[0x2000:0x3000]=seed
    cleared=bytes(0 if c in (1,2,4) else c for c in cells)
    cp=[stage_one.tile(program,cleared,x-3,y-3,video[0x2b1],video[0x2d6])
        for y in range(stage_one.TILE_ROWS) for x in range(stage_one.TILE_COLUMNS)]
    permission=smoke.eligibility(pairs,cp)
    assert 0x700+len(permission)<=0x2000
    data[0x700:0x700+len(permission)]=permission
    nav=enemy_navigation.original_maps(program)
    if not full_session:nav=nav[:2048]
    (out/'game-navigation.bin').write_bytes(nav)
    (out/'game-radar-y.bin').write_bytes(bytes(70+y*106//56 for y in range(56)))
    music,audio_metadata=game_audio.build(program,out)
    sprite_metadata=game_sprites.write_assets(out,data)
    import game_hud
    game_hud.write_local_assets(out,(out/'palette.bin').read_bytes(),root=root)
    source_root=root
    if full_session:
        from session_build import reference
        source_root,_=reference()
    game_core.prepare(source_root,out,full_session=full_session,
                      source_directory=source_root/'src' if full_session else None)
    import game_multi
    multi=game_multi.prepare(root,out,program,enemies=0 if full_session or enemies==1 else enemies)
    if full_session:
        multi['scope']='Full native round progression; no fixture population override; HUD and real hardware sprite limits remain enabled'
    native_bank=1+len(banks)//16384
    declarations=dict(GAME_NATIVE_BANK=native_bank,
                      GAME_TEST_ENEMIES=0 if full_session or enemies==1 else enemies,GAME_RENDER_OPT=int(not legacy_render),
                      PLAYER_DATA_BANK=native_bank+1,GAME_AUDIO_BANK=native_bank+2,
                      GAME_RESOURCE_BANK=native_bank+3)
    report=json.loads((out/'prepare.json').read_text())
    declarations.update(GAME_EMPTY_TILE=report['effects']['empty'][0],
                        GAME_DEATH_TILE=report['effects']['death'][0],
                        GAME_SMOKE_TILE=report['effects']['smoke'][0])
    black=report['palette_translation'][11]
    declarations['GAME_BLACK']=black
    declarations['GAME_RADAR_COLOR']=report['palette_translation'][12]*16+report['palette_translation'][1]
    radar_define='    DEFINE GAME_RADAR_UNIFORM_SOURCE 1\n    DEFINE GAME_RING_REFRESH 1\n    DEFINE GAME_SPRITE_CLIP_FAST 1\n    DEFINE GAME_HUD_PROGRAMS 1\n' if not legacy_render else ''
    (out/'game-config.inc').write_text('    DEFINE GAMEPLAY_CONFIGURED 1\n'+radar_define+'\n'.join(f'{k} EQU ${v:04x}' for k,v in declarations.items())+'\n')
    records=flags.records(video,cells)
    (out/'flag-records.bin').write_bytes(bytes(v for r in records for v in
        (r['address']&255,r['address']>>8,r['kind'],r['hud_slot'],r['tile_x'],r['tile_y'])))
    rocks=[i+0x9800 for i,c in enumerate(cells) if c==3]
    (out/'rock-cells.bin').write_bytes(b''.join(r.to_bytes(2,'little') for r in rocks))
    (out/'game-native-raw.bin').write_bytes(code)
    metadata=dict(banks=declarations,audio=audio_metadata,sprites=sprite_metadata,
                  native_source_sha256=hashlib.sha256(program).hexdigest(),
                  effects=report['effects'],rock_count=len(rocks),multi_enemy=multi,render_optimized=not legacy_render,
                  radar_uniform_source=not legacy_render)
    (out/'game-resources.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (out/'game-rock-count.inc').write_text(f'ROCK_COUNT EQU {len(rocks)}\n')
    resources=nav.ljust(16384,b'\xff')
    result=banks+code+data+music+resources
    if full_session:
        from session_build import append_resources as append_session
        result=append_session(root,out,result)
    return result


def renderer_source(text, *, phase_cache=True):
    def replace(a,b):
        nonlocal text
        if text.count(a)!=1:raise ValueError(f'Renderer boundary changed: {a[:60]!r}')
        text=text.replace(a,b)
    replace('names EQU $c400','names EQU $d400')
    replace('    ORG $4000','    INCLUDE "game-config.inc"\n    ORG $4000')
    replace('reg 8,$2a','reg 8,$28')
    replace('reg 9,$82','reg 9,$80')
    replace('reg 7,11','reg 7,GAME_BLACK')
    replace('    call render\n    ; Enable','    call Game_Init\n    call render\n    ; Enable')
    replace('loop:\n    call input\n    call render', 'loop:\n    call Game_Prepare\n    call render')
    replace('    xor 1\n    ld (back),a\n    ei','    xor 1\n    ld (back),a\n    call GameHUD_Commit\n    call GameSprites_Commit\n    ei')
    replace('    call Ring_Prepare\n.hud:', '    call Ring_Prepare\n    call Game_RingPatch\n.hud:')
    replace('    ld hl,$0200','    ld hl,$0300')
    replace('    ld hl,$4200','    ld hl,$4300')
    replace('    ld c,$98\n    otir\n    jr .packet',
            '    ld c,$98\n    IF GAME_RENDER_OPT\n    call GamePacketFast_Transfer\n    ELSE\n    otir\n    ENDIF\n    jr .packet')
    replace('    ld (hud_page),a\n.packet:',
            '    ld (hud_page),a\n    IFDEF GAME_HUD_PROGRAMS\n    jp (hl)\n    ENDIF\n.packet:')
    # Update the two expanded edge atlases without transitive substitutions.
    replacements={'$0600':'$0500','$4600':'$4500','$06e0':'$0680','$46e0':'$4680',
                  '$8c00':'$8d00','$8d00':'$8f00','$8f00':'$9100',
                  '$9000':'$9300','$9100':'$9500'}
    import re
    start=text.index('render.hud_uploaded:');end=text.index('.no_boundary:',start)
    text=text[:start]+re.sub(r'\$(?:0600|4600|06e0|46e0|8c00|8d00|8f00|9000|9100)',
        lambda m:replacements[m[0]],text[start:end])+text[end:]
    replace('    ld h,$8e\n    DUP 28','    ld h,$90\n    DUP 28')
    start=text.index('.boundary_needed:\n');end=text.index('.no_boundary:',start)
    body=text[start+len('.boundary_needed:\n'):end]
    text=text[:start]+'.boundary_needed:\n    IF GAME_RENDER_OPT\n    call GameBoundary_Upload\n    ELSE\n'+body+'    ENDIF\n'+text[end:]
    start=text.index('.no_left:\n');end=text.index('render_done:',start)
    text=text[:start]+'.no_left:\n    call Game_RadarUpload\n    IF GAME_RENDER_OPT\n    call GameDirty_Plan\n    ENDIF\n    call Ring_UploadNames\n    call Game_DirtyTileUpload\n'+text[end:]
    start=text.index('radar:\n');end=text.index('; HL is a 16-bit VRAM address.',start)
    text=text[:start]+'radar:\n    jp Game_Radar\n\n'+text[end:]
    # Gameplay radar reads native cells and the 56-byte Game_RadarCellRows.
    # The free-camera pixel-coordinate tables have no gameplay references.
    replace('radar_x:\n    INCBIN "radar-x.bin"\nradar_y:\n    INCBIN "radar-y.bin"\n','')
    replace('palette:\n', '''    INCLUDE "modules/renderer/msx2.inc"
    INCLUDE "modules/native/core.inc"
    INCLUDE "game-hud.inc"
    INCLUDE "modules/actors/msx2.inc"
    INCLUDE "modules/audio/first-stage.inc"
palette:
''')
    from game_phase_cache import transform as phase_cache_transform
    if phase_cache:
        text=phase_cache_transform(text)
    text+='''
    OUTPUT "game-native-linked.bin"
    ORG $8000
    INCBIN "game-native-raw.bin",0,$3500
    INCLUDE "game-native-motion.inc"
    ASSERT $ <= $b600
    defs $b600-$,$ff
    INCLUDE "game-native-ai.inc"
    ASSERT $ <= $bf00
    defs $bf00-$,$ff
    INCBIN "game-native-raw.bin",$3f00,$100
'''
    return text


def copy_sources(root,out,assembly):
    # Copy authored include facades/submodules, never another code/data copy.
    module_root=source_path('modules')
    for source in module_root.rglob('*.inc'):
        target=Path(assembly)/'modules'/source.relative_to(module_root)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    for source in out.iterdir():
        if source.suffix in ('.bin','.inc'):shutil.copyfile(source,assembly/source.name)
    for name in ('game-phase-cache.inc','game-main.inc','game-core.inc','game-sprites.inc','game-sprite-mask-fast.inc','game-sprite-clip-fast.inc','game-audio.inc','game-hud.inc','game-dirty.inc','game-smoke-cache.inc','game-radar-fast.inc','game-name-stream.inc','game-boundary-fast.inc','game-packet-fast.inc','game-multi.inc'):
        shutil.copyfile(source_path(name),assembly/name)
    # Keep the established free-camera ring untouched.
    shutil.copyfile(source_path('game-ring.inc'),out/'ring.inc')
    shutil.copyfile(source_path('game-ring.inc'),assembly/'ring.inc')
    if (out/'session-build.json').exists():
        from session_build import copy_sources as copy_session_sources
        copy_session_sources(out,assembly)


def finalize_banks(assembly,out,banks):
    metadata=json.loads((out/'game-resources.json').read_text())
    bank=metadata['banks']['GAME_NATIVE_BANK']
    linked=(assembly/'game-native-linked.bin').read_bytes()
    assert len(linked)==16384,len(linked)
    at=(bank-1)*16384
    banks[at:at+16384]=linked
    if metadata['render_optimized']:
        from hud_programs import link as link_hud_programs
        banks=link_hud_programs(banks,assembly,out)
    if (out/'session-build.json').exists():
        from session_build import finalize
        banks=finalize(assembly,out,banks)
    (out/'banks.bin').write_bytes(banks)
    return banks
