; Twelve sprites contain the frame, flags and enemy markers.
; The player's independent 2x2 marker has priority over the map and blinks.
; RAM base masks retain white scenery; only dirty cells are recomposed.
Radar_Base EQU $c800
Radar_Colors EQU $c240
    IF FULL_GAME
Radar_Last EQU $c640
Radar_Next EQU $c650
Radar_PublishedPoints EQU $db40 ; 12 cells * 16 bytes; smoke rows end DB40
Radar_StagedVisibility EQU $ce00
Radar_WorkVisibility EQU $ce0c
    ELSE
Radar_Last EQU $cf00            ; player, enemy1, enemy2: packed X/Y pairs
Radar_Next EQU $cf20
Radar_PublishedPoints EQU $cf60
Radar_StagedVisibility EQU $cd88
Radar_WorkVisibility EQU $cd94
    ENDIF
Radar_Dirty EQU $cf08
Radar_Cell EQU $cf0a
Radar_PlotColor EQU $cf0b
Radar_CellsWork EQU $cf0c
Radar_Initializing EQU $cf0d
Radar_PointRow EQU $cf0e
Radar_Budget EQU $cf0f
Radar_ScanCell EQU $cf10
Radar_Checked EQU $cf11
Radar_Ready EQU $cf12
Radar_PublishCursor EQU $cf14
Radar_PublishBudget EQU $cf15
Radar_PublishCell EQU $cf16
Radar_PublishChecked EQU $cf17
Radar_PendingCell EQU $cf18
Radar_Scanned EQU $cf19
Radar_CoordinateSource EQU $cf1e
Radar_DeferAge EQU $cf28
Radar_DrawBuffer EQU $cf2a
Radar_DrawShift EQU $cf2c
Radar_DrawColors EQU $cf2e
Radar_PublishAge EQU $cf30
Radar_TailWork EQU $cf32
Radar_PlayerSAT EQU $cf34
Radar_PlayerPoint EQU $cf38
Radar_PlayerVisible EQU $cf3a
Radar_PlayerColor EQU $cf3b
Radar_PlayerColors EQU $cf3c
Radar_PlayerColorDrawn EQU $cf3f
Radar_BaseVisibility EQU $cfa8
Radar_Payloads EQU $c980          ; twelve80-byte normal/shift/color payloads
Radar_StagedPoints EQU $cd40

Radar_Init:
    ld a,1
    ld (Radar_Initializing),a
    IF RADAR_PLAYER_SPRITE
    ld a,255
    ld (Radar_PlayerColorDrawn),a
    ; One resident 2x2 mask plus its lossless Y=216 sentinel phase. Enemy
    ; facings using these groups go through the existing victim cache.
    ld a,ENEMY_MASK_BANK
    ld ($7000),a
    ld hl,$b000
    ld de,$7800+RADAR_PLAYER_PATTERN*8
    ld b,64
    call Sprite_Upload
    ENDIF
    ld a,HUD_DATA_BANK
    ld ($7000),a
    ld hl,$9000
    ld de,Radar_Base
    ld bc,384
    ldir
    ld hl,Radar_Last
    IF FULL_GAME
    ld b,16
    ELSE
    ld b,6
    ENDIF
    ld a,255
    ld (Radar_PendingCell),a
.last:
    ld (hl),a
    inc hl
    djnz .last
    xor a
    IF ENEMY_COUNT >= 2 || SMOKE_RUNTIME
    ld (Radar_DeferAge),a
    ld (Radar_PublishAge),a
    ENDIF
    ld (Radar_Scanned),a
    ld (Radar_Dirty),a
    ld (Radar_Dirty+1),a
    ld (Radar_ScanCell),a
    ld (Radar_Ready),a
    ld (Radar_Ready+1),a
    ld (Radar_PublishCursor),a
    ld hl,Radar_BaseVisibility
    ld de,Radar_BaseVisibility+1
    ld bc,11
    ld (hl),a
    ldir
    ld hl,Radar_WorkVisibility
    ld de,Radar_WorkVisibility+1
    ld bc,11
    ld (hl),a
    ldir
    ld hl,Radar_PublishedPoints
    ld de,Radar_PublishedPoints+1
    IF FULL_GAME
    ld bc,191
    ELSE
    ld bc,71
    ENDIF
    ld (hl),255
    ldir
    ret

Radar_UpdatePoints:
    call Radar_AllowIRQ
    IF !RADAR_PLAYER_SPRITE
    ld hl,(hud_player_x)
    ld (Radar_Next),hl
    ld (point_x),hl
    ENDIF
    IF FULL_GAME
    ld hl,$ffff
    ld (Radar_Next),hl       ; Independent player sprite owns its own marker.
    ld hl,Full_EnemyPoints
    ld de,Radar_Next+2
    ld bc,14
    ldir
    ELSE
    ld hl,(hud_enemy_x)
    ld (Radar_Next+2),hl
    ld (enemy_x),hl
    IF ENEMY_COUNT > 1
    ld hl,(Enemy2_PointX)
    ELSE
    ld hl,$ffff
    ENDIF
    ld (Radar_Next+4),hl
    ENDIF
    ld a,BLACK
    ld (point_color),a
    ld a,RADAR_CACHE_BANK
    ld ($7000),a
    IF RADAR_PLAYER_SPRITE
    ld ix,Radar_Last+2
    ld hl,Radar_Next+2
    IF FULL_GAME
    ld b,7
    ELSE
    ld b,2
    ENDIF
    ELSE
    ld ix,Radar_Last
    ld hl,Radar_Next
    ld b,3
    ENDIF
.point:
    ld d,(hl)
    inc hl
    ld e,(hl)
    inc hl
    IF RADAR_MARKER_QUANTUM == 2
    ld a,d
    cp 255
    jr z,.quantized
    and $fe
    ld d,a
    ld a,e
    and $fe
    ld e,a
.quantized:
    ENDIF
    ld a,(ix)
    cp d
    jr nz,.changed
    ld a,(ix+1)
    cp e
    jr z,.next
.changed:
    push bc
    push hl
    push de
    ld d,(ix)
    ld e,(ix+1)
    call Radar_Mark
    pop de
    push de
    call Radar_Mark
    pop de
    ld (ix),d
    ld (ix+1),e
    pop hl
    pop bc
.next:
    inc ix
    inc ix
    djnz .point
    ret

Radar_Prepare:
    call Radar_UpdatePoints
Radar_PrepareQueued:
    xor a
    ld (Radar_CellsWork),a
    ld a,1
    ld (Radar_Budget),a
    ld a,(Radar_Initializing)
    or a
    jr nz,.drain
    ld a,(paused)
    or a
    jr nz,.budget_ready
    IF (ENEMY_COUNT >= 2 && !STAGE_TILE_STRIPS) || SMOKE_RUNTIME
    ; Let terrain catch up before optional marker composition. Dirty markers
    ; remain queued and retain the existing sixteen-refresh acceptance limit.
    ld a,(player_steps)
    cp 2
    jr z,.defer
    ld a,(row_left)
    ld hl,column_left
    or (hl)
    jr nz,.pressure
    ld hl,(world_x)
    call stage_div8
    ld a,(previous_x)
    cp l
    jr nz,.pressure
    ld hl,(world_y)
    call stage_div8
    ld a,(previous_y)
    cp l
    jr nz,.pressure
    ENDIF
    ld a,(player_steps)
    cp 2
    jr nz,.budget_ready
    IF (ENEMY_COUNT >= 2 && !STAGE_TILE_STRIPS) || SMOKE_RUNTIME
    jr .defer
.pressure:
    ld a,(Radar_DeferAge)
    inc a
    ld (Radar_DeferAge),a
    cp 2
    jr nc,.budget_ready      ; Terrain pressure cannot permanently starve markers.
    ENDIF
.defer:
    xor a
    ld (Radar_Budget),a
    jr .budget_ready
.drain:
    ld a,12
    ld (Radar_Budget),a
.budget_ready:
    call Radar_DirtyMask
    jr z,.done
    ld a,(Radar_ScanCell)
    ld (Radar_Cell),a
    ld b,a
    or a
    jr z,.rotated
.rotate:
    srl h
    rr l
    jr nc,.rotate_next
    set 3,h                 ; rotate only the twelve meaningful bits
.rotate_next:
    djnz .rotate
.rotated:
    ld a,12
    ld (Radar_Checked),a
.cell:
    ld a,(Radar_Budget)
    or a
    jr z,.done
    srl h
    rr l
    jr nc,.skip
    push hl
    IF ENEMY_COUNT >= 2 || SMOKE_RUNTIME
    xor a
    ld (Radar_DeferAge),a
    ENDIF
    ld a,(Radar_Cell)
    ld (hud_cell),a
    call Radar_RenderCell
    ld hl,Radar_Budget
    dec (hl)
    pop hl
.skip:
    ld a,(Radar_Cell)
    inc a
    cp 12
    jr c,.scan_next
    xor a
.scan_next:
    ld (Radar_Cell),a
    ld (Radar_ScanCell),a
    ld a,(Radar_Checked)
    dec a
    ld (Radar_Checked),a
    jr nz,.cell
.done:
    IF FULL_GAME
    call Radar_AllowIRQ
    ELSE
    di
    ENDIF
    ret

; The same pending mask determines tail reservation and actual composition.
Radar_DirtyMask:
    ld hl,(Radar_Dirty)
    IF STAGE_TILE_STRIPS && !SMOKE_RUNTIME
    ; A just-uploaded cell still owns its staged metadata until next-frame
    ; commit. Tail composition must not overwrite that display snapshot.
    ld a,(Radar_PendingCell)
    cp 12
    jr nc,.pending_safe
    ld (hud_cell),a
    push hl
    call Radar_CellBit
    pop hl
    ld a,e
    cpl
    and l
    ld l,a
    ld a,d
    cpl
    and h
    ld h,a
.pending_safe:
    ENDIF
    ld de,(hud_flags_dirty)
    ld a,e
    cpl
    and l
    ld l,a
    ld a,d
    cpl
    and h
    and 15
    ld h,a
    ld a,h
    or l
    ret

    IF STAGE_TILE_STRIPS && !SMOKE_RUNTIME
Radar_TailBudget:
    xor a
    ld (Radar_TailWork),a
    ld a,(player_steps)
    cp 2
    ret z
    call Radar_DirtyMask
    ret z
    ld a,1
    ld (Radar_TailWork),a
    ret
Radar_PrepareTail:
    ld a,(ticks)
    ld hl,frame_tick
    cp (hl)
    ret nz                  ; Retain dirty work if the frame already ended.
    ld a,(Radar_TailWork)
    or a
    ret z
    call Radar_AllowIRQ
    jp Radar_PrepareQueued
    ENDIF

Radar_CellBit:
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    ld de,Radar_CellBits
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ret
Radar_CellBits:
    dw 1,2,4,8,16,32,64,128,256,512,1024,2048

; The fifteen fixed-screen body entries depend only on vertical scroll. Keep
; the arithmetic and sentinel decisions in a ROM table, not the frame budget.
Radar_Coordinates:
    call Radar_EarlyCoordinates
    jp Radar_FinishCoordinates
Radar_EarlyCoordinates:
    call Radar_AllowIRQ
    IF RADAR_PLAYER_SPRITE
    call Radar_PlayerCoordinates
    ld hl,Radar_PlayerSAT
    ld de,$7600
    ld b,4
    call Sprite_Upload
    ENDIF
    ld a,RADAR_SAT_BANK
    ld ($7000),a
    ld a,(scroll_y)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    IF !RADAR_PLAYER_SPRITE
    ld d,h
    ld e,l
    ENDIF
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    IF !RADAR_PLAYER_SPRITE
    or a
    sbc hl,de               ; scroll *60 = *64 -*4
    ENDIF
    ld de,$8000
    add hl,de
    ld (Radar_CoordinateSource),hl
    IF RADAR_PLAYER_SPRITE
    ld de,4
    add hl,de
    ENDIF
    ld de,$7600+RADAR_MAP_SLOT*4
    ld b,12                 ; First radar band precedes every moving actor upload.
    jp Sprite_Upload
Radar_FinishCoordinates:
    call Radar_AllowIRQ
    ld a,RADAR_SAT_BANK
    ld ($7000),a
    ld hl,(Radar_CoordinateSource)
    push hl
    ld de,48+RADAR_MAP_SLOT*4
    add hl,de
    ld de,fuel_sat
    ld bc,12
    ldir
    call update_life_sat
    pop hl                   ; Body attributes stream directly from the ROM table.
    ld de,12+RADAR_MAP_SLOT*4
    add hl,de
    ld de,$760c+RADAR_MAP_SLOT*4
    ld b,48
    jp Sprite_Upload

    IF RADAR_PLAYER_SPRITE
Radar_PlayerCoordinates:
    ld hl,(hud_player_x)
    ld (point_x),hl
    ld (Radar_PlayerPoint),hl
    xor a
    ld (Radar_PlayerVisible),a
    ld a,l
    cp 255
    jr z,.hidden
    ld a,1
    ld (Radar_PlayerVisible),a
    ld a,h
    add a,RADAR_Y-1
    ld hl,scroll_y
    add a,(hl)
    ld b,RADAR_PLAYER_PATTERN
    cp 216
    jr nz,.position
    dec a
    ld b,RADAR_PLAYER_PATTERN+4
    jr .position
.hidden:
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.safe_hidden
    inc a
.safe_hidden:
    ld b,RADAR_PLAYER_PATTERN
.position:
    ld (Radar_PlayerSAT),a
    ld a,(point_x)
    add a,RADAR_X
    ld (Radar_PlayerSAT+1),a
    ld a,b
    ld (Radar_PlayerSAT+2),a
    xor a
    ld (Radar_PlayerSAT+3),a
    ; Original routine $0300 chooses white/black dot codes on an eight-tick
    ; cadence. Retain that native clock at either display refresh frequency.
    ld a,(player_native_ticks)
    and 8
    ld a,WHITE
    jr z,.color
    ld a,BLACK
.color:
    ld (Radar_PlayerColor),a
    ld hl,Radar_PlayerColorDrawn
    cp (hl)
    ret z
    ld (hl),a
    or $20
    ld hl,Radar_PlayerColors
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    ld hl,Radar_PlayerColors
    ld de,$7400
    ld b,3                  ; Only these rows can contain either resident mask.
    jp Sprite_Upload
    ENDIF

; D/E = 2x2 anchor. Every anchor maps to at most four cells, precomputed in ROM.
Radar_Mark:
    ld a,d
    cp 255
    ret z
    ld b,a
    ld a,e
    rrca
    ld c,a
    and $1f
    or $80
    ld h,a
    ld a,c
    and $80
    ld l,a
    ld a,b
    add a,a
    or l
    ld l,a
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld hl,(Radar_Dirty)
    ld a,l
    or e
    ld l,a
    ld a,h
    or d
    ld h,a
    ld (Radar_Dirty),hl
    ret

; Native flag updates already built a bare frame/flag cell in point_buffer.
Radar_CacheCell:
    call Radar_BaseAddress
    ex de,hl
    ld hl,point_buffer
    ld bc,32
    ldir
    ret
Radar_BaseAddress:
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Radar_Base
    add hl,de
    ret

; The current board has at most two flags touching any cell. Precomputed exact
; frame/flag subsets avoid rescanning and plotting all20 HUD slots on removal.
    IF !FULL_GAME
Radar_RebuildBase:
    ld a,RADAR_CACHE_BANK
    ld ($7000),a
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    ld de,Radar_FlagOffsets
    add hl,de
    ld a,(hl)
    inc hl
    call Radar_FlagVisible
    ld c,a
    ld a,(hl)
    call Radar_FlagVisible
    add a,a
    or c
    push af
    ld a,(hud_cell)
    ld l,a
    ld h,0
    ld de,Radar_WorkVisibility
    add hl,de
    pop af
    ld (hl),a
    rlca
    rlca
    rlca
    rlca
    rlca
    ld c,a
    ld a,(hud_cell)
    rrca
    ld h,a
    and 128
    or c
    ld l,a
    ld a,h
    and 7
    or $a0
    ld h,a
    ld de,point_buffer
    ld bc,32
    ldir
    call Radar_CacheCell
    jp Radar_RenderCell
Radar_FlagVisible:
    cp 255
    jr z,.hidden
    IF HUD_ALERTS
    cp RADAR_SPECIAL_FLAG_OFFSET
    jr nz,.ordinary
    ld a,(radar_clock)
    and 32
    jr nz,.hidden
    ld a,RADAR_SPECIAL_FLAG_OFFSET
.ordinary:
    ENDIF
    push hl
    ld l,a
    ld h,0
    ld de,hud_flags
    add hl,de
    ld a,(hl)
    cp 255
    ld a,0
    jr z,.done
    inc a
.done:
    pop hl
    ret
.hidden:
    xor a
    ret
Radar_FlagOffsets:
    INCBIN "radar-cell-flag-offsets.bin"
    ENDIF

Radar_RenderCell:
    call Radar_AllowIRQ
    ld hl,Radar_CellsWork
    inc (hl)
    IF ENEMY_COUNT >= 2
    ; Compose in the final queued payload. A second 80-byte RAM copy need not
    ; sit between native movement and the remaining terrain cache budget.
    call Radar_BufferAddress
    ld (Radar_DrawBuffer),hl
    ld de,32
    add hl,de
    ld (Radar_DrawShift),hl
    add hl,de
    ld (Radar_DrawColors),hl
    ENDIF
    call Radar_BaseAddress
    IF ENEMY_COUNT >= 2
    ld de,(Radar_DrawBuffer)
    ELSE
    ld de,point_buffer
    ENDIF
    ld bc,32
    ldir
    ld a,(hud_cell)
    add a,a
    ld l,a
    ld h,0
    ld de,Radar_Origins
    add hl,de
    ld a,(hl)
    ld (hud_cell_x),a
    inc hl
    ld a,(hl)
    ld (hud_cell_y),a
    IF ENEMY_COUNT >= 2
    ld hl,(Radar_DrawColors)
    ld d,h
    ld e,l
    inc de
    ELSE
    ld hl,Radar_Colors
    ld de,Radar_Colors+1
    ENDIF
    ld bc,15
    ld (hl),WHITE|$20
    ldir
    ld hl,Radar_Last+2
    IF FULL_GAME
    ld b,7
    ELSE
    ld b,2
    ENDIF
.enemy:
    ld d,(hl)
    inc hl
    ld e,(hl)
    inc hl
    push hl
    push bc
    ld a,RED|$20
    call Radar_Plot
    pop bc
    pop hl
    djnz .enemy
    IF !RADAR_PLAYER_SPRITE
    ld a,(Radar_Last)
    ld d,a
    ld a,(Radar_Last+1)
    ld e,a
    ld a,BLACK|$20
    call Radar_Plot
    ENDIF
    ; Prepare the sentinel phase in RAM. All subsequent transfers can use
    ; the same short atomic packets, including before the header split.
    IF ENEMY_COUNT >= 2
    ld hl,(Radar_DrawBuffer)
    ld de,(Radar_DrawShift)
    ELSE
    ld hl,point_buffer
    ld de,point_buffer+32
    ENDIF
    xor a
    ld (de),a
    inc de
    ld bc,15
    ldir
    inc hl
    xor a
    ld (de),a
    inc de
    ld bc,15
    ldir
    IF ENEMY_COUNT < 2
    call Radar_BufferAddress
    ex de,hl
    ld hl,point_buffer
    ld bc,64
    ldir
    ld hl,Radar_Colors
    ld bc,16
    ldir
    ENDIF
    jp Radar_Commit

Radar_BufferAddress:
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,hl
    add hl,de
    ld de,Radar_Payloads
    add hl,de
    ret
Radar_Commit:
    ld a,(hud_cell)
    ld l,a
    ld h,0
    IF FULL_GAME
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ELSE
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ENDIF
    ld de,Radar_StagedPoints
    add hl,de
    ex de,hl
    ld hl,Radar_Last
    IF FULL_GAME
    ld bc,16
    ELSE
    ld bc,6
    ENDIF
    ldir
    ld a,(hud_cell)
    ld l,a
    ld h,0
    ld de,Radar_WorkVisibility
    add hl,de
    ld a,(hl)
    ld de,Radar_StagedVisibility-Radar_WorkVisibility
    add hl,de
    ld (hl),a
    call Radar_CellBit
    ld hl,(Radar_Dirty)
    ld a,e
    cpl
    and l
    ld l,a
    ld a,d
    cpl
    and h
    ld h,a
    ld (Radar_Dirty),hl
    ld hl,(Radar_Ready)
    ld a,l
    or e
    ld l,a
    ld a,h
    or d
    ld h,a
    ld (Radar_Ready),hl
    di
    ret

; A cell is uploaded only after its last raster line. The CPU state that
; describes the visible points advances at the next frame boundary.
Radar_WaitPublish:
    IF PLAYER_FAST_BLITTER
    ; Retain terrain priority in this unaccepted integration experiment.
    ld a,(row_left)
    ld hl,column_left
    or (hl)
    ret nz
    ENDIF
    IF STAGE_TILE_STRIPS || SMOKE_RUNTIME
    ld a,(Stage_GuardClosed)
    or a
    ret nz                  ; A late native tick may already have crossed VBlank.
    ENDIF
    ld hl,(Radar_Ready)
    ld a,h
    or l
    ret z
    IF ENEMY_COUNT >= 2 || SMOKE_RUNTIME
    ld a,(Radar_Initializing)
    or a
    jr nz,.wait
    ld a,(paused)
    or a
    jr nz,.wait
    ld a,(row_left)
    ld hl,column_left
    or (hl)
    jr z,.wait
    ld a,(Radar_PublishAge)
    cp 2
    jr nc,.wait
    inc a
    ld (Radar_PublishAge),a
    cp 2
    ret c                    ; Share busy frames with terrain; never starve radar.
    ENDIF
.wait:
    di
    IF STAGE_TILE_STRIPS || SMOKE_RUNTIME
    ld a,(Stage_GuardClosed)
    or a
    ret nz                  ; Never sleep into the next frame's radar window.
    ENDIF
    ld a,(Radar_Scanned)
    cp 2
    ret z                    ; Retain payloads if native work used the safe window.
    or a
    jr nz,.ready
    ei
    halt
    jr .wait
.ready:
    di
    jp Radar_PublishReady

Radar_PublishReady:
    call Radar_AllowIRQ
    ld a,1
    ld (Radar_PublishBudget),a
    ld a,(Radar_Initializing)
    or a
    jr nz,.initial
    ld a,(paused)
    or a
    jr nz,.budget_ready
    ld hl,(player_rate)
    ld de,PLAYER_RATE
    add hl,de
    jr nc,.budget_ready
    di
    ret                     ; preserve CPU room for the predicted second tick
.initial:
    ld a,12
    ld (Radar_PublishBudget),a
.budget_ready:
    ld hl,(Radar_Ready)
    ld a,h
    or l
    jr z,.done
    ld a,(Radar_PublishCursor)
    ld (Radar_PublishCell),a
    ld b,a
    or a
    jr z,.rotated
.rotate:
    srl h
    rr l
    jr nc,.rotate_next
    set 3,h
.rotate_next:
    djnz .rotate
.rotated:
    ld a,12
    ld (Radar_PublishChecked),a
.cell:
    ld a,(Radar_PublishBudget)
    or a
    jr z,.done
    srl h
    rr l
    jr nc,.skip
    push hl
    ld a,(Radar_PublishCell)
    ld (hud_cell),a
    IF ENEMY_COUNT >= 2 || SMOKE_RUNTIME
    xor a
    ld (Radar_PublishAge),a
    ENDIF
    call Radar_UploadCell
    call Radar_AllowIRQ
    ld hl,Radar_PublishBudget
    dec (hl)
    pop hl
.skip:
    ld a,(Radar_PublishCell)
    inc a
    cp 12
    jr c,.scan_next
    xor a
.scan_next:
    ld (Radar_PublishCell),a
    ld (Radar_PublishCursor),a
    ld a,(Radar_PublishChecked)
    dec a
    ld (Radar_PublishChecked),a
    jr nz,.cell
.done:
    di
    ret

Radar_UploadCell:
    call Radar_BufferAddress
    push hl
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$78a0
    add hl,de
    ex de,hl
    pop hl
    ld b,32
    call Sprite_Upload
    push hl
    ld hl,$0160             ; shifted start is384bytes after normal start
    add hl,de               ; DE already advanced32bytes
    ex de,hl
    pop hl
    ld b,32
    call Sprite_Upload
    push hl
    ld a,(hud_cell)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$7400+RADAR_MAP_SLOT*16
    add hl,de
    ex de,hl
    pop hl
    ld b,16
    call Sprite_Upload
    call Radar_AllowIRQ       ; Metadata commits do not touch VDP control ports.
    ld a,(hud_cell)
    ld (Radar_PendingCell),a
    ld a,(Radar_Initializing)
    or a
    call nz,Radar_CommitPublished
    call Radar_CellBit
    ld hl,(Radar_Ready)
    ld a,e
    cpl
    and l
    ld l,a
    ld a,d
    cpl
    and h
    ld h,a
    ld (Radar_Ready),hl
    ret

Radar_CommitPublished:
    ld a,(Radar_PendingCell)
    cp 12
    ret nc
    ld (hud_cell),a
    ld a,255
    ld (Radar_PendingCell),a
    ld a,(hud_cell)
    ld l,a
    ld h,0
    IF FULL_GAME
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ELSE
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ENDIF
    ld de,Radar_StagedPoints
    add hl,de
    push hl
    ld de,Radar_PublishedPoints-Radar_StagedPoints
    add hl,de
    ex de,hl
    pop hl
    IF FULL_GAME
    ld bc,16
    ELSE
    ld bc,6
    ENDIF
    ldir
    ld a,(hud_cell)
    ld l,a
    ld h,0
    ld de,Radar_StagedVisibility
    add hl,de
    ld a,(hl)
    ld de,Radar_BaseVisibility-Radar_StagedVisibility
    add hl,de
    ld (hl),a
    ret

Radar_Plot:
    ld (Radar_PlotColor),a
    ld a,d
    cp 255
    ret z
    ld a,(hud_cell_x)
    ld c,a
    ld a,d
    sub c
    inc a
    cp 17
    ret nc
    ld a,(hud_cell_y)
    ld c,a
    ld a,e
    sub c
    inc a
    cp 16
    ret nc
    dec a
    ld (Radar_PointRow),a
    ld a,(hud_cell_x)
    ld c,a
    ld a,d
    sub c
    inc a
    add a,a
    ld l,a
    ld h,0
    ld de,Radar_PointMasks
    add hl,de
    ld b,(hl)
    inc hl
    ld c,(hl)
    ld a,(Radar_PointRow)
    inc a
    jr nz,.first_row
    xor a                    ; the upper pixel lies above the cell
    jr .single_row
.first_row:
    dec a
    cp 14
    jr z,.single_row         ; row15 is deliberately transparent
    ld l,a
    ld h,0
    IF ENEMY_COUNT >= 2
    ld de,(Radar_DrawBuffer)
    ELSE
    ld de,point_buffer
    ENDIF
    add hl,de
    ld a,(hl)
    or b
    ld (hl),a
    inc hl
    ld a,(hl)
    or b
    ld (hl),a
    ld de,15
    add hl,de
    ld a,(hl)
    or c
    ld (hl),a
    inc hl
    ld a,(hl)
    or c
    ld (hl),a
    jr .colors
.single_row:
    ld l,a
    ld h,0
    IF ENEMY_COUNT >= 2
    ld de,(Radar_DrawBuffer)
    ELSE
    ld de,point_buffer
    ENDIF
    add hl,de
    ld a,(hl)
    or b
    ld (hl),a
    ld de,16
    add hl,de
    ld a,(hl)
    or c
    ld (hl),a
.colors:
    ld a,(Radar_PointRow)
    ld b,3
    cp 255
    jr nz,.not_above
    xor a
    dec b
.not_above:
    cp 14
    jr nz,.color_start
    dec b
.color_start:
    ld l,a
    ld h,0
    IF ENEMY_COUNT >= 2
    ld de,(Radar_DrawColors)
    ELSE
    ld de,Radar_Colors
    ENDIF
    add hl,de
    ld a,(Radar_PlotColor)
.color:
    ld (hl),a
    inc hl
    djnz .color
    ret
Radar_PointMasks:
    db $80,0,$c0,0,$60,0,$30,0,$18,0,$0c,0,$06,0,$03,0
    db $01,$80,0,$c0,0,$60,0,$30,0,$18,0,$0c,0,$06,0,$03,0,$01

; Each atomic packet is at most16data bytes. No VRAM pointer spans an ISR.
Radar_Pointer:
    vdp_write 14,7
    ld a,e
    out ($99),a
    ld a,d
    or $40
    out ($99),a
    ret
Radar_Write16:
    push de
    ld a,d
    or $40
    ld d,a
    ld b,16
    call Sprite_Upload
    pop de
    ret
Radar_AllowIRQ:
    ld a,(Radar_Initializing)
    or a
    ret nz
    ei
    nop
    ret
Radar_ServiceIRQ:
    call Radar_AllowIRQ
    di
    ret
Radar_Next16:
    ld a,e
    add a,16
    ld e,a
    ld a,d
    adc a,0
    ld d,a
    ret
Radar_Origins:
    db 0,254,16,255,32,0,0,13,16,14,32,15
    db 0,28,16,29,32,30,0,43,16,44,32,45
