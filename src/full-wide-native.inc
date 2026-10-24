Full_WideSourceBank EQU $d2e0
Full_WideNative:
    ld a,(Stage_RowBatch)
    cp 1
    jp z,.none             ; Horizontal source storage now holds complete cells.
    cp 2
    jp nz,.none
    ld a,(tile_y)
    call Stage_StripMod3
    or a
    jp nz,.none
    ld a,(tile_y)
    add a,5
    cp STAGE_ROWS
    jp nc,.none
    ld a,(tile_y)
    and 31
    cp 27
    jp nc,.none
    ld a,(column_left)
    cp 5
    jp c,.none
    ld a,(tile_y)
    inc a
    ld hl,column_y
    cp (hl)
    jp nz,.none
    ld a,(cache_top)
    ld b,a
    ld a,(tile_y)
    add a,5
    sub b
    cp 32
    jp nc,.none
    ld a,(tile_y)
    add a,3
    ld c,a
    ld a,(tile_x)
    ld b,a
    call Full_ObjectAtTile
    or a
    jp nz,.none
    ld a,(tile_y)
    ld c,a
    call .smoke
    or a
    jp nz,.none
    ld a,(tile_y)
    call Stage_StripDiv3
    ld a,c
    or $80
    ld h,a
    ld a,(tile_x)
    add a,a
    ld l,a
    push hl
    ld a,(Full_WideVBank)
    ld (Full_WideSourceBank),a
    ld hl,48
    ld (stage_command+10),hl
    ld a,3
    ld (stage_command+3),a
    ld a,(column_left)
    sub 5
    ld (column_left),a
    ld a,(column_y)
    add a,5
    ld hl,Stage_ColumnEnd
    cp (hl)
    jr nz,.column_cursor
    ld a,(Stage_ColumnTop)
.column_cursor:
    ld (column_y),a
.done:
    pop hl
    ld a,(Full_WideSourceBank)
    scf
    ret
.none:
    xor a
    ret
.smoke:
    ld d,5
.check:
    ld a,(Stage_RowBatch)
    cp 1
    jr nz,.next_y
    inc b
    jr .probe
.next_y:
    inc c
.probe:
    call Smoke_Batchable
    or a
    ret nz
    dec d
    jr nz,.check
    ret
