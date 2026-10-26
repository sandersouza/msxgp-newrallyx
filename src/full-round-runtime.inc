Full_IDBank EQU $dfbc
Full_ResourceBank EQU $dfbd
Full_HBank EQU $dfbe
Full_VBank EQU $dfbf
Full_HBytes EQU $dfc0
Full_VBytes EQU $dfc2
Full_VOffset EQU $dfc4
Full_Div3Address EQU $dfc6
Full_Loading EQU $dfc8
Full_Layout EQU $dfc9
Full_Transitions EQU $dfca
Full_RadarFlags EQU $dfd0
Full_WideHBank EQU $d2d8
Full_WideVBank EQU $d2d9
Full_WideHData EQU $d2da
Full_WideVData EQU $d2db
Full_WideHBytes EQU $d2dc
Full_WideVBytes EQU $d2de
    INCLUDE "full-terrain-cache.inc"

Full_CopyCold:
    ld a,PLAYER_BANK
    ld ($7000),a
    call Full_CopyColdNative
Full_CopyPresentation:
    ld a,FULL_TERRAIN_BANK
    ld ($7000),a
    ld hl,$9000
    ld de,Full_PresentStart
    ld bc,Full_PresentEnd-Full_PresentStart
    ldir
    ret

Full_NextRound:
    ld a,4
    ld (Session_State),a
    ld a,1
    ld (Full_Loading),a
    ld hl,Full_Transitions
    inc (hl)
    call show_scene
    xor a
    ld (Session_State),a
    ld (Session_Drawn),a
    ld a,(ticks)
    ld (frame_tick),a
    ret

; E300..E3EF is renderer scratch in the selected-routine build. The original
; bitmap HUD writers are excluded; E3F0 remains the native input byte.
Full_Div3:
    ld l,a
    ld h,$e3
    ld a,(hl)
    ret

; B/C=global tile X/Y. All input registers except AF survive; no bank change.
Full_ObjectAtTile:
    push iy
    call Full_CacheEnter
    call Full_ObjectAtTileNative
    push af
    call Full_CacheLeave
    pop af
    pop iy
    ret

; The radar IRQ leaves its SAT pointer at fuel slot13. Restore fuel and the
; complete player pair against the same R23, every physical refresh. Foreground
; pattern preparation must not publish a player Y from a newer camera plan.
Full_FuelIRQ:
    ld a,(irq_scroll_y)
    call update_fuel_sat_value
    ld hl,fuel_sat
    ld bc,$0c98
    otir
    ld a,(Death_DisplayState)
    or a
    jr nz,.hidden
    ld a,(irq_scroll_y)
    call Player_Draw.sat_value
    jr .player
.hidden:
    ld a,(irq_scroll_y)
    add a,211
    cp 216
    jr nz,.hidden_y
    inc a
.hidden_y:
    ld (player_sat),a
    ld (player_sat+4),a
.player:
    ld hl,player_sat
    ld bc,$0898
    otir
    ; Fuel is fetched at line82. Restore its colors/gauge after the radar
    ; attributes, leaving the VBlank transaction room for complete car masks.
    HUD_VBlankSprites
    ret

Full_TileSource:
    ld a,(tile_x)
    ld b,a
    ld a,(tile_y)
    ld c,a
    call Full_ObjectAtTile
    or a
    ret z
    cp 15
    jr z,.rock
    ld e,a
    ld d,0
    ld hl,Flag_DisplayActive
    add hl,de
    ld a,(hl)
    or a
    jr z,.empty
    ld a,e
    cp 9
    ld a,0
    jr c,.kind
    ld a,e
    cp 9
    ld a,27
    jr z,.kind
    ld a,9
    jr .kind
.rock:
    ld a,18
.kind:
    push af
    ld h,0
    ld l,c
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    ld e,a
    add a,a
    add a,e
    ld e,a
    ld a,b
    ld l,a
    ld h,0
    ld bc,stage_flower_phase
    add hl,bc
    ld a,(hl)
    add a,e
    ld e,a
    pop af
    add a,e
    add a,a
    ld l,a
    ld h,0
    ld de,Full_ObjectSources
    add hl,de
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    scf
    ret
.empty:
    ld a,FLAG_ROW_X
    ld (stage_command),a
    ld a,FLAG_ROW_Y
    ld (stage_command+2),a
    scf
    ret

Full_RestoreFlagCells:
    ld ix,Flag_Records
    ld hl,Flag_Cells
    ld de,Flag_Active+1
    ld b,10
.next:
    ld a,(de)
    or a
    ld a,0
    jr z,.cell
    ld a,(ix+0)
.cell:
    ld (hl),a
    inc hl
    ld a,(de)
    or a
    ld a,0
    jr z,.high
    ld a,(ix+1)
.high:
    ld (hl),a
    inc hl
    inc de
    push de
    ld de,6
    add ix,de
    pop de
    djnz .next
    ret
