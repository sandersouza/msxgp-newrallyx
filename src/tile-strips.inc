; Exact 24x8 / 8x24 copies within one original world cell. Keep every pixel;
; flag owners and death repairs continue through their existing adapters.
Stage_TryStrip:
    bit 0,a
    jr nz,.no
    ld a,(Death_DisplayState)
    or a
    jr nz,.no
    ld a,(tile_x)
    cp STAGE_COLUMNS
    jr nc,.no
    ld a,(tile_y)
    cp STAGE_ROWS
    jr nc,.no
    IF FULL_GAME
    call Full_TryWideStrip
    ret c
    ENDIF
    ld a,(Stage_RowBatch)
    cp 1
    jr z,.horizontal
    cp 2
    jp z,.vertical
.no:
    or a
    ret
.horizontal:
    ld a,(tile_x)
    call Stage_StripMod3
    or a
    jr nz,.no
    ld a,(tile_x)
    and 31
    cp 30
    jr nc,.no
    ld a,(row_left)
    cp 2
    jp c,.no
    ld a,(tile_x)
    inc a
    ld b,a
    ld a,(row_x)
    cp b
    jr nz,.no
    inc a
    ld hl,Stage_RowEnd
    cp (hl)
    jp z,.no
    ld a,(cache_left)
    ld c,a
    ld a,(tile_x)
    add a,2
    sub c
    cp STAGE_CACHE_COLUMNS
    jp nc,.no
    IF SMOKE_RUNTIME
    ld a,(tile_x)
    inc a
    ld b,a
    ld a,(tile_y)
    ld c,a
    call Smoke_Batchable
    jp nz,.no
    inc b
    call Smoke_Batchable
    jp nz,.no
    ENDIF
    ld a,(tile_x)
    call Stage_StripDiv3
    ld a,(tile_y)
    ld l,a
    and 128
    rlca
    IF FULL_GAME
    push hl
    ld hl,Full_HBank
    add a,(hl)
    pop hl
    ELSE
    add a,STRIP_H_BANK
    ENDIF
    ld ($7000),a
    ld a,l
    and 127
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,c
    add a,a
    ld e,a
    ld d,0
    add hl,de
    ld de,$8000
    add hl,de
    call Stage_StripSource
    ld a,2
    ld (stage_command+3),a
    ld hl,24
    ld (stage_command+8),hl
    ld hl,row_left
    dec (hl)
    dec (hl)
    ld a,(row_x)
    add a,2
    ld hl,Stage_RowEnd
    cp (hl)
    jr nz,.row_cursor
    ld a,(Stage_RowLeft)
.row_cursor:
    ld (row_x),a
    jp .emit
.vertical:
    ld a,(tile_y)
    call Stage_StripMod3
    or a
    jp nz,.no
    ld a,(tile_y)
    and 31
    cp 30
    jp nc,.no
    ld a,(column_left)
    cp 2
    jp c,.no
    ld a,(tile_y)
    inc a
    ld b,a
    ld a,(column_y)
    cp b
    jp nz,.no
    inc a
    ld hl,Stage_ColumnEnd
    cp (hl)
    jp z,.no
    ld a,(cache_top)
    ld c,a
    ld a,(tile_y)
    add a,2
    sub c
    cp 32
    jp nc,.no
    IF SMOKE_RUNTIME
    ld a,(tile_x)
    ld b,a
    ld a,(tile_y)
    inc a
    ld c,a
    call Smoke_Batchable
    jp nz,.no
    inc c
    call Smoke_Batchable
    jp nz,.no
    ENDIF
    ld a,(tile_y)
    call Stage_StripDiv3
    IF FULL_GAME
    ld a,(Full_VBank)
    ELSE
    ld a,STRIP_V_BANK
    ENDIF
    ld ($7000),a
    ld a,c
    or $80
    ld h,a
    ld a,(tile_x)
    add a,a
    ld l,a
    call Stage_StripSource
    ld a,3
    ld (stage_command+3),a
    ld hl,24
    ld (stage_command+10),hl
    ld hl,column_left
    dec (hl)
    dec (hl)
    ld a,(column_y)
    add a,2
    ld hl,Stage_ColumnEnd
    cp (hl)
    jr nz,.column_cursor
    ld a,(Stage_ColumnTop)
.column_cursor:
    ld (column_y),a
.emit:
    call stage_copy_destination
    ld hl,8
    ld (stage_command+8),hl
    ld (stage_command+10),hl
    ld a,2
    ld (stage_command+3),a
    scf
    ret
Stage_StripSource:
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    ret
Stage_StripDiv3:
    IF FULL_GAME
    push hl
    push de
    push bc
    call Full_Div3
    pop bc
    ld c,a
    pop de
    pop hl
    ret
    ELSE
    ASSERT (STRIP_DIV3_ADDR & 255) == 0
    ld l,a
    ld h,STRIP_DIV3_ADDR >> 8
    ld a,STRIP_H_BANK+1
    ld ($7000),a
    ld c,(hl)
    ret
    ENDIF
Stage_StripMod3:
    ld l,a
    ld h,0
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    ret
Stage_StripInit:
    IF FULL_GAME
    jp Full_StripInit
    ELSE
    INCLUDE "strip-init.inc"
    ENDIF
