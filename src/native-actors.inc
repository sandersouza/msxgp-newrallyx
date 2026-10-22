; Six original bitmap actors. The scene owns no guest bytes. Each tile-sized
; piece honors original tile priority, and wrapping is split at tile borders.
Native_ActorTags EQU $e200
Native_ActorPalettes EQU $e280
Native_ActorValid EQU $e300
Native_ActorX EQU $e600
Native_ActorY EQU $e601
Native_ActorU0 EQU $e602
Native_ActorU1 EQU $e603
Native_ActorV0 EQU $e604
Native_ActorV1 EQU $e605
Native_ActorU EQU $e606
Native_ActorV EQU $e607
Native_ActorSlot EQU $e608
Native_ActorFlags EQU $e609
Native_ActorPalette EQU $e60a
Native_ActorCount EQU $e60b
Native_ActorW EQU $e60c
Native_ActorH EQU $e60d
Native_ActorDX EQU $e60e
Native_ActorDY EQU $e60f
Native_ActorMode EQU $e610
Native_ActorBlocked EQU $e611

Native_DrawActors:
    ld a,(Native_FrameActor)
    add a,a
    ld l,a
    ld h,0
    ld bc,Native_FrameOAM
    add hl,bc
    push hl
    pop ix
    ld bc,Native_FrameAttrs-Native_FrameOAM
    add hl,bc
    push hl
    pop iy                    ; original highest-priority slot 1e is drawn last
.actor:
    ld a,(ix+$01)
    cp 212
    jp nc,.next
    ld b,a
    ld a,(iy+1)
    and $80
    jp nz,.next               ; ninth X bit places this actor outside the maze
    ld a,b
    ld c,0
    cp 12
    jr nc,.left
    ld a,12
    sub b
    ld c,a
.left:
    ld a,c
    ld (Native_ActorU0),a
    ld a,212
    sub b
    cp 16
    jr c,.right
    ld a,16
.right:
    ld (Native_ActorU1),a
    ld a,(Native_FrameScrollX)
    add a,b
    sub 3
    ld (Native_ActorX),a
    ld a,(iy+0)
    cp 19
    jp c,.next
    cp 235
    jp nc,.next
    ld b,a
    ld c,0
    cp 220
    jr c,.top
    sub 219
    ld c,a
.top:
    ld a,c
    ld (Native_ActorV0),a
    ld a,b
    sub 18
    cp 16
    jr c,.bottom
    ld a,16
.bottom:
    ld (Native_ActorV1),a
    ld a,241
    sub b
    ld b,a
    ld a,(Native_FrameScrollY)
    add a,b
    ld (Native_ActorY),a
    ld a,(ix+0)
    ld (Native_ActorFlags),a
    ; Different car palettes must not evict the same pattern every frame.
    ld b,a
    ld a,(iy+1)
    and 7
    rlca
    rlca
    rlca
    rlca
    xor b
    and 127
    ld (Native_ActorSlot),a
    ld e,a
    ld d,0
    ld hl,Native_ActorTags
    add hl,de
    ld a,(Native_ActorFlags)
    cp (hl)
    jr nz,.upload
    ld hl,Native_ActorPalettes
    add hl,de
    ld a,(iy+1)
    and 63
    cp (hl)
    jr nz,.upload
    ld hl,Native_ActorValid
    add hl,de
    ld a,(hl)
    or a
    jr nz,.cached
.upload:
    ld a,(iy+1)
    and 63
    ld (Native_ActorPalette),a
    push ix
    call Native_UploadActor
    pop ix
.cached:
    xor a
    ld (Native_ActorMode),a
    ld (Native_ActorBlocked),a
.reset:
    ld a,(Native_ActorV0)
    ld (Native_ActorV),a
.row:
    ld a,(Native_ActorY)
    ld b,a
    ld a,(Native_ActorV)
    add a,b
    ld (Native_ActorDY),a
    and 7
    ld b,a
    ld a,8
    sub b
    ld b,a
    ld a,(Native_ActorV)
    ld c,a
    ld a,(Native_ActorV1)
    sub c
    cp b
    jr c,.height
    ld a,b
.height:
    ld (Native_ActorH),a
    ld a,(Native_ActorU0)
    ld (Native_ActorU),a
.column:
    ld a,(Native_ActorX)
    ld b,a
    ld a,(Native_ActorU)
    add a,b
    ld (Native_ActorDX),a
    and 7
    ld b,a
    ld a,8
    sub b
    ld b,a
    ld a,(Native_ActorU)
    ld c,a
    ld a,(Native_ActorU1)
    sub c
    cp b
    jr c,.width
    ld a,b
.width:
    ld (Native_ActorW),a
    ; Tile priority is uniform over this piece, even across the torus seam.
    ld a,(Native_ActorDY)
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(Native_ActorDX)
    rrca
    rrca
    rrca
    and 31
    ld e,a
    ld d,0
    add hl,de
    ld (Native_TileIndex),hl
    ld de,Native_ShadowAttrs
    add hl,de
    bit 5,(hl)
    jr z,.unblocked
    ld a,1
    ld (Native_ActorBlocked),a
    jr .advance
.unblocked:
    ld a,(Native_ActorMode)
    or a
    jr nz,.paint
    call Native_DirtyBothPages
    jr .advance
.paint:
    call Native_ActorPiece
.advance:
    ld a,(Native_ActorW)
    ld b,a
    ld a,(Native_ActorU)
    add a,b
    ld (Native_ActorU),a
    ld b,a
    ld a,(Native_ActorU1)
    cp b
    jp nz,.column
    ld a,(Native_ActorH)
    ld b,a
    ld a,(Native_ActorV)
    add a,b
    ld (Native_ActorV),a
    ld b,a
    ld a,(Native_ActorV1)
    cp b
    jp nz,.row
    ld a,(Native_ActorMode)
    or a
    jr nz,.next
    ld a,(Native_ActorBlocked)
    or a
    jr z,.fast
    ld a,1
    ld (Native_ActorMode),a
    jp .reset
.fast:
    call Native_ActorFast
.next:
    ld a,(Native_FrameActor)
    inc a
    ld (Native_FrameActor),a
    ret

; No priority tile intersects this actor: split only at the 256-pixel seams.
Native_ActorFast:
    ld a,(Native_ActorV0)
    ld (Native_ActorV),a
.row:
    ld a,(Native_ActorY)
    ld b,a
    ld a,(Native_ActorV)
    add a,b
    ld (Native_ActorDY),a
    neg
    ld b,a
    ld a,(Native_ActorV)
    ld c,a
    ld a,(Native_ActorV1)
    sub c
    ld c,a
    ld a,b
    or a
    ld a,c
    jr z,.height
    cp b
    jr c,.height
    ld a,b
.height:
    ld (Native_ActorH),a
    ld a,(Native_ActorU0)
    ld (Native_ActorU),a
.column:
    ld a,(Native_ActorX)
    ld b,a
    ld a,(Native_ActorU)
    add a,b
    ld (Native_ActorDX),a
    neg
    ld b,a
    ld a,(Native_ActorU)
    ld c,a
    ld a,(Native_ActorU1)
    sub c
    ld c,a
    ld a,b
    or a
    ld a,c
    jr z,.width
    cp b
    jr c,.width
    ld a,b
.width:
    ld (Native_ActorW),a
    call Native_ActorPiece
    ld a,(Native_ActorW)
    ld b,a
    ld a,(Native_ActorU)
    add a,b
    ld (Native_ActorU),a
    ld b,a
    ld a,(Native_ActorU1)
    cp b
    jr nz,.column
    ld a,(Native_ActorH)
    ld b,a
    ld a,(Native_ActorV)
    add a,b
    ld (Native_ActorV),a
    ld b,a
    ld a,(Native_ActorV1)
    cp b
    jr nz,.row
    ret

Native_ActorPiece:
    ld hl,Native_ActorCommand
    ld de,Native_Command
    ld bc,15
    ldir
    ld a,(Native_ActorSlot)
    and 15
    rlca
    rlca
    rlca
    rlca
    ld b,a
    ld a,(Native_ActorU)
    add a,b
    ld (Native_Command),a
    ld a,(Native_ActorSlot)
    and $70
    add a,80
    ld b,a
    ld a,(Native_ActorV)
    add a,b
    ld (Native_Command+2),a
    ld a,(Native_ActorDX)
    ld (Native_Command+4),a
    ld a,(Native_ActorDY)
    ld (Native_Command+6),a
    ld a,(Native_DrawPage)
    ld (Native_Command+7),a
    ld a,(Native_ActorW)
    ld (Native_Command+8),a
    ld a,(Native_ActorH)
    ld (Native_Command+10),a
    jp Native_SendCommand
Native_ActorCommand:
    db 0,0,80,3,0,0,0,0,16,0,16,0,0,0,$98

Native_UploadActor:
    call Native_WaitCommand
    ld a,(Native_ActorFlags)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    set 7,h
    ld a,1
    call Native_HUDMapAssets
    ld de,Native_PackedBuffer
    ld bc,64
    ldir
    call Native_RestoreGame
    ld a,(Native_ActorPalette)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Native_Lookup
    add hl,de
    ld de,Native_PixelBuffer
    ld ix,Native_PackedBuffer
    ld b,64
.convert:
    ld a,(ix+0)
    rrca
    rrca
    rrca
    rrca
    and 15
    call Native_UploadTile.pair
    ld a,(ix+0)
    and 15
    call Native_UploadTile.pair
    inc ix
    djnz .convert
    ld a,(Native_ActorSlot)
    ld c,a
    and 15
    add a,a
    add a,a
    add a,a
    ld e,a
    ld a,c
    and $70
    add a,80
    ld d,a
    ld hl,Native_PixelBuffer
    ld a,16
.row:
    push af
    ld a,d
    rlca
    and 1
    or 6                     ; actor atlas crosses the 16KB VRAM bank boundary
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
    ld bc,$0898
    call Native_HUDOTIR
    inc d
    pop af
    dec a
    jr nz,.row
    ld a,(Native_ActorSlot)
    ld e,a
    ld d,0
    ld hl,Native_ActorTags
    add hl,de
    ld a,(Native_ActorFlags)
    ld (hl),a
    ld hl,Native_ActorPalettes
    add hl,de
    ld a,(Native_ActorPalette)
    ld (hl),a
    ld hl,Native_ActorValid
    add hl,de
    ld (hl),1
    ret
