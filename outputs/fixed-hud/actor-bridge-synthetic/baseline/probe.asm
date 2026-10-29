 OUTPUT "probe.rom"
cx EQU $c000
cy EQU $c002
Death_State EQU $c600
GAME_NATIVE_BANK EQU 1
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 call GameSprites_Init
main:
 jp main
 INCLUDE "actors.inc"
 INCLUDE "game-sprites.inc"
 ASSERT $ < $8000
 defs $8000-$,$ff
