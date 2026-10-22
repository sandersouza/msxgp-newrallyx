; Observe every actual Z80 calculation against independent Tcl arithmetic.
; Original state is untouched; all math uses host fields.
Native_TestFineClock:
    ld ix,50000
    ld iy,2
.next:
    call Native_DeadlineNext
    dec ix
    ld a,ixh
    or ixl
    jr nz,.next
    dec iy
    ld a,iyh
    or iyl
    jr z,.done
    ld ix,50000
    jr .next
.done:
    ld hl,0
    ld (Native_DeadlineLine),hl
    ld (Native_DeadlineError),hl
    xor a
    ld (Native_FineIndex),a
    inc a
    ld (Native_FineProofDone),a
    ret
