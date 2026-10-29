; Two bitplanes queue changed physical name cells for each back table.
; No VRAM reads or copies; fixed HUD/edge names are published by the ring first.
GameDirty_Lengths EQU $c096
GameDirty_Mask EQU $c098
GameDirty_Covered EQU $c099
GameDirty_Address EQU $c09a
GameDirty_Bits EQU $2600          ; two128-byte bitsets
GameDirty_Queues EQU $2700        ; two128-byte nonzero-byte queues

GameDirty_Mark:
    ; HL=changed world_ids address; preserve all caller registers.
    push af
    push bc
    push de
    push hl
    push hl
    ld a,l
    and 7
    ld e,a
    ld d,0
    ld hl,GameDirty_Masks
    add hl,de
    ld c,(hl)
    pop hl
    ld a,h
    and 3
    rrca
    rrca
    rrca
    ld d,a
    ld a,l
    srl a
    srl a
    srl a
    or d
    ld b,a
    ld e,a
    ld d,GameDirty_Bits>>8
    ld a,(de)
    or a
    jr nz,.first_present
    ld a,(GameDirty_Lengths)
    ld l,a
    ld h,GameDirty_Queues>>8
    ld (hl),b
    ld hl,GameDirty_Lengths
    inc (hl)
.first_present:
    ld a,(de)
    or c
    ld (de),a
    set 7,e
    ld a,(de)
    or a
    jr nz,.second_present
    ld a,(GameDirty_Lengths+1)
    or $80
    ld l,a
    ld h,GameDirty_Queues>>8
    ld (hl),b
    ld hl,GameDirty_Lengths+1
    inc (hl)
.second_present:
    ld a,(de)
    or c
    ld (de),a
    pop hl
    pop de
    pop bc
    pop af
    ret

GameDirty_Plan:
    ; Prefer one sequential refill when individual writes would cost more.
    xor a
    ld (GameDirty_Covered),a
    ld hl,GameDirty_Lengths
    ld de,seen
    ld a,(back)
    or a
    jr z,.selected
    inc hl
    inc de
    inc de
.selected:
    ld a,(hl)
    or a
    ret z
    cp 24
    jr nc,.full
    ld a,(de)
    cp $ff
    ret nz
.full:
    ld a,$ff
    ld (de),a
    ld (GameDirty_Covered),a
    ret

GameDirty_Upload:
    ld a,(back)
    or a
    ld hl,GameDirty_Lengths
    ld ix,GameDirty_Queues
    ld iy,GameDirty_Bits
    jr z,.selected
    inc hl
    ld ix,GameDirty_Queues+128
    ld iy,GameDirty_Bits+128
.selected:
    ld a,(hl)
    or a
    ret z
    ld b,a
    ld (hl),0
    ld a,(GameDirty_Covered)
    or a
    jr z,.sparse
    push iy
    pop hl
    ld (hl),0
    ld d,h
    ld e,l
    inc de
    ld bc,127
    ldir
    ret
.sparse:
    di
    reg 14,0
    ei
.group:
    ld e,(ix+0)
    inc ix
    ld d,0
    push iy
    pop hl
    add hl,de
    ld a,(hl)
    ld (hl),0
    ld (GameDirty_Mask),a
    ld l,e
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,world_ids
    add hl,de
    ld (GameDirty_Address),hl
.bit:
    ld a,(GameDirty_Mask)
    srl a
    ld (GameDirty_Mask),a
    call c,GameDirty_One
    ld hl,(GameDirty_Address)
    inc hl
    ld (GameDirty_Address),hl
    ld a,(GameDirty_Mask)
    or a
    jr nz,.bit
    djnz .group
    ret

GameDirty_One:
    ld hl,(GameDirty_Address)
    ld a,(mapcol)
    ld e,a
    ld a,l
    and 31
    sub e
    and 31
    cp 1
    ret c
    cp 24
    ret nc
    ld a,h
    and 3
    rlca
    rlca
    rlca
    ld d,a
    ld a,l
    rrca
    rrca
    rrca
    rrca
    rrca
    and 7
    or d
    ld e,a
    ld a,(maprow)
    ld d,a
    ld a,e
    sub d
    and 31
    cp 28
    ret nc
    ld a,(back)
    add a,a
    add a,a
    ld d,a
    ld a,h
    and 3
    or $60
    or d
    ld d,a
    di
    ld a,l
    out ($99),a
    ld a,d
    out ($99),a
    ei
    ld a,(hl)
    out ($98),a
    ret
GameDirty_Masks:
    db 1,2,4,8,16,32,64,128
