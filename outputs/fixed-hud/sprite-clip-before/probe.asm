    DEFINE GAMEPLAY_CONFIGURED 1
GAME_RENDER_OPT EQU 1
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
    INCLUDE "game-sprite-mask-fast.inc"

    ASSERT $ < $8000
    defs $8000-$,$ff
