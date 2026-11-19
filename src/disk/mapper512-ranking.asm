; Experimental cold victim-rank reconstruction. No gameplay policy change.
; A=family0..3; Page1 holds8896-byte basis at4000 (4160 HUD low then high bytes followed
; by4x8x9 LE edge costs). DE=8000 output Page2,4160 bytes. CF=0 success,
; CF=1 invalid family/destination. AF/BC/DE/HL scratch; IX/IY preserved.
; Entry/return DI; caller owns separate source/output, slots, mapper, Page0,
; Page3 code/stack. No VDP/PSG/mapper/OS writes. Source basis must be validated.
; Private counters/base pointers last only through this nonreentrant cold call;
; never call from IRQ/NMI or during active gameplay. CA00 is diagnostic only.
    OUTPUT "ranking.bin"
    ORG $ca00
Mapper512Rank_Build:
    push ix
    push iy
    cp 4
    jp nc,.fail
    ld b,a
    ld a,d
    cp $80
    jp nz,.fail
    ld a,e
    or a
    jp nz,.fail
    ld hl,$6080
    ld de,144
    ld a,b
    or a
    jr z,.base_ready
.family:
    add hl,de
    djnz .family
.base_ready:
    ld (FamilyBase),hl
    ld de,$8000
    ld ix,$4000
    ld iy,$5040
    xor a
    ld (Current),a
.phase:
    ld a,(Current)
    and 7
    ld l,a
    ld h,0
    add hl,hl
    ld b,h
    ld c,l
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,bc
    ld bc,(FamilyBase)
    add hl,bc
    ld (EdgeBase),hl
    xor a
    ld (Old),a
.old:
    ld l,(ix+0)
    ld h,(iy+0)
    inc ix
    inc iy
    push hl
    ld a,(Old)
    cp 64
    jr nc,.unknown
    and 7
    add a,a
    jr .edge
.unknown:
    ld a,16
.edge:
    ld c,a
    ld b,0
    ld hl,(EdgeBase)
    add hl,bc
    ld c,(hl)
    inc hl
    ld b,(hl)
    pop hl
    add hl,bc
    jr c,.clip
    ld bc,128
    add hl,bc
    jr c,.clip
    ld a,h
    cp 255
    jr nz,.store
.clip:
    ld a,254
.store:
    ld (de),a
    inc de
    ld a,(Old)
    inc a
    ld (Old),a
    cp 65
    jr c,.old
    ld a,(Current)
    inc a
    ld (Current),a
    cp 64
    jr c,.phase
    pop iy
    pop ix
    or a
    ret
.fail:
    pop iy
    pop ix
    scf
    ret
FamilyBase: dw 0
EdgeBase: dw 0
Current: db 0
Old: db 0
