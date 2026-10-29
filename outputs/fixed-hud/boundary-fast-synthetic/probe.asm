 OUTPUT "probe.rom"
phase EQU $c01d
prior_phase EQU $c020
hud_page EQU $c024
back EQU $c006
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
     INCLUDE "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/experiments/fixed-hud/game-boundary-fast.inc"
hud_upload:
.packet:
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,(hl)
    inc hl
    or a
    jr z,.done
    ld b,a
    push hl
    ex de,hl
    ld a,h
    and $40
    rlca
    rlca
    ld c,a
    ld a,(back)
    add a,a
    or c
    ld c,a
    ld a,(hud_page)
    cp c
    di
    jr z,.target
    ld a,c
    ld (hud_page),a
    out ($99),a
    ld a,$8e
    out ($99),a
.target:
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ei
    pop hl
    ld c,$98
    otir
    jr .packet
.done:
    ld a,(phase)
    add a,4
    ld ($7000),a
    ret

Probe_End:
     ASSERT $ < $8000
     defs $8000-$,$ff
    