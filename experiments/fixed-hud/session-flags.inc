; Per-phase flag glyphs are prepared at round load in an independent16KiB RAM
; segment. Capturing one flag clears one known bit in each of64 cached phases.
; Names execute from that segment; active-frame work never rebuilds all flags.
GameSession_ClearFlags:
    ld a,(GameSession_FlagSegment)
    call .clear
    ld a,(GameSession_FlagOffSegment)
    call .clear
    jp GameSession_RestorePage0
.clear:
    out ($fc),a
    ld hl,0
    ld de,1
    ld bc,$3fff
    ld (hl),0
    ldir
    ret
GameSession_WriteFlags:
    ld d,a
    ld e,0
    ld hl,$ce80
    ld a,(GameSession_FlagSegment)
    out ($fc),a
    ld bc,256
    ldir
    ld a,(GameSession_FlagOffSegment)
    out ($fc),a
    ld a,(GameSession_Phase)
    ld d,a
    ld e,0
    ld hl,$ce80
    ld bc,256
    ldir
    ; S is native flag index9. Hide its known bit in the second immutable
    ; phase set; collection subsequently clears both sets without rebuilding.
    ld a,(GameSession_Phase)
    ld h,a
    ld l,239
    ld e,(hl)
    inc l
    ld d,(hl)
    inc l
    ld a,(hl)
    cpl
    ld c,a
    ex de,hl
    ld a,(hl)
    and c
    ld (hl),a
    jp GameSession_RestorePage0

GameSession_SelectFlags:
    ld a,(GameSession_Blink)
    or a
    ld a,(GameSession_FlagSegment)
    jr z,.selected
    ld a,(GameSession_FlagOffSegment)
.selected:
    out ($fc),a
    ret
GameSession_FlagKey:
    ld a,(GameSession_Blink)
    rlca
    rlca
    rlca
    ld b,a
    ld a,(GameSession_FlagGeneration)
    or b
    ret
GameSession_FlagNames:
    call GameSession_SelectFlags
    ld a,(phase)
    ld h,a
    ld l,1
    ld de,.done
    push de
    jp (hl)
.done:
    call GameSession_RestorePage0
    ret

GameSession_FlagCollected:
    ld a,(Flag_Last)
    dec a
    ld (GameSession_FlagIndex),a
    jp GameSession_RemoveFlag
GameSession_RemoveFlag:
    ld a,(GameSession_FlagSegment)
    call .segment
    ld a,(GameSession_FlagOffSegment)
    call .segment
    call GameSession_RestorePage0
    ld hl,GameSession_FlagGeneration
    inc (hl)
.done:
    ret
.segment:
    out ($fc),a
    ld a,(GameSession_FlagIndex)
    ld c,a
    add a,a
    add a,c
    add a,212
    ld l,a
    ld h,0
    ld b,64
.phase:
    ld e,(hl)
    inc l
    ld d,(hl)
    inc l
    ld a,(hl)
    cpl
    ld c,a
    dec l
    dec l
    push hl
    ex de,hl
    ld a,(hl)
    and c
    ld (hl),a
    pop hl
    inc h
    djnz .phase
    ret

GameSession_FlagUpload:
    ld a,(prior_phase)
    ld hl,phase
    cp (hl)
    jr nz,.upload
    ld a,(pattern_back)
    ld e,a
    ld d,0
    ld hl,GameSession_FlagLoaded
    add hl,de
    call GameSession_FlagKey
    cp (hl)
    ret z
    ld c,a
    xor (hl)
    and $7f
    jr nz,.upload
    ld (hl),c
    ld a,(Flag_Active+10)     ; S is index9, after the zero sentinel.
    or a
    ret z
    jp GameSession_FlagBlinkUpload
.upload:
    call GameSession_SelectFlags
    ld a,(phase)
    ld h,a
    ld l,0
    ld a,(hl)
    ld (GameSession_Count),a
    or a
    jr z,.done
    ld hl,$0490
    call GamePattern_Address
    ld a,(phase)
    ld h,a
    ld l,52
    ld a,(GameSession_Count)
    call tile_bytes
    call upload
    ld hl,$4490
    call GamePattern_Address
    ld a,(phase)
    ld h,a
    ld l,132
    ld a,(GameSession_Count)
    call tile_bytes
    call upload
.done:
    call GameSession_RestorePage0
    ld a,(pattern_back)
    ld e,a
    ld d,0
    ld hl,GameSession_FlagLoaded
    add hl,de
    call GameSession_FlagKey
    ld (hl),a
    ret

; B=dynamic actor glyph slot, C=flag source glyph minus96. Staging is Page3
; RAM so the Page0 mapper switch cannot hide its source or caller stack.
GameSession_CloneFlag:
    push bc
    ld a,c
    sub 50
    add a,a
    add a,a
    add a,a
    add a,52
    ld l,a
    ld a,(phase)
    ld h,a
    call GameSession_SelectFlags
    ld de,$ce80
    ld bc,8
    ldir
    ld a,l
    add a,72
    ld l,a
    ld bc,8
    ldir
    call GameSession_RestorePage0
    pop bc
    ld a,b
    add a,a
    add a,a
    add a,a
    ld e,a
    ld d,HIGH Game_RadarPatterns
    ld hl,$ce80
    ld bc,8
    ldir
    ld a,e
    sub 8
    ld e,a
    inc d
    ld bc,8
    ldir
    ret
