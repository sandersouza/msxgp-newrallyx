; Page0 map data may be selected only inside these resident helpers. The
; foreground returns to its original RAM segment before any Page0 code/data use.
; Module contract: Resident Page0/ASCII16 access helpers; foreground only; restore main RAM segment.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
GameSession_MapPage:
    push hl
    ld hl,GameSession_MapSegments
    or a
    jr z,.selected
    inc hl
.selected:
    ld a,(hl)
    out ($fc),a
    pop hl
    ret
GameSession_RestorePage0:
    ld a,(GameSession_MainSegment)
    out ($fc),a
    ret
GameSession_CopyMap:
    ld ($7000),a
    ld a,c
    out ($fc),a
    ld hl,$8000
    ld de,0
    ld bc,$4000
    ldir
    jp GameSession_RestorePage0

; B/C=world top-left, IY=nine theme-local tile IDs in mapped ROM.
GameSession_PatchObject:
    push ix
    ld ix,$0303
.row:
    push bc
    ld a,c
    and $80
    rlca
    call GameSession_MapPage
    ld a,c
    and 127
    ld l,a
    ld h,0
    REPT 7
    add hl,hl
    ENDR
    ld e,b
    ld d,0
    add hl,de
    ld ixl,3
.cell:
    ld a,(iy+0)
    ld (hl),a
    inc hl
    inc iy
    dec ixl
    jr nz,.cell
    pop bc
    inc c
    dec ixh
    jr nz,.row
    pop ix
    jp GameSession_RestorePage0
