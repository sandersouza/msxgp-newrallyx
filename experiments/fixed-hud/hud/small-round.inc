; Slot6 is the same32-byte white sprite. Right-align two4x5 glyphs.
; IY points to its cleared pattern, already adjusted for sentinel216.
GH_CopySmallRound:
    ld a,(GH_Value)
    rrca
    rrca
    rrca
    rrca
    and 15
    call GH_SmallGlyph
    push hl
    ld a,(GH_Value)
    and 15
    call GH_SmallGlyph
    ex de,hl
    pop hl
    ld b,5
.row:
    ld a,(hl)
    inc hl
    ld c,a
    srl a
    srl a
    srl a
    ld (iy+0),a
    ld a,c
    and 7
    rrca
    rrca
    rrca
    ld c,a
    ld a,(de)
    inc de
    or c
    ld (iy+16),a
    inc iy
    djnz .row
    ret
GH_SmallGlyph:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld e,a
    ld d,0
    add hl,de
    ld de,GameHUD_SmallDigits
    add hl,de
    ret
GameHUD_SmallDigits:
    ; Generated from the same authored font used by the static compositor.
    INCLUDE "hud-small-font-data.inc"
