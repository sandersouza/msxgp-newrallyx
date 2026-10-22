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
    ; Cache shifts are queued once per tile; jobs write only hidden guard tiles.
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
    add a,47
    jr .column
.left:
    dec a
    ld (previous_x),a
    sub 16
.column:
    ld (column_x),a
    ld hl,(world_y)
    call stage_div8
    ld a,l
    sub 3
    ld (column_y),a
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
    add a,28
    jr .row
.up:
    dec a
    ld (previous_y),a
    sub 3
.row:
    ld (row_y),a
    ld hl,(world_x)
    call stage_div8
    ld a,l
    sub 16
    ld (row_x),a
    ld a,64
    ld (row_left),a
    ret
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
    ld b,22
    ld a,(player_steps)
    cp 2
    jr nz,.patch_budget
    ld b,16
.patch_budget:
    ld a,(player_patch_work)
    or a
    jr z,.next
    ld a,b
    sub 6
    ld b,a
.next:
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
    ld (row_x),a
    ld a,(row_y)
    ld (tile_y),a
    jr .draw
.column:
    dec a
    ld (column_left),a
    ld a,(column_x)
    ld (tile_x),a
    ld a,(column_y)
    ld (tile_y),a
    inc a
    ld (column_y),a
.draw:
    push bc
    call stage_tile
    pop bc
    ei
    nop
    di
    djnz .next
    ret

stage_load:
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
    sub 16
    ld (row_x),a
    ld hl,(world_y)
    call stage_div8
    ld a,l
    ld (previous_y),a
    sub 3
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

stage_tile:
    ld a,(driving)
    or a
    jr z,.source
    ld a,(cache_left)
    ld c,a
    ld a,(tile_x)
    sub c
    cp 64
    ret nc
    ld a,(cache_top)
    ld c,a
    ld a,(tile_y)
    sub c
    cp 32
    ret nc
.source:
    ld a,(driving)
    or a
    jp nz,stage_copy_tile
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
    ld hl,stage_command_template
    ld de,stage_command
    ld bc,15
    ldir
    vdp_write 14,4
    xor a
    out ($99),a
    ld a,$48
    out ($99),a
    ld hl,stage_atlas
    ld de,1024
    jp upload
stage_wait_command:
    vdp_write 15,2
.busy:
    in a,($99)
    and 1
    jr nz,.busy
    vdp_write 15,0
    ret
stage_copy_tile:
    ld a,(tile_x)
    ld c,a
    cp STAGE_COLUMNS
    jr nc,.flower
    ld a,(tile_y)
    cp STAGE_ROWS
    jr nc,.flower
    jr .id
.flower:
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
    call stage_wait_command  ; Prepare RAM packet while the previous copy executes.
    vdp_write 17,32
    ld hl,stage_command
    ld bc,$0f9b
    otir
    ret
stage_command_template:
    db 0,0,16,2,0,0,0,0,8,0,8,0,0,0,$d0
stage_atlas:
    INCBIN "stage-atlas.bin"
stage_cache_bounds:
    ld hl,(world_x)
    call stage_div8
    ld a,l
    sub 16
    ld (cache_left),a
    ld hl,(world_y)
    call stage_div8
    ld a,l
    sub 3
    ld (cache_top),a
    ret
stage_landmarks:
    INCBIN "stage-landmarks.bin"

stage_radar:
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
stage_radar_x:
    INCBIN "stage-radar-x.bin"
stage_radar_y:
    INCBIN "stage-radar-y.bin"
