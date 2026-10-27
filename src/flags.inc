; Stage 04: immutable original flag order + persistent collected state.
; No score, fuel reward or level transition is executed at this stage.
    IF INCREMENTAL_STAGE >= 4
Flag_Active EQU $c500           ; zero sentinel then ten active bytes; page aligned
Flag_Count EQU $c50b
Flag_Last EQU $c50c             ; original slot+1
Flag_Kind EQU $c50d
Flag_Jobs EQU $c50e
Flag_X EQU $c50f
Flag_Y EQU $c510
Flag_HudWork EQU $c511
Flag_HudPending EQU $c512
Flag_Cells EQU $c520            ; original compact two-byte address scan
    IF PLAYER_FAST_BLITTER || SMOKE_RUNTIME
Flag_DisplayActive EQU $c534
Flag_Frame:
    ld hl,Flag_Active
    ld de,Flag_DisplayActive
    ld bc,11
    ldir
    ret
    ENDIF
Flag_Init:
    xor a
    ld (Flag_Active),a
    IF ENEMY_COUNT
    ld (Flag_HudPending),a
    ENDIF
    ld hl,Flag_Active+1
    ld b,10
.active:
    ld (hl),1
    inc hl
    djnz .active
    ld b,7
.clear:
    ld (hl),a
    inc hl
    djnz .clear
    IF PLAYER_FAST_BLITTER || SMOKE_RUNTIME
    call Flag_Frame
    ENDIF
    ld hl,Flag_Records
    ld de,Flag_Cells
    ld b,10
.cell:
    push bc
    ldi
    ldi
    ld bc,4
    add hl,bc
    pop bc
    djnz .cell
    ret
Flag_Update:
    ld de,(Rock_ProbeCell)      ; original geometry already ran this logical tick
    ld hl,Flag_Cells
    ld b,10
.next:
    ld a,e
    cp (hl)
    inc hl
    jr nz,.miss
    ld a,d
    cp (hl)
.miss:
    inc hl
    jr z,.found
    djnz .next
    ret
.found:
    dec hl
    ld (hl),0
    dec hl
    ld (hl),0
    ld a,11
    sub b
    ld c,a
    ld h,Flag_Active/256
    ld l,c
    ld (hl),0
    ld a,c
    ld (Flag_Last),a
    dec a
    ld l,a
    ld h,0
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,Flag_Records
    add hl,de
    ld a,(Flag_Count)
    inc a
    ld (Flag_Count),a
    inc hl
    inc hl
    ld a,(hl)
    ld (Flag_Kind),a
    inc hl
    push hl
    inc hl
    ld a,(hl)
    ld (Flag_X),a
    inc hl
    ld a,(hl)
    ld (Flag_Y),a
    ld a,9
    ld (Flag_Jobs),a
    IF SMOKE_RUNTIME
    call Smoke_CollectedFlag
    ENDIF
    pop hl
    IF HUD_ENABLED
    ld a,(hl)                 ; HUD uses its established row-major flag slots
    IF ENEMY_COUNT
    inc a
    ld (Flag_HudPending),a
    ret
    ELSE
    ld b,255
    ld c,255
    jp HUD_SetFlag
    ENDIF
    ELSE
    ret
    ENDIF

    IF ENEMY_COUNT
Flag_PublishHUD:
    IF FULL_GAME
    ei
    nop
    ENDIF
    IF HUD_ENABLED
    ld a,(Flag_HudPending)
    or a
    ret z
    dec a
    push af
    xor a
    ld (Flag_HudPending),a
    pop af
    ld bc,$ffff
    jp HUD_SetFlag
    ELSE
    ret
    ENDIF
    ENDIF

; Entered only for marked flag tiles. Preserve exact source coordinates while
; active; substitute the original empty-path tile after collection.
Flag_Source:
    and $fe
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld c,a
    rrca
    rrca
    rrca
    rrca
    and 15
    IF PLAYER_FAST_BLITTER || SMOKE_RUNTIME
    add a,Flag_DisplayActive&255
    ENDIF
    ld l,a
    ld h,Flag_Active/256
    ld a,(hl)
    or a
    jr z,.empty
    ld a,c
    and 15
    or 16
    ld (stage_command+2),a
    jp stage_copy_destination
.empty:
    ld a,FLAG_EMPTY_X
    ld (stage_command),a
    ld a,FLAG_EMPTY_Y
    ld (stage_command+2),a
    jp stage_copy_destination

Flag_Stream:
    ld a,(Flag_Jobs)
    or a
    ret z
    IF PLAYER_FAST_BLITTER || SMOKE_RUNTIME
    ld a,(Flag_Last)
    add a,Flag_DisplayActive&255
    ld l,a
    ld h,Flag_DisplayActive/256
    ld a,(hl)
    or a
    ret nz                  ; Publish collection with the next display snapshot.
    ENDIF
    push bc
    IF PLAYER_FAST_BLITTER
    call Bitmap_Restore     ; Saved terrain must precede collection publication.
    ELSE
    ; Remove the optional car row before replacing its underlying terrain. Its
    ; saved bytes may still contain the flag and must not be restored afterwards.
    ld a,(player_patch_valid)
    or a
    jr z,.unpatched
    ld hl,player_patch_saved
    call Player_WriteRow
    xor a
    ld (player_patch_valid),a
.unpatched:
    ENDIF
    pop bc
    IF ENEMY_RENDER
    jp Flag_StreamRows
    ENDIF
.next:
    ld a,9
    ld hl,Flag_Jobs
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
    ld a,(Flag_X)
    add a,e
    ld (tile_x),a
    ld a,(Flag_Y)
    add a,c
    ld (tile_y),a
    push bc
    call stage_tile
    pop bc
    ld hl,Flag_Jobs
    dec (hl)
    dec b
    ret z
    ld a,(hl)
    or a
    jr nz,.next
    ; Reapply the optional last car row after all dirty terrain jobs. The caller
    ; reserves six jobs for any patch work, including this collection refresh.
    push bc
    IF !PLAYER_FAST_BLITTER
    call Player_Patch
    ENDIF
    pop bc
    ret
    IF ENEMY_RENDER
Flag_RowWidth EQU $c513
Flag_StreamRows:
    IF SESSION_RUNTIME
    ei                      ; RAM brush preparation must not delay the header split.
    nop
    ENDIF
    ld a,9
    ld hl,Flag_Jobs
    sub (hl)
    ld c,0
.row:
    cp 3
    jr c,.source
    sub 3
    inc c
    jr .row
.source:
    ld a,FLAG_ROW_X
    ld (stage_command),a
    ld a,FLAG_ROW_Y
    ld (stage_command+2),a
    ld a,(Flag_Y)
    add a,c
    ld (tile_y),a
    ld a,(Flag_X)
    ld (tile_x),a
    IF SMOKE_RUNTIME
    call Smoke_ClearPublishedRow
    ENDIF
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
    ld (Flag_RowWidth),a
    ld (stage_command+8),a
    push bc
    call stage_copy_destination
    pop bc
    ld a,(Flag_RowWidth)
    cp 24
    jr z,.done
    push bc
    ld c,a
    ld a,FLAG_ROW_X
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
    ld hl,Flag_Jobs
    ld a,(hl)
    sub 3
    ld (hl),a
    jp nz,Flag_StreamRows
    push bc
    IF !PLAYER_FAST_BLITTER
    call Player_Patch
    ENDIF
    pop bc
    ret
    ENDIF
    IF FULL_GAME
Flag_Records EQU $df80
    ELSE
Flag_Records:
    INCBIN "flag-records.bin"
    ASSERT $-Flag_Records == 60
    ENDIF
    ENDIF
