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
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_EnemyFarNative
