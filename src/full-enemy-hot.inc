Full_EnemyLoop:
    ei
    nop
    ld (Full_EnemyAction),hl
    xor a
    ld (Full_EnemyIndex),a
.actor:
    call Full_EnemySelect
    call Full_EnemyInactive
    jr c,.next
    call Full_EnemyLoad
    call .dispatch
    ei
    nop
    call Full_EnemySave
.next:
    ei
    nop
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
    ld a,(Full_EnemyIndex)
    ld l,a
    ld h,0
    ld de,Full_EnemyPatterns
    add hl,de
    ld a,(hl)
    ld (Full_EnemyPattern),a
    ld a,(Full_EnemyIndex)
    add a,a
    add a,a
    add a,a
    add a,PLAYER_SLOT*4+8
    ld (Full_EnemySATByte),a
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
    ld hl,Full_EnemyPrepareRadar
    jp Full_EnemyLoop
Enemy_Draw:
    ld a,(player_steps)
    or a
    ret z
    ld hl,FullEnemy_DrawOne
    call Full_EnemyLoop
Enemy_DrawDone:
    jp Full_EnemyTerminatorResident
