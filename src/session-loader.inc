; Cold session hooks fit in the resident bank. UI code executes at B800.
Session_State EQU $c7d0       ; 0 game, 1 cast, 2 game over, 5 start, 6 select, 7 challenge
    IF FULL_GAME
Full_ChallengeBypass EQU $c7f0
Full_UIHeld EQU $c7f1
Full_UIEdges EQU $c7f2
Full_UIReveal EQU $dfe4
Full_UITimer EQU $dfe6
Full_UICastDone EQU $dfe7
Full_UIWidth EQU $dfe8
Full_UIRows EQU $dfe9
Full_UIDestination EQU $dfea
Full_UIRowDestination EQU $dfec
Full_UIBackground EQU $dfee
Full_UIForeground EQU $dfef
Full_UIPairs EQU Score_Old ; UI and gameplay score scratch never execute together.
    IF FLAG_POPUPS
Popup_Active EQU $dfe4
Popup_Pending EQU $dfe5
Popup_X EQU $dfe6
Popup_Y EQU $dfe7
Popup_Tick EQU $dfe8
Popup_Age EQU $dfe9
Popup_Column EQU $dfea
Popup_Source EQU $dfeb
Popup_Destination EQU $dfed
Popup_Bank EQU $dfef
Popup_Rows EQU $dff0
Popup_Width EQU $dff1
Sprite_UploadBank EQU $c7f3
Popup_Frame:
    ld a,(paused)
    or a
    jr nz,.idle
    ld a,(Popup_Active)
    ld hl,Popup_Pending
    or (hl)
    jr z,.idle
    ld a,(Popup_Active)
    or a
    jr z,.work
    ld a,(ticks)
    ld hl,Popup_Tick
    sub (hl)
    ld b,a
    ld a,(ticks)
    ld (hl),a
    ld a,(Popup_Age)
    add a,b
    ld (Popup_Age),a
    cp 45
    jr nc,.work
    ld a,(Popup_Pending)
    ld hl,Death_State
    or (hl)
    jr z,.idle               ; Steady labels need no ROM/mapper/VDP work.
.work:
    ld a,SESSION_BANK
    ld ($7000),a
    call $b81e
    ld a,PLAYER_BANK
    ld ($7000),a
    ld a,1
    ret
.idle:
    xor a
    ret
Popup_RestoreTile:
    call stage_tile.source   ; Forced owned cell, including smoke capture/publication.
    ld a,SESSION_BANK
    ld ($7000),a
    ret
    ENDIF
    ENDIF
Session_Drawn EQU $c7d1
Session_Credits EQU $c7d2
Session_Keys EQU $c7d3
Session_High EQU $c7d4        ; eight original high-score digits survive reload
Session_Edges EQU $c7dc
Session_Ready EQU $c7dd
Session_HeldDirections EQU $c7de
Session_SelectedDirection EQU $c7df
    IF FULL_GAME
Session_Digits EQU $d140
    ELSE
Session_Digits EQU $c7e0
    ENDIF
Session_WallBlocks EQU $c7e6
Session_RiskFrames EQU $c7e8
Session_GuardActive EQU $c7e9
Session_PositionIRQ EQU $c7ea
Session_Init:
    ld a,SESSION_BANK
    ld ($7000),a
    jp $b806
Session_Main:
    ld a,SESSION_BANK
    ld ($7000),a
    call $b800
    IF AUDIO_ENABLED
    push af
    call Audio_Work
    pop af
    ENDIF
    IF FULL_GAME
    cp 3
    jp z,Full_UIResumeChallenge
    ENDIF
    cp 2
    jp nz,main
    call show_scene
    ld a,SESSION_BANK
    ld ($7000),a
    call $b803
    ld a,(ticks)
    ld (frame_tick),a
    jp main
Session_Check:
    IF FULL_GAME
    ld a,7
    call read_keys
    and 2
    ld b,a
    ld a,(Full_DebugHeld)
    xor b
    and b
    ld c,a
    ld a,b
    ld (Full_DebugHeld),a
    ld a,c
    or a
    jr z,.debug_done
    ld a,SESSION_BANK
    ld ($7000),a
    call $b81b
    or a
    jp nz,Full_DebugNextRound
.debug_done:
    ld a,(Full_Attract)
    or a
    jr z,.active
    ld a,SESSION_BANK
    ld ($7000),a
    jp $b818
.active:
    ENDIF
    ld a,(Life_State)
    cp 2
    jr z,.finished
    ld a,(Round_State)
    cp 3
    ret nz
    IF FULL_GAME
    jp Full_NextRound
    ENDIF
.finished:
    ld (Session_State),a
    IF FULL_GAME
    ld a,(Session_Keys)
    ld (Full_UIHeld),a
    xor a
    ld (Full_UIEdges),a
    ENDIF
    IF AUDIO_ENABLED
    ld a,4                  ; Original two-part game-over song request.
    ld ($e9f5),a
    ENDIF
    ret
Session_VBlank:
    IF FULL_GAME
    push hl
    in a,($aa)
    push af
    xor a
    call read_keys
    ld b,a
    ld a,(Full_UIHeld)
    cpl
    and b
    ld hl,Full_UIEdges
    or (hl)
    ld (hl),a
    ld a,b
    ld (Full_UIHeld),a
    pop af
    out ($aa),a              ; Preserve an interrupted foreground keyboard read.
    pop hl
    ENDIF
    ld a,(ticks)
    inc a
    ld (ticks),a
    jp irq_return
Session_CopyImage:
    xor a
    out ($99),a
    ld a,$40
    out ($99),a
    ld a,SESSION_IMAGE_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$4000
    ei
    call upload
    ld a,SESSION_DATA_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$2a00
    IF FULL_GAME
    call upload
    ld a,SESSION_BANK
    ld ($7000),a
    ret
    ELSE
    jp upload
    ENDIF
    IF FULL_GAME
Full_UIResumeChallenge:
    ld a,3                   ; Restore video only; do not reset challenge velocities/placements.
    ld (Full_Loading),a
    ld a,255
    ld (player_drawn),a
    xor a
    ld (Score_HighValid),a
    call show_scene
    xor a
    ld (Full_Loading),a
    IF AUDIO_ENABLED
    inc a
    ld (Audio_NewScene),a
    ENDIF
    ld a,(Full_UIHeld)
    ld (Session_Keys),a
    xor a
    ld (Session_State),a
    ld (Session_Drawn),a
    ld a,(ticks)
    ld (frame_tick),a
    jp main
    ENDIF

; Merge joystick1 with the keyboard; restore the original PSG output latch.
Session_Joystick:
    ld a,(key0)
    ld b,a
    ld a,(Session_Keys)
    cpl
    and b
    ld c,a
    ld a,b
    ld (Session_Keys),a
    bit 5,c
    jr z,.read
    ld hl,Session_Credits
    inc (hl)
    jr nz,.credit
    dec (hl)
.credit:
    IF AUDIO_ENABLED
    ld a,$80
    ld ($e9f6),a
    ENDIF
    ld a,(hl)
    ld ($e024),a
.read:
    ld a,15
    out ($a0),a
    in a,($a2)
    ld c,a
    and $af
    or 3                    ; Port1 pin8 low, trigger pins6/7 released for input.
    out ($a1),a
    ld a,14
    out ($a0),a
    in a,($a2)
    cpl
    and $3f
    ld b,a
    ld a,15
    out ($a0),a
    ld a,c
    out ($a1),a
    ld hl,dy
    bit 0,b
    jr z,.down
    dec (hl)
.down:
    bit 1,b
    jr z,.left
    inc (hl)
.left:
    ld hl,dx
    bit 2,b
    jr z,.right
    dec (hl)
.right:
    bit 3,b
    jr z,.smoke
    inc (hl)
.smoke:
    bit 4,b
    jr z,Session_JoystickReturn
    ld a,1
    ld (Smoke_Key),a
Session_JoystickReturn:
    ld a,(key8)
    and $f0
    ld c,a
    dec a
    and c
    jr nz,.rollover
    ld a,b
    and 15
    ld c,a
    dec a
    and c
    jr nz,.rollover
    ld hl,Session_RiskFrames
    ld a,(hl)
    or a
    ret z
    dec (hl)
    ret
.rollover:
    ld a,8
    ld (Session_RiskFrames),a
    ret

    IF AUDIO_ENABLED
; Physical refreshes clock audio after packet readiness. Native ticks stay
; unchanged; the PSG sustains the preceding note while the renderer works.
Audio_Work:
    ld a,(ticks)
    ld hl,Audio_LastUI
    sub (hl)
    cp 2
    ret c
    srl a
    ld (Audio_Elapsed),a
    add a,a                 ; Retain an odd refresh instead of losing half a beat.
    add a,(hl)
    ld (hl),a
    ld a,AUDIO_BANK
    ld ($7000),a
    call Audio_RuntimeStep
Audio_WorkReturn:
    ld a,PLAYER_BANK
    ld ($7000),a
    ret
    ENDIF
