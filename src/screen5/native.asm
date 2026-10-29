; Stage-3 entry. Native_Reset is supplied by the explicit loader probe fixture.
    INCLUDE "native-state.inc"
    ORG $4000
    db "AB"
    dw Native_Boot,0,0,0,0,0,0
Native_Boot:
    di
    ld sp,NATIVE_STACK
    IF NATIVE_VIDEO
    ld a,5
    call $005f
    di
    ENDIF
    xor a
    ld hl,NATIVE_STATE
    ld de,NATIVE_STATE+1
    ld bc,127
    ld (hl),a
    ldir
    inc a
    ld (Native_Status),a
    in a,($a8)
    ld (Native_Primary),a
    rlca
    rlca
    and 3
    ld c,a
    ld b,0
    ld hl,$fcc1
    add hl,bc
    ld a,(hl)
    and $80
    or c
    ld c,a
    ld de,4
    add hl,de
    ld a,(hl)
    and $c0
    rrca
    rrca
    rrca
    rrca
    or c
    ld (Native_RAMSlot),a
    ld hl,$fcc5
    ld de,Native_InitialSlots
    ld bc,4
    ldir
    ld a,(Native_RAMSlot)
    ld h,$80
    call $0024
    di
    ld hl,Native_LoaderImage
    ld de,NATIVE_LOADER
    ld bc,Native_LoaderEnd-Native_LoaderStart
    ldir
    jp Native_LoaderStart
Native_LoaderImage:
    PHASE NATIVE_LOADER
    INCLUDE "native-loader.inc"
    DEPHASE
    ASSERT Native_LoaderEnd <= NATIVE_LOADER_LIMIT
