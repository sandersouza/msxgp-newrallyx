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

; Conservative cell rejection avoids preparing/drawing a complete record for a
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
    ld a,(Full_RegisteredCurrent)
    or a
    jr z,.far               ; Unregistered cars still retain their exact radar anchors.
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
    ld (ix+2),l
    ld (ix+3),h
    ld hl,(Full_EnemySource)
    ld de,10
    add hl,de
    ld a,(hl)
    dec hl
    dec hl
    dec hl
    call Player_AxisY
    ld (ix+4),l
    ld (ix+5),h
    ld (ix+0),0
    call FullEnemy_RadarOne
    jp Full_EnemyInactive.hide_only
