; Four immutable terrain copies and four fine-phase caches in 128KiB VRAM.
; The visible set is never written. Name-table double buffering is independent.
    IFDEF GAME_HUD_PROGRAMS
pattern_back EQU $c027
pattern_front EQU $c028
pattern_phases EQU $c029
pattern_next EQU $c02d

GamePhase_Init:
    ld a,$ff
    ld (pattern_front),a
    ld hl,pattern_phases
    ld b,4
.invalidate:
    ld (hl),a
    inc hl
    djnz .invalidate
    xor a
    ld (pattern_next),a
    ld a,1
    ld ($7000),a
    ld a,2
.set:
    ld (pattern_back),a
    ld hl,0
    call GamePattern_Address
    ld hl,$8000
    ld de,2048
    call upload
    ld hl,$4000
    call GamePattern_Address
    ld hl,$8800
    ld de,2048
    call upload
    ld a,(pattern_back)
    inc a
    cp 4
    jr c,.set
    ret

GamePhase_Select:
    ld b,a
    ld c,0
    ld hl,pattern_phases
.match:
    ld a,(pattern_front)
    cp c
    jr z,.next
    ld a,(hl)
    cp b
    jr z,.selected
.next:
    inc hl
    inc c
    ld a,c
    cp 4
    jr c,.match
    ld a,(pattern_next)
.victim:
    ld c,a
    ld a,(pattern_front)
    cp c
    ld a,c
    jr nz,.chosen
    inc a
    and 3
    jr .victim
.chosen:
    inc a
    and 3
    ld (pattern_next),a
.selected:
    ld a,c
    ld (pattern_back),a
    ret

; HL=offset in one 32KiB pattern/color set. Preserve HL for caller source setup.
GamePattern_Address:
    di
    ld a,h
    and $40
    rlca
    rlca
    ld c,a
    ld a,(pattern_back)
    add a,a
    or c
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
    ELSE
GamePattern_Address:
    ld a,(back)
    or a
    jr z,.address
    set 7,h
.address:
    jp address
    ENDIF
