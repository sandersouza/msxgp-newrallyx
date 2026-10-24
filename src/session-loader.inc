; Cold session hooks fit in the resident bank. UI code executes at B800.
Session_State EQU $c7d0       ; 0 gameplay, 1 title, 2 game over, 3 round clear
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
    ret
Session_VBlank:
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
    ld a,SESSION_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$2a00
    jp upload

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
