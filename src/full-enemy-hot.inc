Full_EnemyLoop:
    ei
    ld (Full_EnemyAction),hl
    xor a
    ld (Full_EnemyIndex),a
.actor:
    call Full_EnemySelect
    call Full_EnemyInactive
    jr c,.next
    call .dispatch
.next:
    ei
    ld hl,Full_EnemyIndex
    inc (hl)
    ld a,(hl)
    ld hl,$e24e
    cp (hl)
    jr c,.actor
    ret
.dispatch:
    ld hl,(Full_EnemyAction)
    jp (hl)
Full_EnemySelect:
    call Full_TurboOn         ; Pure descriptor selection, before sprite I/O.
    ld a,(Full_EnemyIndex)
    ld c,a
    ld l,a
    ld h,0
    ld de,Full_EnemyPatterns
    add hl,de
    ld a,(hl)
    ld (Full_EnemyPattern),a
    ld l,c
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$e088
    add hl,de
    ld (Full_EnemySource),hl
    call Full_EnemyRegistered
    ld (Full_RegisteredCurrent),a
    call Full_EnemyRecordAddress
    push hl
    pop ix
    ret
Full_EnemySetPoint:
    ld a,(Full_EnemyIndex)
    add a,a
    add a,Full_EnemyPoints & 255
    ld l,a
    ld h,Full_EnemyPoints/256
    ld (hl),b
    inc hl
    ld (hl),c
    ret
Enemy_Prepare:
    ld a,(player_steps)
    or a
    ret z
    call Full_EnemyBuildRegistration
    ld hl,Full_EnemyPrepareRadar
    jp Full_EnemyLoop
Enemy_Draw:
    ld a,(player_steps)
    or a
    ret z
    ld a,PLAYER_SLOT*4+8
    ld (Full_EnemySATCursor),a
    ld hl,FullEnemy_DrawOne
    call Full_EnemyLoop
Enemy_DrawDone:
    jp Full_EnemyTerminatorResident
