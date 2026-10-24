Full_EnemyRecords EQU $ce20   ; seven 32-byte prepared/cache/SAT records, ends CF00
Full_EnemyPoints EQU $c660    ; seven world-radar anchors
Full_EnemySource EQU $c670
Full_EnemyPattern EQU $c672
Full_EnemySATByte EQU $c673
Full_EnemyIndex EQU $c674
Full_EnemyAction EQU $c676

Enemy_InitPatterns:
    call FullEnemy_InitShared
    ld hl,Full_EnemyRecords
    ld de,Full_EnemyRecords+1
    ld bc,223
    xor a
    ld (hl),a
    ldir
    ld hl,Full_EnemyRecords+14
    ld b,7
.invalid:
    ld (hl),255
    inc l
    ld (hl),255
    ld de,3
    add hl,de
    ld (hl),255
    ld de,3
    add hl,de
    ld (hl),255
    inc l
    ld (hl),216             ; Invalid hidden-Y tag; first publish must write SAT.
    ld de,24
    add hl,de
    djnz .invalid
    ld hl,Full_EnemyPoints
    ld de,Full_EnemyPoints+1
    ld bc,13
    ld (hl),255
    ldir
    ret
Enemy_Radar:
    ld a,(player_steps)
    or a
    ret z
    ld bc,(Full_EnemyPoints)
    ld a,b
    ld b,c
    ld c,a
    jp HUD_SetEnemy
Full_EnemyFrame:
    ld a,(player_steps)
    or a
    ret z
    ld hl,Full_EnemyFrameOne
    call Full_EnemyLoop
    jp Full_EnemyTerminatorResident
Full_EnemyFrameOne:
    call Full_EnemyPrepareRadar
    jp FullEnemy_DrawOne
Full_EnemyPrepareRadar:
    call FullEnemy_PrepareOne
    jp FullEnemy_RadarOne
Full_EnemyPatterns:
    db 192,200,208,216,224,232,248

; Parked descriptors have no radar point or visible sprite. Reuse their caches
; without loading/saving thirty bytes three times per refresh.
Full_EnemyInactive:
    call Full_EnemyFar
    ret c
    ld hl,(Full_EnemyAction)
    ld de,FullEnemy_DrawOne
    or a
    sbc hl,de
    jr nz,.native
    call Full_EnemyRecordAddress
    ld a,(hl)
    or a
    jr z,.hide_only          ; Hidden prepared poses need no thirty-byte copy.
.native:
    ld hl,(Full_EnemySource)
    ld de,10
    add hl,de
    ld a,(hl)
    cp 56
    jr nc,.parked
    or a
    ret
.parked:
    call Full_EnemyRecordAddress
    ld (hl),0
    ld bc,$ffff
    call Full_EnemySetPoint
    ld hl,(Full_EnemyAction)
    ld de,FullEnemy_DrawOne
    or a
    sbc hl,de
    jr z,.hide_only
    ld hl,(Full_EnemyAction)
    ld de,Full_EnemyFrameOne
    or a
    sbc hl,de
    jr nz,.skip
.hide_only:
    call Full_EnemyRecordAddress
    ld de,22
    add hl,de
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.hide
    inc a
.hide:
    cp (hl)
    jr z,.skip               ; Same scroll and already hidden: retain the exact SAT.
    ld (hl),a
    push hl
    inc hl
    inc hl
    inc hl
    inc hl
    ld (hl),a
    pop hl
    di
    vdp_write 14,7
    ei
    nop
    ld a,(Full_EnemySATByte)
    ld e,a
    ld d,$76
    ld b,8
    call Sprite_Upload
.skip:
    scf
    ret

Full_EnemyTerminatorResident:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_EnemyTerminator
