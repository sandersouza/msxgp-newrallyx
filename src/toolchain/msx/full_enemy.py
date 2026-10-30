"""Reuse one complete-car adapter over seven native descriptors and caches."""
from .enemy_population import replace_once,compact_patterns,COMPACT_PATTERNS
import re


def pattern_plan(*,radar_pattern=240):
    common=((0,4),(8,12),(16,188))
    victims=(192,200,208,216,224,232,248)
    used=set(range(20,116))|set(range(132,188))|set(range(radar_pattern,radar_pattern+8))
    for body,window in common:
        for base in (body,window):
            if used.intersection(range(base,base+4)):raise ValueError('Common enemy mask overlaps HUD')
            used.update(range(base,base+4))
    for base in victims:
        if used.intersection(range(base,base+8)):raise ValueError('Enemy cache overlaps another mask')
        used.update(range(base,base+8))
    for base in (116,124):
        if used.intersection(range(base,base+8)):raise ValueError('Compact radar spare cache overlaps HUD')
        used.update(range(base,base+8))
    if used!=set(range(256)):raise ValueError('Full enemy pattern allocation is incomplete')
    return common,victims


def registration_table():
    result=bytearray(512)
    for actor in range(7):result[0x93+actor*32]=1<<actor
    return bytes(result)


def validate_extension_space(bank):
    """Do not replace native instructions when installing bank-local helpers."""
    if (len(bank)!=16384 or bank[0x3800:0x3f00]!=bytes([255])*0x700 or
            bank[0x3500:0x3600]!=bytes([255])*0x100):
        raise ValueError('Full enemy helpers overlap occupied native bank space')


RECORD_FIELDS=dict(Enemy_Visible=0,Enemy_Flag=1,Enemy_WorldX=2,Enemy_WorldY=4,
    Enemy_DrawX=6,Enemy_DrawY=8,Enemy_Clip=10,Enemy_EC=11,Enemy_SatY=12,
    Enemy_Work=13,Enemy_Cache=14,Enemy_CacheClip=15,Enemy_Body=16,
    Enemy_Window=17,Enemy_LastEC=18,Enemy_Index=19,Enemy_TopRow=20,
    Enemy_CacheTop=21,Enemy_SAT=22)


def indexed_records(text):
    """Compile private complete-car fields against the current IX record.

    Field-address materialization preserves DE, including a prepared VDP write
    destination. Runtime callees preserve IX, including raster IRQs.
    """
    fields='|'.join(RECORD_FIELDS)
    pattern=re.compile(r'^(\s*)ld (a|bc|de|hl),\(('+fields+r')(?:\+(\d+))?\)(.*)$',re.M)
    def read(m):
        indent,reg,name,extra,comment=m.groups();at=RECORD_FIELDS[name]+int(extra or 0)
        if len(reg)==1:return f'{indent}ld {reg},(ix+{at}){comment}'
        return f'{indent}ld {reg[1]},(ix+{at})\n{indent}ld {reg[0]},(ix+{at+1}){comment}'
    text=pattern.sub(read,text)
    pattern=re.compile(r'^(\s*)ld \(('+fields+r')(?:\+(\d+))?\),(a|bc|de|hl)(.*)$',re.M)
    def write(m):
        indent,name,extra,reg,comment=m.groups();at=RECORD_FIELDS[name]+int(extra or 0)
        if len(reg)==1:return f'{indent}ld (ix+{at}),{reg}{comment}'
        return f'{indent}ld (ix+{at}),{reg[1]}\n{indent}ld (ix+{at+1}),{reg[0]}{comment}'
    text=pattern.sub(write,text)
    pattern=re.compile(r'^(\s*)ld hl,('+fields+r')\b(.*)$',re.M)
    text=pattern.sub(lambda m:f'{m[1]}push de\n{m[1]}push ix\n{m[1]}pop hl\n{m[1]}ld de,{RECORD_FIELDS[m[2]]}\n{m[1]}add hl,de\n{m[1]}pop de{m[3]}',text)
    if re.search(r'\b(?:'+fields+r')\b',text):raise ValueError('Uncompiled private actor field reference')
    return text


def assembly(source):
    core,body=source.split('    IF ENEMY_RENDER\n',1)
    end='    ENDIF\n    ENDIF\n'
    if not body.endswith(end):raise ValueError('Enemy adapter boundary changed')
    body=compact_patterns(body[:-len(end)])
    body=replace_once(body,'''    xor a
    ld (Enemy_CacheClip),a
    ld (Enemy_LastEC),a
    ld a,10
    ld (Enemy_Cache),a
    ld a,255
    ld (Enemy_CacheTop),a
    ret''','''    ret                      ; Per-actor records own all prepared/cache fields.''')
    common,_=pattern_plan()
    body=replace_once(body,COMPACT_PATTERNS,'    db '+','.join(str(v) for pair in common for v in pair))
    for old,new in (('Enemy_InitPatterns','FullEnemy_InitShared'),('Enemy_Prepare','FullEnemy_PrepareOne'),
                    ('Enemy_Radar','FullEnemy_RadarOne'),('Enemy_DrawDone','FullEnemy_DrawOneDone'),
                    ('Enemy_Draw','FullEnemy_DrawOne')):
        body=re.sub(r'\b'+old+r'\b',new,body)
    body=replace_once(body,'ld d,11','ld d,3')
    body=replace_once(body,'cp 10\n    jr nc,.dynamic','cp 3\n    jr nc,.dynamic')
    for cell,offset,target in (('90',8,'Player_Axis'),('92',10,'Player_AxisY')):
        signed='8d' if cell=='90' else '8f'
        body=replace_once(body,f'    ld a,($e0{cell})\n    ld hl,$e0{signed}\n    call {target}',
            f'    ld hl,(Full_EnemySource)\n    ld de,{offset}\n    add hl,de\n    ld a,(hl)\n    dec hl\n    dec hl\n    dec hl\n    call {target}')
    body=replace_once(body,'    ld a,($e097)',
        '    ld hl,(Full_EnemySource)\n    ld de,15\n    add hl,de\n    ld a,(hl)')
    body=replace_once(body,'''    ld a,(Enemy_Contact)
    or a
    ret nz                    ; source hides the colliding car during the hold''','''    ld a,(Enemy_Contact)
    or a
    jr z,.alive
    ld hl,(Enemy_HitAddress)
    ld de,(Full_EnemySource)
    or a
    sbc hl,de
    ld de,14
    or a
    sbc hl,de
    ret z''')
    body=replace_once(body,'''    ld hl,$e004
    ld b,5
.registered:
    ld a,(hl)
    inc hl
    cp $93
    jr nz,.other
    ld a,(hl)
    cp $e0
    jr z,.bounds
.other:
    inc hl
    djnz .registered
    ret''','''    ld a,(Full_RegisteredCurrent)
    or a
    ret z''')
    body=body.replace('ld a,248','ld a,(Full_EnemyPattern)')
    body=replace_once(body,'ld a,252','ld a,(Full_EnemyPattern)\n    add a,4')
    body=replace_once(body,'''    ld a,c
    add a,$c0
    ld c,a''','''    ld a,(Full_EnemyPattern)
    rlca
    rlca
    rlca
    and $c0
    add a,c
    ld c,a''')
    body=replace_once(body,'    ld a,$7f\n    out ($99),a',
        '    ld a,(Full_EnemyPattern)\n    cp 224\n    ld a,$7e\n    jr c,.top_high\n    inc a\n.top_high:\n    out ($99),a')
    body=replace_once(body,'    ld a,$30\n    out ($99),a',
        '    ld a,(Full_EnemySATByte)\n    add a,a\n    add a,a\n    out ($99),a')
    body=replace_once(body,'ld a,19*4','ld a,(Full_EnemySATByte)')
    body=replace_once(body,'    ld a,216\n    out ($98),a\n    ret','    ret')
    body=body.replace('jp HUD_SetEnemy','jp Full_EnemySetPoint')
    body=body.replace('FullEnemy_DrawOne:','FullEnemy_DrawPrepared:')
    body=replace_once(body,'''FullEnemy_DrawPrepared:
    ld a,(driving)
    or a
    ret z''','''FullEnemy_DrawPrepared:''')
    body=replace_once(body,'''.x:
    ld b,a
    ld a,(Enemy_SatY)
    ld hl,Enemy_SAT''','''.x:
    ld b,a
    ld a,(Full_EnemySATDirty)
    or a
    jr nz,.sat_changed
    ld a,(Enemy_SatY)
    cp (ix+22)
    jr nz,.sat_changed
    ld a,b
    cp (ix+23)
    jr nz,.sat_changed
    ld a,(Enemy_Body)
    cp (ix+24)
    jr nz,.sat_changed
    ld a,(Enemy_Window)
    cp (ix+28)
    ret z
.sat_changed:
    ld a,(Enemy_SatY)
    ld hl,Enemy_SAT''')
    first=body.index('FullEnemy_PrepareOne:\n');last=body.index('FullEnemy_DrawPrepared:\n')
    for axis,world,offset,cell in [('Player_Axis','Enemy_WorldX',5,8),('Player_AxisY','Enemy_WorldY',7,10)]:
        old=f'''    ld hl,(Full_EnemySource)
    ld de,{cell}
    add hl,de
    ld a,(hl)
    dec hl
    dec hl
    dec hl
    call {axis}
    ld ({world}),hl'''
        new=f'    ld hl,({world})'
        body=replace_once(body,old,new)
    first=body.index('FullEnemy_PrepareOne:\n');last=body.index('FullEnemy_DrawPrepared:\n')
    native=indexed_records(body[first:last]).replace('FullEnemy_PrepareOne:','FullEnemyPrepareNative:').replace('FullEnemy_RadarOne:','FullEnemyRadarNative:')
    native=native.replace('(player_x)','(Full_CameraCentreX)').replace('(player_y)','(Full_CameraCentreY)')
    native=native.replace('FullEnemyPrepareNative:\n','FullEnemyPrepareNative:\n    call FullEnemyWorldNative\n    call FullEnemyFastPose\n    ret c\n',1)
    native=native.replace('FullEnemyRadarNative:\n','FullEnemyRadarNative:\n    ld a,(Full_EnemyWorldChanged)\n    or a\n    ret z\n',1)
    native=replace_once(native,'''    bit 7,h
    jr z,.phase
    ld a,$80
    ld (ix+11),a
.phase:''','''.phase:''')
    pose_start=native.index('    ld b,a\n    ld a,(ix+20)')
    pose_end=native.index('FullEnemyRadarNative:',pose_start)
    native=native[:pose_start]+'    ld a,1\n    ld (ix+0),a\n    ret\n\n'+native[pose_end:]
    if '($7000)' in native:raise ValueError('Bank-local actor preparation changes its own mapper')
    wrappers='''FullEnemy_PrepareOne:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp FullEnemyPrepareNative
FullEnemy_RadarOne:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp FullEnemyRadarNative
FullEnemy_WorldOne:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp FullEnemyWorldNative
'''
    body=body[:first]+wrappers+indexed_records(body[last:])
    body=replace_once(body,'''    ld a,(ix+6)
    ld b,a
    ld a,(ix+11)
    or a
    ld a,b
    jr z,.x
    add a,32
.x:''','''    ld a,(ix+7)
    bit 7,a
    ld a,(ix+6)
    jr z,.x
    xor a
.x:''')
    body=replace_once(body,'''    ld a,(Full_EnemyPattern)
    ld b,64
    call Enemy_Upload''','''    ld a,(Full_EnemyPattern)
    cp 16
    jr nz,.contiguous
    ld b,32
    call Enemy_Upload
    ld a,(Full_EnemyWindowPattern)
    ld b,32
    call Enemy_Upload
    jr .mask_complete
.contiguous:
    ld b,64
    call Enemy_Upload
.mask_complete:''')
    body=body.replace('call Sprite_Upload','call Full_QueueSprite')
    start=body.index('    ld c,a\n    vdp_write 14,7')
    top_end=body.index('.colors:',start)
    body=body[:start]+'    call Full_QueueTopMask\n'+body[top_end:]
    # Gameplay drawing now prepares RAM packets only. The upload abstraction
    # owns every actual VDP transaction, including initial direct uploads.
    start=body.index('FullEnemy_DrawPrepared:')
    drawing=body[start:]
    drawing=drawing.replace('    vdp_write 14,7\n','')
    drawing=drawing.replace('    out ($99),a\n','')
    body=body[:start]+drawing
    resident=core+'    IF ENEMY_RENDER\nEnemy_HitAddress EQU $c63c\n'+body+'\n    INCLUDE "full-enemy-loop.inc"\n'+end
    return resident,native
