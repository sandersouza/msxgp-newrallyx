; Immutable 24x8 maze/flower strips in otherwise unused VRAM lines208..231.
; Descriptor matching is exact; every other sequence uses the normal tile path.
Native_StripCount EQU $e680
Native_StripX EQU $e681
Native_StripY EQU $e682

Native_WarmStrips:
    ld a,3
    call Native_HUDMapAssets
    ld hl,$a800
    xor a
    ld (Native_StripX),a
    ld a,208
    ld (Native_StripY),a
    ld a,NATIVE_STRIP_COUNT
    ld (Native_StripCount),a
.strip:
    ld a,(Native_StripX)
    ld e,a                    ; packed byte offset, twelve per strip
    ld a,(Native_StripY)
    ld d,a
    ld a,8
.row:
    push af
    ld a,7
    ld (Native_HUDWriteBank),a
    ld a,d
    rrca
    and $80
    or e
    ld (Native_HUDWriteAddress),a
    ld a,d
    rrca
    and $3f
    ld (Native_HUDWriteAddress+1),a
    ld bc,$0c98
    call Native_HUDOTIR
    inc d
    pop af
    dec a
    jr nz,.row
    ld a,(Native_StripX)
    add a,12
    cp 120
    jr c,.x
    xor a
    ld (Native_StripX),a
    ld a,(Native_StripY)
    add a,8
    ld (Native_StripY),a
    xor a
.x:
    ld (Native_StripX),a
    ld a,(Native_StripCount)
    dec a
    ld (Native_StripCount),a
    jr nz,.strip
    jp Native_RestoreGame

Native_TryStrip:
    ld a,(Native_TileCode)
    cp 144
    jr z,.eligible
    cp 146
    jr z,.eligible
    cp $56
    jp c,.miss
    cp $66
    jp nc,.miss
.eligible:
    ld hl,(Native_TileIndex)
    ld a,l
    and 31
    cp 30
    jp nc,.miss               ; a GPU strip must never cross a tile row
    ld a,(Native_TileAttr)
    ld b,a
    rrca
    rrca
    rrca
    rrca
    and 15
    xor b
    ld b,a
    ld a,(Native_TileCode)
    xor b
    and 15
    add a,a
    ld e,a
    ld d,0
    ld hl,Native_StripOffsets
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld hl,Native_StripKeys
    add hl,de
    ld a,(hl)
    or a
    jp z,.miss
    ld (Native_StripCount),a
    inc hl
    push hl
    pop ix
.candidate:
    ld hl,(Native_TileIndex)
    ld de,$2000
    add hl,de
    ld a,(ix+0)
    cp (hl)
    jr nz,.next
    inc hl
    ld a,(ix+1)
    cp (hl)
    jr nz,.next
    inc hl
    ld a,(ix+2)
    cp (hl)
    jr nz,.next
    dec hl
    dec hl
    set 2,h
    ld a,(ix+3)
    cp (hl)
    jr nz,.next
    inc hl
    ld a,(ix+4)
    cp (hl)
    jr nz,.next
    inc hl
    ld a,(ix+5)
    cp (hl)
    jr z,.hit
.next:
    ld de,8
    add ix,de
    ld a,(Native_StripCount)
    dec a
    ld (Native_StripCount),a
    jr nz,.candidate
.miss:
    xor a
    ret
.hit:
    ld hl,Native_StripCommand
    ld de,Native_Command
    ld bc,15
    ldir
    ld a,(ix+6)
    ld (Native_Command),a
    ld a,(ix+7)
    ld (Native_Command+2),a
    ld hl,(Native_TileIndex)
    ld a,l
    and 31
    add a,a
    add a,a
    add a,a
    ld (Native_Command+4),a
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,h
    add a,a
    add a,a
    add a,a
    ld (Native_Command+6),a
    call Native_SendCommand
    call Native_DirtyBothPages
    ld hl,(Native_TileIndex)
    ld a,l
    and 7
    cp 6
    jr c,.one_group
    inc hl
    inc hl
    ld (Native_TileIndex),hl
    call Native_DirtyBothPages
    ld hl,(Native_TileIndex)
    dec hl
    dec hl
    ld (Native_TileIndex),hl
.one_group:
    ; Copy all three exact descriptors together. The immutable snapshot is
    ; still mapped; only our host tags and dirty bits change.
    ld hl,(Native_TileIndex)
    ld e,l
    ld a,h
    add a,Native_ShadowCodes/256
    ld d,a
    ld a,h
    add a,$20
    ld h,a
    ld bc,3
    ldir
    ld hl,(Native_TileIndex)
    ld e,l
    ld a,h
    add a,Native_ShadowAttrs/256
    ld d,a
    ld a,h
    add a,$24
    ld h,a
    ld bc,3
    ldir
    ld hl,(Native_TileIndex)
    ld a,h
    add a,Native_ShadowBlack/256
    ld h,a
    ld (hl),$ff
    inc hl
    ld (hl),$ff
    inc hl
    ld (hl),$ff
    ld hl,(Native_TileIndex)
    ld a,l
    and 7
    add a,a
    ld e,a
    ld d,0
    push hl
    ld hl,Native_StripClearMasks
    add hl,de
    ld c,(hl)
    inc hl
    ld b,(hl)
    pop hl
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    set 7,l
    ld h,Native_RenderDirty/256
    ld a,c
    and (hl)
    ld (hl),a
    ld a,b
    inc a
    jr z,.mask_done
    inc hl
    ld a,b
    and (hl)
    ld (hl),a
.mask_done:
    scf
    ret
Native_StripCommand:
    db 0,0,208,3,0,0,0,2,24,0,8,0,0,0,$d0
Native_StripOffsets EQU $3a00
Native_StripKeys EQU $3a20
Native_StripClearMasks:
    dw $fff8,$fff1,$ffe3,$ffc7,$ff8f,$ff1f,$fe3f,$fc7f
