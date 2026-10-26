Full_EnemyLoop:
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
    jp Full_TurboOff        ; A culled final descriptor can skip its draw exit.
.dispatch:
    ld hl,(Full_EnemyAction)
    jp (hl)
Full_EnemySelect:
    call Full_TurboOn         ; Pure descriptor selection, before sprite I/O.
    ld a,(Full_EnemyIndex)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$e088
    add hl,de
    ld (Full_EnemySource),hl
    ld a,PLAYER_BANK
    ld ($7000),a
    ld a,1
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
    ld hl,Full_EnemyPrepareRadar
    jp Full_EnemyLoop
Enemy_Draw:
    ld a,PLAYER_SLOT*4+8
    ld (Full_EnemySATCursor),a
    ld hl,FullEnemy_DrawOne
    call Full_EnemyLoop
Enemy_DrawDone:
    jp Full_EnemyTerminatorResident
