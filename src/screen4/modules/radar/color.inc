; Reuse contract: radar-color-blink (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_SpecialFrame, GameSession_RadarColor
; Inputs: SpecialFrame reads physical clock. RadarColor: HL=pattern byte, adjacent color row,
;   IX identifies native actor; caller draws player last.
; Outputs: Latched blink phase and existing yellow-flag/player color priority; returns HL to
;   the pattern row.
; Registers: SpecialFrame AF/HL scratch. RadarColor AF/HL scratch with final pattern-row HL,
;   BC preserved; DE/IX/IY untouched.
; Interrupts: IFF unchanged; foreground cache edit, no VDP port traffic here.
; Memory / hardware: Existing GameSession_Blink byte and caller-owned radar pattern/color row.
; Reuse boundary: Binding to the accepted SCREEN4 colors and native actor identity; not a
;   general palette compositor.
; Keep this summary synchronized with the registry and modules/README.md.

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
