; Banked UI only. Gameplay remains resident; original glyphs stay 8x8.
    jp Session_Frame
    jp Session_AfterStart
    jp Session_Reset
    jp Session_FourWay
    jp Session_SaveMotion
    jp Session_RestoreMotion
    IF FULL_GAME
    jp Full_SessionDeath
    jp Full_DrawRound
    jp Full_DemoFrame
    ENDIF

; Keep only movement/camera state. Fuel, score, enemy state and clocks still tick.
Session_SaveMotion:
    xor a
    ld (Session_GuardActive),a
    ld a,(Session_RiskFrames)
    or a
    jr nz,.snapshot
    ld a,($e06d)
    or a
    jp p,.x_positive
    neg
.x_positive:
    cp 8
    ret c
    ld a,($e06f)
    or a
    jp p,.y_positive
    neg
.y_positive:
    cp 8
    ret c
.snapshot:
    ld a,1
    ld (Session_GuardActive),a
    ld hl,$e048
    ld de,$d200
    ld bc,20
    ldir
    ld hl,$e068
    ld bc,24
    ldir
    ret
Session_RestoreMotion:
    ld hl,($e05a)
    push hl                  ; Keep the original perpendicular centering decision.
    ld hl,($e069)
    push hl
    ld a,($e06b)
    push af                  ; Keep a newly selected escape direction.
    ld hl,$d200
    ld de,$e048
    ld bc,20
    ldir
    ld de,$e068
    ld bc,24
    ldir
    pop af
    ld ($e06b),a
    pop hl
    ld ($e069),hl
    pop hl
    ld ($e05a),hl
    ld hl,Session_WallBlocks
    inc (hl)
    ret nz
    inc hl
    inc (hl)
    ret

; Four-way arcade input: a new direction wins over a still-held old direction.
; Simultaneous new edges use one deterministic bit, never a diagonal.
Session_FourWay:
    ld c,a
    ld a,(Session_HeldDirections)
    cpl
    and c
    ld hl,Session_HeldDirections
    ld (hl),c
    jr nz,.choose
    ld a,(Session_SelectedDirection)
    and c
    jr nz,.selected
    ld a,c
.choose:
    ld b,a
    neg
    and b
.selected:
    ld (Session_SelectedDirection),a
    cpl
    ld b,a
    ret

Session_Reset:
    xor a
    ld hl,Session_State
    ld de,Session_State+1
    ld bc,31
    ld (hl),a
    ldir
    inc a
    ld (Session_State),a
    ret
Session_Frame:
    ld a,(Session_State)
    ld hl,Session_Drawn
    cp (hl)
    call nz,Session_Draw
    in a,($aa)
    and $f0
    out ($aa),a
    in a,($a9)
    cpl
    ld b,a
    ld a,(Session_Keys)
    cpl
    and b
    ld (Session_Edges),a
    ld a,b
    ld (Session_Keys),a
    ld a,(Session_Edges)
    bit 5,a
    jr z,.start
    ld hl,Session_Credits
    inc (hl)
    jr nz,.credit
    dec (hl)                 ; Original credit counter saturates at255.
.credit:
    ld a,(Session_Credits)
    ld ($e024),a
    call Session_DrawCredits
.start:
    IF FULL_GAME
    ld a,(Session_Edges)
    and 6
    jr z,.waiting
    ld b,1
    bit 2,a
    jr z,.one_player
    inc b
.one_player:
    ld a,(Session_Credits)
    cp b
    jr c,.waiting
    ld a,b
    ld (Full_Players),a
    ld a,(Session_Credits)
    sub b
    ELSE
    ld a,(Session_Edges)
    bit 1,a
    jr z,.waiting
    ld a,(Session_Credits)
    or a
    jr z,.waiting
    dec a
    ENDIF
    ld (Session_Credits),a
    ld hl,$e060
    ld de,Session_High
    ld bc,8
    ldir
    xor a
    ld (Session_Ready),a
    ld a,2                   ; Resident caller reloads the original initial state.
    ret
.waiting:
    IF FULL_GAME
    call Full_AttractWait
    ret
    ENDIF
    ld a,1
    ret

Session_AfterStart:
    IF FULL_GAME
    call Full_SessionInit
    ld a,1
    call HUD_SetPlayerNumber
    ld a,(Full_Attract)
    or a
    jr z,.active_mode
    xor a
    ld ($e020),a
    ld ($e021),a
.active_mode:
    ENDIF
    ld hl,Session_High
    ld de,$e060
    ld bc,8
    ldir
    ld a,(Session_Credits)
    ld ($e024),a
    xor a
    ld (Session_State),a
    ld (Session_Drawn),a
    ld (Session_Ready),a
    ld (paused),a
    ld (Session_HeldDirections),a
    ld (Session_SelectedDirection),a
    ld (Score_HighValid),a
    ld (Session_RiskFrames),a
    jp Score_Publish

Session_Draw:
    IF FULL_GAME
    ld hl,0
    ld (Full_AttractClock),hl
    ENDIF
    ld (Session_Drawn),a
    xor a
    ld (Session_Ready),a
    di
    ld hl,Session_Registers
    ld c,10
.register:
    ld b,(hl)
    inc hl
    ld a,(hl)
    inc hl
    call register
    dec c
    jr nz,.register
    call Session_CopyImage
    ; Copy the selected status line without moving any original font pixel.
    di
    vdp_write 14,4
    xor a
    out ($99),a
    IF FULL_GAME
    ld a,$44
    ELSE
    ld a,$70
    ENDIF
    out ($99),a
    ld a,(Session_State)
    dec a
    add a,a
    add a,a
    add a,$aa
    ld h,a
    ld l,0
    ld de,1024
    ei
    call upload
    call Session_DrawCredits
    ld hl,$e060
    ld de,Session_Digits
    call Score_ReadDigits
    ld hl,Session_Digits
    IF FULL_GAME
    inc hl                   ; Seven visible digits; the native record stays eight.
    ld de,120/2
    ld b,7
    ELSE
    ld de,56*128+160/2
    ld b,HUD_DIGITS
    ENDIF
    call Session_Number
    IF !FULL_GAME
    ld hl,$e0a0
    ld de,Session_Digits
    call Score_ReadDigits
    ld hl,Session_Digits
    ld de,80*128+160/2
    ld b,HUD_DIGITS
    call Session_Number
    ENDIF
    ld a,(ticks)
    ld b,a
.wait_blank:
    di
    ld a,(ticks)
    cp b
    jr nz,.show
    ei
    halt
    jr .wait_blank
.show:
    di
    vdp_write 1,$62
    ei
    ld a,1
    ld (Session_Ready),a
    ret
Session_Registers:
    db 0,6,1,$22,8,$2a,25,0,26,0,27,0,23,0,2,$5f,14,4,15,0

Session_DrawCredits:
    ld a,(Session_Credits)
    IF FULL_GAME
    cp 10
    jr c,.credit_ready
    ld a,9
.credit_ready:
    ld (Session_Digits),a
    ld hl,Session_Digits
    ld de,192*128+CREDIT_X/2
    ld b,1
    jr Session_Number
    ELSE
    ld b,0
.hundreds:
    cp 100
    jr c,.tens_begin
    sub 100
    inc b
    jr .hundreds
.tens_begin:
    ld hl,Session_Digits
    ld (hl),b
    inc hl
    ld b,0
.tens:
    cp 10
    jr c,.digits
    sub 10
    inc b
    jr .tens
.digits:
    ld (hl),b
    inc hl
    ld (hl),a
    ld hl,Session_Digits
    IF FULL_GAME
    ld de,192*128+160/2
    ELSE
    ld de,152*128+160/2
    ENDIF
    ld b,3
    ENDIF
Session_Number:
    push bc
    push hl
    push de
    ld a,(hl)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld bc,$b600
    IF FULL_GAME
    ld a,(Full_NumberBlack)
    or a
    jr z,.font_ready
    ld bc,$b200
.font_ready:
    ENDIF
    add hl,bc
    ld b,8
.row:
    push bc
    di
    ld a,d
    rlca
    rlca
    and 3
    or 4
    ld b,14
    call register
    ld a,e
    out ($99),a
    ld a,d
    and $3f
    or $40
    out ($99),a
    ld bc,$0498
    otir
    ei
    push hl
    ld hl,128
    add hl,de
    ex de,hl
    pop hl
    pop bc
    djnz .row
    pop de
    pop hl
    inc hl
    inc de
    inc de
    inc de
    inc de
    pop bc
    djnz Session_Number
    ret

    IF FULL_GAME
    INCLUDE "full-session.inc"
    ENDIF
