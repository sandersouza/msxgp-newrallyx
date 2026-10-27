; Complete cells precede the legacy 8x48 fallback. Ordinary exact strips
; cover its remaining cases; use this native bank space for RAM-only traversals.
Full_WideNative:
    xor a
    ret

Full_EnemyPrepareLoop:
    call Full_TurboOn
    ld hl,Full_EnemyPrepareRadar
    ld (Full_EnemyAction),hl
    ld hl,$e088
    ld (Full_EnemySource),hl
    ld ix,Full_EnemyRecords
    xor a
    ld (Full_EnemyIndex),a
    inc a
    ld (Full_RegisteredCurrent),a
.actor:
    call Full_EnemyFarNative.frame ; This batch already selects preparation, with registration enabled.
    call nc,Full_EnemyPrepareRadar
    ld hl,(Full_EnemySource)
    ld de,32
    add hl,de
    ld (Full_EnemySource),hl
    add ix,de
    ld hl,Full_EnemyIndex
    inc (hl)
    ld a,(hl)
    ld hl,$e24e
    cp (hl)
    jr c,.actor
    ret

; A VBlank may stop an optional stream after its cell command, before the
; owned tail of that row/column is consumed. Retire it before forecasting the
; next edge, so an already finished guard cannot block new lookahead work.
Full_TrimPendingQueues:
.row:
    ld a,(row_left)
    or a
    jr z,.column
    ld a,(row_x)
    ld e,a
    ld a,(row_y)
    ld d,a
    call .owned
    jr c,.column
    ld hl,row_left
    dec (hl)
    ld a,(row_x)
    inc a
    ld hl,Stage_RowEnd
    cp (hl)
    jr nz,.row_cursor
    ld a,(Stage_RowLeft)
.row_cursor:
    ld (row_x),a
    jr .row
.column:
    ld a,(column_left)
    or a
    ret z
    ld a,(column_x)
    ld e,a
    ld a,(column_y)
    ld d,a
    call .owned
    ret c
    ld hl,column_left
    dec (hl)
    ld a,(column_y)
    inc a
    ld hl,Stage_ColumnEnd
    cp (hl)
    jr nz,.column_cursor
    ld a,(Stage_ColumnTop)
.column_cursor:
    ld (column_y),a
    jr .column
.owned:
    call Full_WorldAddress
    ld a,(hl)
    cp 128
    jr z,.missing
    cp e
    jr nz,.missing
    inc l
    ld a,(hl)
    cp d
    ret z
.missing:
    scf
    ret
