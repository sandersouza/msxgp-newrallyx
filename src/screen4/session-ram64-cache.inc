; Default 64 KiB profile. Immutable 64-phase records live in unused VRAM
; 1000..17FF in each of eight16KiB sets (16KiB total). CPU keeps eight records.
GameSession_BuildFlags:
    xor a
    ld (GameSession_Phase),a
    ld (pattern_back),a
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
    ld b,$40
    call GameSession_FlagCacheAddress
    ld hl,$3800
    ld de,242
    call upload
    ld hl,GameSession_Phase
    inc (hl)
    ld a,(hl)
    cp 64
    jr nz,.phase
    jp GameSession_ClearFlags

; B=VDP access bit (0 read /40 write), phase=GameSession_Phase.
; Foreground VDP control-port ownership follows GamePattern_Address.
GameSession_FlagCacheAddress:
    di
    ld a,(GameSession_Phase)
    REPT 3
    rrca
    ENDR
    and 7
    out ($99),a
    ld a,$8e
    out ($99),a
    xor a
    out ($99),a
    ld a,(GameSession_Phase)
    and 7
    or $10
    or b
    out ($99),a
    ei
    ret

; Foreground only, main Page0 mapped. Prepare the inactive VRAM set's exact
; phase, keeping native flags, palette and the original dot merger unchanged.
; Owns AF/BC/DE/HL/IX/IY; leaves Game_RadarCount unchanged.
GameSession_EnsureFlags:
    call GameSession_SelectFlags
    ld l,242
    ld a,(phase)
    cp (hl)
    jr z,.ready
    ld (GameSession_Phase),a
    ld b,0
    call GameSession_FlagCacheAddress
    call GameSession_SelectFlags
    ld l,0
    ld bc,$f298
    call GameSession_ReadFlagCache
    ; HL now points at F2 in this same record. Pointer page is implicit in H;
    ; all consumers use H directly, avoiding ten redundant pointer-high writes.
    ld a,(phase)
    ld (hl),a
    inc l
    ld (hl),0
    ld a,(GameSession_AnyCaptured)
    or a
    jr z,.ready
    ld ix,Flag_Active+1
    ld b,10
    xor a
.collected:
    push af
    ld c,(ix+0)
    inc c
    dec c
    call z,GameSession_ClearFlagBit
    inc ix
    pop af
    inc a
    djnz .collected
.ready:
    jp GameSession_ApplyBlink
