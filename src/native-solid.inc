; Conservative uniform-color classification. FF means use the original pixels.
Native_SolidFirst EQU $e626
Native_SolidCount EQU $e628
Native_SolidColor EQU $e629

Native_ClassifyTile:
    ld a,(Native_TileAttr)
    and 63
    ld e,a
    ld d,0
    ld hl,Native_BlackMasks
    add hl,de
    ld a,(hl)
    cpl
    ld c,a
    ld a,(Native_TileCode)
    ld e,a
    ld hl,Native_TileMasks
    add hl,de
    ld a,(hl)
    ld b,a
    and c
    jr nz,.single
    ld a,BLACK                ; both black indices have identical background RGB
    jr .done
.single:
    ld a,b
    ld c,0
    cp 1
    jr z,.lookup
    ld c,5
    cp 2
    jr z,.lookup
    ld c,10
    cp 4
    jr z,.lookup
    ld c,15
    cp 8
    jr z,.lookup
    ld a,$ff
    jr .done
.lookup:
    ld b,0
    ld a,(Native_TileAttr)
    and 63
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Native_Lookup
    add hl,de
    add hl,bc
    ld a,(hl)
    and 15
.done:
    ld (Native_TileBlack),a     ; clean-cache tag: color0..15, or FF nonuniform
    ret

; Merge equal solid cells up to the row edge, including already clean neighbors.
; No pixel outside the frozen snapshot is inferred from a captured arcade frame.
Native_DrawSolidRun:
    ld (Native_SolidColor),a
    ld hl,(Native_TileIndex)
    ld (Native_SolidFirst),hl
    xor a
    ld (Native_SolidCount),a
.cell:
    ; Extending a fill across an unchanged solid neighbor changes no pixels.
    ; Preserve existing actor/page dirtiness without introducing another copy.
    ld hl,(Native_TileIndex)
    ld de,Native_ShadowBlack
    add hl,de
    ld a,(Native_SolidColor)
    cp (hl)
    call nz,Native_DirtyBothPages
    call Native_RecordTile
    call Native_ClearRenderBit
    ld a,(Native_SolidCount)
    inc a
    ld (Native_SolidCount),a
    ld hl,(Native_TileIndex)
    ld a,l
    and 31
    cp 31
    jr z,.send
    inc hl
    ld (Native_TileIndex),hl
    call Native_ReadFrameTile
    ld hl,(Native_TileIndex)
    ld de,Native_ShadowCodes
    add hl,de
    ld a,(Native_TileCode)
    cp (hl)
    jr nz,.classify
    ld hl,(Native_TileIndex)
    ld de,Native_ShadowAttrs
    add hl,de
    ld a,(Native_TileAttr)
    cp (hl)
    jr z,.send                ; leave unchanged neighbors to the cheap skip path
.classify:
    call Native_ClassifyTile
    ld b,a
    ld a,(Native_SolidColor)
    cp b
    jr z,.cell
.send:
    ld hl,Native_SolidCommand
    ld de,Native_Command
    ld bc,15
    ldir
    ld hl,(Native_SolidFirst)
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
    ld a,(Native_SolidCount)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld (Native_Command+8),hl
    ld a,(Native_SolidColor)
    ld b,a
    rlca
    rlca
    rlca
    rlca
    or b
    ld (Native_Command+12),a
    call Native_SendCommand
    scf
    ret
Native_SolidCommand:
    db 0,0,0,0,0,0,0,2,8,0,8,0,0,0,$c0

Native_ClearRenderBit:
    ld hl,(Native_TileIndex)
    ld a,l
    and 7
    ld b,a
    ld c,1
    jr z,.mask
.shift:
    sla c
    djnz .shift
.mask:
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    set 7,l
    ld h,Native_RenderDirty/256
    ld a,c
    cpl
    and (hl)
    ld (hl),a
    ret
