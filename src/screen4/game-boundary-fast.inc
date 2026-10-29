; Exact four-atlas transition packet. The current phase bank is mapped at8000;
; prior_phase is the HUD worker's previous phase for this inactive VRAM set.
; The existing packet worker restores phase+4 on completion and preserves the
; established R14/back-buffer and DI/EI ownership rules.
GameBoundary_Upload:
    ld a,(prior_phase)
    cp $ff
    ld a,8
    jr z,.previous
    ld a,(prior_phase)
    and 7
.previous:
    ld l,a
    ld h,0
    ld e,l
    ld d,h
    add hl,hl
    add hl,de
    ld de,$a900
    add hl,de
    ld a,(hl)
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    ex de,hl
    ld ($7000),a
    ld a,$ff
    ld (hud_page),a
    jp hud_upload.packet
GameBoundary_Upload_End:
