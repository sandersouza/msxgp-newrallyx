; Exact full-height horizontal clipping. Enter only for dirty native patterns
; with GS_Sentinel=0, GS_Top=0 and GS_Bottom=16. IX/IY address complete
; 64-byte source/destination patterns; GS_Mask is the existing 16-bit mask.
; Public SAT/colors/pattern/cache and VRAM bytes retain their existing layout.
; Clobbers AF/BC/DE/HL/IX/IY under the existing sprite API. Private row/plane,
; pattern-ID, tail and ink scratch need not reproduce the former slow loop.
GS_MaskedCopyFast:
    push ix
    pop hl
    push iy
    pop de
    ld a,(GS_Mask+1)
    ld b,a
    ld a,(GS_Mask)
    ld c,a
    DUP 2
        DUP 16
            ld a,(hl)
            and b
            ld (de),a
            inc hl
            inc de
        EDUP
        DUP 16
            ld a,(hl)
            and c
            ld (de),a
            inc hl
            inc de
        EDUP
    EDUP
    call GS_InteriorAttributes
    jp GS_UploadActor
GS_MaskedCopyFast_End:
