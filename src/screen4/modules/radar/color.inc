; Module contract: Physical-clock blink state and SCREEN4 radar color priority.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
GameSession_SpecialFrame:
    ld a,(clock_ticks)
    and 16
    ld hl,GameSession_Blink
    cp (hl)
    ret z
    ld (hl),a
    ret

; SCREEN4 has two colors per eight-pixel row. Preserve yellow flags when an
; enemy shares that row. The player's marker, drawn last, has color priority.
GameSession_RadarColor:
    push bc
    inc h
    ld b,(hl)
    ld a,b
    rrca
    rrca
    rrca
    rrca
    xor b
    and 15
    jr nz,.pattern_ready
    dec h
    ld (hl),0
    inc h
.pattern_ready:
    ld a,ixl
    cp $68
    jr z,.player
    ld a,b
    and $f0
    cp $c0
    jr nz,.red
    dec h
    ld a,(hl)
    inc h
    or a
    ld a,b
    jr nz,.store
.red:
    ld a,$6a
    jr .store
.player:
    ld a,(GameSession_Blink)
    or a
    ld a,$8a
    jr z,.store
    ld a,$ba
.store:
    ld (hl),a
    dec h
    pop bc
    ret
