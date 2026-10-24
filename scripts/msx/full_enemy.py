"""Reuse one complete-car adapter over seven native descriptors and caches."""
from .enemy_population import replace_once,compact_patterns,COMPACT_PATTERNS
import re


def pattern_plan(*,radar_pattern=240):
    common=((0,4),(8,12),(16,188))
    victims=(192,200,208,216,224,232,248)
    used=set(range(20,188))|set(range(radar_pattern,radar_pattern+8))
    for body,window in common:
        for base in (body,window):
            if used.intersection(range(base,base+4)):raise ValueError('Common enemy mask overlaps HUD')
            used.update(range(base,base+4))
    for base in victims:
        if used.intersection(range(base,base+8)):raise ValueError('Enemy cache overlaps another mask')
        used.update(range(base,base+8))
    if used!=set(range(256)):raise ValueError('Full enemy pattern allocation is incomplete')
    return common,victims


def assembly(source):
    core,body=source.split('    IF ENEMY_RENDER\n',1)
    end='    ENDIF\n    ENDIF\n'
    if not body.endswith(end):raise ValueError('Enemy adapter boundary changed')
    body=compact_patterns(body[:-len(end)])
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
    body=replace_once(body,'    ld hl,$e004\n    ld b,5',
        '    ld de,(Full_EnemySource)\n    ld a,e\n    add a,11\n    ld e,a\n    ld hl,$e004\n    ld b,5')
    body=replace_once(body,'cp $93','cp e')
    body=replace_once(body,'cp $e0','cp d')
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
    return core+'    IF ENEMY_RENDER\nEnemy_HitAddress EQU $c63c\n'+body+'\n    INCLUDE "full-enemy-loop.inc"\n'+end
