Full_EnemyRecords EQU $ce20   ; seven 32-byte prepared/cache/SAT records, ends CF00
Full_EnemyPoints EQU $c660    ; seven world-radar anchors
Full_EnemySource EQU $c670
Full_EnemyPattern EQU $c672
Full_EnemySATByte EQU $c673
Full_EnemyIndex EQU $c674
Full_EnemyWindowPattern EQU $c675
Full_EnemyAction EQU $c676
Full_RegisteredMask EQU $c678
Full_EnemySATCursor EQU $c67a
Full_EnemySATDirty EQU $c67b
Full_RegisteredCurrent EQU $c67d
Full_EnemyWorldChanged EQU $c67e
Full_EnemyWorldKeys EQU $db20 ; Four native coordinate bytes per actor; DB3C..3F spare.

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
    call Full_PresentBegin
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_EnemyDrawBatch
Full_EnemyFrameRestart:
    ld a,1
    ld (Full_RenderRestart),a
    jp Full_EnemyFrame
FullEnemy_DrawOne:
    jp Full_EnemyDrawNative
Full_EnemyPrepareRadar:
    call FullEnemyPrepareNative
    jp FullEnemyRadarNative ; Selection already mapped the RAM-only player helpers.
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
    ld (ix+31),0            ; Hidden radar publication must not survive cache reuse.
    ld bc,$ffff
    call Full_EnemySetPoint
    ld hl,(Full_EnemyAction)
    ld de,FullEnemy_DrawOne
    or a
    sbc hl,de
    jr z,.hide_only
    ld hl,(Full_EnemyAction)
    ld de,Full_EnemyPrepareRadar
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
