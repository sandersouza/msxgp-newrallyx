; Same four-way edge policy and joystick latch protocol as the shared session.
read_keys:
    ld c,a
    in a,($aa)
    ld b,a
    and $f0
    or c
    out ($aa),a
    in a,($a9)
    cpl
    push af
    ld a,b
    out ($aa),a
    pop af
    ret
    IF SESSION_HARDWARE_CHECK
; Cold UI only. 1=boot active,2=consume skip key until every row releases.
; Active gameplay never calls this IRQ path: no per-frame gameplay overhead.
GameSession_BootKeyGate EQU $c0fb
GameSession_BootSkip EQU $c0fc
GameSession_BootAnyKey:
    ; Called only by the cold IRQ, whose wrapper preserves DE.
    ld e,10
.row:
    ld a,e
    call read_keys
    or a
    ret nz
    dec e
    jp p,.row
    xor a
    ret
    ENDIF
GameSession_LatchKeys:
    IF SESSION_HARDWARE_CHECK
    ld a,(GameSession_BootKeyGate)
    or a
    jr z,.normal
    call GameSession_BootAnyKey
    or a
    jr z,.released
    ld a,2
    ld (GameSession_BootKeyGate),a
    dec a
    ld (GameSession_BootSkip),a
    ret
.released:
    ld a,(GameSession_BootKeyGate)
    cp 2
    ret nz
    xor a
    ld (GameSession_BootKeyGate),a
    ret
.normal:
    ENDIF
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
    ret
Game_ReadInput:
    xor a
    call read_keys
    ld b,a
    ld a,(Session_Keys)
    cpl
    and b
    ld c,a
    ld a,b
    ld (Session_Keys),a
    bit 5,c
    jr z,.pause
    ld hl,Session_Credits
    inc (hl)
    jr nz,.credit
    dec (hl)
.credit:
    ld a,(hl)
    ld ($e024),a
    ld a,$80
    ld ($e9f6),a
.pause:
    ld a,(Full_Attract)
    or a
    jr z,.human
    ld a,$ff
    ld ($e3f0),a
    xor a
    ld (Smoke_Key),a
    ret
.human:
    ld a,4
    call read_keys
    and 32
    ld b,a
    ld a,(GameSession_PauseHeld)
    xor b
    and b
    ld a,b
    ld (GameSession_PauseHeld),a
    jr z,.debug
    ld a,(paused)
    xor 1
    ld (paused),a
.debug:
    ld a,7
    call read_keys
    IF SESSION_TEST_MODE
    push af
    push bc
    call GameSession_TestKeys
    pop bc
    pop af
    ENDIF
    and 2
    ld b,a
    ld a,(Full_DebugHeld)
    xor b
    and b
    ld a,b
    ld (Full_DebugHeld),a
    jr z,.keys
    ld a,(Death_State)
    or a
    jr nz,.keys
    ld a,(Full_Attract)
    or a
    jr nz,.keys
    ld a,1
    ld (Full_ChallengeBypass),a
    call GameSession_NextRound
.keys:
    ld a,8
    call read_keys
    ld (GameSession_Key8),a
    ld b,a
    and 1
    ld (Smoke_Key),a
    push bc
    ld a,6
    call read_keys
    and 2
    ld hl,Smoke_Key
    or (hl)
    ld (hl),a
    pop bc
    ld c,0
    bit 4,b
    jr z,.up
    set 2,c
.up:
    bit 5,b
    jr z,.down
    set 5,c
.down:
    bit 6,b
    jr z,.right
    set 4,c
.right:
    bit 7,b
    jr z,.stick
    set 3,c
.stick:
    push bc
    ld a,15
    out ($a0),a
    in a,($a2)
    ld c,a
    and $af
    or 3
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
    ld a,b
    pop bc
    bit 0,a
    jr z,.stick_down
    set 5,c
.stick_down:
    bit 1,a
    jr z,.stick_left
    set 4,c
.stick_left:
    bit 2,a
    jr z,.stick_right
    set 2,c
.stick_right:
    bit 3,a
    jr z,.stick_smoke
    set 3,c
.stick_smoke:
    bit 4,a
    jr z,.four_way
    ld a,1
    ld (Smoke_Key),a
.four_way:
    ld a,c
    call Session_FourWay
    ld a,(Smoke_Key)
    or a
    jr z,.publish
    res 1,b
.publish:
    ld a,b
    ld ($e3f0),a
    ret
    INCLUDE "session-four-way.inc"
    INCLUDE "session-test.inc"

; Hardware input is sampled once per presentation. Preserve the original
; guard's60Hz lifetime through every elapsed native tick, including catch-up.
GameSession_InputTick:
    ld a,(Session_HeldDirections)
    ld b,a
    dec a
    and b
    ld a,8
    jr nz,.store
    ld a,(Session_RiskFrames)
    or a
    ret z
    dec a
.store:
    ld (Session_RiskFrames),a
    ret
