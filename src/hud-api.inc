; Public HUD contract. See docs/hud.md. All setters: DI, no VRAM writes.
; They preserve BC/DE/HL/IX/IY and alternate registers. AF is scratch.
; Stable state is separate from game RAM and the keyboard producer.

; HL -> HUD_DIGITS numeric digits, most significant first. Full-game storage
; retains eight digits while the renderer displays seven. C=1 on invalid input.
HUD_SetScore:
    push de
    ld de,hud_score_pending
    call hud_copy_number
    jr c,.done
    jr z,.done
    ld a,1
    ld (hud_score_dirty),a
.done:
    pop de
    ret
HUD_SetHiscore:
    push de
    ld de,hud_high_pending
    call hud_copy_number
    jr c,.done
    jr z,.done
    ld a,1
    ld (hud_high_dirty),a
.done:
    pop de
    ret
hud_copy_number:
    push bc
    push hl
    ld b,HUD_DIGITS
.validate:
    ld a,(hl)
    cp 10
    jr nc,.invalid
    inc hl
    djnz .validate
    pop hl
    push hl
    push de
    ld b,HUD_DIGITS
    ld c,0
.compare:
    ld a,(de)
    xor (hl)
    or c
    ld c,a
    inc hl
    inc de
    djnz .compare
    ld a,c
    pop de
    pop hl
    push hl
    push af
    ld bc,HUD_DIGITS
    ldir
    pop af
    pop hl
    pop bc
    or a
    ret
.invalid:
    pop hl
    pop bc
    scf
    ret

; A = remaining cars, 0..9. Invalid input is rejected without changing state.
HUD_SetLives:
    cp 10
    jr nc,hud_invalid
    ld (lives),a
    or a
    ret

; A = original gauge's whole fuel units. The native gauge clips at 54.
; Fractional fuel, depletion flags, smoke cost and bonus conversion stay in game logic.
HUD_SetFuel:
    IF HUD_ALERTS
    push af
    cp 6                    ; Original full tank is60 units; exactly10% stays yellow.
    ld a,YELLOW|$20
    jr nc,.color
    ld a,RED|$20
.color:
    ld (hud_fuel_color),a
    pop af
    cp 54
    jr c,.scale
    ld a,54
.scale:
    ENDIF
    push hl
    push de
    ld l,a
    ld h,0
    ld de,hud_fuel_scale
    add hl,de
    ld a,(hl)
    ld (hud_fuel_pixels),a
    pop de
    pop hl
    or a
    ret

; B/C = local radar anchor X/Y (2..46 / 2..56), preserving a native 2x2 dot.
HUD_SetPlayer:
    ld a,b
    cp 255
    jr nz,.visible
    ld (hud_player_x),a
    ld (hud_player_y),a
    or a
    ret
.visible:
    ld a,b
    cp 2
    jr c,hud_invalid
    cp 47
    jr nc,hud_invalid
    ld a,c
    cp 2
    jr c,hud_invalid
    cp 57
    jr nc,hud_invalid
    ld (hud_player_y),a
    ld a,b
    ld (hud_player_x),a
    or a
    ret
HUD_SetEnemy:
    ld a,b
    cp 255
    jr nz,.visible
    ld (hud_enemy_x),a
    ld (hud_enemy_y),a
    or a
    ret
.visible:
    ld a,b
    cp 2
    jr c,hud_invalid
    cp 47
    jr nc,hud_invalid
    ld a,c
    cp 2
    jr c,hud_invalid
    cp 57
    jr nc,hud_invalid
    ld (hud_enemy_y),a
    ld a,b
    ld (hud_enemy_x),a
    or a
    ret
hud_invalid:
    scf
    ret

; A = numeric-content cadence, 2, 3 or 4 refreshes.
HUD_SetCadence:
    cp 2
    jr c,hud_invalid
    cp 5
    jr nc,hud_invalid
    ld (cadence),a
    or a
    ret
hud_fuel_scale:
    INCBIN "hud-fuel-scale.bin"

; Private neutral-state reset, called by HUD_Init after resource uploads.
HUD_InitState:
    IF FULL_GAME
    ld hl,hud_score_pending
    ld de,hud_score_pending+1
    ld bc,31
    ld (hl),0
    ldir
    ENDIF
    ld hl,HUD_API_BASE
    ld de,HUD_API_BASE+1
    ld bc,37
    ld (hl),0
    ldir
    xor a
    ld (lives),a
    ld (radar_clock),a
    ld (hud_fuel_pixels),a
    ld (hud_fuel_drawn),a
    IF HUD_ALERTS
    ld a,YELLOW|$20
    ld (hud_fuel_color),a
    ld (hud_fuel_color_drawn),a
    xor a
    ld (hud_fuel_ready),a
    ld (hud_fuel_queued),a
    ENDIF
    ld hl,hud_flags
    ld b,40
    ld a,255
.hide:
    ld (hl),a
    inc hl
    djnz .hide
    xor a
    ld (hud_flags_dirty),a
    ld (hud_flags_dirty+1),a
    ld (hud_force),a
    ld (hud_scan_cell),a
    ld a,2
    ld (cadence),a
    ld a,(cadence)
    ld b,a
    ld a,(ticks)
    sub b
    ld (hud_score_at),a
    ld (hud_high_at),a
    ld (fuel_at),a
    ld a,255
    ld (hud_player_x),a
    ld (hud_player_y),a
    ld a,255
    ld (hud_enemy_x),a
    ld (hud_enemy_y),a
    ld a,255
    ld (hud_enemy_drawn_x),a
    ld (hud_enemy_drawn_y),a
    ld (point_x),a
    ld (point_y),a
    ld (enemy_x),a
    ld (enemy_y),a
    ld (point_color),a
    ld (life_drawn),a
    ld a,1
    ld (hud_player_number),a
    ld (hud_player_number_drawn),a
    ret

; A=flag slot 0..9, B/C=local 2x2 anchor. B=255 hides a collected flag.
; Updates only affected matrix cells; flag ownership/collection stays in game logic.
HUD_SetFlag:
    cp 10
    jp nc,hud_flag_invalid
HUD_SetRadarPoint:
    cp 20
    jr nc,hud_flag_invalid
    ld (hud_flag_id),a
    ld a,b
    cp 255
    jr z,.valid
    cp 2
    jr c,hud_flag_invalid
    cp 47
    jr nc,hud_flag_invalid
    ld a,c
    cp 2
    jr c,hud_flag_invalid
    cp 57
    jr nc,hud_flag_invalid
.valid:
    push bc
    push de
    push hl
    ld a,(hud_flag_id)
    add a,a
    ld l,a
    ld h,0
    ld de,hud_flags
    add hl,de
    ld a,b
    cp (hl)
    jr nz,.change
    inc hl
    ld a,c
    cp (hl)
    jr z,.done
    dec hl
.change:
    push hl
    push bc
    ld b,(hl)
    inc hl
    ld c,(hl)
    call hud_mark_flag
    pop bc
    pop hl
    ld (hl),b
    inc hl
    ld (hl),c
    call hud_mark_flag
.done:
    pop hl
    pop de
    pop bc
    or a
    ret
hud_flag_invalid:
    scf
    ret
hud_mark_flag:
    ld a,b
    cp 255
    ret z
    call hud_mark_pixel
    inc b
    call hud_mark_pixel
    inc c
    call hud_mark_pixel
    dec b
    jp hud_mark_pixel
hud_mark_pixel:
    push bc
    ld a,b
    rrca
    rrca
    rrca
    rrca
    and 3
    ld e,a
    ld a,c
    sub e
    add a,2
    ld d,0
.band:
    cp 15
    jr c,.index
    sub 15
    inc d
    jr .band
.index:
    ld a,d
    add a,a
    add a,d
    add a,e
    ld b,a
    ld hl,1
    or a
    jr z,.mask
.shift:
    add hl,hl
    djnz .shift
.mask:
    ld de,(hud_flags_dirty)
    ld a,l
    or e
    ld l,a
    ld a,h
    or d
    ld h,a
    ld (hud_flags_dirty),hl
    pop bc
    ret

; Scheduled after the header split. Two dirty cells per frame bound VRAM work.
HUD_FlushFlags:
    IF FULL_GAME
    call Radar_AllowIRQ
    ENDIF
    IF RADAR_BLITTER
    xor a
    ld (hud_flags_dirty),a
    ld (hud_flags_dirty+1),a
    ret
    ENDIF
    IF RADAR_CELLS_ONLY
    IF !FULL_GAME
    ld a,(Radar_Initializing)
    or a
    jr nz,.cell_budget
    ld a,(paused)
    or a
    jr nz,.cell_budget
    ld a,(player_steps)
    cp 2
    ret z
.cell_budget:
    ENDIF
    ld b,1                  ; Bound flag-base composition as well as marker work.
    ELSE
    ld b,2
    ENDIF
.cell:
    push bc
    ld hl,(hud_flags_dirty)
    ld a,h
    or l
    jr z,.done
    ld a,(hud_scan_cell)
    ld c,a
.find:
    ld hl,1
    ld b,c
    ld a,b
    or a
    jr z,.test
.shift_mask:
    add hl,hl
    djnz .shift_mask
.test:
    ld de,(hud_flags_dirty)
    ld a,l
    and e
    ld b,a
    ld a,h
    and d
    or b
    jr nz,.found
    inc c
    ld a,c
    cp 12
    jr c,.find
    ld c,0
    jr .find
.found:
    IFDEF HUD_COLLECTION_METER
    push hl
    ld hl,Flag_HudWork
    inc (hl)
    pop hl
    ENDIF
    ld a,c
    ld (hud_cell),a
    inc a
    cp 12
    jr c,.cursor
    xor a
.cursor:
    ld (hud_scan_cell),a
.clear:
    ld a,l
    cpl
    ld e,a
    ld a,h
    cpl
    ld d,a
    ld hl,(hud_flags_dirty)
    ld a,l
    and e
    ld l,a
    ld a,h
    and d
    ld h,a
    ld (hud_flags_dirty),hl
    call hud_render_cell
    pop bc
    djnz .cell
    ret
.done:
    pop bc
    ret

hud_render_cell:
    IF FULL_GAME
    call Radar_AllowIRQ       ; Dynamic flag composition is RAM work.
    ENDIF
    IF RADAR_CELLS_ONLY && !FULL_GAME
    jp Radar_RebuildBase
    ENDIF
    ld a,HUD_DATA_BANK
    ld ($7000),a
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$9000
    add hl,de
    ld de,point_buffer
    ld bc,32
    ldir
    ld a,(hud_cell)
    ld d,0
.divide:
    cp 3
    jr c,.origin
    sub 3
    inc d
    jr .divide
.origin:
    ld e,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld (hud_cell_x),a
    ld a,d
    add a,a
    add a,a
    add a,a
    add a,a
    sub d
    add a,e
    sub 2
    ld (hud_cell_y),a
    ld hl,hud_flags
    IF FULL_GAME
    ld b,10
    ELSE
    ld b,20
    ENDIF
.flag:
    push bc
    ld a,(hl)
    inc hl
    ld c,(hl)
    inc hl
    push hl
    cp 255
    jr z,.next_flag
    IF FULL_GAME
    ld d,a
    ld a,b
    cp 1
    jr nz,.visible_flag
    ld hl,radar_clock
    bit 5,(hl)
    jr nz,.next_flag
.visible_flag:
    ld a,d
    ENDIF
    ld (hud_pixel_x),a
    ld a,c
    ld (hud_pixel_y),a
    call hud_plot_cell_pixel
    ld hl,hud_pixel_x
    inc (hl)
    call hud_plot_cell_pixel
    ld hl,hud_pixel_y
    inc (hl)
    call hud_plot_cell_pixel
    ld hl,hud_pixel_x
    dec (hl)
    call hud_plot_cell_pixel
.next_flag:
    pop hl
    pop bc
    djnz .flag
    IF RADAR_CELLS_ONLY
    call Radar_CacheCell
    IF FULL_GAME
    ld a,(hud_cell)
    ld (Radar_PublishCursor),a ; Collection/blink changes precede ordinary markers.
    call Radar_CellBit
    ld hl,(Radar_Urgent)
    ld a,e
    or l
    ld l,a
    ld a,d
    or h
    ld h,a
    ld (Radar_Urgent),hl
    ENDIF
    jp Radar_RenderCell
    ELSE
    ; Shift both 16-row halves by one row for sentinel avoidance.
    ld hl,point_buffer
    ld de,point_buffer+32
    ld b,2
.half:
    xor a
    ld (de),a
    inc de
    ld c,15
.copy:
    ld a,(hl)
    ld (de),a
    inc hl
    inc de
    dec c
    jr nz,.copy
    inc hl
    djnz .half
    vdp_write 14,7
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$38a0
    add hl,de
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ld hl,point_buffer
    ld bc,$2098
    otir
    ; Shifted phase is twelve patterns (384 bytes) later.
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$3a20
    add hl,de
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ld hl,point_buffer+32
    ld bc,$2098
    otir
    ret
    ENDIF
hud_plot_cell_pixel:
    ld a,(hud_cell_x)
    ld e,a
    ld a,(hud_pixel_x)
    sub e
    cp 16
    ret nc
    ld c,a
    ld a,(hud_cell_y)
    ld e,a
    ld a,(hud_pixel_y)
    sub e
    cp 15
    ret nc
    ld e,a
    ld a,c
    and 8
    add a,a
    add a,e
    ld e,a
    ld d,0
    ld hl,point_buffer
    add hl,de
    ld a,c
    and 7
    ld c,a
    ld a,$80
    jr z,.paint
.shift:
    rrca
    dec c
    jr nz,.shift
.paint:
    or (hl)
    ld (hl),a
    ret


; A=0 scheduled updates, A=1 force queued content while the game is paused.
HUD_SetForce:
    and 1
    ld (hud_force),a
    ret
HUD_Tick:
    push hl
    ld hl,radar_clock
    inc (hl)
    IF HUD_ALERTS
    ld a,(hl)
    and 31
    jr nz,.done
    push bc
    push de
    ld bc,(hud_flags+RADAR_SPECIAL_FLAG_OFFSET)
    ld a,b
    ld b,c
    ld c,a
    call hud_mark_flag       ; Only dirty the S flag's existing radar cells.
    pop de
    pop bc
.done:
    ENDIF
    pop hl
    ret

; Renderer-owned phases. These clobber AF/BC/DE/HL/IX; preserve IY and AF'/BC'/DE'/HL'.
HUD_PrepareFrame:
    IFDEF HUD_FUEL_METER
    IF !PLAYER_FAST_BLITTER
    xor a
    ld (Fuel_HudWork),a
    ENDIF
    ENDIF
    IF RADAR_CELLS_ONLY
    IF STAGE_TILE_STRIPS && !SMOKE_RUNTIME
    ; Ordinary marker payloads are produced after terrain's raster deadline.
    ; Blank-screen initialization still drains every cell before unblanking.
    ld a,(Radar_Initializing)
    or a
    jr nz,.initial_markers
    call Radar_UpdatePoints
    call Radar_TailBudget
    jp update_fuel
.initial_markers:
    call Radar_Prepare
    ELSE
    call Radar_Prepare
    ENDIF
    IF PLAYER_FAST_BLITTER
    ld a,(Radar_Initializing)
    or a
    ret z                   ; Ordinary fuel publication precedes the bitmap car.
    ENDIF
    jp update_fuel
    ELSE
    call update_radar
    ENDIF
    call update_fuel
    IF INCREMENTAL_STAGE >= 9
    ei                      ; Remaining HUD work only prepares canonical RAM.
    nop
    ENDIF
    call update_fuel_sat
    call update_life_sat
    jp update_lives
    IF RADAR_CELLS_ONLY
; Publish fixed-screen coordinates before any actor-pattern uploads. The first
; radar band has a much earlier fetch deadline than the centered player.
HUD_PrepareCoordinates:
    jp Radar_Coordinates
HUD_PrepareEarlyCoordinates:
    jp Radar_EarlyCoordinates
HUD_FinishCoordinates:
    jp Radar_FinishCoordinates
    ENDIF
HUD_DrawContent:
    IF FULL_GAME
    call Radar_AllowIRQ
    ENDIF
    IFDEF HUD_SCORING_METER
    xor a
    ld (Score_HudPairs),a
    ENDIF
    IFDEF HUD_COLLECTION_METER
    xor a
    ld (Flag_HudWork),a
    ENDIF
    call hud_draw_player_number
    call update_life_digit
    IF RADAR_CELLS_ONLY
    call HUD_ContentWindow
    ret c
    ENDIF
    call HUD_FlushNumbers
    IF RADAR_CELLS_ONLY
    call HUD_ContentWindow
    ret c
    ENDIF
    IF FULL_GAME
    ret
    ELSE
    jp HUD_FlushFlags
    ENDIF

    IF RADAR_CELLS_ONLY
HUD_ContentWindow:
    call Radar_AllowIRQ
    di                      ; Observe any pending close IRQ before spending work.
    ld a,(Radar_Initializing)
    or a
    jr nz,.ready
    ld a,(raster_phase)
    IF FULL_GAME
    cp 1
    jr z,.ready
    ELSE
    cp 3
    jr z,.ready
    cp 4
    jr z,.ready
    ENDIF
    scf
    ret
.ready:
    or a
    ret
    ENDIF


; B/C = arcade-local radar coordinates (0..63, 0..111); B=255 hides.
; These wrappers preserve BC/DE/HL/IX/IY; normalized coordinates stay private.
HUD_SetNativePlayer:
    push bc
    push de
    push hl
    call hud_project_native
    call nc,HUD_SetPlayer
    jr hud_native_point_return
HUD_SetNativeEnemy:
    push bc
    push de
    push hl
    call hud_project_native
    call nc,HUD_SetEnemy
    jr hud_native_point_return
HUD_SetNativePoint:
    ld (hud_flag_id),a
    push bc
    push de
    push hl
    call hud_project_native
    jr c,hud_native_point_return
    ld a,(hud_flag_id)
    call HUD_SetRadarPoint
hud_native_point_return:
    pop hl
    pop de
    pop bc
    ret
hud_project_native:
    ld a,b
    cp 255
    jr z,.hidden
    cp 64
    jp nc,hud_invalid
    ld a,c
    cp 112
    jp nc,hud_invalid
    ld l,b
    ld h,0
    ld de,hud_project_x
    add hl,de
    ld b,(hl)
    ld l,c
    ld h,0
    ld de,hud_project_y
    add hl,de
    ld c,(hl)
.hidden:
    or a
    ret
hud_project_x:
    INCBIN "hud-project-x.bin"
hud_project_y:
    INCBIN "hud-project-y.bin"


; Blank-display preparation: publish a complete initial state before unblanking.
; This may drain all twelve dirty radar cells; do not call it every game frame.
HUD_Prime:
    ld a,(hud_force)
    push af
    ld a,1
    ld (hud_force),a
    IF RADAR_CELLS_ONLY
    call HUD_PrepareCoordinates
    ENDIF
    call HUD_PrepareFrame
.drain:
    IF FULL_GAME
    call HUD_FlushFlags
    ENDIF
    call HUD_DrawContent
    ld hl,(hud_flags_dirty)
    ld a,h
    or l
    ld b,a
    ld a,(hud_score_dirty)
    or b
    ld b,a
    ld a,(hud_high_dirty)
    or b
    jr nz,.drain
    IF RADAR_CELLS_ONLY
    call Radar_PublishReady
    xor a
    ld (Radar_Initializing),a
    ENDIF
    pop af
    ld (hud_force),a
    ret


; A=1 or 2, selected by the original turn/player logic. Only the label glyph changes.
HUD_SetPlayerNumber:
    cp 1
    jp c,hud_invalid
    cp 3
    jp nc,hud_invalid
    ld (hud_player_number),a
    or a
    ret
hud_draw_player_number:
    ld a,(hud_player_number)
    ld b,a
    ld a,(hud_player_number_drawn)
    cp b
    ret z
    ld a,b
    ld (hud_player_number_drawn),a
    dec a
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$9300
    add hl,de
    ld a,HUD_DATA_BANK
    ld ($7000),a
    IF !FULL_GAME
    vdp_write 14,4
    ENDIF
    ld de,PLAYER_LABEL_X/2
    ld a,8
.row:
    push af
    IF FULL_GAME
    ei
    nop
    di
    vdp_write 14,4            ; The radar ISR may have changed R14 between glyph rows.
    ENDIF
    ld a,e
    out ($99),a
    ld a,d
    or $40
    out ($99),a
    ld bc,$0498
    otir
    ld a,e
    add a,128
    ld e,a
    jr nc,.next
    inc d
.next:
    pop af
    dec a
    jr nz,.row
    ret
