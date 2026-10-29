    OUTPUT "probe.rom"
cy EQU $c002
    ORG $4000
    db "AB"
    dw boot,0,0,0,0,0,0
boot:
    di
    ld sp,$f380
    call GameSprites_Init
main:
    jp main
    INCLUDE "game-sprites.inc"
    ASSERT $ < $8000
    defs $8000-$,$ff
