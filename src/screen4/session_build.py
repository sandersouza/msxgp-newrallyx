"""Full-session resources and narrow adapters for the shared audio-branch rules.

Original payloads stay under ignored references/. The first-stage build remains
independent. This module never modifies the functional source checkout.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import os

from build_profiles import source_view

REVISION='6d562a791b0cc242119a31dd686ff8e93eb94fe0'
ROCK_CODEC_AUTHORIZATION='User approved2026-10-28:55/576 pixels,24x24 stones only in this experiment; final visual acceptance remains with user.'


def reference():
    view=source_view(REVISION)
    from scripts.scenes.bundle import verify_manifest
    record=json.loads((view.parents[1]/'audio-reference/build.json').read_text())
    assert record['revision']==REVISION
    bundle=Path(record['bundle']).resolve()
    assert bundle.is_relative_to(view/'references/build')
    verify_manifest(bundle)
    assert hashlib.sha256((bundle/'raster-scroll.rom').read_bytes()).hexdigest()==record['rom_sha256']
    return view,bundle


def worlds(root,out):
    """Keep the existing accepted codec; effects retain their exact fixed IDs."""
    from game_build import inputs
    from scripts.msx import stage_one,tilemap
    from scripts.msx.round_scenery import pixels
    from scripts.msx.smoke import eligibility
    from prepare import encode_tile
    from effect_codec import adapt
    program,video,cells,pairs,assets=inputs(root)
    palette=bytearray((out/'palette.bin').read_bytes())
    assert palette[30:32]==bytes(2),'Need the unused black slot for original later-round orange'
    palette[30:32]=bytes((0x70,3))
    (out/'palette.bin').write_bytes(palette)
    report=json.loads((out/'prepare.json').read_text())
    fixed=list(range(28,47))
    before_p=(out/'terrain-patterns.bin').read_bytes()
    before_c=(out/'terrain-colors.bin').read_bytes()
    result=[]
    for layout in range(4):
        geometry=stage_one.cells_from_rom(program,0x30+layout)
        wall=0x0d+layout;flower=0x53+(layout+1)*9
        pairs=[stage_one.tile(program,geometry,x-3,y-3,wall,flower)
               for y in range(174) for x in range(102)]
        raw=stage_one.bitmap(pairs,assets,bytes(palette))
        codec=tilemap.encode(raw,bytes(palette))
        patterns=bytearray(2048);colors=bytearray(2048)
        for slot in fixed:
            patterns[slot*8:slot*8+8]=before_p[slot*8:slot*8+8]
            colors[slot*8:slot*8+8]=before_c[slot*8:slot*8+8]
        dictionary={}
        available=iter([n for n in range(64) if n not in fixed])
        def register(key):
            if key not in dictionary:
                slot=next(available)
                dictionary[key]=slot
                patterns[slot*8:slot*8+8]=key[0];colors[slot*8:slot*8+8]=key[1]
            return dictionary[key]
        translation=[]
        for n in range(codec['tiles']):
            translation.append(register((codec['patterns'][n*8:n*8+8],codec['colors'][n*8:n*8+8])))
        ids=bytearray(b''.join(codec['banks']))
        ids[:]=bytes(translation[n] for n in ids)
        for y in range(256):
            for x in range(128):
                if y>=174 or x>=102:ids[y*128+x]=ids[(y%3)*128+x%3]
        objects=bytearray()
        object_changes=0
        for kind in range(1,5):
            source=bytearray(1792);source[0]=kind
            tiles=[pixels(stage_one.tile(program,source,x,y,wall,flower),assets,bytes(palette))
                   for y in range(3) for x in range(3)]
            # Existing scenery codec and dimensions; report every changed pixel.
            converted,changed=adapt(tiles,bytes(palette));object_changes+=changed
            if changed and kind==3 and ROCK_CODEC_AUTHORIZATION is None:
                raise ValueError('Stone codec requires explicit user authorization:55/576 pixels,24x24 dimensions')
            objects.extend(register(encode_tile(tile)) for tile in converted)
        # Each theme's empty road follows its native palette too.
        empty=pixels(stage_one.tile(program,bytes(1792),0,0,wall,flower),assets,bytes(palette))
        ep,ec=encode_tile(empty)
        patterns[37*8:38*8]=ep;colors[37*8:38*8]=ec
        # Retain the previous spare cloth slot for the fixed atlas layout.
        # Precomputed boundary atlases include both colors, including at the HUD.
        assert objects[12]==26 and 56 not in dictionary.values()
        patterns[56*8:57*8]=patterns[26*8:27*8]
        colors[56*8:57*8]=bytes(((12 if c>>4==6 else c>>4)<<4)|(12 if c&15==6 else c&15)
                              for c in colors[26*8:27*8])
        resource=bytes(patterns+colors)+bytes(objects)
        result.append(dict(map=bytes(ids),terrain=bytes(patterns+colors),objects=bytes(objects),
                           permission=eligibility(pairs,pairs),
                           changed_pixels=codec['changed_pixels'],object_changes=object_changes,
                           terrain_tiles=len(dictionary),layout=layout))
        (out/f'session-map-{layout}.bin').write_bytes(ids)
        (out/f'session-terrain-{layout}.bin').write_bytes(resource)
    (out/'session-worlds.json').write_text(json.dumps([{k:v for k,v in r.items() if not isinstance(v,bytes)} for r in result],indent=2)+'\n')
    return result


def append_resources(root,out,banks):
    from game_boundary_stable import family
    from hud_programs import transition_packet,compile_packet
    view,production=reference()
    result=bytearray(banks)
    metadata=json.loads((out/'game-resources.json').read_text())
    constants={}
    def page(data):
        assert len(data)<=16384
        number=1+len(result)//16384
        assert number<256,'Full-session resources exceed the ASCII16 bank range'
        result.extend(bytes(data).ljust(16384,b'\xff'))
        return number
    profiles=worlds(root,out)
    terrain_banks=[];map_banks=[];edge_banks=[];edge_costs=[]
    compiled=json.loads((out/'hud-programs.json').read_text())
    for layout,profile in enumerate(profiles):
        terrain_banks.append(page((profile['terrain']+profile['permission']).ljust(0x2800,b'\0')+profile['objects']))
        map_banks.extend((page(profile['map'][:16384]),page(profile['map'][16384:])))
        terrain=profile['terrain']
        pixels=[bytes(terrain[2048+i*8+y]>>4 if terrain[i*8+y]&(128>>x) else terrain[2048+i*8+y]&15
                      for y in range(8) for x in range(8)) for i in range(64)]
        families=[family(pixels,which,slot,capacity=57 if which==0 else 48) for which,slot in ((0,160),(1,208))]
        atlases=[]
        for fx in range(8):
            bank=bytearray(0x2920)
            arrays=[]
            for which,slot,lut,pg,ct,number in ((0,160,0xa00,0xb00,0xd00,0xf00),(1,208,0x1000,0x1100,0x1300,0x1500)):
                ids,patterns,colors,count=families[which][fx]
                assert count<=(57 if which==0 else 48),(layout,fx,which,count)
                if which==0:
                    assert json.loads((out/'hud-layout.json').read_text())['allocated_slots']<=41
                    ids=bytes(137+n-208 if n>=208 else n for n in ids)
                bank[lut:lut+len(ids)]=ids;bank[pg:pg+len(patterns)]=patterns;bank[ct:ct+len(colors)]=colors
                bank[number]=count
                if which==0:arrays.extend((patterns[:384],colors[:384],patterns[384:],colors[384:]))
                else:arrays.extend((patterns,colors))
            atlases.append((bank,arrays))
        pointers={};costs=[[0]*8 for _ in range(9)]
        unique={};storage=bytearray()
        for old in range(9):
            for current in range(8):
                data=transition_packet(atlases[old][1] if old<8 else (b'',)*6,atlases[current][1],
                                       (0x500,0x4500,0x448,0x4448,0x680,0x4680),merge_gap=6)
                payload,relocations=compile_packet(data,0x8000,back_address=0xc027,packed8=True)
                from session_phase import compiled_cycles
                costs[old][current]=compiled_cycles(payload,1,0x8000)
                if data not in unique:
                    if len(storage)+len(payload)>16384:page(storage);storage=bytearray()
                    if storage:payload,relocations=compile_packet(data,0x8000+len(storage),back_address=0xc027,packed8=True)
                    unique[data]=(1+len(result)//16384,0x8000+len(storage))
                    compiled['relocations'].extend(dict(offset=len(result)+len(storage)+at,symbol=name) for at,name in relocations)
                    storage.extend(payload)
                pointers[old,current]=unique[data]
        if storage:page(storage)
        for fx,(bank,_) in enumerate(atlases):
            for old in range(9):
                b,address=pointers[old,fx];bank[0x2900+old*3:0x2903+old*3]=bytes((b,address&255,address>>8))
            edge_banks.append(page(bank))
        edge_costs.append(costs)
    compiled['boundary_programs']=True
    (out/'hud-programs.json').write_text(json.dumps(compiled,indent=2)+'\n')
    from session_phase import append_costs
    result=append_costs(result,edge_costs,out)
    production_config=(production/'config.inc').read_text()
    defs={n:int(v[1:],16) if v.startswith('$') else int(v) for n,v in re.findall(r'(?m)^(\w+) EQU (\$[\da-fA-F]+|\d+)\s*$',production_config)}
    original=(production/'raster-scroll.rom').read_bytes()
    from session_cosmetics import cast_footer
    image=b''.join(original[defs[name]*16384:(defs[name]+1)*16384] for name in ('SESSION_IMAGE_BANK','SESSION_DATA_BANK'))
    image=cast_footer(root,out,image,defs)
    for i,name in enumerate(('SESSION_IMAGE_BANK','SESSION_DATA_BANK')):constants[name]=page(image[i*16384:(i+1)*16384])
    constants['SESSION_BANK']=page(b'')
    constants['SESSION_COLD_BANK']=page(b'')
    constants['SESSION_DECOR_BANK']=page(decorations(root,out,production))
    constants['AUDIO_BANK']=metadata['banks']['GAME_AUDIO_BANK']
    from session_boot import append as append_boot,enabled as boot_enabled
    append_boot(root,out,page)
    constants['SESSION_BOOT_BANK']=page(b'')
    constants.update(SESSION_HARDWARE_CHECK=int(boot_enabled()),SESSION_RUNTIME=1,FULL_GAME=1,FLAG_POPUPS=1,AUDIO_ENABLED=1,
                     SESSION_TEST_MODE=int(os.environ.get('NRX_TEST_MODE','0')),
                     SESSION_MSX_LOGO=int(json.loads((out/'session-title.json').read_text())['logo']['enabled']),
                     WHITE=defs['WHITE'],RED=defs['RED'],BLACK=defs['BLACK'],UI_CAST_BACKGROUND=defs['UI_CAST_BACKGROUND'])
    (out/'session-bank-tables.inc').write_text('GameSession_TerrainBanks:\n    db '+','.join(map(str,terrain_banks))+
        '\nGameSession_MapBanks:\n    db '+','.join(map(str,map_banks))+
        '\nGameSession_EdgeBanks:\n    db '+','.join(map(str,edge_banks))+'\n')
    (out/'session-production-audio.bin').write_bytes(original[defs['AUDIO_BANK']*16384:(defs['AUDIO_BANK']+1)*16384])
    (out/'session-ui-palette.bin').write_bytes((production/'palette.bin').read_bytes())
    names=['full-ui-data.inc','ui-font.bin','ui-rock.bin','ui-redcar.bin','audio-score.inc']
    names += [p.name for p in production.glob('ui-reveal-*.bin')]
    for name in names:shutil.copyfile(production/name,out/name)
    for name in ('full-ui.inc','full-audio-runtime.inc','full-audio-state.inc'):
        shutil.copyfile(view/'src'/name,out/name)
    from session_title import shift_reveal
    path=out/'full-ui-data.inc';path.write_text(shift_reveal(path.read_text()))
    # Keep experimental audio corrections out of the functional checkout.
    ui=(out/'full-ui.inc').read_text()
    ui=ui.replace('    call Session_CopyImage\n','    call Session_CopyImage\n    IFDEF UI_MSX_LOGO_ENABLED\n    call UI_MSXLogo_Draw\n    ENDIF\n    call UI_CastFooter_Init\n',1)
    ui=ui.replace('Full_UICastFrame:\n','Full_UICastFrame:\n    call UI_CastFooter_Tick\n',1)
    old='    jr c,.waiting\n    ld a,1\n    ld (Session_State),a'
    assert old in ui
    ui=ui.replace(old,'    jr c,.waiting\n    ld a,($e9f5)\n    bit 2,a\n    jr nz,.waiting\n    ld a,1\n    ld (Session_State),a',1)
    start=ui.index('Full_UIDrawChallenge:');end=ui.index('Full_UIUnsigned:',start)
    ui=ui[:start]+'''Full_UIDrawChallenge:
    ld hl,GameSession_ChallengeReveal
    ld (Full_UIReveal),hl
    xor a
    ld (Full_UITimer),a
    ld (Full_UICastDone),a
    ld a,1
    ld (Audio_NewScene),a
    ld a,$40
    ld ($e9f5),a
    jp Full_UIDraw.show
'''+ui[end:]
    ui=ui.replace('    jp z,Full_UIChallengeWait','    jp z,GameSession_ChallengeFrame',1)
    # Labels only: time all callback exits, including the shared tail-call wait.
    start=ui.index('Full_UIChallengeWait:');end=ui.index('UI_BlackCommand:',start)
    wait=ui[start:end].replace('    ld a,3\n    ret','    ld a,3\n.done:\n    ret').replace('    ld a,1\n    ret','    ld a,1\n.wait_done:\n    ret')
    ui=ui[:start]+wait+ui[end:]
    (out/'full-ui.inc').write_text(ui)
    challenge_reveal(out,defs)
    audio=(out/'full-audio-runtime.inc').read_text()
    start=audio.index('.heading:\n',audio.index('.engine:\n'))
    end=audio.index('.key:\n',start)
    # Steering does not change oscillator pitch/timbre or retrigger its envelope.
    # Heading1's calibrated envelope retains the arcade engine fundamental;
    # the previous horizontal1/3 table multiplied it by three.
    audio=audio[:start]+'.heading:\n    ld a,b\n'+audio[end:]
    audio=audio.replace('    ld a,($e069)             ; Original engine selects its second note at fine speed $20.', '''    ld hl,($e069)
    bit 7,h
    jr z,.magnitude
    xor a
    sub l
    ld l,a
.magnitude:
    ld a,l                   ; Classify speed magnitude equally in both directions.''',1)
    audio=audio.replace('    ld a,16                  ; Audible tone and envelope run without per-sample CPU work.',
                        '    ld a,12                  ; Quieter fixed-volume engine; no per-sample CPU work.',1)
    start=audio.index('.engine:\n');end=audio.index('.quiet:\n',start)
    engine=audio[start:end].replace('    ret z\n    ld (hl),a','    jp z,Audio_EngineGain\n    ld (hl),a',1)
    engine=engine.replace('    jp Audio_ApplyC','    call Audio_ApplyC\n    jp Audio_EngineGain',1)
    audio=audio[:start]+engine+audio[end:]
    audio+='''
; Quantized PSG levels12/13 approximate an85% RMS target after revoicing.
; The phase comes from the physical sound clock; turns never reset it.
Audio_EngineGain:
    ld a,(clock_ticks)
    rrca
    and 31
    ld c,a
    ld a,(Audio_EngineKey)
    cp 3
    ld a,c
    jr z,.drive
    add a,a
    add a,a
    add a,a
    sub c
    and 31
    cp 7
    jr .volume
.drive:
    add a,a
    add a,a
    add a,c
    and 31
    cp 5
.volume:
    ld a,12
    adc a,0
.level:
    ld hl,Audio_PlayDesired+10
    cp (hl)
    ret z
    ld (hl),a
    ld a,1
    ld (Audio_NoiseDirty),a
    ret
'''
    (out/'full-audio-runtime.inc').write_text(audio)
    score=(out/'audio-score.inc').read_text()
    parameters=dict(re.findall(r'(?m)^(Audio_Engine1\w+) EQU (\d+)$',score))
    for velocity in ('Idle','Cruise','Drive'):
        for field in ('Envelope','Tone','Shape'):
            key='Audio_Engine0'+velocity+field
            score=re.sub(r'(?m)^'+key+r' EQU \d+$',key+' EQU '+parameters['Audio_Engine1'+velocity+field],score)
        # The native engine fundamental survives the approved revoicing.
        for heading in range(4):
            key=f'Audio_Engine{heading}{velocity}Tone'
            score=re.sub(r'(?m)^'+key+r' EQU \d+$',key+' EQU '+str(int(parameters['Audio_Engine1'+velocity+'Envelope'])*32),score)
    (out/'audio-score.inc').write_text(score)
    from session_audio_assets import patch as patch_audio_assets
    patch_audio_assets(root,out,production)
    audio=(out/'full-audio-runtime.inc').read_text()
    # A packet with smokeID2 uses matching carrier/envelope periods. Shape8
    # is a free-running hardware saw; no scanline or sample-rate callbacks.
    audio=audio.replace('    ld (Audio_FXPointer),hl\n    ld hl,Audio_NoisePhase',
                        '    ld (Audio_FXPointer),hl\n    call Audio_SmokeEnvelope\n    ld hl,Audio_NoisePhase',1)
    audio+='''
Audio_SmokeEnvelope:
    ld a,(Audio_NoiseID)
    cp 2
    ret nz
    ld hl,(Audio_PlayDesired+4)
    ld (Audio_PlayDesired+11),hl
    ld a,8
    ld (Audio_PlayDesired+13),a
    ret
'''
    audio=audio.replace('Audio_RenderMusic:\n','''Audio_RenderMusic:
    ld a,(Audio_NoiseID)
    cp 2
    jr z,.smoke
    cp 8
    jr nz,.normal
.smoke:
    ld hl,(Audio_PlayDesired+2)
    push hl
    ld a,(Audio_PlayDesired+9)
    push af
    ld hl,(Audio_PlayDesired+4)
    ld (Audio_PlayDesired+2),hl
    ld a,(Audio_PlayDesired+10)
    ld (Audio_PlayDesired+9),a
    call .normal
    pop af
    ld (Audio_PlayDesired+9),a
    pop hl
    ld (Audio_PlayDesired+2),hl
    ret
.normal:
''',1)
    from session_completion import audio_runtime
    (out/'full-audio-runtime.inc').write_text(audio_runtime(audio))
    text=(view/'src/full-session.inc').read_text()
    start=text.index('Full_DrawRound:');end=text.index('; 0 same-player restart',start)
    text=re.sub(r'(?m)^\w+ EQU .*\n','',text[:start]+text[end:])
    (out/'session-turns.inc').write_text(text)
    controls=(view/'src/session.inc').read_text()
    (out/'session-four-way.inc').write_text(controls[controls.index('Session_FourWay:'):controls.index('Session_Reset:')])
    guard=controls[controls.index('Session_SaveMotion:'):controls.index('; Four-way arcade input:')]
    (out/'session-motion.inc').write_text(guard)
    native=(view/'src/full-round-native.inc').read_text()
    start=native.index('    push bc\n',native.index('.flag:'));end=native.index('    inc ix\n',start)
    native=native[:start]+native[end:]
    start=native.index('    ld l,a\n',native.index('    ld (Full_Layout),a'))
    end=native.index('    ld a,1\n',start)
    native=native[:start]+native[end:]
    native=native[:native.index('Full_ProfileRecords:')]
    (out/'session-native-round.inc').write_text(native)
    shutil.copyfile(view/'src/round-objects.inc',out/'session-native-objects.inc')
    config=out/'game-config.inc'
    with config.open('a') as file:
        file.write('\n    DEFINE GAME_FULL_SESSION 1\n'+''.join(f'{k} EQU ${v:04x}\n' for k,v in constants.items()))
    metadata.update(full_session=True,shared_revision=REVISION,enemy_policy='Native phase progression; no diagnostic population clamp')
    (out/'game-resources.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report=dict(revision=REVISION,banks=constants,terrain_banks=terrain_banks,map_banks=map_banks,edge_banks=edge_banks,
                production_bundle=str(production),stone_authorization=ROCK_CODEC_AUTHORIZATION)
    (out/'session-build.json').write_text(json.dumps(report,indent=2)+'\n')
    return result


def decorations(root,out,production):
    from prepare import shifted_hud,encode_tile
    from scripts.scenes.bundle import load_assets
    assets=load_assets(root/'references/assets/nrallyx')
    hud=(out/'hud.bin').read_bytes();second=bytearray(hud)
    glyph=assets.pixels['tiles'][2*64:3*64]
    for y in range(8):
        for x in range(8):
            second[(24+y)*48+x]=8 if assets.palette['lookup'][38*4+glyph[y*8+x]] else 11
    result=bytearray(8192)
    for phase in range(64):
        x,y=phase%8,phase//8
        old=shifted_hud(hud,x,y,11);new=shifted_hud(second,x,y,11)
        entries=[];patterns=bytearray();colors=bytearray()
        for at,(a,b) in enumerate(zip(old[0],new[0])):
            before=(old[1][a*8:a*8+8],old[2][a*8:a*8+8])
            after=(new[1][b*8:b*8+8],new[2][b*8:b*8+8])
            if before!=after:
                row,column=divmod(at,7)
                address=0xd400+row*32+26+column
                entries.extend((address&255,address>>8,156+len(patterns)//8))
                patterns.extend(after[0]);colors.extend(after[1])
        assert len(patterns)<=32
        base=phase*128;result[base]=len(patterns)//8
        result[base+1:base+1+len(entries)]=bytes(entries)
        result[base+16:base+16+len(patterns)]=patterns
        result[base+48:base+48+len(colors)]=colors
    raw=(production/'flag-popup-pixels.bin').read_bytes()
    for ordinal in range(20):
        image=bytes(v for byte in raw[ordinal*96:(ordinal+1)*96] for v in (byte>>4,byte&15))
        encoded=[encode_tile(bytes(image[y*24+column*8+x] for y in range(8) for x in range(8))) for column in range(3)]
        result.extend(b''.join(p for p,c in encoded)+b''.join(c for p,c in encoded))
    (out/'session-decor.bin').write_bytes(result)
    return result


def challenge_reveal(out,colors):
    """Cold reveal table using original8x8 font and complete native item art."""
    font=(out/'ui-font.bin').read_bytes();background=colors['UI_CAST_BACKGROUND'];white=colors['WHITE'];red=colors['RED']
    pixels=bytearray();dictionary={};steps=[]
    def unit(source,x,y,width,height,delay):steps.append((source,y*128+x//2,width//2,height,delay))
    def text(value,x,y,ink):
        for i,char in enumerate(value):
            key=char,ink
            if key not in dictionary:
                dictionary[key]=len(pixels)
                for row in font[ord(char)*8:ord(char)*8+8]:
                    for column in range(0,8,2):
                        pixels.append(((ink if row&(128>>column) else background)<<4)|
                                      (ink if row&(64>>column) else background))
            unit('GameSession_ChallengePixels+'+str(dictionary[key]),x+i*8,y,8,8,2)
    text('CHALLENGING STAGE',60,40,red)
    a=list(steps[-1]);a[-1]=17;steps[-1]=tuple(a)
    text('NO.',96,64,white);unit('1',128,64,16,8,17)
    unit('UI_Rock',96,96,24,24,11);text('=',128,104,white);unit('2',144,104,16,8,17)
    unit('UI_RedCar',100,128,16,16,11);text('=',128,136,white);unit('3',144,136,16,8,17)
    text("RED CARS DON'T MOVE",40,168,white);text('UNTIL FUEL RUNS OUT.',48,184,white)
    lines=['GameSession_ChallengeReveal:']
    for source,dest,width,height,delay in steps:lines.extend((f'    dw {source},{dest}',f'    db {width},{height},{delay}'))
    lines+=['GameSession_ChallengeRevealEnd:','GameSession_ChallengePixels:','    INCBIN "session-challenge-pixels.bin"']
    (out/'session-challenge-data.inc').write_text('\n'.join(lines)+'\n')
    (out/'session-challenge-pixels.bin').write_bytes(pixels)
    (out/'session-challenge-reveal.json').write_text(json.dumps(dict(units=len(steps),glyph_bitmap_bytes=len(pixels),
        nominal_refreshes=sum(step[-1]+1 for step in steps),glyph_scale='Original8x8; rock24x24; car16x16',
        sequence=['Typed title','Typed stage number','Rock, equality, count','Red car, equality, count','Typed rule lines']),indent=2)+'\n')


def copy_sources(out,assembly):
    from session_cosmetics import hud_source
    path=assembly/'game-hud.inc';path.write_text(hud_source(path.read_text(),symmetric_gauge=json.loads((out/'hud-module.json').read_text())['symmetric_gauge']))
    for name in ('session-resident.inc','session-cold.inc','session-ui.inc','session-flags.inc','session-input.inc','session-challenge.inc','session-phase.inc','session-pattern-address.inc','session-sprite-static.inc','session-test.inc','session-boot.inc','session-startup-options.inc','session-title.inc','session-ui-options.inc','session-msx-logo.inc'):
        shutil.copyfile(Path(__file__).with_name(name),assembly/name)
    test=assembly/'session-test.inc'
    text=test.read_text();at=text.index('    IF SESSION_TEST_MODE')
    (assembly/'session-test-worker.inc').write_text(text[at:])
    test.write_text(text[:at])
    shutil.copyfile(out/'session-motion.inc',assembly/'session-motion.inc')
    shutil.copyfile(out/'session-boot-data.inc',assembly/'session-boot-data.inc')
    shutil.copyfile(out/'session-boot-palette.inc',assembly/'session-boot-palette.inc')
    for name in ('session-challenge-data.inc','session-challenge-pixels.bin'):shutil.copyfile(out/name,assembly/name)
    # All transformations are restricted to this generated full-session view.
    path=assembly/'game-native-ai.inc';text=path.read_text()
    text=text.replace('Full_MSXPlayerSpeed:\n','''Full_MSXPlayerSpeed:
    ; Native challenge parameters park both enemy cohorts. Preserve the
    ; original faster player velocity while their navigation is inactive.
    ; Fuel exhaustion restores nonzero cohorts and the ordinary bandwidth cap.
    ld hl,($e025)
    ld de,($e029)
    ld a,h
    or l
    or d
    or e
    ret z
''',1)
    text=text.replace('    call Full_CacheEnter\n','    call Full_CacheEnter\n    call GameSession_EnemyRocks\n',1)
    text=text.replace('    ld a,(hl)\n    or a\n    jr nz,.roads','    ld a,(hl)\n    and 15                  ; Navigation bit4 is stone occupancy, not an exit.\n    jr nz,.roads',1)
    text+='\n'+Path(__file__).with_name('session-enemy-rock.inc').read_text()
    path.write_text(text)
    path=assembly/'game-host.inc';text=path.read_text()
    text=text.replace('Death_Begin:\n','''Death_Begin:
    IF SESSION_TEST_MODE
    ld a,(GameSession_Invulnerable)
    or a
    ret nz
    ENDIF
''',1)
    path.write_text(text)
    path=assembly/'game-phase-cache.inc';text=path.read_text()
    start=text.index('GamePhase_Select:');end=text.index('; HL=offset in one 32KiB',start)
    text=text[:start]+'GamePhase_Select:\n    jp GameSession_PhaseSelect\n\n'+text[end:]
    # Smoke owns2800..281F; phase metadata must survive all smoke row marks.
    text=text.replace('pattern_phases EQU $c029','pattern_phases EQU $2820').replace('ld b,4','ld b,8').replace('cp 4','cp 8')
    start=text.index('GamePattern_Address:');end=text.index('    ELSE',start)
    text=text[:start]+'    INCLUDE "session-pattern-address.inc"\n'+text[end:]
    path.write_text(text)
    path=assembly/'ring.inc';path.write_text(path.read_text().replace('or $20','or $08').replace('or $60','or $48').replace('sub $b8','sub $d0'))
    path=assembly/'game-dirty.inc';path.write_text(path.read_text().replace('or $60','or $48'))
    path=assembly/'game-boundary-fast.inc';path.write_text(path.read_text().replace('    jp hud_upload.packet','    jp (hl)',1))
    path=assembly/'game-sprites.inc';text=path.read_text()
    text=text.replace('GameSprites_Init:\n','GameSprites_Init:\n    call GameSession_SharedInit\n',1)
    start=text.index('GS_TryFast:');end=text.index('GS_InteriorAttributes:',start)
    text=text[:start]+text[start:end].replace('    call GS_CheckColor\n','    call GS_CheckColor\n    call GameSession_SharedSprite\n    ret c\n',1)+text[end:]
    path.write_text(text)
    path=assembly/'game-sprite-clip-fast.inc'
    path.write_text(path.read_text().replace('GS_ClippedCopyFast:','GS_LegacyClippedCopyFast:',1)+'\n'+Path(__file__).with_name('session-sprite-clip.inc').read_text())
    path=assembly/'game-main.inc';text=path.read_text()
    text=text.replace('    call Game_Frame\n','    call Game_Frame\n    call GameSession_AfterFrame\n',1)
    text=text.replace('    djnz .flags\n    ld ix,Game_SmokeList','    djnz .flags\n    call GameSession_PopupOverlay\n    ld ix,Game_SmokeList',1)
    start=text.index('    ld a,$ff\n    ld (Game_LastWorldGeneration)')
    end=text.index('\nGame_RingPatch:',start)
    text=text[:start]+'    jp GameSession_Boot\n'+text[end:]
    start=text.index('    ld a,c\n',text.index('Game_RestoreOne:'))
    end=text.index('    pop bc\n    jp Game_PatchOne',start)
    text=text[:start]+'''    ld a,c
    and $80
    rlca
    call GameSession_MapPage
    ld a,c
    and 127
    ld l,a
    ld h,0
    REPT 7
    add hl,hl
    ENDR
    ld e,b
    ld d,0
    add hl,de
    ld a,(hl)
    push af
    call GameSession_RestorePage0
    pop af
'''+text[end:]
    path.write_text(text)
    path=assembly/'ring.inc';text=path.read_text()
    text=text.replace('    add a,2\n    ld ($7000),a','    call GameSession_MapPage',1).replace('    ld d,$80\n','    ld d,0\n',1)
    text=text.replace('Ring_LoadRun:\n','Ring_LoadRun:\n    call GameMap_LoadRun\n    jp GameSession_RestorePage0\nGameMap_LoadRun:\n',1)
    text=text.replace('Ring_LoadColumns:\n','Ring_LoadColumns:\n    call GameMap_LoadColumns\n    jp GameSession_RestorePage0\nGameMap_LoadColumns:\n',1)
    text=text.replace('cp $c0','cp $40').replace('    ld a,3\n    ld ($7000),a','    ld a,1\n    call GameSession_MapPage')
    text=text.replace('    xor 3\n    ld ($7000),a','    xor 1\n    call GameSession_MapPage')
    path.write_text(text)
    path=assembly/'game-core.inc';text=path.read_text().replace('    ld bc,$3ff','    ld bc,$3c9')
    text=text.replace('    call GameAudio_Init\n    ld a,GameAudio_EVENT_START\n    call GameAudio_Event','    ld a,1\n    ld (Audio_NewScene),a')
    text=text.replace('Game_Frame:\n    ld (Game_Due),a\n','''Game_Frame:
    ld (Game_Due),a
    or a
    jp z,Game_Position
    ld a,(Game_State)
    or a
    call z,Game_ReadInput
''',1)
    text=text.replace('    call Game_ReadInput\n    call $8f24','    call GameSession_InputTick\n    ld a,(paused)\n    or a\n    jr nz,.tick\n    call $8f24')
    text=text.replace('    ld a,2\n    ld (Game_State),a\n    ret','    jp GameSession_NextRound',1)
    start=text.index('    ld a,($e00f)\n',text.index('.death:'));end=text.index('.active:\n',start)
    text=text[:start]+'    jp GameSession_Death\n'+text[end:]
    text=text.replace('    ld a,(Fuel_SpeedClock)\n    and 7\n    call z,$8472\n','')
    text=text.replace('    call $b60c\n    call $8069','    call $b60c\n    call Session_SaveMotion\n    call $8069',1)
    text=text.replace('    call $9052\n    call Game_Animation','    call $9052\n    call GameSession_ValidateMotion\n    call Game_Animation',1)
    start=text.index('Game_ReadInput:');end=text.index('Player_Position:',start)
    text=text[:start]+'    INCLUDE "session-input.inc"\n\n'+text[end:]
    text=text.replace('    call GameAudio_Event\n.smoke:', '    call GameAudio_Event\n    call GameSession_FlagCollected\n.smoke:',1)
    path.write_text(text)
    path=assembly/'game-radar-fast.inc';text=path.read_text().replace('    call $a700','    call GameSession_FlagNames',1)
    text=text.replace('    call GameSession_FlagNames','    call GameSession_FlagNames\n    call GameSession_LabelNames',1)
    text=text.replace('.clone:\n    ENDIF','.clone:\n    ENDIF\n    ld a,c\n    cp 50\n    jr c,.regular\n    cp 60\n    jr nc,.regular\n    call GameSession_CloneFlag\n    ld a,(Game_RadarCount)\n    dec a\n    pop bc\n    jp .point\n.regular:',1)
    # Enemies first, player last: its white/black marker has color priority.
    text=text.replace('    inc a\n    ld b,a\n    ld ix,$e068','''    ld l,a
    ld h,0
    REPT 5
    add hl,hl
    ENDR
    ld de,$e068
    add hl,de
    push hl
    pop ix
    inc a
    ld b,a''',1).replace('    ld de,32\n    add ix,de','    ld de,-32\n    add ix,de',1)
    start=text.index('    inc h\n    ld a,GAME_RADAR_COLOR',text.index('.point:'))
    end=text.index('.merge:\n',start)
    text=text[:start]+'    call GameSession_RadarColor\n'+text[end:]
    path.write_text(text)
    path=assembly/'game-hud.inc';text=path.read_text().replace('GH_ReadRound:\n    ld a,(HUD_INPUT_ROUND)','GH_ReadRound:\n    call GameSession_DisplayRound',1)
    (assembly/'hud-implementation.inc').write_text(text)
    variant=json.loads((out/'hud-module.json').read_text())
    module=Path(__file__).with_name('hud')
    shutil.copyfile(module/'native-inputs.inc',assembly/'hud-native-inputs.inc')
    shutil.copyfile(module/'small-round.inc',assembly/'hud-round-worker.inc')
    from hud_module import FONT
    (assembly/'hud-small-font-data.inc').write_text(''.join('    db '+','.join(map(str,FONT[c]))+'\n' for c in '0123456789 '))
    path.write_text((module/(variant['name']+'.inc')).read_text())


def renderer_source(text,out):
    # Physical VRAM layout:eight16KiB sets plus untouched sprite gaps.
    text=text.replace('    add a,8\n    out ($99),a\n    ld a,$82','    add a,2\n    out ($99),a\n    ld a,$82',1)
    start=text.index('    ld a,(pattern_back)\n',text.index('commit:'));end=text.index('    reg 3,$1f',start)
    text=text[:start]+'''    ld a,(pattern_back)
    ld (pattern_front),a
    add a,a
    add a,a
    add a,a
    out ($99),a
    ld a,$84
    out ($99),a
    ld a,(pattern_back)
    out ($99),a
    ld a,$8a
    out ($99),a
    ld a,$9f
    out ($99),a
    ld a,$83
    out ($99),a
'''+text[end+len('    reg 3,$1f\n'):]
    start=text.index('    push hl\n    ex de,hl',text.index('hud_upload:'));end=text.index('    pop hl\n    ld c,$98',start)
    text=text[:start]+'    push hl\n    ex de,hl\n    call GamePattern_Address\n'+text[end:]
    text=text.replace('cx EQU $c000','''    MACRO vdp_write number,value
    reg number,value
    ENDM
cx EQU $c000''',1)
    start=text.index('clock_irq:');end=text.index('upload:\n',start)
    text=text[:start]+'''clock_irq:
    push af
    in a,($99)
    bit 7,a
    jr z,.done
    push hl
    ld hl,(clock_ticks)
    inc hl
    ld (clock_ticks),hl
    pop hl
    ld a,(Session_State)
    or a
    jr z,.done
    push bc
    push de
    push hl
    call GameSession_LatchKeys
    pop hl
    pop de
    pop bc
.done:
    pop af
    ei
    reti
'''+text[end:]
    text=text.replace('    call boundaries\n','    call GameSession_Boundaries\n',1)
    text=text.replace('.boundary_needed:\n','.boundary_needed:\n    call GameSession_MapEdges\n',1)
    text=text.replace('render.hud_uploaded:\n','render.hud_uploaded:\n    call GameSession_FlagUpload\n',1)
    text=text.replace('.no_left:\n','.no_left:\n    call GameSession_LabelUpload\n    call GameSession_PopupUpload\n',1)
    text=text.replace('    INCLUDE "game-audio-data.inc"\n    INCLUDE "game-audio.inc"',
        '    INCLUDE "full-audio-state.inc"\n    INCLUDE "session-resident.inc"\n    INCLUDE "session-flags.inc"\n    INCLUDE "session-bank-tables.inc"')
    # Native cold worker owns AC00/AE00, as in the shared production adapter.
    text=text.replace('    INCBIN "game-native-raw.bin",0,$3500','''    INCBIN "game-native-raw.bin",0,$2c00
    INCLUDE "session-native-objects.inc"
    ASSERT $ <= $ae00
    defs $ae00-$,$ff
    INCLUDE "session-native-round.inc"
    ASSERT $ <= $b000
    defs $b000-$,$ff
    INCBIN "game-native-raw.bin",$3000,$500''')
    text+='''
    OUTPUT "session-boot-linked.bin"
    ORG $8000
    DISP $2900
GameSession_StartupWorkers:
    IF SESSION_HARDWARE_CHECK
    INCLUDE "session-startup-options.inc"
    ENDIF
    ASSERT $ <= $2c00
    defs $2c00-$,0
    IF HUD_SMALL_ROUND
    INCLUDE "hud-round-worker.inc"
    ENDIF
    INCLUDE "session-test-worker.inc"
GameSession_BootEnd:
    ASSERT $ <= $3000
    ENT
    defs $9000-$,$ff
    DISP $d300
    IF SESSION_HARDWARE_CHECK
    INCLUDE "session-boot-data.inc"
    ENDIF
    ASSERT $ <= $df00
    ENT
    defs $c000-$,$ff

    OUTPUT "session-ui-linked.bin"
    ORG $8000
    INCLUDE "session-ui.inc"
    ASSERT $ <= $c000
    defs $c000-$,$ff

    OUTPUT "session-cold-linked.bin"
    ORG $8000
    DISP $1400
GameSession_ColdStart:
    INCLUDE "session-cold.inc"
GameSession_ColdEnd:
    ASSERT $ <= $2000
    ENT
    defs $c000-$,$ff

    OUTPUT "session-audio-linked.bin"
    ORG $8000
    INCBIN "session-production-audio.bin",0,$1b00
    INCLUDE "audio-score.inc"
    INCLUDE "full-audio-runtime.inc"
    ASSERT $ <= $a580
    defs $a580-$,$ff
    INCBIN "session-production-audio.bin",$2580,$1a80
'''
    return text


def finalize(assembly,out,banks):
    result=bytearray(banks);metadata=json.loads((out/'session-build.json').read_text())
    for name,key in (('ui','SESSION_BANK'),('cold','SESSION_COLD_BANK'),('audio','AUDIO_BANK'),('boot','SESSION_BOOT_BANK')):
        data=(assembly/f'session-{name}-linked.bin').read_bytes()
        assert len(data)==16384,(name,len(data))
        at=(metadata['banks'][key]-1)*16384;result[at:at+16384]=data
    return result


def assemble_existing(out):
    """Relink authored adapters against an already generated resource bundle."""
    import subprocess,tempfile
    import game_build,game_core
    out=Path(out).resolve();root=Path(__file__).resolve().parents[2]
    view,_=reference();game_core.prepare(view,out,full_session=True,source_directory=view/'src')
    text=renderer_source(game_build.renderer_source(Path(__file__).with_name('lab.asm').read_text()),out)
    (out/'lab.asm').write_text(text)
    with tempfile.TemporaryDirectory(prefix='.link-',dir=out) as temporary:
        assembly=Path(temporary)
        for name in ('lab.asm','palette.bin','radar-x.bin','radar-y.bin'):
            shutil.copyfile(out/name,assembly/name)
        game_build.copy_sources(root,out,assembly)
        subprocess.run([str(root/'.tools/sjasmplus/1.24.0/sjasmplus'),'--nologo','--sym=lab.sym','--lst=lab.lst','lab.asm'],cwd=assembly,check=True)
        banks=game_build.finalize_banks(assembly,out,bytearray((out/'banks.bin').read_bytes()))
        resident=(assembly/'fixed-hud.rom').read_bytes();assert len(resident)==16384
        (out/'fixed-hud.rom').write_bytes(resident+banks)
        for name in ('lab.sym','lab.lst'):shutil.copyfile(assembly/name,out/name)
    print(out/'fixed-hud.rom')


def export_cartridge(out):
    root=Path(__file__).resolve().parents[2]
    destination=root/'outputs/test-roms'
    destination.mkdir(parents=True,exist_ok=True)
    build=json.loads((out/'session-build.json').read_text())
    test_mode=bool(build['banks'].get('SESSION_TEST_MODE',0))
    suffix=('-test' if test_mode else '')+('-hud-classic' if json.loads((out/'hud-module.json').read_text())['name']=='classic' else '')+('-no-logo' if '-no-logo' in out.name else '')+('-no-check' if not build['banks'].get('SESSION_HARDWARE_CHECK',1) else '')
    target=destination/f'newrallyx-screen4-full-game{suffix}.rom'
    shutil.copyfile(out/'fixed-hud.rom',target)
    # WebMSX consumes the bracketed filename hint before mapper selection.
    # Keep the measured cartridge byte-identical and retain canonical paths.
    webmsx_target=target.with_name(target.stem+' [ASCII16].rom')
    shutil.copyfile(target,webmsx_target)
    manifest=dict(rom=str(target.relative_to(root)),rom_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        mapper='ASCII16',webmsx_rom=str(webmsx_target.relative_to(root)),
        bytes=target.stat().st_size,source_revision=build['revision'],presenter='Optimized SCREEN4 gameplay; shared SCREEN5 UI',
        enemy_policy='Native full-session progression',minimum_mapper_ram_kib=128,
        status='Experimental test cartridge; final visual/audio/timing acceptance remains with user',
        source_bundle=str(out.resolve()),test_mode=test_mode,hardware_check=bool(build['banks'].get('SESSION_HARDWARE_CHECK',1)),title=json.loads((out/'session-title.json').read_text()),hud_module=json.loads((out/'hud-module.json').read_text()))
    (destination/f'full-session-build{suffix}.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Test ROM:',target)
    print('WebMSX ROM:',webmsx_target)
    return target


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--assemble-existing',type=Path);selection.add_argument('--export',type=Path)
    options=parser.parse_args()
    if options.export:export_cartridge(options.export)
    else:assemble_existing(options.assemble_existing)
