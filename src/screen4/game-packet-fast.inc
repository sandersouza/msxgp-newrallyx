; B=1..255, C=$98, HL=source. Return B=0, C unchanged, HL+=length.
; AF is scratch; DE/IX/IY, mapper/VDP address and interrupt ownership unchanged.
GamePacketFast_Transfer:
    ld a,b
    cp 16
    jr c,.tail
.burst:
    ; Unroll the frequent full16-byte burst, then use OTIR only for1..15 bytes.
    ; Entering with B=0 would mean256 writes in OTIR, so callers must reject it.
    REPT 16
    outi
    ENDR
    ld a,b
    cp 16
    jr nc,.burst
    or a
    ret z
.tail:
    otir
    ret
GamePacketFast_End:
