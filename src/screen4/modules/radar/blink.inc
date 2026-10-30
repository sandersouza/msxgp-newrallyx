; Blink variants differ at exactly the original S point's one pattern bit.
; Colors and the other flag glyphs remain valid in this exact phase/set.
; Module contract: One-bit S glyph transfer; foreground VDP ownership; restores main Page0 segment.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
GameSession_FlagBlinkUpload:
    call GameSession_SelectFlags
    ld a,(phase)
    ld h,a
    ld l,239
    ld e,(hl)
    inc l
    ld d,(hl)
    ld a,(de)
    ld b,a
    ld a,e
    sub 52
    ld l,a
    ld h,0
    ld de,$0490
    add hl,de
    call GamePattern_Address
    ld a,b
    out ($98),a
    jp GameSession_RestorePage0
