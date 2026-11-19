; Same instructions as original resident IRQ. Page1 is required only by the
; nonzero-session UI branch; all world accessors obey the state0/DI invariant.
; Page3 stays mapped even while the expanded flag cache replaces Page0.
GamePlain_IRQ:
    push af
    in a,($99)
    bit 7,a
    jr z,.done
    push hl
    ld hl,(clock_ticks)
    inc hl
    ld (clock_ticks),hl
    pop hl
    ld a,(Session_State)
    or a
    jr z,.done
    push bc
    push de
    push hl
    call GameSession_LatchKeys
    pop hl
    pop de
    pop bc
.done:
    pop af
    ei
    reti
