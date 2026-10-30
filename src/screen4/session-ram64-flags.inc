; 64 KiB profile. Eight CPU records mirror the eight VRAM sets.
; Main Page0 3800..3FFF: count, executable names, 80 pattern/color bytes,
; ten offset/reserved/mask triples, phase key (F2), blink key (F3).
; Pointer page is implicit in H; stored high bytes are unused. No RAM banking.
; The unused128K segment alias C0D3 is a boolean in this profile, not a bank.
GameSession_AnyCaptured EQU GameSession_FlagSegment
GameSession_ClearFlags:
    ld hl,$38f2
    ld b,8
    ld a,$ff
.invalidate:
    ld (hl),a
    inc h
    djnz .invalidate
    ld hl,GameSession_FlagLoaded
    ld b,8
.keys:
    ld (hl),a
    inc hl
    djnz .keys
    xor a
    ld (GameSession_FlagGeneration),a
    ld (GameSession_AnyCaptured),a
    ld hl,Flag_Active+1
    ld b,10
.active:
    ld a,(hl)
    or a
    jr z,.captured
    inc hl
    djnz .active
    ret
.captured:
    ld a,1
    ld (GameSession_AnyCaptured),a
    ret

GameSession_SelectFlags:
    ld a,(pattern_back)
    add a,$38
    ld h,a
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
    call GameSession_EnsureFlags
    ld l,1
    jp (hl)

GameSession_FlagCollected:
    ld a,(Flag_Last)
    dec a
    ld (GameSession_FlagIndex),a
    jp GameSession_RemoveFlag
GameSession_RemoveFlag:
    ld a,1
    ld (GameSession_AnyCaptured),a
    ld h,$38
    ld b,8
.slot:
    ld l,242
    ld a,(hl)
    cp $ff
    jr z,.next
    ld a,(GameSession_FlagIndex)
    call GameSession_ClearFlagBit
.next:
    inc h
    djnz .slot
    ld hl,GameSession_FlagGeneration
    inc (hl)
.done:
    ret

; H=record, A=flag index. Preserve H and B for record/flag loops.
GameSession_ClearFlagBit:
    ld c,a
    add a,a
    add a,c
    add a,212
    ld l,a
    ld e,(hl)
    inc l
    ld d,h
    inc l
    ld a,(hl)
    cpl
    ld c,a
    push hl
    ex de,hl
    ld a,(hl)
    and c
    ld (hl),a
    pop hl
    ret

; H=selected CPU record; returns H unchanged. Mutate only the original S point.
GameSession_ApplyBlink:
    ld l,243
    ld a,(GameSession_Blink)
    cp (hl)
    ret z
    ld (hl),a
    ld l,239
    ld e,(hl)
    inc l
    ld d,h
    inc l
    ld c,(hl)
    ld a,(GameSession_Blink)
    or a
    jr nz,.hide
    ld a,(Flag_Active+10)
    or a
    jr z,.hide
    ld a,(de)
    or c
    ld (de),a
    ret
.hide:
    ld a,c
    cpl
    ld c,a
    ld a,(de)
    and c
    ld (de),a
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
    ld a,(Flag_Active+10)
    or a
    ret z
    jp GameSession_FlagBlinkUpload
.upload:
    call GameSession_SelectFlags
    ld l,0
    ld a,(hl)
    ld (GameSession_Count),a
    or a
    jr z,.done
    ld hl,$0490
    call GamePattern_Address
    call GameSession_SelectFlags
    ld l,52
    ld a,(GameSession_Count)
    call GameSession_UploadFlagBytes
    ld hl,$4490
    call GamePattern_Address
    call GameSession_SelectFlags
    ld l,132
    ld a,(GameSession_Count)
    call GameSession_UploadFlagBytes
.done:
    ld a,(pattern_back)
    ld e,a
    ld d,0
    ld hl,GameSession_FlagLoaded
    add hl,de
    call GameSession_FlagKey
    ld (hl),a
    ret

; A=1..10 glyphs, HL=source. Foreground VDP pointer already selected.
; Exact1..80-byte transfer through the established paced OUTI primitive.
GameSession_UploadFlagBytes:
    add a,a
    add a,a
    add a,a
    ld b,a
    ld c,$98
    jp GamePacketFast_Transfer

; B=actor glyph slot, C=source glyph minus96. Both arrays are in main Page0:
; copy directly instead of staging through Page3 as the128K banked host needs.
GameSession_CloneFlag:
    ld a,c
    sub 50
    add a,a
    add a,a
    add a,a
    add a,52
    ld l,a
    call GameSession_SelectFlags
    ld a,b
    add a,a
    add a,a
    add a,a
    ld e,a
    ld d,HIGH Game_RadarPatterns
    REPT 8
    ldi
    ENDR
    ld a,l
    add a,72
    ld l,a
    ld a,e
    sub 8
    ld e,a
    inc d
    REPT 8
    ldi
    ENDR
    ret
