 OUTPUT "probe.rom"
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
     call $0138
     rrca
     rrca
     and 3
     ld c,a
     ld b,0
     ld hl,$fcc1
     add hl,bc
     ld a,(hl)
     and $80
     or c
     ld c,a
     ld de,4
     add hl,de
     ld a,(hl)
     and $0c
     or c
     ld h,$80
     call $0024
     ld a,4
     call $005f
     di
     reg 0,4
     reg 1,$42
     reg 8,$28
     reg 9,$80
main:
     jp main
Baseline_Transfer:
     nop
     otir
     ret
     INCLUDE "game-packet-fast.inc"
     ASSERT $ < $8000
     defs $8000-$,$ff
