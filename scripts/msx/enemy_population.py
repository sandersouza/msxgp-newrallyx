"""Unroll the authored presentation adapter for the two-enemy experiment.

Only host assembly is generated here. Native population initialization and AI
remain one original call over every descriptor. Stage 08 uses its source verbatim.
"""
import re


def replace_once(source, old, new):
    if source.count(old)!=1:
        raise ValueError(f'Enemy presentation template changed: {old!r}')
    return source.replace(old,new,1)


def actor_images(ram,pixels,flags,count,planes=2):
    """Screen-coordinate oracle, in reverse SAT priority for opaque composition."""
    result=[]
    translation=bytes(6 if i==3 else 10 if i==9 else 14 if i==11 else i for i in range(256))
    for actor in reversed(range(count)):
        at=0x5d0 if actor==0 else 0x640
        if not ram[at+2]:continue
        image=pixels[flags.index(ram[at+3])*256:][:256].translate(translation)
        if planes==1:image=bytes(6 if p else 0 for p in image)
        result.append((image,int.from_bytes(ram[at+8:at+10],'little',signed=True),
                       int.from_bytes(ram[at+10:at+12],'little',signed=True)))
    return result


COMPACT_PATTERNS='''    db 0,4,8,12,16,116,120,124,128,188,192,196
    db 200,204,208,212,216,220,224,228,232,236,240,244,248,252'''


def compact_patterns(source):
    return replace_once(source,
        '    db 0,4,8,12,16,188,192,196,200,204,208,212\n    db 216,220,224,228,232,236,240,244,248,252',COMPACT_PATTERNS)


def assembly(source, count, planes=2,*,compact=False,player_slot=15,radar_player=False):
    if count==1:
        if not compact:return source
        source=compact_patterns(source)
        preloaded=11 if radar_player else 12
        source=replace_once(source,'ld d,11',f'ld d,{preloaded}')
        source=replace_once(source,'cp 10\n    jr nc,.dynamic',f'cp {preloaded}\n    jr nc,.dynamic')
        target=player_slot+2
        source=replace_once(source,'ld a,19*4',f'ld a,{target}*4')
        return replace_once(source,'ld a,$30\n    out ($99),a',f'ld a,${target*16&255:02x}\n    out ($99),a')
    if count!=2 or planes not in (1,2):raise ValueError('Validate two enemies before increasing the experiment')
    core,body=source.split('    IF ENEMY_RENDER\n',1)
    ending='    ENDIF\n    ENDIF\n'
    if not body.endswith(ending):raise ValueError('Enemy presentation boundary changed')
    body=body[:-len(ending)]
    variants=[]
    for index in range(2):
        prefix=f'Enemy{index+1}_'
        text=body.replace('Enemy_',prefix)
        text=replace_once(text,'ld d,11','ld d,8')
        text=replace_once(text,'ld a,10\n    ld ('+prefix+'Cache),a','ld a,255\n    ld ('+prefix+'Cache),a')
        text=replace_once(text,'cp 10\n    jr nc,.dynamic','cp 8\n    jr nc,.dynamic')
        text=replace_once(text,'    ret nz                    ; source hides the colliding car during the hold',
            '    jr z,.alive\n    ld hl,(Enemy_HitAddress)\n'
            f'    ld de,${0xe096+index*32:04x}\n    or a\n    sbc hl,de\n    ret z')
        if index:
            text=re.sub(r'\$c5([de][0-9a-f])',lambda m:f'${int(m[0][1:],16)+0x70:04x}',text)
            text=replace_once(text,prefix+'SAT EQU $c600',prefix+'SAT EQU $c610')
            text=replace_once(text,prefix+'Masks EQU $c620',prefix+'Masks EQU $c624')
            for old in ('e090','e08d','e092','e08f','e097'):
                text=text.replace('$'+old,f'${int(old,16)+32:04x}')
            text=replace_once(text,'cp $93','cp $b3')
            text=replace_once(text,'ld a,19*4','ld a,21*4')
            text=replace_once(text,'ld a,$30\n    out ($99),a','ld a,$50\n    out ($99),a')
            text=text.replace('jp HUD_SetEnemy','jp Enemy2_SetPoint')
            text=replace_once(text,prefix+'GuardClosed EQU $c658','')
            text=prefix+'Visible EQU $c642\n'+text
        else:
            text=text.replace('ld a,248','ld a,240').replace('ld a,252','ld a,244')
            text=replace_once(text,'add a,$c0','add a,$80')
            text=prefix+'Visible EQU Enemy_Visible\n'+text
        text=text.replace(prefix+'Contact','Enemy_Contact')
        if planes==1:text=single_plane(text,prefix,index)
        if compact:
            text=compact_patterns(text)
            preloaded=10 if radar_player else 11
            text=replace_once(text,'ld d,8',f'ld d,{preloaded}')
            text=replace_once(text,'cp 8\n    jr nc,.dynamic',f'cp {preloaded}\n    jr nc,.dynamic')
            slot=19+index*planes
            target=player_slot+2+index*planes
            text=replace_once(text,f'ld a,{slot}*4',f'ld a,{target}*4')
            old=(slot*16)&255;new=(target*16)&255
            text=replace_once(text,f'ld a,${old:02x}\n    out ($99),a',f'ld a,${new:02x}\n    out ($99),a')
            if target<16:
                text=replace_once(text,'ld a,$75\n    out ($99),a','ld a,$74\n    out ($99),a')
        variants.append(text)
    aliases='''Enemy_HitAddress EQU $c63c
Enemy_RadarWork EQU Enemy1_RadarWork
Enemy_RadarSource EQU Enemy1_RadarSource
Enemy_GuardClosed EQU Enemy1_GuardClosed
'''
    wrappers=WRAPPERS.replace('ld a,23*4','ld a,21*4') if planes==1 else WRAPPERS
    if compact:
        wrappers=replace_once(wrappers,'''    IF HUD_ENABLED
    jp Enemy2_DrawPoint
    ELSE
    ret
    ENDIF''','    ret')
        wrappers=wrappers[:wrappers.index('Enemy2_DrawPoint:\n')]
        return core+'    IF ENEMY_RENDER\n'+aliases+''.join(variants)+wrappers+ending
    wrappers=replace_once(wrappers,'    jp Enemy2_Radar','    call Enemy2_Radar\n    jp Enemy_PairRadar')
    wrappers=replace_once(wrappers,'Enemy2_DrawPoint:\n','''Enemy2_DrawPoint:
    ld a,(Enemy_PairMode)
    or a
    jr z,.separate
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.merged_hide
    inc a
.merged_hide:
    ld ($c620),a
    jp .publish
.separate:
''')
    return core+'    IF ENEMY_RENDER\n'+aliases+''.join(variants)+wrappers+'    INCLUDE "enemy-radar-pair.inc"\n'+ending


def single_plane(source,prefix,index):
    """Preserve every opaque source pixel; publish one red silhouette per car."""
    source=source.replace('ld a,PLAYER_DATA_BANK','ld a,ENEMY_MASK_BANK')
    source=replace_once(source,'ld bc,64\n    add hl,bc','ld bc,960\n    add hl,bc')
    source=replace_once(source,'    or a\n    jp z,.upload\n','')
    begin=source.index('    ld a,('+prefix+'EC)\n    or $6a')
    end=source.index('.attributes:\n',begin)
    source=source[:begin]+source[end:]
    begin=source.index('    inc hl\n    ld a,('+prefix+'SatY)\n',source.index('.attributes:\n'))
    end=source.index('    jr .publish',begin)
    source=source[:begin]+source[end:]
    source=replace_once(source,'ld bc,$0898','ld bc,$0498')
    source=replace_once(source,'ld b,8\n    call Sprite_Upload','ld b,4\n    call Sprite_Upload')
    source=replace_once(source,'ld b,32\n    call Sprite_Upload','ld b,16\n    call Sprite_Upload')
    source=replace_once(source,'ld b,64\n    call '+prefix+'Upload','ld b,32\n    call '+prefix+'Upload')
    source=replace_once(source,'ld b,4\n.top_mask:','ld b,2\n.top_mask:')
    if index:
        source=replace_once(source,'ld a,21*4','ld a,20*4')
        source=replace_once(source,'ld a,$50\n    out ($99),a','ld a,$40\n    out ($99),a')
    return source


WRAPPERS='''
; The extra dot uses two spare pattern groups, never an enemy victim group.
Enemy2_PointX EQU $c638
Enemy2_PointY EQU $c639
Enemy2_PointDrawnX EQU $c63a
Enemy2_PointDrawnY EQU $c63b
Enemy_InitPatterns:
    call Enemy1_InitPatterns
    call Enemy2_InitPatterns
    ld a,255
    ld (Enemy2_PointDrawnX),a
    ld (Enemy2_PointDrawnY),a
    ret
Enemy_Prepare:
    call Enemy1_Prepare
    jp Enemy2_Prepare
Enemy_Radar:
    call Enemy1_Radar
    jp Enemy2_Radar
Enemy2_SetPoint:
    ld a,b
    ld (Enemy2_PointX),a
    ld a,c
    ld (Enemy2_PointY),a
    ret
Enemy_Draw:
    call Enemy1_Draw
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    di
    ENDIF
    call Enemy2_Draw
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    di
    ENDIF
    IF HUD_ENABLED
    jp Enemy2_DrawPoint
    ELSE
    ret
    ENDIF
Enemy_DrawDone:
    ret
Enemy2_DrawPoint:
    ld a,(Enemy2_PointX)
    ld d,a
    ld hl,Enemy2_PointDrawnX
    cp (hl)
    jr nz,.upload
    ld a,(Enemy2_PointY)
    ld hl,Enemy2_PointDrawnY
    cp (hl)
    jr z,.attributes
.upload:
    ld a,d
    ld (Enemy2_PointDrawnX),a
    ld a,(Enemy2_PointY)
    ld e,a
    ld (Enemy2_PointDrawnY),a
    call draw_point
    ld hl,(Enemy_RadarSource)
    vdp_write 14,7
    ld a,$40
    out ($99),a
    ld a,$7f
    out ($99),a
    ld bc,$4098
    IF INCREMENTAL_STAGE >= 9
    ld de,$7f40
    call Sprite_Upload
    ELSE
    otir
    ENDIF
.attributes:
    ld a,(Enemy2_PointX)
    ld d,a
    ld a,(Enemy2_PointY)
    ld e,a
    ld hl,$c620
    ld c,232
    call point_attribute
    ld a,(Enemy2_PointX)
    cp 255
    jr nz,.publish
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.hide
    inc a
.hide:
    ld ($c620),a
.publish:
    IF SPRITE_FLICKER
    ret
    ENDIF
    vdp_write 14,7
    ld a,23*4
    out ($99),a
    ld a,$76
    out ($99),a
    ld hl,$c620
    ld bc,$0498
    otir
    ld a,216
    out ($98),a
    ret
'''
