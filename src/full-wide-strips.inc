; Validation executes in native-bank free space; only resident code changes
; the mapper for the final lookup and exact six-tile VDP copy.
Full_TryWideStrip:
    ld a,PLAYER_BANK
    ld ($7000),a
    call Full_WideNative
    jr nc,.restore
    ld ($7000),a
    call Stage_StripSource
    call stage_copy_destination
    ld hl,8
    ld (stage_command+8),hl
    ld (stage_command+10),hl
    ld a,2
    ld (stage_command+3),a
    scf
    ret
.restore:
    ld a,(tile_y)
    rlca
    rlca
    and 3
    ld hl,Full_IDBank
    add a,(hl)
    ld ($7000),a
    or a
    ret
