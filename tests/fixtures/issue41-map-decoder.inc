; Experimental cold-only map decoder, resident Page1. Input C010=source8KiB
; page, C011..12=fragment address. DATAREG selects the lower cartridge window.
; Output: exact16KiB map at0000..3FFF, main Page0 RAM selected by MapSetup.
; Clobbers AF/BC/DE/HL/IX/IY/IFF, cartridge lower window; upper unchanged.
; Scratch C022..24 is diagnostic-only and requires a lifetime audit for a game
; integration. No extra segment/buffer; overlapping LZ matches use forward LDIR.
; Only builder-verified streams are accepted. Not a public/untrusted-file parser.
MapSetup:
    di
    ; Cartridge entry precedes DOS RAMAD initialization. Clone the working
    ; Page3 RAM slot, selecting its subslot for Page0 before the primary switch.
    ; Execute every instruction here in Page1; BIOS cannot unmap its own Page0.
    in a,($a8)
    rlca
    rlca
    and 3
    ld c,a
    ld e,a
    ld d,0
    ld hl,$fcc1
    add hl,de
    bit 7,(hl)
    jr z,.primary
    ld a,($ffff)
    cpl
    ld b,a
    rlca
    rlca
    and 3
    ld e,a
    ld a,b
    and $fc
    or e
    ld ($ffff),a
.primary:
    in a,($a8)
    and $fc
    or c
    out ($a8),a
    jp MapEntry
    defs $47fd-$,0
MapNext:
    ; Register-PC changes inside an emulator breakpoint skip that breakpoint's
    ; test at the new PC. Re-enter through a guest jump so every case is armed.
    jp MapEntry
MapEntry:
    ld a,($c010)
    ld (DATAREG),a
    ld hl,($c011)
    call MapFragment
    ld de,0
.token:
    ld a,d
    cp $40
    jp z,$4500
    call MapByte
    bit 7,a
    jr nz,.match
    inc a
    ld c,a
.literal:
    call MapByte
    ld (de),a
    inc de
    dec c
    jr nz,.literal
    jr .token
.match:
    and 127
    add a,3
    ld c,a
    call MapByte
    ld ixl,a
    call MapByte
    ld ixh,a
    push hl
    push de
    push ix
    pop hl
    ex de,hl
    or a
    sbc hl,de
    pop de
    ld b,0
    ldir
    pop hl
    jr .token
MapFragment:
    ld c,(hl)
    inc hl
    ld b,(hl)
    inc hl
    push bc
    pop iy
    ld a,(hl)
    inc hl
    ld ($c022),a
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld ($c023),de
    ret
MapByte:
    ld a,iyh
    or iyl
    jr nz,.read
    push bc
    push de
    ld a,($c022)
    ld (DATAREG),a
    ld hl,($c023)
    call MapFragment
    pop de
    pop bc
.read:
    dec iy
    ld a,(hl)
    inc hl
    ret
MapEnd:
