; Persistent 32x32 character-name ring. Original IDs stay in RAM independently
; of the HUD overrides in VRAM. No VRAM reads or bitmap movement are used.
Ring_Position:
    ; A=world tile X, C=world tile Y -> HL=original-ID cache address.
    and 31
    ld e,a
    ld a,c
    and 31
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld d,$d8
    add hl,de
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
    ld ixh,32
.fast:
    ld a,(ring_length)
    ld c,a
    ld b,0
    ldir
    ld a,(ring_length)
    ld c,a
    ld a,128
    sub c
    ld c,a
    ld b,0
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
    ld a,(ring_length)
    ld c,a
    ld a,32
    sub c
    ld c,a
    ld b,0
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
    ld b,32
.row:
    push bc
    call Ring_LoadRun
    ld hl,ring_y
    inc (hl)
    pop bc
    djnz .row
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
    ld a,(mapcol)
    call Ring_Position
    ld ix,boundary_ids
    ld iy,ring_pointers
    ld b,28
.ids:
    ld (iy+0),l
    ld a,h
    and 3
    or $20
    ld (iy+1),a
    ld a,(hl)
    ld (ix+2),a
    ld a,l
    add a,24
    and 31
    ld e,a
    ld a,l
    and $e0
    or e
    ld l,a
    ld (iy+2),l
    ld a,h
    and 3
    or $20
    ld (iy+3),a
    ld a,(hl)
    ld (ix+0),a
    ld a,l
    inc a
    and 31
    ld e,a
    ld a,l
    and $e0
    or e
    ld l,a
    ld a,(hl)
    ld (ix+1),a
    ld l,(iy+0)
    ld h,(iy+1)
    ld a,h
    and 3
    or $d8
    ld h,a
    ld de,32
    add hl,de
    ld a,h
    and 3
    or $d8
    ld h,a
    inc ix
    inc ix
    inc ix
    ld de,4
    add iy,de
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
    ld b,32
.row:
    push bc
    push hl
    call Ring_Address
    pop hl
    ld a,(hl)
    out ($98),a
    ld de,32
    add hl,de
    pop bc
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
    jr nc,.full
    inc hl
    ld a,(hl)
    ld b,a
    ld a,(maprow)
    sub b
    ld (ring_dy),a
    inc a
    cp 3
    jr nc,.full
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
    add a,31
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
    ld ix,ring_pointers
    ld iy,names
    di
    reg 14,0
    ei
    ld a,(back)
    add a,a
    add a,a
    or $40
    ld d,a
    ld b,28
.hud_row:
    push bc
    di
    ld a,(ix+0)
    out ($99),a
    ld a,(ix+1)
    or d
    out ($99),a
    ei
    ld a,(iy+0)
    out ($98),a
    di
    ld a,(ix+2)
    out ($99),a
    ld a,(ix+3)
    or d
    out ($99),a
    ei
    push iy
    pop hl
    ld a,l
    add a,24
    ld l,a
    ld a,(ring_first)
    ld b,a
    ld c,$98
    otir
    ld a,(ring_rest)
    or a
    jr z,.next
    di
    ld a,(ix+2)
    and $e0
    out ($99),a
    ld a,(ix+3)
    or d
    out ($99),a
    ei
    ld a,(ring_rest)
    ld b,a
    ld c,$98
    otir
.next:
    ld bc,4
    add ix,bc
    ld bc,32
    add iy,bc
    pop bc
    djnz .hud_row
    ret
