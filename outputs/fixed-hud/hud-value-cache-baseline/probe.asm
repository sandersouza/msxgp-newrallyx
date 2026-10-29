    OUTPUT "probe.rom"
cy EQU $c002
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
    in a,($a8)
    rlca
    rlca
    and 3
    ld c,a
    ld b,0
    ld hl,$fcc1
    add hl,bc
    bit 7,(hl)
    jr z,.primary
    ld a,($ffff)
    cpl
    ld b,a
    rlca
    rlca
    and 3
    ld d,a
    ld a,b
    and $fc
    or d
    ld ($ffff),a
.primary:
    in a,($a8)
    and $fc
    or c
    out ($a8),a
 call GameHUD_Init
main:
 jp main
 INCLUDE "game-hud.inc"
 ASSERT $<$8000
 defs $8000-$,$ff
