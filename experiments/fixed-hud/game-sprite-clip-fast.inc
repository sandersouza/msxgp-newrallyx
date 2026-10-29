; Exact dirty vertical/sentinel clipping. IX=64-byte native source;
; IY=actor pattern base+sentinel shift. Public sprite outputs/cache are unchanged.
; Reuse private GS_Row/Plane/Tail scratch; no new RAM. Called only from .slow.
GS_ClippedCopyFast:
    push iy
    pop hl
    ld a,(GS_Sentinel)
    or a
    jr z,.clear_main
    dec hl
.clear_main:
    ld d,h
    ld e,l
    inc de
    ld bc,63
    ld (hl),0
    ldir
    ld a,(GS_Sentinel)
    or a
    jr z,.count
    ld hl,GameSprites_Patterns+512
    ld de,GameSprites_Patterns+513
    ld bc,63
    ld (hl),0
    ldir
.count:
    ld hl,GameSprites_Patterns+512
    ld (GS_Tail),hl
    ld a,(GS_Bottom)
    ld b,a
    ld a,(GS_Sentinel)
    or a
    ld a,b
    jr z,.bottom
    cp 16
    jr c,.bottom
    dec a
.bottom:
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
    ld a,(GS_Top)
    ld e,a
    ld d,0
    add hl,de
    push hl
    push iy
    pop hl
    add hl,de
    ex de,hl
    pop hl
    ld a,(GS_Plane)
    and 1
    ld a,(GS_Mask+1)
    jr z,.mask
    ld a,(GS_Mask)
.mask:
    ld b,a
    ld a,(GS_Row)
    or a
    jr z,.tail
    ld c,a
.copy:
    ld a,(hl)
    and b
    ld (de),a
    inc hl
    inc de
    dec c
    jr nz,.copy
.tail:
    ld a,(GS_Sentinel)
    or a
    jr z,.next
    ld a,(GS_Bottom)
    cp 16
    jr nz,.next
    ld a,(ix+15)
    and b
    ld hl,(GS_Tail)
    ld (hl),a
.next:
    ld de,16
    add ix,de
    add iy,de
    ld hl,(GS_Tail)
    add hl,de
    ld (GS_Tail),hl
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
GS_ClippedCopyFast_End:
