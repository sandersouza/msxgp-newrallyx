Full_EnemyRecords EQU $ce20   ; seven 32-byte prepared/cache/SAT records, ends CF00
Full_EnemyPoints EQU $c660    ; seven world-radar anchors
Full_EnemySource EQU $c670
Full_EnemyPattern EQU $c672
Full_EnemySATByte EQU $c673
Full_EnemyIndex EQU $c674
Full_EnemyAction EQU $c676
Full_RegisteredMask EQU $c678
Full_EnemySATCursor EQU $c67a
Full_EnemySATDirty EQU $c67b
Full_RegisteredCurrent EQU $c67d

Full_EnemyBuildRegistration:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_BuildRegistrationNative
Full_EnemyRegistered:
    ld a,($e24e)
    cp 4
    jr nc,.mask
    ld hl,(Full_EnemySource)
    ld de,11
    add hl,de
    ex de,hl
    ld hl,$e004
    ld b,5
.slot:
    ld a,(hl)
    inc hl
    cp e
    jr nz,.other
    ld a,(hl)
    cp d
    jr z,.found
.other:
    inc hl
    djnz .slot
    xor a
    ret
.found:
    ld a,1
    or a
    ret
.mask:
    ld a,(Full_EnemyIndex)
    ld e,a
    ld d,0
    ld hl,Full_EnemyBits
    add hl,de
    ld a,(Full_RegisteredMask)
    and (hl)
    ret
Full_EnemyBits:
    db 1,2,4,8,16,32,64

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
    ld a,PLAYER_SLOT*4+8
    ld (Full_EnemySATCursor),a
    call Full_EnemyBuildRegistration
    ld hl,Full_EnemyFrameOne
    call Full_EnemyLoop
    jp Full_EnemyTerminatorResident
Full_EnemyFrameOne:
    call Full_EnemyPrepareRadar
    jp FullEnemy_DrawOne
FullEnemy_DrawOne:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_EnemyDrawNative
Full_EnemyPrepareRadar:
    call FullEnemy_PrepareOne
    jp FullEnemy_RadarOne
Full_EnemyPatterns:
    db 192,200,208,216,224,232,248

; Parked descriptors have no radar point or visible sprite. Retain their caches.
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
    jr z,.hide_only          ; Hidden prepared poses need no drawing work.
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
    ld (ix+30),255          ; A former destination may now contain the list terminator.
.skip:
    scf
    ret

Full_EnemyTerminatorResident:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_EnemyTerminator
