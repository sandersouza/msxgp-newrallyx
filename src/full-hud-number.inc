; The caller already maps HUD_BANK for the pair fonts. Keep eight native
; digits, cropping the first source glyph and its destination cell.
Full_HUDWritePair:
    ld a,(hud_field_index)
    or a
    jr nz,.pair
    ld bc,4
    add hl,bc
    ex de,hl
    add hl,bc
    ex de,hl
    ld a,8
.single_row:
    push af
    ei
    nop
    di
    vdp_write 14,4
    ld a,e
    out ($99),a
    ld a,d
    or $40
    out ($99),a
    ld bc,$0498
    otir
    ld bc,4
    add hl,bc
    ld a,e
    add a,128
    ld e,a
    jr nc,.single_next
    inc d
.single_next:
    pop af
    dec a
    jr nz,.single_row
    ret
.pair:
    ld a,8
.pair_row:
    push af
    ei
    nop
    di
    vdp_write 14,4
    ld a,e
    out ($99),a
    ld a,d
    or $40
    out ($99),a
    ld bc,$0898
    otir
    ld a,e
    add a,128
    ld e,a
    jr nc,.pair_next
    inc d
.pair_next:
    pop af
    dec a
    jr nz,.pair_row
    ret
