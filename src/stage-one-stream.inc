; Full first-stage map, 512x256 pixel ring and bounded one-pixel camera.
; Tile ROM stride: 512 bytes per scanline, four tile rows per ASCII16 bank.
world_x EQU $c0b0
world_y EQU $c0b2
previous_x EQU $c0b4
previous_y EQU $c0b5
column_left EQU $c0b6
row_left EQU $c0b7
column_x EQU $c0b8
column_y EQU $c0b9
row_y EQU $c0ba
row_x EQU $c0bb
tile_x EQU $c0bc
tile_y EQU $c0bd
camera_page EQU $c0be
tile_vram_bank EQU $c455
cache_left EQU $c46f
cache_top EQU $c470
    IF FULL_GAME
Stage_PreferRows EQU $c679
    ELSE
Stage_PreferRows EQU $c5e9
    ENDIF
Stage_ColumnTop EQU $cf1a
Stage_ColumnEnd EQU $cf1b
Stage_RowLeft EQU $cf1c
Stage_RowEnd EQU $cf1d
Stage_RowBatch EQU $cf26
Stage_RunLength EQU $cf27

stage_move:
    ld hl,(world_x)
    ld de,STAGE_WIDTH-VIEWPORT_WIDTH
    ld a,(dx)
    call stage_axis
    ld (world_x),hl
    ld hl,(world_y)
    ld de,STAGE_HEIGHT-201
    ld a,(dy)
    call stage_axis
    ld (world_y),hl
    jp HUD_Tick
stage_axis:
    or a
    ret z
    inc a
    jr z,.negative
    or a
    sbc hl,de
    add hl,de
    ret nc
    inc hl
    ret
.negative:
    ld a,h
    or l
    ret z
    dec hl
    ret

stage_position:
    ld a,(driving)
    or a
    call nz,stage_cache_bounds
    IF INCREMENTAL_STAGE >= 9 && !FULL_GAME
    ; Columns and rows must own the same 32-row window, even while a row job
    ; lags a short camera reversal. Otherwise a column can erase a ring row
    ; which previous_y still considers valid and never queues for repair.
    ld a,(previous_y)
    sub STAGE_CACHE_TOP_GUARD
    ld (cache_top),a
    IF ENEMY_COUNT >= 2 || SMOKE_RUNTIME
    ld a,(previous_x)
    sub STAGE_CACHE_GUARD
    ld (cache_left),a
    ENDIF
    ENDIF
    IF SESSION_RUNTIME
    di                      ; Only the actual scroll snapshot needs atomicity.
    ENDIF
    ld hl,(world_x)
    ld de,-8
    add hl,de
    ld a,l
    ld (camera_x),a
    neg
    and 7
    ld (scroll_low),a
    ld a,h
    and 1
    add a,a
    ld (camera_page),a
    ld de,7
    add hl,de
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l
    and 63
    ld (scroll_high),a
    ld hl,(world_y)
    ld a,l
    ld (camera_y),a
    sub BODY_TOP
    ld (scroll_y),a
    IF SESSION_RUNTIME
    ld a,(Session_PositionIRQ)
    or a
    jr z,.position_atomic
    ei
    nop
.position_atomic:
    ENDIF
    ; Cache shifts are queued once per tile; jobs write only hidden guard tiles.
    IF FULL_GAME
    jp Full_StageQueue
    ELSE
    ld a,(column_left)
    or a
    jr nz,.vertical
    ld hl,(world_x)
    call stage_div8
    ld a,(previous_x)
    cp l
    jr z,.vertical
    ld b,a
    ld a,l
    sub b
    bit 7,a
    ld a,b
    jr nz,.left
    inc a
    ld (previous_x),a
    IF INCREMENTAL_STAGE >= 9 && (ENEMY_COUNT >= 2 || SMOKE_RUNTIME)
    push af
    sub STAGE_CACHE_GUARD
    ld (cache_left),a
    pop af
    ENDIF
    add a,STAGE_CACHE_COLUMNS-STAGE_CACHE_GUARD-1
    jr .column
.left:
    dec a
    ld (previous_x),a
    sub STAGE_CACHE_GUARD
    IF INCREMENTAL_STAGE >= 9 && (ENEMY_COUNT >= 2 || SMOKE_RUNTIME)
    ld (cache_left),a
    ENDIF
.column:
    ld (column_x),a
    IF INCREMENTAL_STAGE >= 9
    ld a,(previous_y)
    sub STAGE_CACHE_TOP_GUARD
    ld (Stage_ColumnTop),a
    add a,32
    ld (Stage_ColumnEnd),a
    ld hl,(world_y)
    call stage_div8
    ld a,l
    ld (column_y),a          ; Start at the actual visible row during reversals.
    ELSE
    ld hl,(world_y)
    call stage_div8
    ld a,l
    sub STAGE_CACHE_TOP_GUARD
    ld (column_y),a
    ENDIF
    ld a,32
    ld (column_left),a
.vertical:
    ld a,(row_left)
    or a
    ret nz
    ld hl,(world_y)
    call stage_div8
    ld a,(previous_y)
    cp l
    ret z
    ld b,a
    ld a,l
    sub b
    bit 7,a
    ld a,b
    jr nz,.up
    inc a
    ld (previous_y),a
    IF INCREMENTAL_STAGE >= 9
    push af
    sub STAGE_CACHE_TOP_GUARD
    ld (cache_top),a
    pop af
    ENDIF
    add a,32-STAGE_CACHE_TOP_GUARD-1
    jr .row
.up:
    dec a
    ld (previous_y),a
    IF INCREMENTAL_STAGE >= 9
    push af
    sub STAGE_CACHE_TOP_GUARD
    ld (cache_top),a
    pop af
    ENDIF
    sub STAGE_CACHE_TOP_GUARD
.row:
    ld (row_y),a
    ld hl,(world_x)
    call stage_div8
    ld a,l
    IF INCREMENTAL_STAGE >= 9
    ld (row_x),a             ; Queue visible columns before the left guard.
    IF ENEMY_COUNT >= 2 || SMOKE_RUNTIME
    ld a,(previous_x)
    ENDIF
    sub STAGE_CACHE_GUARD
    ld (Stage_RowLeft),a
    add a,STAGE_CACHE_COLUMNS
    ld (Stage_RowEnd),a
    ELSE
    sub STAGE_CACHE_GUARD
    ld (row_x),a
    ENDIF
    ld a,STAGE_CACHE_COLUMNS
    ld (row_left),a
    ret
    ENDIF
stage_div8:
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ret

stage_stream:
    ld a,(driving)
    or a
    jr nz,stage_stream_driving
    ld b,4
.column:
    ld a,(column_left)
    or a
    jr z,.rows
    dec a
    ld (column_left),a
    ld a,(column_x)
    ld (tile_x),a
    ld a,(column_y)
    ld (tile_y),a
    inc a
    IF INCREMENTAL_STAGE >= 9
    ld hl,Stage_ColumnEnd
    cp (hl)
    jr nz,.column_cursor
    ld a,(Stage_ColumnTop)
.column_cursor:
    ENDIF
    ld (column_y),a
    push bc
    call stage_tile
    pop bc
    djnz .column
.rows:
    ld b,8
.row:
    ld a,(row_left)
    or a
    ret z
    dec a
    ld (row_left),a
    ld a,(row_x)
    ld (tile_x),a
    inc a
    IF INCREMENTAL_STAGE >= 9
    ld hl,Stage_RowEnd
    cp (hl)
    jr nz,.row_cursor
    ld a,(Stage_RowLeft)
.row_cursor:
    ENDIF
    ld (row_x),a
    ld a,(row_y)
    ld (tile_y),a
    push bc
    call stage_tile
    pop bc
    djnz .row
    ret

; Persistent, bounded guard jobs. Both axes use exact atlas copies in driving
; mode; the VDP handles pixel transfer while the CPU prepares the next tile.
stage_stream_driving:
    IF INCREMENTAL_STAGE >= 9
    call Stage_QueuePriority
    ENDIF
    IF RASTER_GUARD
    IF FULL_GAME
    ld b,1                   ; Keep ordinary prefetch within one presentation frame.
    ld a,(Full_CameraBlocked)
    or a
    jp z,.effect_budget
    ld b,8                   ; Finish an urgent edge instead of repeating holds.
    jp .effect_budget
    ELSE
    ld b,64                  ; real raster deadline bounds invisible prefetch
    jp .effect_budget
    ENDIF
    ENDIF
    IF INCREMENTAL_STAGE >= 4
    ld b,20
    ELSE
    ld b,22
    ENDIF
    ld a,(player_steps)
    cp 2
    jr nz,.patch_budget
    ld b,16
.patch_budget:
    IF INCREMENTAL_STAGE >= 6
    dec b                    ; recurring bounded fuel adapter/publication
    ld a,(Fuel_ConsumeWork)
    or a
    jr z,.fuel_hud_budget
    ld a,b
    sub 3
    jr nc,.fuel_consumed
    xor a
.fuel_consumed:
    ld b,a
.fuel_hud_budget:
    IF HUD_ENABLED
    ld a,(Fuel_HudWork)
    ld c,a
    ld a,b
    sub c
    jr nc,.fuel_remaining
    xor a
.fuel_remaining:
    ld b,a
    ENDIF
    ENDIF
    IF INCREMENTAL_STAGE >= 4
    IF HUD_ENABLED
    ld a,(Flag_HudWork)
    or a
    jr z,.hud_budgeted
    ld c,a
.hud_cost:
    ld a,b
    sub 6
    jr nc,.hud_remaining
    xor a
.hud_remaining:
    ld b,a
    dec c
    jr nz,.hud_cost
.hud_budgeted:
    ENDIF
    IF INCREMENTAL_STAGE >= 5
    IF HUD_ENABLED
    ld a,(Score_HudPairs)
    or a
    jr z,.numbers_budgeted
    ld c,a
.number_cost:
    ld a,b
    sub 4
    jr nc,.number_remaining
    xor a
.number_remaining:
    ld b,a
    dec c
    jr nz,.number_cost
.numbers_budgeted:
    ENDIF
    ENDIF
    ld a,(Flag_Jobs)
    or a
    jr z,.normal_patch
    IF INCREMENTAL_STAGE >= 6
    ld a,(player_patch_work)
    ld c,a
    ld a,(player_patch_valid)
    or c
    jr z,.effect_budget     ; no optional car row exists to restore/reapply
    ENDIF
    ld a,b
    sub 6
    jr nc,.flag_remaining
    xor a
.flag_remaining:
    ld b,a
    jr .effect_budget
.normal_patch:
    ENDIF
    ld a,(player_patch_work)
    or a
    jr z,.effect_budget
    ld a,b
    sub 6
    IF INCREMENTAL_STAGE >= 4
    jr nc,.patch_remaining
    xor a
.patch_remaining:
    ENDIF
    ld b,a
.effect_budget:
    IF INCREMENTAL_STAGE >= 4
    ld a,b
    or a
    ret z
    ENDIF
    IF INCREMENTAL_STAGE >= 3
    call Death_Stream
    ld a,b
    or a
    ret z
    ENDIF
    IF INCREMENTAL_STAGE >= 4
    call Flag_Stream
.after_flags:
    ld a,b
    or a
    ret z
    ENDIF
    IF INCREMENTAL_STAGE >= 5
    IF !((RADAR_CELLS_ONLY && HUD_ENABLED) || (INCREMENTAL_STAGE >= 9 && ENEMY_COUNT >= 2 && !HUD_ENABLED))
    IF ENEMY_RENDER
    ; A newly collected flag can leave a bounded score publication pending.
    ; Start its measured ~3 ms transaction before the footer, or retain it for
    ; the next refresh. Native collection state and visible terrain are final.
    ld a,(Flag_Count)
    ld hl,Score_Seen
    cp (hl)
    jr z,.score_ready
    ld a,(paused)
    or a
    jr nz,.score_ready
    ld a,(Death_State)
    or a
    jr nz,.score_ready
    ld a,(player_steps)
    cp 2
    ret z                    ; keep the observed two-tick stress frame bounded
    ld a,(raster_phase)
    cp 2
    ret nc
.score_ready:
    ENDIF
    call Score_Frame
    ld a,b
    or a
    ret z
    ENDIF
    ENDIF
    IF ENEMY_COUNT && !ENEMY_RENDER
    ; One native tick uses the blank interval. A second tick still runs in the
    ; body and reserves its measured enemy cost before hidden guard copies.
    ; Visible flag/death jobs and their score publication retain priority.
    ld a,(player_steps)
    cp 2
    jr nz,.enemy_budgeted
    ld a,b
    sub 7
    jr nc,.enemy_remaining
    xor a
.enemy_remaining:
    ld b,a
    or a
    ret z
.enemy_budgeted:
    ENDIF
.next:
    IF RASTER_GUARD && !FULL_GAME
    ld a,(Stage_GuardClosed)
    or a
    ret nz
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    ; Choose the queue with less remaining guard slack. Neither axis can
    ; monopolize the budget while the other drifts into the visible viewport.
    ld a,(row_left)
    or a
    jr z,.column_first
    ld a,(Stage_PreferRows)
    or a
    ld a,(row_left)
    jr nz,.row
.column_first:
    ENDIF
    ld a,(column_left)
    or a
    jr nz,.column
    ld a,(row_left)
    or a
    jr nz,.row
    push bc
    call stage_position
    pop bc
    ld a,(column_left)
    or a
    jr nz,.column
    ld a,(row_left)
    or a
    ret z
.row:
    dec a
    ld (row_left),a
    ld a,(row_x)
    ld (tile_x),a
    inc a
    IF INCREMENTAL_STAGE >= 9
    ld hl,Stage_RowEnd
    cp (hl)
    jr nz,.row_cursor
    ld a,(Stage_RowLeft)
.row_cursor:
    ENDIF
    ld (row_x),a
    ld a,(row_y)
    ld (tile_y),a
    IF STAGE_SOLID_RUNS
    ld a,1
    ld (Stage_RowBatch),a
    ENDIF
    jr .draw
.column:
    IF STAGE_SOLID_RUNS
    ld a,2
    ld (Stage_RowBatch),a
    ld a,(column_left)
    ENDIF
    dec a
    ld (column_left),a
    ld a,(column_x)
    ld (tile_x),a
    ld a,(column_y)
    ld (tile_y),a
    inc a
    IF INCREMENTAL_STAGE >= 9
    ld hl,Stage_ColumnEnd
    cp (hl)
    jr nz,.column_cursor
    ld a,(Stage_ColumnTop)
.column_cursor:
    ENDIF
    ld (column_y),a
.draw:
    push bc
    IF FULL_GAME
    xor a
    ld (Full_CacheWorked),a
    ENDIF
    call stage_tile
    IF STAGE_SOLID_RUNS
    xor a
    ld (Stage_RowBatch),a
    ENDIF
    pop bc
    ei
    nop
    IF !FULL_GAME
    di
    ENDIF
    IF FULL_GAME
    ld a,(Full_CacheWorked)
    or a
    jp z,.next               ; Already-owned tiles consume no GPU work budget.
    ENDIF
    IF STAGE_SOLID_RUNS
    dec b
    jp nz,.next
    ELSE
    djnz .next
    ENDIF
    ret

    IF INCREMENTAL_STAGE >= 9
; World coordinates remain fixed during streaming. Normalize each queue's tile
; debt by its guard size once per refresh, rather than repeating divides/tile.
Stage_QueuePriority:
    ei
    nop
    IF FULL_GAME
    ld a,(Full_CameraBlocked)
    or a
    jr z,.ordinary
    and 1
    ld (Stage_PreferRows),a
    ret
.ordinary:
    ENDIF
    ld hl,(world_y)
    call stage_div8
    ld a,(previous_y)
    sub l
    jp p,.vertical_abs
    neg
.vertical_abs:
    IF STAGE_CACHE_GUARD >= STAGE_CACHE_TOP_GUARD
    add a,STAGE_CACHE_GUARD-STAGE_CACHE_TOP_GUARD
    ENDIF
    ld b,a
    ld hl,(world_x)
    call stage_div8
    ld a,(previous_x)
    sub l
    jp p,.horizontal_abs
    neg
.horizontal_abs:
    IF STAGE_CACHE_GUARD < STAGE_CACHE_TOP_GUARD
    add a,STAGE_CACHE_TOP_GUARD-STAGE_CACHE_GUARD
    ENDIF
    cp b
    ld a,0
    jr c,.rows
    jr nz,.store
.rows:
    inc a
.store:
    ld (Stage_PreferRows),a
    IF !FULL_GAME
    di
    ENDIF
    ret
    ENDIF

    IF !FULL_GAME
stage_load:
    IF FULL_GAME
    call Full_CacheClear
    ENDIF
    IF STAGE_SOLID_RUNS
    xor a
    ld (Stage_RowBatch),a
    ENDIF
    ld a,(driving)
    or a
    jr nz,.camera
    ld a,(scene)
    add a,a
    add a,a
    ld l,a
    ld h,0
    ld de,stage_landmarks
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld (world_x),de
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld (world_y),de
.camera:
    ld a,(driving)
    or a
    call nz,stage_cache_bounds
    ld hl,(world_x)
    call stage_div8
    ld a,l
    ld (previous_x),a
    sub STAGE_CACHE_GUARD
    ld (row_x),a
    ld hl,(world_y)
    call stage_div8
    ld a,l
    ld (previous_y),a
    sub STAGE_CACHE_TOP_GUARD
    ld (tile_y),a
    ld b,32
.y:
    push bc
    ld a,(row_x)
    ld (tile_x),a
    ld b,64
.x:
    push bc
    call stage_tile
    pop bc
    ld hl,tile_x
    inc (hl)
    djnz .x
    ld hl,tile_y
    inc (hl)
    pop bc
    djnz .y
    xor a
    ld (column_left),a
    ld (row_left),a
    ret

    ENDIF
stage_tile:
    IF FULL_GAME
    ld a,(Full_CameraBlocked)
    or a
    jr z,.ordinary_bounds
    ld a,(Full_TargetTileX)
    ld c,a
    ld a,(tile_x)
    sub c
    cp 32
    jr nc,.ordinary_bounds
    ld a,(Full_TargetTileY)
    ld c,a
    ld a,(tile_y)
    sub c
    cp 26
    jr c,.source             ; Urgent visible edges override stale guard bounds.
.ordinary_bounds:
    ENDIF
    ld a,(driving)
    or a
    jr z,.source
    ld a,(cache_left)
    ld c,a
    ld a,(tile_x)
    sub c
    cp STAGE_CACHE_COLUMNS
    ret nc
    ld a,(cache_top)
    ld c,a
    ld a,(tile_y)
    sub c
    cp 32
    ret nc
.source:
    IF FULL_GAME
    call Full_CacheProbe
    ret c
    ENDIF
    IF TILE_MODE
    jp TileMap_Copy
    ENDIF
    ld a,(driving)
    or a
    IF SMOKE_RUNTIME
    jr z,.static_source
    ld a,(Smoke_Valid)
    or a
    jp z,stage_copy_tile
    call Smoke_CaptureCode
    call stage_copy_tile
    jp Smoke_RecordDisplay
.static_source:
    ELSE
    jp nz,stage_copy_tile
    ENDIF
    ; Source uses global coordinates; destination uses modulo 64x32 tiles.
    ld a,(tile_x)
    cp STAGE_COLUMNS
    jr nc,.blank
    ld a,(tile_y)
    cp STAGE_ROWS
    jr nc,.blank
    srl a
    srl a
    inc a
    ld ($7000),a
    ld a,(tile_x)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl                  ; tile column * 4 packed bytes
    ld a,(tile_y)
    and 3
    add a,a
    add a,a
    add a,a
    add a,a
    or $80
    or h
    ld h,a
    jr .destination
.blank:
    ; Extend the native repeating flower selector during camera overscroll.
    ; Coordinates >=224 represent negative guard tiles; the view never reaches
    ; those positive map rows. Destination still uses the original coordinates.
    ld a,(tile_x)
    ld l,a
    ld h,0
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    add a,a
    add a,a
    ld c,a
    ld a,(tile_y)
    ld l,a
    ld h,0
    add hl,de
    ld a,(hl)
    add a,a
    add a,a
    add a,a
    add a,a
    or $80
    ld h,a
    ld l,c
    ld a,1
    ld ($7000),a
.destination:
    ld a,(tile_x)
    and 32
    rrca
    rrca
    rrca
    rrca
    ld b,a                     ; R14 = page*2 + half-page
    ld a,(tile_y)
    and 16
    rrca
    rrca
    rrca
    rrca
    or b
    ld (tile_vram_bank),a
    ld b,14
    call register
    ld a,(tile_y)
    and 15
    add a,a
    add a,a
    ld d,a                     ; tile row * 1024 bytes (modulo 16KB)
    ld a,(tile_x)
    and 31
    add a,a
    add a,a
    ld e,a                     ; tile column * 4 packed bytes
    ld a,8
.line:
    push af
    ld a,e
    out ($99),a
    ld a,d
    or $40
    out ($99),a
    ld bc,$0498
    otir
    ld bc,508
    add hl,bc                 ; Next packed scanline, preserving tile X.
    ld a,e
    add a,128
    ld e,a
    jr nc,.next
    inc d
.next:
    pop af
    dec a
    jr z,.tile_done
    cp 4
    jr nz,.continue
    push af
    ld a,(driving)
    or a
    jr z,.no_irq_window
    ei
    nop
    di
    ld a,(tile_vram_bank)
    ld b,14
    call register             ; The footer may have changed R14 to its own tables.
.no_irq_window:
    pop af
.continue:
    jr .line
.tile_done:
    ret
stage_flower_phase:
    INCBIN "stage-flower-phase.bin"
stage_command EQU $c460
stage_atlas_init:
    IF TILE_MODE
    jp TileMap_Init
    ENDIF
    ld hl,stage_command_template
    ld de,stage_command
    ld bc,15
    ldir
    IF STAGE_BANKED_ATLAS
    IF FULL_GAME
    ld a,(Full_ResourceBank)
    ELSE
    ld a,PLAYER_DATA_BANK
    ENDIF
    ld ($7000),a
    ENDIF
    vdp_write 14,4
    xor a
    out ($99),a
    ld a,$48
    out ($99),a
    IF FULL_GAME
    ld hl,$8000
    ld de,4096
    ELSE
    ld hl,stage_atlas
    ld de,STAGE_ATLAS_BYTES
    ENDIF
    jp upload
stage_wait_command:
    IF FULL_GAME
    di                       ; Foreground cache work can now span VBlank.
    ENDIF
    vdp_write 15,2
.busy:
    in a,($99)
    and 1
    IF ENEMY_RENDER || PLAYER_BLITTER
    jr z,.complete
    ; A 24x8 visible repair can still be executing. No port latch is open:
    ; service raster IRQs between polls, then restore their status selector.
    ei
    nop
    di
    vdp_write 15,2
    jr .busy
.complete:
    ELSE
    jr nz,.busy
    ENDIF
    IF INCREMENTAL_STAGE < 9
    vdp_write 15,0
    ENDIF
    ; Stage09 callers do not consume S0. IRQ entry selects its own status;
    ; leaving S2 here avoids one redundant control transaction per cache tile.
    ret
stage_copy_tile:
    IF FULL_GAME
    call Full_TurboOn
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    ei                      ; ROM lookup and RAM packet preparation own no VDP latch.
    nop
    ENDIF
    IF INCREMENTAL_STAGE >= 3
    ld a,(Death_DisplayState)
    or a
    jr z,.terrain
    call Death_Source
    jp c,stage_copy_destination
.terrain:
    ENDIF
    IF SMOKE_RUNTIME
    call Smoke_Source
    jp c,stage_copy_destination
    ENDIF
    IF FULL_GAME
    call Full_TileSource
    jp c,stage_copy_destination
    ENDIF
    ld a,(tile_x)
    ld c,a
    cp STAGE_COLUMNS
    jr nc,.flower
    ld a,(tile_y)
    cp STAGE_ROWS
    jr nc,.flower
    jr .id
.flower:
    IF SMOKE_RUNTIME
    push bc
    push de
    push hl
    call Stage_TryFlowerRow
    pop hl
    pop de
    pop bc
    ret c
    ENDIF
    ld hl,stage_flower_phase
    ld e,c
    ld d,0
    add hl,de
    ld c,(hl)
    ld a,(tile_y)
    ld e,a
    ld hl,stage_flower_phase
    add hl,de
    ld a,(hl)
.id:
    ld l,a
    IF STAGE_SOURCE_XY
    and $c0
    rlca
    rlca
    IF FULL_GAME
    push hl
    ld hl,Full_IDBank
    add a,(hl)
    pop hl
    ELSE
    add a,STAGE_ID_BANK
    ENDIF
    ld ($7000),a
    ld a,l
    and 63
    or $80
    ld h,a                    ; each world row is exactly 256 source-address bytes
    ld a,c
    add a,a
    ld l,a
    ld a,(hl)
    IF STAGE_TILE_STRIPS
    bit 0,a
    jr nz,.not_strip_candidate
    ld c,a
    ld a,(Stage_RowBatch)
    cp 1
    jr z,.horizontal_strip
    cp 2
    ld a,c
    jr nz,.not_strip_candidate
    inc hl
    bit 0,(hl)
    dec hl
    jr z,.not_strip_candidate
    jr .try_strip
.horizontal_strip:
    ld a,c
    bit 2,a
    jr z,.not_strip_candidate
.try_strip:
    push hl
    push af
    call Stage_TryStrip
    jr nc,.not_strip
    pop af
    pop hl
    ret
.not_strip:
    pop af
    pop hl
.not_strip_candidate:
    and $fb                 ; Strip tags are lookup metadata, never source X.
    ENDIF
    IF STAGE_SOLID_RUNS
    bit 1,a
    jp nz,Stage_SolidTile
    ENDIF
    IF INCREMENTAL_STAGE >= 4
    bit 0,a
    jp nz,Flag_Source
    ENDIF
    ld (stage_command),a
    inc hl
    ld a,(hl)
    IF STAGE_TILE_STRIPS
    and $fe
    ENDIF
    ld (stage_command+2),a
    ELSE
    and 128
    rlca
    add a,STAGE_ID_BANK
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
    ld b,0
    add hl,bc
    ld bc,$8000
    add hl,bc
    ld a,(hl)
    add a,a
    add a,a
    add a,a
    ld (stage_command),a
    ENDIF
stage_copy_destination:
    IF FULL_GAME
    call Full_TurboOff
    call Full_CacheCommand
    ret c
    ENDIF
    ld a,(tile_x)
    and 31
    add a,a
    add a,a
    add a,a
    ld (stage_command+4),a
    ld a,(tile_y)
    and 31
    add a,a
    add a,a
    add a,a
    ld (stage_command+6),a
    ld a,(tile_x)
    and 32
    rlca
    rlca
    rlca
    ld (stage_command+7),a
    IF STAGE_SOURCE_XY || PLAYER_BLITTER
    ; Service a pending raster before the indivisible status/command transaction.
    ; No VDP port latch is open here; the ISR does not change mapper banks.
    ei
    nop
    di
    ENDIF
    call stage_wait_command  ; Prepare RAM packet while the previous copy executes.
    vdp_write 17,32
    IF INCREMENTAL_STAGE >= 9
    ; ISR hooks never access R17 or the command engine. Its indirect register
    ; stream remains valid while the header/footer owns the other VDP ports.
    ei
    nop
    ENDIF
    ld hl,stage_command
    ld bc,$0f9b
    otir
    IF INCREMENTAL_STAGE >= 9
    di
    ENDIF
stage_copy_done:
    ret
    IF SMOKE_RUNTIME
; Outside-world flowers repeat in exact three-tile rows. Copy those pixels
; together instead of spending three command transactions on each new row.
Stage_TryFlowerRow:
    ld a,(Stage_RowBatch)
    cp 1
    jr z,.horizontal
    cp 2
    jp z,.vertical
    jp .no
.horizontal:
    ld a,(row_left)
    cp 2
    jp c,.no
    ld a,(tile_x)
    and 31
    cp 30
    jp nc,.no
    ld a,(tile_x)
    ld l,a
    ld h,0
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    or a
    jp nz,.no
    ld a,(tile_x)
    inc a
    ld b,a
    ld a,(row_x)
    cp b
    jp nz,.no
    inc a
    ld hl,Stage_RowEnd
    cp (hl)
    jp z,.no
    ld a,(cache_left)
    ld d,a
    ld a,(tile_x)
    add a,2
    sub d
    cp STAGE_CACHE_COLUMNS
    jp nc,.no
    ld a,(tile_y)
    ld c,a
    call Smoke_Batchable
    jp nz,.no
    inc b
    call Smoke_Batchable
    jp nz,.no
    ld a,(tile_y)
    ld l,a
    ld h,0
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    add a,a
    ld l,a
    ld h,0
    ld de,Stage_FlowerSources
    add hl,de
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    ld a,24
    ld (stage_command+8),a
    call stage_copy_destination
    ld a,8
    ld (stage_command+8),a
    ld hl,row_left
    dec (hl)
    dec (hl)
    ld a,(row_x)
    add a,2
    ld hl,Stage_RowEnd
    cp (hl)
    jr nz,.cursor
    ld a,(Stage_RowLeft)
.cursor:
    ld (row_x),a
    scf
    ret
.vertical:
    ld a,(column_left)
    cp 2
    jp c,.no
    ld a,(tile_y)
    and 31
    cp 30
    jp nc,.no
    ld a,(tile_y)
    ld l,a
    ld h,0
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    or a
    jp nz,.no
    ld a,(tile_y)
    inc a
    ld c,a
    ld a,(column_y)
    cp c
    jp nz,.no
    inc a
    ld hl,Stage_ColumnEnd
    cp (hl)
    jp z,.no
    ld a,(cache_top)
    ld d,a
    ld a,(tile_y)
    add a,2
    sub d
    cp 32
    jp nc,.no
    ld a,(tile_x)
    ld b,a
    call Smoke_Batchable
    jp nz,.no
    inc c
    call Smoke_Batchable
    jp nz,.no
    ld a,(tile_x)
    ld l,a
    ld h,0
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    add a,a
    ld l,a
    ld h,0
    ld de,Stage_FlowerVerticalSources
    add hl,de
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    IF STAGE_TILE_STRIPS
    ld a,3
    ld (stage_command+3),a
    ENDIF
    ld a,24
    ld (stage_command+10),a
    call stage_copy_destination
    ld a,8
    ld (stage_command+10),a
    IF STAGE_TILE_STRIPS
    ld a,2
    ld (stage_command+3),a
    ENDIF
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
    scf
    ret
.no:
    or a
    ret
Stage_FlowerSources:
    INCBIN "flower-sources.bin"
Stage_FlowerVerticalSources:
    INCBIN "flower-vertical-sources.bin"
    ENDIF
    IF STAGE_SOLID_RUNS
; Adjacent exact solid tiles share one fill command. Stop at owner/texture,
; queue wrap, world bounds and the physical 256-pixel page boundary.
Stage_SolidTile:
    ld e,a
    ld a,1
    ld (Stage_RunLength),a
    ld a,(driving)
    or a
    jp z,.emit
    ld a,(Stage_RowBatch)
    or a
    jp z,.emit
    ld a,(Death_DisplayState)
    or a
    jp nz,.emit
    ld a,(Stage_RowBatch)
    cp 2
    jp z,.column
    ld a,(tile_x)
    ld d,a
.next:
    ld a,(Stage_RunLength)
    cp STAGE_SOLID_RUN_TILES
    jp nc,.emit              ; Bound the final indivisible GPU command.
    ld a,(row_left)
    or a
    jp z,.emit
    inc d
    ld a,(row_x)
    cp d
    jp nz,.emit
    cp STAGE_COLUMNS
    jp nc,.emit
    and 31
    jp z,.emit
    ld a,(cache_left)
    ld b,a
    ld a,d
    sub b
    cp STAGE_CACHE_COLUMNS
    jp nc,.emit
    inc hl
    inc hl
    IF FULL_GAME
    push bc
    push hl
    ld l,d
    ld h,0
    push de
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    pop de
    pop hl
    or a
    jr nz,.same_object_row
    ld b,d
    ld a,(tile_y)
    ld c,a
    call Full_ObjectAtTile
    jr .object_row_checked
.same_object_row:
    xor a
.object_row_checked:
    pop bc
    or a
    jp nz,.emit
    ENDIF
    ld a,(hl)
    IF STAGE_TILE_STRIPS
    and $fb
    ENDIF
    cp e
    jp nz,.emit
    IF SMOKE_RUNTIME
    push bc
    ld b,d
    ld a,(tile_y)
    ld c,a
    call Smoke_Batchable
    pop bc
    jp nz,.emit
    ENDIF
    ld a,(row_left)
    dec a
    ld (row_left),a
    ld a,d
    inc a
    ld bc,Stage_RowEnd
    push hl
    ld h,b
    ld l,c
    cp (hl)
    pop hl
    jr nz,.cursor
    ld a,(Stage_RowLeft)
.cursor:
    ld (row_x),a
    ld a,(Stage_RunLength)
    inc a
    ld (Stage_RunLength),a
    IF FULL_GAME
    jp .next
    ELSE
    jr .next
    ENDIF
.column:
    ld a,(tile_y)
    ld d,a
.column_next:
    ld a,(Stage_RunLength)
    cp STAGE_SOLID_RUN_TILES
    jp nc,.emit
    ld a,(column_left)
    or a
    jp z,.emit
    inc d
    ld a,(column_y)
    cp d
    jp nz,.emit
    cp STAGE_ROWS
    jp nc,.emit
    and 31
    jp z,.emit
    ld a,(cache_top)
    ld b,a
    ld a,d
    sub b
    cp 32
    jp nc,.emit
    inc h                    ; Source-address rows are exactly 256 bytes.
    IF FULL_GAME
    push bc
    push hl
    ld l,d
    ld h,0
    push de
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    pop de
    pop hl
    or a
    jr nz,.same_object_column
    ld c,d
    ld a,(tile_x)
    ld b,a
    call Full_ObjectAtTile
    jr .object_column_checked
.same_object_column:
    xor a
.object_column_checked:
    pop bc
    or a
    jp nz,.emit
    ENDIF
    ld a,(hl)
    IF STAGE_TILE_STRIPS
    and $fb
    ENDIF
    cp e
    jp nz,.emit
    IF SMOKE_RUNTIME
    push bc
    ld c,d
    ld a,(tile_x)
    ld b,a
    call Smoke_Batchable
    pop bc
    jp nz,.emit
    ENDIF
    ld a,(column_left)
    dec a
    ld (column_left),a
    ld a,d
    inc a
    ld bc,Stage_ColumnEnd
    push hl
    ld h,b
    ld l,c
    cp (hl)
    pop hl
    jr nz,.column_cursor
    ld a,(Stage_ColumnTop)
.column_cursor:
    ld (column_y),a
    ld a,(Stage_RunLength)
    inc a
    ld (Stage_RunLength),a
    IF FULL_GAME
    jp .column_next
    ELSE
    jr .column_next
    ENDIF
.emit:
    ld a,e
    rrca
    rrca
    rrca
    rrca
    and 15
    ld c,a
    rlca
    rlca
    rlca
    rlca
    or c                     ; HMMV writes packed bytes, two SCREEN5 pixels.
    ld (stage_command+12),a
    ld a,(Stage_RunLength)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(Stage_RowBatch)
    cp 2
    jr z,.height
    ld (stage_command+8),hl
    jr .command
.height:
    ld (stage_command+10),hl
.command:
    ld a,$c0
    ld (stage_command+14),a
    call stage_copy_destination
    ld hl,8
    ld (stage_command+8),hl
    ld (stage_command+10),hl
    ld a,$d0
    ld (stage_command+14),a
    ret
    ENDIF
stage_command_template:
    db 0,0,16,2,0,0,0,0,8,0,8,0,0,0,$d0
    IF STAGE_TILE_STRIPS
    INCLUDE "tile-strips.inc"
    ENDIF
    IF STAGE_BANKED_ATLAS
stage_atlas EQU $b000
    ELSE
stage_atlas:
    INCBIN "stage-atlas.bin"
    ENDIF
stage_cache_bounds:
    ld hl,(world_x)
    call stage_div8
    ld a,l
    sub STAGE_CACHE_GUARD
    ld (cache_left),a
    ld hl,(world_y)
    call stage_div8
    ld a,l
    sub STAGE_CACHE_TOP_GUARD
    ld (cache_top),a
    ret
stage_landmarks:
    INCBIN "stage-landmarks.bin"

stage_radar:
    IF STAGE_RADAR_BANK
    ld a,STAGE_RADAR_BANK
    ld ($7000),a
    ENDIF
    ; Coordinate tables keep projection out of the pre-header raster budget.
    ld hl,(world_x)
    ld de,VIEWPORT_HALF
    add hl,de
    ld (radar_world_x),hl
    ld hl,(world_y)
    ld de,100
    add hl,de
    ld (radar_world_y),hl
    ld hl,(world_x)
    ld de,stage_radar_x
    add hl,de
    ld a,(hl)
    push af
    ld hl,(world_y)
    ld de,stage_radar_y
    add hl,de
    ld c,(hl)
    pop af
    ld b,a
    jp HUD_SetPlayer
    IF STAGE_RADAR_BANK
stage_radar_x EQU $8000
stage_radar_y EQU $8000+STAGE_WIDTH-VIEWPORT_WIDTH+1
    ELSE
stage_radar_x:
    INCBIN "stage-radar-x.bin"
stage_radar_y:
    INCBIN "stage-radar-y.bin"
    ENDIF

    IF TILE_MODE
    INCLUDE "tilemap.inc"
    ENDIF
