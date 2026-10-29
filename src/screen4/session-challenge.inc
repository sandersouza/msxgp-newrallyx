; Cold UI only. Reveal native-size items and type one original glyph per step.
GameSession_ChallengeFrame:
    ld a,(Full_UICastDone)
    or a
    jp nz,Full_UIChallengeWait
    ld a,(Full_UITimer)
    or a
    jr z,.next
    dec a
    ld (Full_UITimer),a
    ld a,1
.delay_done:
    ret
.next:
    ld hl,(Full_UIReveal)
    ld de,GameSession_ChallengeRevealEnd
    or a
    sbc hl,de
    jr c,.unit
    ld a,1
    ld (Full_UICastDone),a
    jp Full_UIChallengeWait
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
    ld a,h
    or a
    jr z,.number
    call Full_UIBlit
    ld a,1
.unit_done:
    ret
.number:
    ld a,l
    cp 1
    jr nz,.rocks
    ld a,($e1b0)
    or a
    ld a,64
    jr z,.draw
    ld a,($e1b0)
    srl a
    srl a
    jr .draw
.rocks:
    cp 2
    ld a,($e251)
    jr z,.draw
    ld a,($e24e)
.draw:
    call Full_UIUnsigned
    ld a,1
.number_done:
    ret
    INCLUDE "session-challenge-data.inc"
