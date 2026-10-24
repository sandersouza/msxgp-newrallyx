; Stage 07: single-player life loss, same-round restart and stopped zero-life run.
    IF INCREMENTAL_STAGE >= 7
Life_State EQU $c5c0          ; 0 active/hold, 1 reloading, 2 game over
Life_Restarting EQU $c5c1
Life_Deaths EQU $c5c2
Death_Limit EQU $c496
Life_Init:
    xor a
    ld (Life_State),a
    ld (Life_Restarting),a
    ld (Life_Deaths),a
    ret
Life_Begin:
    call $98da              ; original active-game decrement, before 2P dispatch
    ld hl,Life_Deaths
    inc (hl)
    ld a,3
    ld ($e020),a
    ld a,($e00f)
    or a
    ld a,120
    jr nz,.limit
    ld a,96                 ; source $a0 counter increments to zero
.limit:
    ld (Death_Limit),a
    ret
Player_RestartNative:
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a025
    ld de,$e025
    ld bc,8
    ldir                    ; original first-stage movement parameters
    ld a,PLAYER_BANK
    ld ($7000),a
    call $88e7              ; original RAM-only fuel/empty/smoke reset prefix
    call Fuel_Init
    ld a,1
    ld ($e28b),a            ; explicit immediate active phase, no arcade intro
    ld ($e020),a
    xor a
    ld ($e2d0),a            ; original per-life high-score display latch reset
    ld (Rock_Contact),a
    call Death_Init
    jp Player_Init.native   ; original car init resets special/life ordinal only
Life_Publish:
    IF HUD_ENABLED
    ld a,($e00f)
    or a
    jr z,.set
    dec a
    cp 10
    jr c,.set
    ld a,9
.set:
    jp HUD_SetLives
    ELSE
    ret
    ENDIF
Life_Flags:
    IF HUD_ENABLED
    ld ix,Flag_Records+3
    ld hl,Flag_Active+1
    ld d,10
.next:
    ld a,(hl)
    or a
    jr nz,.active
    push hl
    push de
    ld a,(ix+0)
    ld bc,$ffff
    call HUD_SetFlag
    pop de
    pop hl
.active:
    inc hl
    ld bc,6
    add ix,bc
    dec d
    jr nz,.next
    ENDIF
    ret
Life_Frame:
    ld a,(driving)
    or a
    ret z
    IF FULL_GAME
    ld a,(Full_Attract)
    or a
    ret nz
    ENDIF
    call Life_Publish
    ld a,(Death_State)
    cp 2
    ret nz
    ld a,(Death_Jobs)
    or a
    ret nz
    ld a,(Life_State)
    or a
    ret nz
    IF FULL_GAME
    ld a,SESSION_BANK
    ld ($7000),a
    call $b812
    cp 1
    jp z,Full_NextRound
    cp 3
    jr nz,.turn_selected
    ld a,2
    ld (Full_Loading),a
    jr .restart
.turn_selected:
    cp 2
    jr nz,.restart
    ELSE
    ld a,($e00f)
    or a
    jr nz,.restart
    ENDIF
    ld a,2
    ld (Life_State),a
    xor a
    ld ($e020),a
    ret
.restart:
    ld a,1
    ld (Life_State),a
    ld (Life_Restarting),a
    call show_scene          ; bounded reload; gameplay/collection RAM retained
    xor a
    ld (Life_Restarting),a
    ld (Life_State),a
    ret
    ENDIF
