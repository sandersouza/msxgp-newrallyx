; Optimized-game continuation for a back table two/three cells behind camera.
; The 32x32 CPU world-ID cache is already prepared. Only entering visible
; terrain columns/rows need VRAM publication; .ready restores every HUD/edge
; name and records the selected table's new origin. Hidden VRAM may stay stale.
; All larger deltas and unseen tables retain the original full upload.
GameNameStream_Wide:
    ld hl,(ring_seen_ptr)
    ld a,(hl)
    cp $ff
    jp z,Ring_UploadNames.full
    ld b,a
    ld a,(mapcol)
    sub b
    ld (ring_dx),a
    add a,3
    cp 7
    jp nc,Ring_UploadNames.full
    inc hl
    ld a,(hl)
    ld b,a
    ld a,(maprow)
    sub b
    ld (ring_dy),a
    add a,3
    cp 7
    jp nc,Ring_UploadNames.full
    ld a,(ring_dx)
    or a
    jr z,.vertical
    bit 7,a
    jr nz,.left
    ld b,a
    ld a,(mapcol)
    add a,24
    sub b
    jr .columns
.left:
    neg
    ld b,a
    ld a,(mapcol)
    inc a
.columns:
    ld (ring_x),a
    ld a,b
    ld (ring_length),a
.column:
    ld a,(ring_x)
    call Ring_UploadColumn
    ld hl,ring_x
    inc (hl)
    ld hl,ring_length
    dec (hl)
    jr nz,.column
.vertical:
    ld a,(ring_dy)
    or a
    jp z,Ring_UploadNames.ready
    bit 7,a
    jr nz,.up
    ld b,a
    ld a,(maprow)
    add a,28
    sub b
    jr .rows
.up:
    neg
    ld b,a
    ld a,(maprow)
.rows:
    ld (ring_y),a
    ld a,b
    ld (ring_length),a
.row:
    ld a,(ring_y)
    call Ring_UploadRow
    ld hl,ring_y
    inc (hl)
    ld hl,ring_length
    dec (hl)
    jr nz,.row
    jp Ring_UploadNames.ready
GameNameStream_End:
