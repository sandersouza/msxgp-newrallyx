; Virtual pattern/color offsets retain their original0/4000 distinction.
; Physical sets occupy16KiB: patterns0000..07FF, colors2000..27FF.
; The gaps retain all original sprite patterns/colors; names move to0800/0C00.
GamePattern_Address:
    di
    ld a,(pattern_back)
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    and $40
    rrca
    or $40
    ld c,a
    ld a,h
    and 7
    or c
    ld c,a
    out ($99),a
    ei
    ret
