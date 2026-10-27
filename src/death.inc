; Stage 03: original 3x3 bitmap effect and 120 logical-tick hold.
; Lives/restart are deliberately deferred to stage 07; Home resets this fixture.
    IF INCREMENTAL_STAGE >= 3
Death_State EQU $c490          ; 0=alive, 1=effect/hold, 2=hold complete
Death_Age EQU $c491
Death_X EQU $c492              ; world tile anchor
Death_Y EQU $c493
Death_Jobs EQU $c494           ; at most nine tiles, charged to stream budget
    IF INCREMENTAL_STAGE >= 9
Death_DisplayState EQU $c49a
    ELSE
Death_DisplayState EQU Death_State
    ENDIF
Death_Init:
    xor a
    ld (Death_State),a
    ld (Death_Age),a
    ld (Death_Jobs),a
    IF INCREMENTAL_STAGE >= 9
    ld (Death_DisplayState),a
    ENDIF
    ret
    IF INCREMENTAL_STAGE >= 9
Death_Frame:
    ld a,(Death_State)
    ld hl,Death_DisplayState
    cp (hl)
    ret z
    ld (hl),a
    ld a,9
    ld (Death_Jobs),a
    ret
    ENDIF
Death_Begin:
    ld a,(Rock_Contact)
    IF ENEMY_CONTACT
    ld hl,Enemy_Contact
    or (hl)
    ENDIF
    or a
    ret z
    call Player_Position
    ld hl,(player_pending_x)
    ld de,-9
    add hl,de
    call stage_div8
    ld a,l
    ld (Death_X),a
    ld hl,(player_pending_y)
    ld de,-8
    add hl,de
    call stage_div8
    ld a,l
    ld (Death_Y),a
    xor a
    ld (Death_Age),a
    inc a
    ld (Death_State),a
    IF INCREMENTAL_STAGE < 9
    ld a,9
    ld (Death_Jobs),a
    ENDIF
    IF INCREMENTAL_STAGE >= 7
    call Life_Begin
    ENDIF
    ret
Death_Tick:
    ld a,(Death_State)
    cp 1
    ret nz
    ld hl,Death_Age
    inc (hl)
    IF INCREMENTAL_STAGE >= 7
    ld a,(Death_Limit)
    cp (hl)
    ret nz
    ELSE
    ld a,(hl)
    cp DEATH_HOLD_TICKS
    ret c
    ENDIF
    ld a,2
    ld (Death_State),a
    IF INCREMENTAL_STAGE < 9
    ld a,9
    ld (Death_Jobs),a          ; restore underlying terrain when the hold expires
    ENDIF
    ret

; Carry indicates an active explosion source. World coordinates remain intact.
Death_Source:
    ld a,(Death_DisplayState)
    cp 1
    ret nz                    ; CP1 clears carry for complete; alive handled below
    ld a,(Death_X)
    ld c,a
    ld a,(tile_x)
    sub c
    cp 3
    jr nc,.outside
    ld e,a
    ld a,(Death_Y)
    ld c,a
    ld a,(tile_y)
    sub c
    cp 3
    jr nc,.outside
    ld c,a
    add a,a
    add a,c
    add a,e
    add a,a
    ld e,a
    ld d,0
    ld hl,Death_Sources
    add hl,de
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    scf
    ret
.outside:
    or a
    ret

; Service effect/restore work before guard tiles, using the same total budget B.
Death_Stream:
    ld a,(Death_Jobs)
    or a
    ret z
    push bc
    ; Contact is discovered after this refresh's sprite/last-row preparation.
    ; Remove that presentation before painting the effect in the same refresh.
    call Player_Patch
    call Player_Draw
    IF ENEMY_RENDER
    IF FULL_GAME
    call Full_EnemyFrameRestart
    ELSE
    call Enemy_Prepare
    call Enemy_Draw
    ENDIF
    ENDIF
    pop bc
    IF INCREMENTAL_STAGE >= 6
    ld a,(Death_DisplayState)
    cp 1
    jp z,Death_StreamRows
    ENDIF
.next:
    ld a,9
    ld hl,Death_Jobs
    sub (hl)
    ld c,0
.row:
    cp 3
    jr c,.column
    sub 3
    inc c
    jr .row
.column:
    ld e,a
    ld a,(Death_X)
    add a,e
    ld (tile_x),a
    ld a,(Death_Y)
    add a,c
    ld (tile_y),a
    push bc
    call stage_tile
    pop bc
    ld hl,Death_Jobs
    dec (hl)
    dec b
    ret z
    ld a,(hl)
    or a
    jr nz,.next
    ret
    IF INCREMENTAL_STAGE >= 6
; Three adjacent atlas tiles can be copied in one 24x8 command. Paint the
; complete effect atomically; the old nine commands could reach its last row
; after that scanline had already been displayed. Split at the 256-pixel
; cache-page boundary, preserving the same world pixels and torus addressing.
Death_RowWidth EQU $c495
Death_StreamRows:
    ld a,9
    ld hl,Death_Jobs
    sub (hl)
    ld c,0
.row:
    cp 3
    jr c,.source
    sub 3
    inc c
    jr .row
.source:
    ld a,c
    add a,a
    add a,c
    add a,a
    ld e,a
    ld d,0
    ld hl,Death_Sources
    add hl,de
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    ld a,(Death_Y)
    add a,c
    ld (tile_y),a
    ld a,(Death_X)
    ld (tile_x),a
    and 31
    ld c,24
    cp 30
    jr c,.width
    neg
    add a,32
    add a,a
    add a,a
    add a,a
    ld c,a
.width:
    ld a,c
    ld (Death_RowWidth),a
    ld (stage_command+8),a
    push bc
    call stage_copy_destination
    pop bc
    ld a,(Death_RowWidth)
    cp 24
    jr z,.done
    push bc
    ld c,a
    ld a,(stage_command)
    add a,c
    ld (stage_command),a
    ld a,24
    sub c
    ld (stage_command+8),a
    ld a,c
    rrca
    rrca
    rrca
    ld c,a
    ld a,(tile_x)
    add a,c
    ld (tile_x),a
    call stage_copy_destination
    pop bc
.done:
    ld a,8
    ld (stage_command+8),a
    ld a,b
    sub 3
    jr nc,.remaining
    xor a
.remaining:
    ld b,a
    ld hl,Death_Jobs
    ld a,(hl)
    sub 3
    ld (hl),a
    jp nz,Death_StreamRows
    ret
    ENDIF
Death_Sources:
    INCBIN "death-sources.bin"
    ASSERT $-Death_Sources == 18
    ENDIF
