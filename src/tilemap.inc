; SCREEN 4 name-table experiment. Patterns/colors retain original 8x8 dimensions.
TileMap_Init:
    ld a,TILE_DATA_BANK
    ld ($7000),a
    vdp_write 14,0
    xor a
    out ($99),a
    ld a,$40
    out ($99),a
    ld hl,$8000
    ld de,8192
    call upload
    vdp_write 14,1
    xor a
    out ($99),a
    ld a,$40
    out ($99),a
    ld hl,$a000
    ld de,8192
    call upload
    vdp_write 3,$7f
    vdp_write 4,3
    vdp_write 10,1
    ret

TileMap_Copy:
    ld a,(tile_x)
    ld c,a
    cp STAGE_COLUMNS
    jr nc,.flower
    ld a,(tile_y)
    cp STAGE_ROWS
    jr c,.lookup
.flower:
    ld hl,stage_flower_phase
    ld e,c
    ld d,0
    add hl,de
    ld c,(hl)
    ld a,(tile_y)
    ld e,a
    ld hl,stage_flower_phase
    add hl,de
    ld a,(hl)
.lookup:
    ld l,a
    and 128
    rlca
    add a,STAGE_ID_BANK
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
    ld b,0
    add hl,bc
    ld de,$8000
    add hl,de
    ld c,(hl)
    ld a,(tile_y)
    and 31
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(tile_x)
    and 31
    ld e,a
    ld d,0
    add hl,de
    ld de,$2000
    add hl,de
    ld a,(tile_x)
    and 32
    rrca
    rrca
    rrca
    rrca
    ld b,14
    ei
    nop
    di
    call register
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ld a,c
    out ($98),a
    ret
