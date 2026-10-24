; The selected-routine adapter uses canonical player-one addresses. Save the
; inactive player's original packets and placements at turn boundaries.
Full_Players EQU $c7eb
Full_Player EQU $c7ec
Full_NewBoard EQU $c7ed
Full_NumberBlack EQU $c7ef
Full_Attract EQU $c7ee
Full_AttractClock EQU $c7ca
Full_Shadow EQU $d230         ; 120 bytes, below the D2D2 IM2 trampoline

Full_SessionInit:
    xor a
    ld (Full_AttractClock),a
    ld (Full_AttractClock+1),a
    ld (Full_Player),a
    ld (Full_NewBoard),a
    ld ix,Full_TurnFields
    ld hl,Full_Shadow
    ld b,120
.copy:
    ld e,(ix+0)
    ld d,(ix+1)
    ld a,(de)
    ld (hl),a
    inc hl
    inc ix
    inc ix
    djnz .copy
    ld a,1
    ld (Full_Shadow+9),a     ; Player two has not prepared its first round yet.
    ld (Full_Shadow+119),a
    ret

Full_AttractWait:
    ld a,(Session_Credits)
    or a
    jr nz,.reset
    ld hl,(Full_AttractClock)
    inc hl
    ld (Full_AttractClock),hl
    ld de,900
    or a
    sbc hl,de
    ld a,1
    ret c
    ld (Full_Attract),a
    ld (Full_Players),a
    ld hl,$e060
    ld de,Session_High
    ld bc,8
    ldir
    ld a,2
    ret
.reset:
    ld hl,0
    ld (Full_AttractClock),hl
    ld a,1
    ret

Full_DemoFrame:
    ld a,(Session_Credits)
    or a
    jr nz,.finish
    ld a,(Death_State)
    cp 2
    jr z,.finish
    ld a,(Round_State)
    cp 3
    jr z,.finish
    ld hl,(Full_AttractClock)
    inc hl
    ld (Full_AttractClock),hl
    ld de,900
    or a
    sbc hl,de
    ret c
.finish:
    xor a
    ld (Full_Attract),a
    ld (Full_AttractClock),a
    ld (Full_AttractClock+1),a
    ld (Session_Drawn),a
    ld a,1
    ld (Session_State),a
    ret

Full_DrawRound:
    ld a,($e1b0)
    dec a
    ld b,0
.hundreds:
    cp 100
    jr c,.tens_begin
    sub 100
    inc b
    jr .hundreds
.tens_begin:
    ld hl,$d148
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
    ld hl,$d148
    ld de,216/2
    ld b,3
    ld a,1
    ld (Full_NumberBlack),a
    call Session_Number
    xor a
    ld (Full_NumberBlack),a
    ret

; 0 same-player restart, 1 prepare next round, 2 final game over,
; 3 restored player's existing round. No rendering or mapper changes here.
Full_SessionDeath:
    xor a
    ld (Full_NewBoard),a
    ld a,($e1b0)
    and 3
    jr nz,.players
    ld a,1
    ld (Full_NewBoard),a     ; Original $191c skips the failed challenge.
.players:
    ld a,(Full_Players)
    cp 2
    jr nz,.current
    ld a,(Full_Shadow+8)
    or a
    jr z,.current
    ld ix,Full_TurnFields
    ld hl,Full_Shadow
    ld b,120
.swap:
    ld e,(ix+0)
    ld d,(ix+1)
    ld a,(de)
    ld c,(hl)
    ld (hl),a
    ld a,c
    ld (de),a
    inc hl
    inc ix
    inc ix
    djnz .swap
    ld a,(Full_Player)
    xor 1
    ld (Full_Player),a
    ld a,($e271)
    ld (Flag_Count),a
    ld (Score_Seen),a
    xor a
    ld (Flag_Jobs),a
    ld (Flag_HudPending),a
    ld (Score_HighValid),a
    call Flag_Frame
    ld a,(Full_NewBoard)
    or a
    ld a,3
    ret z
    ld a,1
    ret
.current:
    ld a,($e00f)
    or a
    ld a,2
    ret z
    ld a,(Full_NewBoard)
    ret

Full_TurnFields:
    dw $e0a0,$e0a1,$e0a2,$e0a3,$e0a4,$e0a5,$e0a6,$e0a7
    dw $e00f,$e1b0,$e1b2,$e271,$e251
    DUP 96, i
    dw $e1c8+i
    EDUP
    DUP 10, i
    dw Flag_Active+1+i
    EDUP
    dw Full_NewBoard
