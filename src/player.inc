; Native movement adapter. Original-derived code/pixels are linked only from local ROMs.
; The renderer retains interrupt, mapper and VRAM ownership. See docs/player.md.
driving EQU $c400
last_enter EQU $c401
player_rate EQU $c402
player_animation EQU $c404
player_x EQU $c405
player_y EQU $c407
player_drawn EQU $c409
player_index EQU $c40a
player_sat EQU $c410
player_patch_valid EQU $c418
player_patch_x EQU $c419
player_patch_y EQU $c41b
player_patch_saved EQU $c420
player_patch_data EQU $c430
player_patch_mode EQU $c43a
player_patch_count EQU $c43b
player_patch_byte EQU $c43c
player_native_ticks EQU $c440
player_phase EQU $c44f
player_pending_x EQU $c450
player_pending_y EQU $c452
frame_tick EQU $c456
player_patch_work EQU $c471
player_steps EQU $c472

Player_Init:
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a000
    ld de,$e000
    ld bc,4096
    ldir
    ld a,PLAYER_BANK
    ld ($7000),a
    call $8c6c               ; Original player initialization.
    ld hl,($e027)
    ld ($e069),hl           ; Begin running upward at the original forward speed.
    ld ($e02d),hl
    xor a
    ld (player_rate),a
    ld (player_rate+1),a
    ld (player_animation),a
    ld (player_patch_valid),a
    ld (player_native_ticks),a
    ld (player_native_ticks+1),a
    inc a
    ld (player_steps),a
    ld a,255
    ld (player_drawn),a
    ld (player_phase),a
    call Player_Position
    jp Player_Apply

Player_Update:
    ld a,(driving)
    or a
    jp z,stage_move
    call Player_Apply
    jp HUD_Tick

; Advance the next simulation state after the header. Presentation consumes it
; next refresh, keeping native wall probes outside the header's hard deadline.
Player_Advance:
    ld a,(driving)
    or a
    ret z
    ld a,(paused)
    or a
    ret nz
    call Player_Input
    ld a,PLAYER_BANK
    ld ($7000),a
    ld a,1
    ld (player_steps),a
    ei                       ; Raster handlers preserve native registers/RAM/bank.
    nop
    call Player_Tick
    ld hl,(player_rate)
    ld de,PLAYER_RATE
    add hl,de
    ld (player_rate),hl
    jr nc,.ticked
    ld a,2
    ld (player_steps),a
    call Player_Tick
.ticked:
    di
    jp Player_Position

Player_Tick:
    call $8069               ; Original fractional movement, then steering/wall probes.
    call $9052
    ld hl,player_animation
    inc (hl)
    ld a,(hl)
    cp 4
    jr c,.done
    ld (hl),0
    call $9ddf              ; Original twelve-angle steering animation.
.done:
    ld hl,(player_native_ticks)
    inc hl
    ld (player_native_ticks),hl
    ret

Player_Input:
    ; Native active-low joystick bits: up/down/right/left = 5/4/3/2.
    ld b,255
    ld a,(dy)
    or a
    jr z,.horizontal
    jp m,.up
    res 4,b
    jr .horizontal
.up:
    res 5,b
.horizontal:
    ld a,(dx)
    or a
    jr z,.done
    jp m,.left
    res 3,b
    jr .done
.left:
    res 2,b
.done:
    ld a,b
    ld ($e3f0),a
    ret

Player_Position:
    ld a,($e070)            ; Cell X, signed pixel offset X.
    ld hl,$e06d
    call Player_Axis
    ld (player_pending_x),hl
    ld a,($e072)            ; Cell Y grows downward; native offset grows upward.
    ld hl,$e06f
    call Player_AxisY
    ld (player_pending_y),hl
    ret
Player_Apply:
    ld hl,(player_pending_x)
    ld (player_x),hl
    ld de,-VIEWPORT_HALF
    add hl,de
    ld (world_x),hl
    ld hl,(player_pending_y)
    ld (player_y),hl
    ld de,-105
    add hl,de
    ld (world_y),hl
    ret
Player_AxisY:
    ld c,(hl)
    ld h,0
    ld l,a
    call Player_Cell
    ld a,c
    neg
    jr Player_Offset
Player_Axis:
    ld c,(hl)
    ld h,0
    ld l,a
    call Player_Cell
    ld a,c
Player_Offset:
    ld e,a
    ld d,0
    bit 7,a
    jr z,.positive
    dec d
.positive:
    add hl,de
    ret
Player_Cell:
    add hl,hl
    add hl,hl
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,36                 ; 24-pixel flower border + native cell centre.
    add hl,de
    ret

Player_Radar:
    ld a,(driving)
    or a
    jp z,stage_radar
    ld hl,(player_x)
    call stage_div8
    ld de,player_radar_x
    add hl,de
    ld b,(hl)
    ld hl,(player_y)
    call stage_div8
    ld de,player_radar_y
    add hl,de
    ld c,(hl)
    jp HUD_SetPlayer

Player_Draw:
    ld a,(driving)
    or a
    ret z
    ld a,(scroll_y)
    add a,107
    cp 216
    ld a,0
    jr nz,.phase
    inc a
.phase:
    ld c,a
    ld a,(player_phase)
    cp c
    jr nz,.changed
    ld a,($e077)            ; Original animation/flip byte.
    ld b,a
    ld a,(player_drawn)
    cp b
    jr z,.attributes
.changed:
    ld a,c
    ld (player_phase),a
    ld a,($e077)
    ld (player_drawn),a
    ld l,a
    ld h,0
    ld de,player_flags
    add hl,de
    ld a,(hl)
    cp 12
    ret nc
    ld (player_index),a
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl                ; 128 bytes: two planes, normal and shifted phases.
    ld de,$8000
    add hl,de
    ld a,(player_phase)
    or a
    jr z,.source
    ld de,64
    add hl,de
.source:
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    vdp_write 14,7
    ld a,$a0
    out ($99),a
    ld a,$7d
    out ($99),a
    ld bc,$4098
    otir
.attributes:
    ld a,(scroll_y)
    add a,107                ; Logical centre=(132,116); fixed R18 centres at128.
    ld b,180
    cp 216
    jr nz,.safe
    dec a
    ld b,180
.safe:
    ld hl,player_sat
    ld (hl),a
    inc hl
    ld (hl),PLAYER_X
    inc hl
    ld (hl),b
    inc hl
    ld (hl),0
    inc hl
    ld (hl),a
    inc hl
    ld (hl),PLAYER_X
    inc hl
    ld a,b
    add a,4
    ld (hl),a
    inc hl
    ld (hl),0
    vdp_write 14,7
    ld a,PLAYER_SLOT*4        ; Replace HUD terminator with car slots 17/18.
    out ($99),a
    ld a,$76
    out ($99),a
    ld hl,player_sat
    ld bc,$0898
    otir
    ld a,216                 ; Slot 19 terminates the thirteen free SAT slots.
    out ($98),a
    ret

; Restore the previous one-row patch, then complete the shifted full-height car.
; Runs just after the header split, before the car's fixed screen band (108..123).
Player_Patch:
    xor a
    ld (player_patch_work),a
    ld a,(player_patch_valid)
    or a
    jr z,.current
    ld a,1
    ld (player_patch_work),a
    ld hl,player_patch_saved
    call Player_WriteRow
    xor a
    ld (player_patch_valid),a
.current:
    ld a,(driving)
    or a
    ret z
    ld a,(scroll_y)
    add a,107
    cp 216
    ret nz
    ld a,1
    ld (player_patch_work),a
    ld hl,(player_x)
    ld de,-8
    add hl,de
    ld (player_patch_x),hl
    ld a,l
    and 1
    add a,8
    ld (player_patch_count),a
    ld hl,(player_y)
    ld a,l
    add a,7
    ld (player_patch_y),a
    xor a
    ld (player_patch_mode),a
    ld (player_patch_byte),a
    ld hl,player_patch_saved
.read:
    call Player_RowPointer
    nop
    nop
    in a,($98)
    ld (hl),a
    inc hl
    ld a,(player_patch_byte)
    inc a
    ld (player_patch_byte),a
    ld b,a
    ld a,(player_patch_count)
    cp b
    jr nz,.read
    ld hl,player_patch_saved
    ld de,player_patch_data
    ld bc,9
    ldir
    ld a,(player_index)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$8600
    add hl,de
    ex de,hl
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,player_patch_data
    ld a,(player_patch_x)
    and 1
    ld c,a
    ld b,16
.pixel:
    ld a,(de)
    inc de
    or a
    jr z,.advance
    push bc
    ld b,a
    ld a,c
    or a
    jr nz,.low
    ld a,b
    rlca
    rlca
    rlca
    rlca
    ld b,a
    ld a,(hl)
    and 15
    or b
    jr .paint
.low:
    ld a,(hl)
    and $f0
    or b
.paint:
    ld (hl),a
    pop bc
.advance:
    ld a,c
    xor 1
    ld c,a
    jr nz,.next_pixel
    inc hl
.next_pixel:
    djnz .pixel
    ld hl,player_patch_data
    call Player_WriteRow
    ld a,1
    ld (player_patch_valid),a
    ret
Player_WriteRow:
    ld a,$40
    ld (player_patch_mode),a
    xor a
    ld (player_patch_byte),a
.byte:
    call Player_RowPointer
    ld a,(hl)
    out ($98),a
    inc hl
    ld a,(player_patch_byte)
    inc a
    ld (player_patch_byte),a
    ld b,a
    ld a,(player_patch_count)
    cp b
    jr nz,.byte
    ret
Player_RowPointer:
    push hl
    ld hl,(player_patch_x)
    srl h
    rr l
    ld a,(player_patch_byte)
    add a,l
    ld e,a
    ld a,(player_patch_y)
    ld d,a
    ld a,e
    and $80
    rlca
    add a,a
    ld b,a
    ld a,d
    rlca
    and 1
    or b
    ld b,14
    call register
    ld a,e
    and $7f
    ld e,a
    ld a,d
    rrca
    and $80
    or e
    out ($99),a
    ld a,d
    rrca
    and $3f
    ld b,a
    ld a,(player_patch_mode)
    or b
    out ($99),a
    pop hl
    ret
player_flags:
    INCBIN "player-flags.bin"
player_radar_x:
    INCBIN "player-radar-x.bin"
player_radar_y:
    INCBIN "player-radar-y.bin"
