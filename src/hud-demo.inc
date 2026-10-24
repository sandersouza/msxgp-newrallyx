; Keyboard diagnostic producer; never include this file in the original-game adapter.
read_keys:
    ld c,a
    in a,($aa)
    and $f0
    or c
    out ($aa),a
    in a,($a9)
    cpl
    ret
keys:
    IF SMOKE_RUNTIME
    ld a,6
    call read_keys
    and 2                   ; Ctrl: active-low native smoke input bit1.
    ld (Smoke_Key),a
    ENDIF
    ld a,8
    call read_keys
    ld (key8),a
    IF SESSION_RUNTIME
    and 1
    add a,a
    ld hl,Smoke_Key
    or (hl)                 ; Space is primary smoke; Ctrl remains an alias.
    ld (hl),a
    ld a,4
    call read_keys
    and 32                  ; P pauses; Space remains available during gameplay.
    ELSE
    and 1
    ENDIF
    ld b,a
    ld a,(last_space)
    xor b
    and b
    ld a,b
    ld (last_space),a
    jr z,.no_pause
    ld a,(paused)
    xor 1
    ld (paused),a
.no_pause:
    IF !SESSION_RUNTIME
    ld a,7
    call read_keys
    and 128
    ld b,a
    ld a,(last_enter)
    xor b
    and b
    ld a,b
    ld (last_enter),a
    jr z,.no_enter
    ld a,(driving)
    xor 1
    ld (driving),a
    xor a
    ld (scene),a
    call show_scene
    ENDIF
.no_enter:
    ld a,(key8)
    and 2
    ld b,a
    ld a,(last_home)
    xor b
    and b
    ld a,b
    ld (last_home),a
    call nz,show_scene
    xor a
    call read_keys
    ld (key0),a
    and $3e
    ld b,a
    ld a,(last_scene)
    xor b
    and b
    ld a,b
    ld (last_scene),a
    jr z,.no_scene
    rrca
    ld c,0
.scene_bit:
    rrca
    jr c,.select
    inc c
    jr .scene_bit
.select:
    ld a,(driving)
    or a
    jr nz,.no_scene
    ld a,c
    ld (scene),a
    call show_scene
.no_scene:
    ld a,(key0)
    and 1
    ld b,a
    ld a,(last_zero)
    xor b
    and b
    ld a,b
    ld (last_zero),a
    jr z,.no_life
    IF INCREMENTAL_STAGE >= 7
    ld a,(driving)
    or a
    jr nz,.no_life
    ENDIF
    ld a,(lives)
    inc a
    cp 10
    jr c,.set_lives
    xor a
.set_lives:
    call HUD_SetLives
.no_life:
    ld a,(key0)
    bit 6,a
    jr z,.not_six
    ld a,2
    ld (cadence),a
.not_six:
    ld a,(key0)
    bit 7,a
    jr z,.not_seven
    ld a,3
    ld (cadence),a
.not_seven:
    ld a,1
    call read_keys
    bit 0,a
    jr z,.not_eight
    ld a,4
    ld (cadence),a
.not_eight:
    ld a,1
    call read_keys
    and 2
    ld b,a
    ld a,(last_nine)
    xor b
    and b
    ld a,b
    ld (last_nine),a
    jr z,.no_score
    ld a,(score_goal)
    cp 31
    jr nc,.no_score
    inc a
    ld (score_goal),a
.no_score:
    ld a,3
    call read_keys
    and 8                     ; F: full -> 3/4 -> 1/2 -> 1/4 -> empty -> full
    ld b,a
    ld a,(last_f)
    xor b
    and b
    ld a,b
    ld (last_f),a
    jr z,.no_fuel
    IF INCREMENTAL_STAGE >= 6
    ld a,(driving)
    or a
    jr nz,.no_fuel
    ENDIF
    ld a,(fuel_goal)
    inc a
    cp 5
    jr c,.fuel_level
    xor a
.fuel_level:
    ld (fuel_goal),a
    ld l,a
    ld h,0
    ld de,hud_demo_fuel_units
    add hl,de
    ld a,(hl)
    call HUD_SetFuel
.no_fuel:
    ld b,0
    ld a,(key8)
    bit 7,a
    jr z,.no_right
    inc b
.no_right:
    bit 4,a
    jr z,.no_left
    dec b
.no_left:
    ld a,b
    ld (dx),a
    ld b,0
    ld a,(key8)
    bit 6,a
    jr z,.no_down
    inc b
.no_down:
    bit 5,a
    jr z,.no_up
    dec b
.no_up:
    ld a,b
    ld (dy),a
    IF SESSION_RUNTIME
    jp Session_Joystick
    ELSE
    ret
    ENDIF


hud_demo_numbers:
    IFDEF HUD_COLLECTION_METER
    IF INCREMENTAL_STAGE >= 5
    ld a,(driving)
    or a
    ret nz
    ENDIF
    ENDIF
    ld a,(content_at)
    ld b,a
    ld a,(ticks)
    sub b
    ld b,a
    ld a,(cadence)
    cp b
    jr z,.due
    ret nc
.due:
    ld a,(ticks)
    ld (content_at),a
    ld a,(score_goal)
    ld b,a
    ld a,(score_state)
    cp b
    ret z
    inc a
    ld (score_state),a
    call hud_demo_number_address
    call HUD_SetScore
    ld a,(score_state)
    ld b,a
    ld a,(high_state)
    cp b
    ret nc
    ld a,b
    ld (high_state),a
    call hud_demo_number_address
    jp HUD_SetHiscore
hud_demo_number_address:
    IF STAGE_TILE_STRIPS
    push af
    ld a,HUD_BANK
    ld ($7000),a
    pop af
    ENDIF
    ld l,a
    ld h,0
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,hud_demo_digits
    add hl,de
    ret
hud_demo_sync_fuel:
    ld a,(fuel_goal)
    ld l,a
    ld h,0
    ld de,hud_demo_fuel_pixels
    add hl,de
    ld a,(hud_fuel_drawn)
    cp (hl)
    ret nz
    ld a,(fuel_goal)
    ld (fuel_state),a
    ret
hud_demo_fuel_units:
    db 54,40,27,13,0
hud_demo_fuel_pixels:
    db 30,22,15,7,0
    IF STAGE_TILE_STRIPS
hud_demo_digits EQU $bf00
    ELSE
hud_demo_digits:
    INCBIN "hud-demo-digits.bin"
    ENDIF

radar_enemies:
    INCBIN "radar-enemies.bin"


; Demonstration values belong to this producer, never to HUD_Init.
hud_demo_reset:
    IF STAGE_TILE_STRIPS
    ld a,HUD_BANK
    ld ($7000),a
    ENDIF
    ld hl,hud_demo_digits+4*6
    call HUD_SetHiscore
    ld a,2
    call HUD_SetLives
    ld a,54
    call HUD_SetFuel
    ld hl,hud_demo_initial_flags
    ld e,0
.flag:
    push de
    push hl
    ld b,(hl)
    inc hl
    ld c,(hl)
    ld a,e
    call HUD_SetFlag
    pop hl
    pop de
    inc hl
    inc hl
    inc e
    ld a,e
    cp 10
    jr c,.flag
    ret
hud_demo_initial_flags:
    INCBIN "hud-demo-flags.bin"
