 OUTPUT "probe.rom"
 MACRO reg number,value
 ld a,value
 out ($99),a
 ld a,$80+number
 out ($99),a
 ENDM
cx EQU $c000
cy EQU $c002
fx EQU $c004
fy EQU $c005
back EQU $c006
count EQU $c007
maprow EQU $c008
mapcol EQU $c009
speed EQU $c00a
keys EQU $c00b
ready EQU $c00c
frames EQU $c00d
oldcol EQU $c00e
oldrow EQU $c00f
hudptr EQU $c010
dotx EQU $c012
doty EQU $c013
seen EQU $c018
phase EQU $c01d
loaded_phase EQU $c01e
prior_phase EQU $c020
clock_ticks EQU $c022
input_tick EQU $c024
elapsed_ticks EQU $c026
ring_x EQU $c030
ring_y EQU $c031
ring_length EQU $c032
ring_dx EQU $c033
ring_dy EQU $c034
ring_first EQU $c035
ring_rest EQU $c036
ring_target EQU $c038
ring_seen_ptr EQU $c03a
world_ids EQU $d800
ring_pointers EQU $ce00
hud_page EQU $c03e
boundary_ids EQU $c920
names EQU $d400
dotpat EQU $c900
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
 reg 1,$02
 reg 0,4
 reg 8,$2a
 reg 9,$82
main:
 jp main
 INCLUDE "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/experiments/fixed-hud/ring.inc"
address:
    di
    ld a,h
    rlca
    rlca
    and 3
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    and $3f
    or $40
    out ($99),a
    ei
    ret

clock_irq:
    push af
    in a,($99)
    bit 7,a
    jr z,.done
    push hl
    ld hl,(clock_ticks)
    inc hl
    ld (clock_ticks),hl
    pop hl
.done:
    pop af
    ei
    reti
upload:
    ld c,$98
    ld a,d
    or a
    jr z,.tail
.page:
    ld b,0
    otir
    dec d
    jr nz,.page
.tail:
    ld a,e
    or a
    ret z
    ld b,e
    otir
    ret
RingProbe_End:
 ASSERT $<$8000
 defs $8000-$,$ff
