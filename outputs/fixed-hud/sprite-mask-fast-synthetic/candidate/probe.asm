 OUTPUT "probe.rom"
cy EQU $c002
 MACRO reg number,value
 ld a,value
 out ($99),a
 ld a,$80+number
 out ($99),a
 ENDM
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 reg 0,4
 reg 1,$42
 reg 8,$28
 reg 9,$80
 call GameSprites_Init
main:
 jp main
 INCLUDE "game-sprites.inc"
Probe_End:
 ASSERT $ < $8000
 defs $8000-$,$ff
