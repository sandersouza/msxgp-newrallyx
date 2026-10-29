; Game-only persistent 32x32 name ring. Keep ring.inc unchanged for the camera
; laboratory. Original IDs, HUD names and their VRAM destinations are identical.
Ring_Position:
    ; A=world tile X, C=world tile Y -> HL=original-ID cache address.
    and 31
    ld e,a
    ld a,c
    and 31
    rrca
    rrca
    rrca
    ld l,a
    and 3
    or $d8
    ld h,a
    ld a,l
    and $e0
    or e
    ld l,a
    ld d,$d8
    ret

Ring_RunAddresses:
    ld a,(ring_y)
    ld l,a
    and $80
    rlca
    add a,2
    ld ($7000),a
    ld a,l
    and 127
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(ring_x)
    ld e,a
    ld d,$80
    add hl,de
    push hl
    ld a,(ring_y)
    ld c,a
    ld a,(ring_x)
    call Ring_Position
    ex de,hl
    pop hl
    ret

Ring_LoadRun:
    ; Copy ring_length fresh ROM IDs from (ring_x,ring_y) into the RAM ring.
    call Ring_RunAddresses
    ld a,e
    and 31
    ld c,a
    ld a,32
    sub c
    ld c,a
    ld a,(ring_length)
    cp c
    jr nc,.split
    ld c,a
    ld b,0
    ldir
    ret
.split:
    sub c
    push af
    ld b,0
    ldir
    pop af
    or a
    ret z
    ld c,a
    ld b,0
    ld a,e
    sub 32
    ld e,a
    jr nc,.rest
    dec d
.rest:
    ldir
    ret

Ring_LoadColumns:
    ld a,(maprow)
    ld (ring_y),a
    ld a,(ring_x)
    and 31
    ld b,a
    ld a,(ring_length)
    add a,b
    cp 33
    jr nc,.wrapped
    call Ring_RunAddresses
    call .strides
    ld a,(ring_length)
    ld ixl,a
    ld ixh,32
.fast:
    ld c,ixl
    ld b,0
    ldir
    ld c,iyh
    add hl,bc
    ld a,h
    cp $c0
    jr c,.bank
    sub $40
    ld h,a
    ld a,3
    ld ($7000),a
.bank:
    ex de,hl
    ld c,iyl
    add hl,bc
    ld a,h
    and 3
    or $d8
    ld h,a
    ex de,hl
    dec ixh
    jr nz,.fast
    ret
.wrapped:
    ; Split at the cache row boundary, but walk ROM/cache rows incrementally.
    ; The original per-row Ring_LoadRun recalculated both addresses 32 times.
    call Ring_RunAddresses
    call .strides
    ld a,iyl
    add a,32
    ld iyl,a
    ld a,e
    and 31
    neg
    add a,32
    ld ixl,a
    ld b,a
    ld a,(ring_length)
    sub b
    ld (ring_rest),a
    ld ixh,32
.split_row:
    ld c,ixl
    ld b,0
    ldir
    ld a,e
    sub 32
    ld e,a
    jr nc,.split_rest
    dec d
.split_rest:
    ld a,(ring_rest)
    ld c,a
    ldir
    ld c,iyh
    add hl,bc
    ld a,h
    cp $c0
    jr c,.split_bank
    sub $40
    ld h,a
    ld a,(maprow)
    and $80
    rlca
    xor 3
    ld ($7000),a
.split_bank:
    ex de,hl
    ld c,iyl
    add hl,bc
    ld a,h
    and 3
    or $d8
    ld h,a
    ex de,hl
    dec ixh
    jr nz,.split_row
    ; Preserve the original helper's final ring_y scratch value.
    ld a,(maprow)
    add a,32
    ld (ring_y),a
    ret
.strides:
    ld a,(ring_length)
    ld c,a
    ld a,128
    sub c
    ld iyh,a
    ld a,32
    sub c
    ld iyl,a
    ret

Ring_Prepare:
    ld a,(oldrow)
    cp $ff
    jr z,.full
    ld b,a
    ld a,(maprow)
    sub b
    ld (ring_dy),a
    inc a
    cp 3
    jr nc,.full
    ld a,(oldcol)
    ld b,a
    ld a,(mapcol)
    sub b
    ld (ring_dx),a
    inc a
    cp 3
    jr nc,.full
    ld a,(ring_dx)
    ld b,a
    ld a,(ring_dy)
    or b
    ret z
    ld a,(ring_dx)
    or a
    jr z,.vertical
    ld a,(mapcol)
    ld b,2
    ld c,a
    ld a,(ring_dx)
    cp 1
    ld a,c
    jr nz,.columns
    add a,23
    inc b
.columns:
    ld (ring_x),a
    ld a,b
    ld (ring_length),a
    call Ring_LoadColumns
.vertical:
    ld a,(ring_dy)
    or a
    jr z,.refresh
    ld b,a
    ld a,(maprow)
    inc b
    jr z,.row
    add a,31
.row:
    ld (ring_y),a
    ld a,(mapcol)
    ld (ring_x),a
    ld a,32
    ld (ring_length),a
    call Ring_LoadRun
    jr .refresh
.full:
    ld a,(mapcol)
    ld (ring_x),a
    ld a,32
    ld (ring_length),a
    call Ring_LoadColumns
.refresh:
    ld a,(mapcol)
    ld (oldcol),a
    ld a,(maprow)
    ld (oldrow),a
    ld c,a
    IFDEF GAME_RING_REFRESH
    ld a,4
    ld ($7000),a
    ld a,(mapcol)
    jp $aa00
    ENDIF
    ld a,(mapcol)
    call Ring_Position
    ld ix,boundary_ids
    ld de,ring_pointers
    ld b,28
.ids:
    ld a,l
    ld (de),a
    inc e
    ld a,h
    sub $b8
    ld (de),a
    inc e
    ld a,(hl)
    ld (ix+2),a
    push hl
    ld a,l
    add a,24
    and 31
    ld c,a
    ld a,l
    and $e0
    or c
    ld l,a
    ld (de),a
    inc e
    ld a,h
    sub $b8
    ld (de),a
    inc e
    ld a,(hl)
    ld (ix+0),a
    ld a,l
    inc a
    and 31
    ld c,a
    ld a,l
    and $e0
    or c
    ld l,a
    ld a,(hl)
    ld (ix+1),a
    pop hl
    ld a,l
    add a,32
    ld l,a
    jr nc,.same_page
    inc h
    ld a,h
    and 3
    or $d8
    ld h,a
.same_page:
    inc ix
    inc ix
    inc ix
    djnz .ids
    ret

Ring_Address:
    ; Original-ID cache address -> corresponding inactive name-table address.
    ld a,h
    and 3
    or $20
    ld h,a
    ld a,(back)
    or a
    jr z,.set
    set 2,h
.set:
    jp address

Ring_UploadColumn:
    ; A is an absolute world column; upload original IDs in every physical row.
    ld c,0
    call Ring_Position
    ld e,l
    ld a,(back)
    add a,a
    add a,a
    or $60
    ld d,a
    di
    reg 14,0
    ei
    ld b,32
.row:
    di
    ld a,e
    out ($99),a
    ld a,d
    out ($99),a
    ei
    ld a,(hl)
    out ($98),a
    ld a,l
    add a,32
    ld l,a
    ld e,a
    jr nc,.same_page
    inc h
    inc d
.same_page:
    djnz .row
    ret

Ring_UploadRow:
    ; A is an absolute world row; upload 32 original IDs before HUD overrides.
    ld c,a
    xor a
    call Ring_Position
    push hl
    call Ring_Address
    pop hl
    ld de,32
    jp upload

Ring_UploadNames:
    ld hl,seen
    ld a,(back)
    or a
    jr z,.seen
    inc hl
    inc hl
.seen:
    ld (ring_seen_ptr),hl
    ld a,(hl)
    cp $ff
    jr z,.full
    ld b,a
    ld a,(mapcol)
    sub b
    ld (ring_dx),a
    inc a
    cp 3
    IFDEF GAMEPLAY_CONFIGURED
    IF GAME_RENDER_OPT
    jp nc,GameNameStream_Wide
    ELSE
    jr nc,.full
    ENDIF
    ELSE
    jr nc,.full
    ENDIF
    inc hl
    ld a,(hl)
    ld b,a
    ld a,(maprow)
    sub b
    ld (ring_dy),a
    inc a
    cp 3
    IFDEF GAMEPLAY_CONFIGURED
    IF GAME_RENDER_OPT
    jp nc,GameNameStream_Wide
    ELSE
    jr nc,.full
    ENDIF
    ELSE
    jr nc,.full
    ENDIF
    ld a,(ring_dx)
    or a
    jr z,.vertical
    ld b,a
    ld a,(mapcol)
    inc b
    jr z,.left
    add a,23
    jr .column
.left:
    inc a
.column:
    call Ring_UploadColumn
.vertical:
    ld a,(ring_dy)
    or a
    jr z,.ready
    ld b,a
    ld a,(maprow)
    inc b
    jr z,.row
    IFDEF GAMEPLAY_CONFIGURED
    IF GAME_RENDER_OPT
    add a,27
    ELSE
    add a,31
    ENDIF
    ELSE
    add a,31
    ENDIF
.row:
    call Ring_UploadRow
    jr .ready
.full:
    ld hl,world_ids
    push hl
    call Ring_Address
    pop hl
    ld de,1024
    call upload
.ready:
    ld hl,(ring_seen_ptr)
    ld a,(mapcol)
    ld (hl),a
    inc hl
    ld a,(maprow)
    ld (hl),a
    ; Two edge names, six HUD names and one left-edge name per visible row.
    ld a,(mapcol)
    add a,24
    and 31
    ld b,a
    ld a,32
    sub b
    cp 9
    jr c,.split
    ld a,8
.split:
    ld (ring_first),a
    ld b,a
    ld a,8
    sub b
    ld (ring_rest),a
    ; Dispatch once for the physical row split. DE walks pointer records and
    ; HL walks RAM names directly, including the eight unrolled OUTI writes.
    ; A two-row loop retains the same DI/EI and port-write ordering.
    ld a,(ring_rest)
    add a,a
    ld l,a
    ld h,0
    ld de,Ring_HudTargets
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    push de
    di
    reg 14,0
    ei
    ld a,(back)
    add a,a
    add a,a
    or $40
    ld ixl,a
    ld ixh,14
    ld de,ring_pointers
    ld hl,names
    ld c,$98
    ret

    MACRO game_ring_hud_rows label,first
label:
.row:
    DUP 2
    di
    ld a,(de)
    out ($99),a
    inc e
    ld a,(de)
    or ixl
    out ($99),a
    inc e
    ei
    ld a,(hl)
    out ($98),a
    di
    ld a,(de)
    out ($99),a
    IF first < 8
    and $e0
    ld iyl,a
    ENDIF
    inc e
    ld a,(de)
    or ixl
    out ($99),a
    IF first < 8
    ld iyh,a
    ENDIF
    inc e
    ei
    ld a,l
    add a,24
    ld l,a
    ld b,first
    ; Counts are fixed by this macro. Retain OUTI's pointer/B/port order while
    ; removing only OTIR's five-cycle repeat overhead between output bytes.
    DUP first
    outi
    EDUP
    IF first < 8
    di
    ld a,iyl
    out ($99),a
    ld a,iyh
    out ($99),a
    ei
    ld b,8-first
    DUP 8-first
    outi
    EDUP
    ENDIF
    EDUP
    dec ixh
    jp nz,.row
    ex de,hl             ; Preserve the previous helper's returned pointers.
    ret
    ENDM

    game_ring_hud_rows Ring_Hud8,8
    game_ring_hud_rows Ring_Hud7,7
    game_ring_hud_rows Ring_Hud6,6
    game_ring_hud_rows Ring_Hud5,5
    game_ring_hud_rows Ring_Hud4,4
    game_ring_hud_rows Ring_Hud3,3
    game_ring_hud_rows Ring_Hud2,2
    game_ring_hud_rows Ring_Hud1,1
Ring_HudTargets:
    dw Ring_Hud8,Ring_Hud7,Ring_Hud6,Ring_Hud5
    dw Ring_Hud4,Ring_Hud3,Ring_Hud2,Ring_Hud1
