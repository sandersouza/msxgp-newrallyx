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
    IF FULL_GAME
    ld a,(Full_Loading)
    cp 2
    jr nz,.not_restoring
    ld a,PLAYER_BANK
    ld ($7000),a
    call $ae06
    call Full_RestoreFlagCells
    jp Player_RestartNative
.not_restoring:
    ENDIF
    IF INCREMENTAL_STAGE >= 7
    ld a,(Life_Restarting)
    or a
    jp nz,Player_RestartNative
    ENDIF
    IF FULL_GAME
    ld a,(Full_Loading)
    or a
    jr z,.fresh
    ld a,PLAYER_BANK
    ld ($7000),a
    call $ae03
    jr .systems
.fresh:
    ENDIF
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a000
    ld de,$e000
    ld bc,4096
    ldir
    IF FULL_GAME
    call Full_CopyPresentation
    ENDIF
    ld a,PLAYER_BANK
    ld ($7000),a
    IF FULL_GAME
    call $ae00
.systems:
    ENDIF
    IF INCREMENTAL_STAGE >= 2
    call Rock_Init
    ENDIF
    IF INCREMENTAL_STAGE >= 3
    call Death_Init
    ENDIF
    IF INCREMENTAL_STAGE >= 4
    call Flag_Init
    ENDIF
    IF INCREMENTAL_STAGE >= 5
    call Score_Init
    ENDIF
    IF INCREMENTAL_STAGE >= 6
    call Fuel_Init
    ENDIF
    IF INCREMENTAL_STAGE >= 7
    call Life_Init
    ENDIF
.native:
    IF SMOKE_RUNTIME
    call Smoke_Init
    ENDIF
    IF COMPLETION_RUNTIME
    call $9b1f
    ld a,(Flag_Count)
    ld (Parameters_Seen),a
    ENDIF
    call $8c6c               ; Original player initialization.
    IF ENEMY_COUNT
    call Enemy_Init
    ENDIF
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
    IF AUDIO_ENABLED
    ld (Audio_NewScene),a
    ENDIF
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
    IF HUD_ENABLED
    jp HUD_Tick
    ELSE
    ret
    ENDIF

; Advance the next simulation state after the header. Presentation consumes it
; next refresh, keeping native wall probes outside the header's hard deadline.
Player_Advance:
    IF ENEMY_COUNT
    ld a,(driving)
    or a
    ret z
    ld a,(paused)
    or a
    ret nz
    ld a,(player_steps)
    IF FULL_GAME
    cp 2
    ret c
    dec a
    ld b,a
    ELSE
    cp 2
    ret nz
    ENDIF
    ld a,PLAYER_BANK
    ld ($7000),a
    ei
    nop
    IF FULL_GAME
.tick:
    push bc
    ENDIF
    call Player_Tick
    IF FULL_GAME
    pop bc
    djnz .tick
    ENDIF
    IF ENEMY_RENDER
    call Player_Position
    di
    ret
    ELSE
    di
    jp Player_Position
    ENDIF
    ELSE
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
    IF INCREMENTAL_STAGE >= 6
    xor a
    ld (Fuel_ConsumeWork),a
    ENDIF
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
    ENDIF

    IF ENEMY_COUNT
; Current scroll/SAT have already been prepared. Use the blank interval for the
; first tick; publish only pending world coordinates, as in the previous loop.
Player_AdvanceEarly:
    IF SESSION_RUNTIME
    ei                      ; Cache checks and input selection own no VDP latch.
    nop
    ENDIF
    ld a,(driving)
    or a
    ret z
    IF FULL_GAME
    call Full_ClockFrame
    ENDIF
    ld a,(paused)
    or a
    ret nz
    IF FULL_GAME
    ld a,1
    ld (player_steps),a
    xor a
    ld (Fuel_ConsumeWork),a
    call Player_Position      ; Snapshot the completed simulation, before new ticks.
    di
    ret
    ELSE
    IF SMOKE_RUNTIME
    xor a
    ld (player_steps),a
    call Smoke_CachePressure
    ret nz                  ; Keep this coherent scene while hidden guards catch up.
    ENDIF
    IF FULL_GAME
    ld a,(Full_ClockDue)
    or a
    ret z
    dec a
    ld (Full_ClockDue),a
    ENDIF
    call Player_Input
    ld a,PLAYER_BANK
    ld ($7000),a
    ld a,1
    ld (player_steps),a
    xor a
    ld (Fuel_ConsumeWork),a
    ei
    nop
    call Player_Tick
    IF FULL_GAME
    xor a                    ; The other physical tick runs after sealing.
    ld b,a
    ld a,(Full_ClockDue)
    sub b
    ld (Full_ClockDue),a
    ld a,b
    inc a
    ld (player_steps),a
    jr .ready
    ELSE
    ld hl,(player_rate)
    ld de,PLAYER_RATE
    add hl,de
    ld (player_rate),hl
    jr nc,.ready
    ENDIF
    ld a,2
    ld (player_steps),a
.ready:
    IF ENEMY_RENDER
    ; Pending coordinates are private to the foreground, never read by the
    ; raster ISR. Keep its header deadline serviceable through this RAM work.
    call Player_Position
    di
    ret
    ELSE
    di
    jp Player_Position
    ENDIF
    ENDIF

    ENDIF
Player_Tick:
    IF FULL_GAME
    ld hl,Full_LoopTicks      ; Count all native work in this presentation loop.
    inc (hl)
    call Full_TurboOn
    call $8f24              ; Original IRQ PRNG advances in active/hold/bonus phases.
    call $83fd              ; Original round phase clock shares the same tick.
    ENDIF
    IF COMPLETION_RUNTIME
    ld a,(Round_State)
    or a
    jr z,.round_active
    call Round_Tick
    jp Player_CountTick
.round_active:
    ENDIF
    IF INCREMENTAL_STAGE >= 3
    ld a,(Death_State)
    or a
    jr z,.alive
    call Death_Tick
    jr Player_CountTick
.alive:
    ENDIF
    IF INCREMENTAL_STAGE >= 6
    call Fuel_Tick
Player_AfterFuel:
    ld a,(Fuel_Active)
    or a
    jr nz,Player_CountTick
    ENDIF
    IF FULL_GAME
    ld a,(player_native_ticks)
    and 1
    jr z,.motion_tick
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_MSXIdleTick
.motion_tick:
    ENDIF
    IF ENEMY_COUNT
    call Enemy_PreMove
Player_AfterEnemyCleanup:
    ENDIF
    IF SMOKE_RUNTIME
    call Smoke_PreTick
    ENDIF
    IF SESSION_RUNTIME
    ld a,SESSION_BANK
    ld ($7000),a
    call $b80c
    ld a,PLAYER_BANK
    ld ($7000),a
    ENDIF
    IF FULL_GAME
    call Full_MSXPlayerSpeed
    ENDIF
    call $8069               ; Original fractional movement, then steering/wall probes.
    IF SMOKE_RUNTIME
    call Smoke_Tick
    ENDIF
    call $9052
    IF SESSION_RUNTIME
    ld a,(Session_GuardActive)
    or a
    call nz,Player_ValidateMotion
    ENDIF
    IF FULL_GAME
    call Full_MSXAnimationTick
    ELSE
    ld hl,player_animation
    inc (hl)
    ld a,(hl)
    cp 4
    jr c,.done
    ld (hl),0
    call $9ddf              ; Original twelve-angle steering animation.
.done:
    ENDIF
    IF ENEMY_COUNT
    call Enemy_AfterMove
    ENDIF
    IF INCREMENTAL_STAGE >= 2
    call Rock_Update
Player_AfterRock:
    ENDIF
    IF INCREMENTAL_STAGE >= 4
    IF ENEMY_CONTACT
    ld a,(Enemy_Contact)
    or a
    jr nz,Player_AfterFlag
    ENDIF
    call Flag_Update
Player_AfterFlag:
    ENDIF
    IF INCREMENTAL_STAGE >= 3
    call Death_Begin
Player_CountTick:
    ENDIF
    IF FULL_GAME
    xor a
    ld (Full_CellRejectedValid),a ; Rejections cannot survive native smoke/object changes.
    ENDIF
    ld hl,(player_native_ticks)
    inc hl
    ld (player_native_ticks),hl
    IF FULL_GAME
    jp Full_TurboOff
    ENDIF
    ret

Player_Input:
    IF FULL_GAME
    ld a,(Full_Attract)
    or a
    jr z,.human
    ld a,255
    ld ($e3f0),a
    ret
.human:
    ENDIF
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
    IF SESSION_RUNTIME
    ld a,SESSION_BANK
    ld ($7000),a
    ld a,b
    cpl
    and $3c
    call $b809               ; Four-way gate; caller maps PLAYER_BANK immediately.
    ENDIF
    IF SMOKE_RUNTIME
    ld a,(Smoke_Key)
    or a
    jr z,.smoke_input_done
    res 1,b
.smoke_input_done:
    ENDIF
    ld a,b
    ld ($e3f0),a
    ret

    IF SESSION_RUNTIME
; Rapid keyboard reversals can place both signed offsets across an inside
; corner. Reject only that position, using the original contact and wall map.
Player_ValidateMotion:
    call $9774
    ld a,d
    and 7
    add a,a
    add a,a
    add a,a
    ld c,a
    ld a,e
    rlca
    rlca
    rlca
    and 7
    or c
    ld c,a
    ld a,e
    and 31
    ld d,a
    ld e,c
    xor a
    call $94e0
    ret nc
    ld a,SESSION_BANK
    ld ($7000),a
    call $b80f
    ld a,PLAYER_BANK
    ld ($7000),a
    ret
    ENDIF

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
    IF FULL_GAME
    ld a,(Full_CacheReady)
    or a
    jp nz,Full_PlayerApply
    ld a,PLAYER_BANK
    ld ($7000),a
    jp $b60c
    ELSE
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
    ENDIF
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
    IF ENEMY_RENDER
    call HUD_SetPlayer
    IF RADAR_PLAYER_SPRITE
    ret                     ; Enemy_Prepare supplies this refresh's radar later.
    ELSE
    jp Enemy_Radar
    ENDIF
    ELSE
    jp HUD_SetPlayer
    ENDIF

Player_Draw:
    IF FULL_GAME
    call Full_TurboOff      ; Death redraw can follow pure terrain/actor work.
    ENDIF
    IF PLAYER_BLITTER
    IF INCREMENTAL_STAGE >= 9
    ld a,($e077)
    ld (player_drawn),a      ; Snapshot before the next original simulation tick.
    ENDIF
    ret                     ; HUD SAT terminator remains before the freed car slots.
    ELSE
    ld a,(driving)
    or a
    ret z
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    ENDIF
    IF INCREMENTAL_STAGE >= 3
    ld a,(Death_DisplayState)
    or a
    jr z,.visible
    IF ENEMY_RENDER
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.hidden_y
    inc a
.hidden_y:
    ld (player_sat),a
    ld (player_sat+4),a
    jp .publish
    ELSE
    vdp_write 14,7
    ld a,PLAYER_SLOT*4
    out ($99),a
    ld a,$76
    out ($99),a
    ld a,216
    out ($98),a
    ret
    ENDIF
.visible:
    ENDIF
    IF INCREMENTAL_STAGE >= 9 || TILE_MODE
    xor a                    ; Normal pixels; SAT Y uses a declared one-pixel bias.
    ELSE
    ld a,(scroll_y)
    add a,107
    cp 216
    ld a,0
    jr nz,.phase
    inc a
    ENDIF
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
    IF INCREMENTAL_STAGE >= 9
    ld de,$7da0
    ld b,64
    call Sprite_Upload
    ELSE
    vdp_write 14,7
    ld a,$a0
    out ($99),a
    ld a,$7d
    out ($99),a
    ld bc,$4098
    otir
    ENDIF
.attributes:
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    ENDIF
    ld a,(scroll_y)
.sat_value:
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
.publish:
    IF FULL_GAME
    ret                      ; Maze IRQ owns the complete player SAT pair.
    ELSE
    IF SPRITE_FLICKER
    ret
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    ld hl,player_sat
    ld de,$7600+PLAYER_SLOT*4
    ld b,8
    call Sprite_Upload
    IF !(RADAR_CELLS_ONLY && ENEMY_RENDER && (HUD_ENABLED || ENEMY_COUNT >= 2))
    ld a,216
    out ($98),a
    ENDIF
    ret
    ENDIF
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
    ENDIF

    ENDIF
; Restore the previous one-row patch, then complete the shifted full-height car.
; Runs just after the header split, before the car's fixed screen band (108..123).
Player_Patch:
    IF (INCREMENTAL_STAGE >= 9 || TILE_MODE) && !PLAYER_BLITTER
    ret
    ENDIF
    IF PLAYER_BLITTER
    jp Bitmap_Restore
    ELSE
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
    IF INCREMENTAL_STAGE >= 3
    ld a,(Death_DisplayState)
    or a
    ret nz
    ENDIF
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
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    ENDIF
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
    ENDIF
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
    IF INCREMENTAL_STAGE >= 9
    ei                      ; Address arithmetic is independent of the raster ISR.
    nop
    ENDIF
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
    IF INCREMENTAL_STAGE >= 9
    di                      ; Own the latch only for R14/address/data access.
    ENDIF
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
