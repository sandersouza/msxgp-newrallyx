; Full-game UI lives in its own ROM bank. All original cast pixels stay 1:1.
Full_UIFrame:
    call Full_DebugRead
    ld a,(Session_State)
    cp 1
    jr nz,.draw
    ld a,(Session_Credits)
    or a
    jr z,.draw
    ld a,6
    ld (Session_State),a
.draw:
    ld a,(Session_State)
    cp 5
    jr z,.input
    ld hl,Session_Drawn
    cp (hl)
    call nz,Full_UIDraw
.input:
    di
    ld a,(Full_UIEdges)
    ld (Session_Edges),a
    xor a
    ld (Full_UIEdges),a
    ld a,(Full_UIHeld)
    ld (Session_Keys),a
    ei
    ld a,(Session_Edges)
    bit 5,a
    jr z,.dispatch
    ld hl,Session_Credits
    inc (hl)
    jr nz,.credit
    dec (hl)
.credit:
    ld a,(hl)
    ld ($e024),a
    IF AUDIO_ENABLED
    ld a,$80
    ld ($e9f6),a
    ENDIF
    ld a,(Session_State)
    cp 7
    jr z,.dispatch           ; A coin never aborts an active challenge interstitial.
    cp 5
    jr z,.credit_number
    cp 6
    jr z,.credit_number
    ld a,6
    ld (Session_State),a
    call Full_UIDraw
.credit_number:
    call Full_UISelectChoice
    call Full_UICredit
.dispatch:
    ld a,(Session_State)
    cp 1
    jr z,.cast
    cp 2
    jr z,.over
    cp 5
    jr z,.start_wait
    cp 7
    jp z,Full_UIChallengeWait
    ld a,(Session_Edges)
    and 6
    jr z,.waiting
    ld b,1
    bit 2,a
    jr z,.one
    inc b
.one:
    ld a,(Session_Credits)
    cp b
    jr c,.waiting
    sub b
    ld (Session_Credits),a
    ld a,b
    ld (Full_Players),a
    ld hl,$e060
    ld de,Session_High
    ld bc,8
    ldir
    call Full_UICredit
    IF AUDIO_ENABLED
    ld a,5
    ld (Session_State),a
    ld a,1
    ld (Audio_NewScene),a
    ld a,$80
    ld ($e9f5),a
    jr .waiting
.start_wait:
    ld a,($e9f5)
    bit 7,a
    jr nz,.waiting
    ELSE
.start_wait:
    ENDIF
    xor a
    ld (Session_Ready),a
    ld a,2
    ret
.cast:
    call Full_UICastFrame
    jp Full_AttractWait
.over:
    ld hl,(Full_AttractClock)
    inc hl
    ld (Full_AttractClock),hl
    ld de,180
    or a
    sbc hl,de
    jr c,.waiting
    ld a,1
    ld (Session_State),a
.waiting:
    ld a,1
    ret

Full_UIDraw:
    ld (Session_Drawn),a
    xor a
    ld (Session_Ready),a
    ld hl,0
    ld (Full_AttractClock),hl
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
    ei
    ld a,(Session_State)
    cp 1
    jr nz,.black
    call Session_CopyImage
    ld hl,UI_CastReveal
    ld (Full_UIReveal),hl
    xor a
    ld (Full_UITimer),a
    ld (Full_UICastDone),a
    jr .show
.black:
    ld a,BLACK
    ld (Full_UIBackground),a
    ld hl,UI_BlackCommand
    ld a,(Session_State)
    cp 7
    jr nz,.clear
    ld a,UI_CAST_BACKGROUND
    ld (Full_UIBackground),a
    ld hl,UI_OrangeCommand
.clear:
    call Full_UIClear
    ld a,WHITE
    ld (Full_UIForeground),a
    call Full_UIColors
    ld a,(Session_State)
    cp 7
    jp z,Full_UIDrawChallenge
    cp 2
    jr z,.over
    ld hl,UI_SelectText
    call Full_UITextList
    call Full_UISelectChoice
    call Full_UICredit
    ld a,RED
    ld (Full_UIForeground),a
    call Full_UIColors
    ld hl,UI_CopyrightText
    call Full_UITextList
    jr .show
.over:
    ld hl,UI_OverText
    call Full_UITextList
.show:
    ld a,(ticks)
    ld b,a
.blank:
    ei
    halt
    ld a,(ticks)
    cp b
    jr z,.blank
    di
    vdp_write 1,$62
    ei
    ld a,1
    ld (Session_Ready),a
    ret

Full_UICastFrame:
    ld a,(Full_UICastDone)
    or a
    ret nz
    ld a,(Full_UITimer)
    or a
    jr z,.next
    dec a
    ld (Full_UITimer),a
    ret
.next:
    ld hl,(Full_UIReveal)
    ld de,UI_CastRevealEnd
    or a
    sbc hl,de
    jr c,.unit
    ld a,1
    ld (Full_UICastDone),a
    ret
.unit:
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    push de
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (Full_UIDestination),de
    ld a,(hl)
    inc hl
    ld (Full_UIWidth),a
    ld a,(hl)
    inc hl
    ld (Full_UIRows),a
    ld a,(hl)
    inc hl
    ld (Full_UITimer),a
    ld (Full_UIReveal),hl
    pop hl
    jp Full_UIBlit

Full_UIBlit:
.row:
    ld de,(Full_UIDestination)
    call Full_UIPointer
    ld a,(Full_UIWidth)
    ld e,a
    ld d,0
    ei
    call upload
    push hl
    ld hl,(Full_UIDestination)
    ld de,128
    add hl,de
    ld (Full_UIDestination),hl
    pop hl
    ld a,(Full_UIRows)
    dec a
    ld (Full_UIRows),a
    jr nz,.row
.done:
    ret

; DE=offset in the UI bitmap at VRAM10000, preserving source HL.
Full_UIPointer:
    di
    ld a,d
    rlca
    rlca
    and 3
    add a,4
    push bc
    ld b,14
    call register
    pop bc
    ld a,e
    out ($99),a
    ld a,d
    and $3f
    or $40
    out ($99),a
    ret

Full_UIClear:
    push hl
    call stage_wait_command
    pop hl
    di
    vdp_write 17,32
    ld bc,$0f9b
    otir
    ei
    call stage_wait_command
    ei
    ret

Full_UIColors:
    ld a,(Full_UIBackground)
    ld b,a
    rlca
    rlca
    rlca
    rlca
    ld c,a
    or b
    ld (Full_UIPairs),a
    ld a,(Full_UIForeground)
    ld d,a
    or c
    ld (Full_UIPairs+1),a
    ld a,d
    rlca
    rlca
    rlca
    rlca
    ld c,a
    or b
    ld (Full_UIPairs+2),a
    ld a,c
    or d
    ld (Full_UIPairs+3),a
    ret

; C=X pixels, A=Y pixels. Font characters stay 8x8.
Full_UIPosition:
    ld l,a
    ld h,0
    REPT 7
    add hl,hl
    ENDR
    ld a,c
    srl a
    ld e,a
    ld d,0
    add hl,de
    ld (Full_UIDestination),hl
    ret

Full_UITextList:
    push hl
    pop ix
.line:
    ld a,(ix+0)
    cp 255
    ret z
    ld c,a
    ld a,(ix+1)
    inc ix
    inc ix
    call Full_UIPosition
    call Full_UIPrint
    jr .line
Full_UIPrint:
    ld a,(ix+0)
    inc ix
    or a
    ret z
    call Full_UIGlyph
    ld hl,(Full_UIDestination)
    ld de,4
    add hl,de
    ld (Full_UIDestination),hl
    jr Full_UIPrint
Full_UIGlyph:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,UI_Font
    add hl,de
    ld de,(Full_UIDestination)
    ld (Full_UIRowDestination),de
    ld a,8
    ld (Full_UIRows),a
.row:
    ld de,(Full_UIRowDestination)
    call Full_UIPointer
    ld c,(hl)
    inc hl
    ld b,4
.pair:
    ld a,c
    rlca
    rlca
    and 3
    push hl
    ld l,a
    ld h,0
    ld de,Full_UIPairs
    add hl,de
    ld a,(hl)
    out ($98),a
    pop hl
    rlc c
    rlc c
    djnz .pair
    ei
    push hl
    ld hl,(Full_UIRowDestination)
    ld de,128
    add hl,de
    ld (Full_UIRowDestination),hl
    pop hl
    ld a,(Full_UIRows)
    dec a
    ld (Full_UIRows),a
    jr nz,.row
    ret

Full_UISelectChoice:
    ld a,BLACK
    ld (Full_UIBackground),a
    ld a,WHITE
    ld (Full_UIForeground),a
    call Full_UIColors
    ld hl,UI_OnePlayerText
    ld a,(Session_Credits)
    cp 2
    jr c,.choice
    ld hl,UI_TwoPlayerText
.choice:
    jp Full_UITextList
Full_UICredit:
    ld c,152
    ld a,140
    call Full_UIPosition
    ld a,(Session_Credits)
    cp 10
    jr c,.digit
    ld a,9
.digit:
    add a,'0'
    jp Full_UIGlyph

Full_UIDrawChallenge:
    ld a,RED
    ld (Full_UIForeground),a
    call Full_UIColors
    ld hl,UI_ChallengeTitle
    call Full_UITextList
    ld a,WHITE
    ld (Full_UIForeground),a
    call Full_UIColors
    ld hl,UI_ChallengeText
    call Full_UITextList
    ld a,64
    ld c,136
    call Full_UIPosition
    ld a,($e1b0)
    or a
    ld a,64
    jr z,.number
    ld a,($e1b0)
    srl a
    srl a
.number:
    call Full_UIUnsigned
    ld a,104
    ld c,152
    call Full_UIPosition
    ld a,($e251)
    call Full_UIUnsigned
    ld a,136
    ld c,152
    call Full_UIPosition
    ld a,($e24e)
    call Full_UIUnsigned
    ld hl,96*128+96/2
    ld (Full_UIDestination),hl
    ld a,12
    ld (Full_UIWidth),a
    ld a,24
    ld (Full_UIRows),a
    ld hl,UI_Rock
    call Full_UIBlit
    ld hl,128*128+100/2
    ld (Full_UIDestination),hl
    ld a,8
    ld (Full_UIWidth),a
    ld a,16
    ld (Full_UIRows),a
    ld hl,UI_RedCar
    call Full_UIBlit
    IF AUDIO_ENABLED
    ld a,1
    ld (Audio_NewScene),a
    ld a,$40
    ld ($e9f5),a
    ENDIF
    jp Full_UIDraw.show
Full_UIUnsigned:
    ld b,'0'
.tens:
    cp 10
    jr c,.digits
    sub 10
    inc b
    jr .tens
.digits:
    push af
    ld a,b
    cp '0'
    jr z,.ones
    call Full_UIGlyph
    ld hl,(Full_UIDestination)
    ld de,4
    add hl,de
    ld (Full_UIDestination),hl
.ones:
    pop af
    add a,'0'
    jp Full_UIGlyph
Full_UIChallengeWait:
    ld hl,(Full_AttractClock)
    inc hl
    ld (Full_AttractClock),hl
    ld de,90
    or a
    sbc hl,de
    jr c,.wait
    IF AUDIO_ENABLED
    ld a,($e9f5)
    bit 6,a
    jr nz,.wait
    ENDIF
    ld a,3
    ret
.wait:
    ld a,1
    ret

UI_BlackCommand:
    dw 0,0,0,512,256,212
    db BLACK*17,0,$c0
UI_OrangeCommand:
    dw 0,0,0,512,256,212
    db UI_CAST_BACKGROUND*17,0,$c0
UI_SelectText:
    db 60,48,"PUSH START BUTTON",0
    db 40,96,"1ST BONUS FOR 20000 PTS",0
    db 40,112,"2ND BONUS FOR 80000 PTS",0
    db 80,140,"CREDIT",0,255
UI_OnePlayerText:
    db 64,72,"   1 PLAYER     ",0,255
UI_TwoPlayerText:
    db 64,72,"1 OR 2 PLAYERS  ",0,255
UI_CopyrightText:
    db 64,176,"@ NAMCO 1981 2ST",0
    db 64,192,"@ RETROWORK 2026",0,255
UI_OverText:
    db 92,96,"GAME OVER",0,255
UI_ChallengeTitle:
    db 60,40,"CHALLENGING STAGE",0,255
UI_ChallengeText:
    db 96,64,"NO.",0
    db 128,104,"=",0
    db 128,136,"=",0
    db 40,168,"RED CARS DON'T MOVE",0
    db 48,184,"UNTIL FUEL RUNS OUT.",0,255
