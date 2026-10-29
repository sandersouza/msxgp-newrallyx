; Write each ordinary clipped byte once: zero prefix, masked live run, suffix.
; Sentinel216 keeps the already verified complete main/tail implementation.
GS_ClippedCopyFast:
    ld a,(GS_Sentinel)
    or a
    jp nz,GS_LegacyClippedCopyFast
    ld a,(GS_Bottom)
    ld b,a
    ld a,(GS_Top)
    ld c,a
    ld a,b
    sub c
    ld (GS_Row),a
    xor a
    ld (GS_Plane),a
.half:
    push ix
    pop hl
    push iy
    pop de
    ld a,(GS_Top)
    ld c,a
    ld b,0
    call GS_ClipRun
    ld a,(GS_Plane)
    and 1
    ld a,(GS_Mask+1)
    jr z,.mask
    ld a,(GS_Mask)
.mask:
    ld b,a
    ld a,(GS_Row)
    ld c,a
    call GS_ClipRun
    ld a,(GS_Bottom)
    ld c,a
    ld a,16
    sub c
    ld c,a
    ld b,0
    call GS_ClipRun
    ld de,16
    add ix,de
    add iy,de
    ld a,(GS_Plane)
    inc a
    ld (GS_Plane),a
    cp 4
    jr nz,.half
    xor a
    ld (GS_Plane),a
    call GS_Attributes
    ld a,(GS_PatternID)
    add a,4
    ld (GS_PatternID),a
    ld a,1
    ld (GS_Plane),a
    call GS_Attributes
    jp GS_UploadActor

; C=0..16 rows, B=mask, HL/DE advance exactly C bytes. No writable code.
GS_ClipRun:
    ld a,c
    or a
    ret z
    push hl
    push de
    ld l,c
    ld h,0
    add hl,hl
    ld de,GS_ClipTargets
    add hl,de
    ld a,(hl)
    inc hl
    ld h,(hl)
    ld l,a
    pop de
    ex (sp),hl
    ret
GS_ClipTargets:
    DUP 17, n
    dw GS_ClipEnd-n*5
    EDUP
    DUP 16
    ld a,(hl)
    and b
    ld (de),a
    inc hl
    inc de
    EDUP
GS_ClipEnd:
    ret
