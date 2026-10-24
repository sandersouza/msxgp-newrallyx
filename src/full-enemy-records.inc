Full_EnemyRecordAddress:
    ld a,(Full_EnemyIndex)
    inc a
    rlca
    rlca
    rlca
    rlca
    rlca
    ld l,a
    ld h,Full_EnemyRecords/256
    ret
Full_EnemyLoad:
    call Full_EnemyRecordAddress
    ld de,Enemy_Visible
    ld bc,20
    ldir
    ld de,Enemy_TopRow
    ld bc,2
    ldir
    ld de,Enemy_SAT
    ld bc,8
    ldir
    ret
Full_EnemySave:
    call Full_EnemyRecordAddress
    ex de,hl
    ld hl,Enemy_Visible
    ld bc,20
    ldir
    ld hl,Enemy_TopRow
    ld bc,2
    ldir
    ld hl,Enemy_SAT
    ld bc,8
    ldir
    ret

; Conservative cell rejection avoids copying a complete sprite record for a
; car which cannot touch the viewport. Exact world/radar positions still update.
Full_EnemyFar:
    ld hl,(Full_EnemyAction)
    ld de,Full_EnemyFrameOne
    or a
    sbc hl,de
    jr z,.frame
    or a
    ret
.frame:
    ld hl,(Full_EnemySource)
    ld de,8
    add hl,de
    ld a,($e070)
    sub (hl)
    add a,7
    cp 15
    jr nc,.far
    inc hl
    inc hl
    ld a,($e072)
    sub (hl)
    add a,6
    cp 13
    jr nc,.far
    or a
    ret
.far:
    ld hl,(Full_EnemySource)
    ld de,8
    add hl,de
    ld a,(hl)
    dec hl
    dec hl
    dec hl
    call Player_Axis
    ld (Enemy_WorldX),hl
    ld hl,(Full_EnemySource)
    ld de,10
    add hl,de
    ld a,(hl)
    dec hl
    dec hl
    dec hl
    call Player_AxisY
    ld (Enemy_WorldY),hl
    call Full_EnemyRecordAddress
    ld (hl),0
    inc hl
    inc hl
    ex de,hl
    ld hl,Enemy_WorldX
    ld bc,4
    ldir
    call FullEnemy_RadarOne
    jp Full_EnemyInactive.hide_only
