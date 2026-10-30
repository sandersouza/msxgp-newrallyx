; Module contract: Cold flag glyph/name cache generation; restores main Page0 mapping.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
GameSession_BuildFlags:
    call GameSession_ClearFlags
    xor a
    ld (GameSession_Phase),a
.phase:
    ld a,(GameSession_Phase)
    and 7
    ld (fx),a
    ld a,(GameSession_Phase)
    REPT 3
    srl a
    ENDR
    ld (fy),a
    ld a,(GameSession_Phase)
    add a,4
    ld ($7000),a
    call $a300
    xor a
    ld (Game_RadarCount),a
    call GameSession_DrawFlagDots
    call GameSession_EncodeFlags
    ld a,(GameSession_Phase)
    call GameSession_WriteFlags
    ld hl,GameSession_Phase
    inc (hl)
    ld a,(hl)
    cp 64
    jr nz,.phase
    xor a
    ld (GameSession_FlagGeneration),a
    ld (GameSession_FlagIndex),a
    ld hl,Flag_Active+1
    ld b,10
.collected:
    push bc
    push hl
    ld a,(hl)
    or a
    call z,GameSession_RemoveFlag
    pop hl
    inc hl
    ld a,(GameSession_FlagIndex)
    inc a
    ld (GameSession_FlagIndex),a
    pop bc
    djnz .collected
    ld a,$ff
    ld hl,GameSession_FlagLoaded
    ld b,8
.keys:
    ld (hl),a
    inc hl
    djnz .keys
    ret

GameSession_DrawFlagDots:
    ld ix,Flag_Records
    ld b,10
.dot:
    push bc
    call GameSession_FlagCoordinates
    call Game_RadarDot
    ld de,6
    add ix,de
    pop bc
    djnz .dot
    ret
GameSession_FlagCoordinates:
    ld a,(ix+0)
    and 31
    add a,8
    ld (Game_RadarX),a
    ld a,(ix+1)
    sub $98
    REPT 3
    add a,a
    ENDR
    ld c,a
    ld a,(ix+0)
    REPT 3
    rlca
    ENDR
    and 7
    or c
    jp Game_RadarCellY

GameSession_EncodeFlags:
    ld a,(Game_RadarCount)
    ld ($ce80),a
    ld b,a
    ld c,146
    ld hl,Game_RadarAddresses
    ld de,$ce81
.name:
    ld a,$21
    ld (de),a
    inc de
    push bc
    ldi
    ldi
    pop bc
    ld a,$36
    ld (de),a
    inc de
    ld a,c
    ld (de),a
    inc de
    inc c
    djnz .name
    ld a,$c9
    ld (de),a
    ld hl,Game_RadarPatterns
    ld de,$ceb4
    ld bc,80
    ldir
    ld hl,Game_RadarColors
    ld de,$cf04
    ld bc,80
    ldir
    ld ix,Flag_Records
    ld iy,$cf54
    ld b,10
.metadata:
    push bc
    call GameSession_FlagCoordinates
    ld a,(Game_RadarY)
    ld c,a
    ld a,(fy)
    add a,c
    ld (doty),a
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(Game_RadarX)
    ld c,a
    ld a,(fx)
    add a,c
    ld (dotx),a
    REPT 3
    rrca
    ENDR
    and 7
    add a,26
    ld e,a
    ld d,HIGH names
    add hl,de
    ld a,(hl)
    sub 64
    add a,a
    add a,a
    add a,a
    add a,52
    ld c,a
    ld a,(doty)
    and 7
    add a,c
    ld (iy+0),a
    ld a,(GameSession_Phase)
    ld (iy+1),a
    ld a,(dotx)
    and 7
    ld c,a
    ld a,$80
    jr z,.mask
.rotate:
    rrca
    dec c
    jr nz,.rotate
.mask:
    ld (iy+2),a
    ld de,3
    add iy,de
    ld de,6
    add ix,de
    pop bc
    djnz .metadata
    ret
