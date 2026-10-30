; First ROM-OK screen only. Original8x8 arcade glyphs, boot palette ink7.
; Foreground, base Z80; owns AF/BC/DE/HL/IX and Page2. No active-game calls.
GameAuto_FormatStatus:
    ; A four-character decimal field fits the supported64..4096KiB range.
    ; This cold-only formatter owns the string; no active-frame conversion runs.
    ld hl,(GameAuto_MemoryKiB)
    ld de,GameAuto_MapperText+7
    xor a
    ld (GameAuto_DigitSeen),a
    ld bc,1000
    call .digit
    ld bc,100
    call .digit
    ld bc,10
    call .digit
    ld a,l
    add a,'0'
    ld (de),a
    ret
.digit:
    ld a,'0'-1
.subtract:
    inc a
    or a
    sbc hl,bc
    jr nc,.subtract
    add hl,bc
    cp '0'
    jr nz,.seen
    push af
    ld a,(GameAuto_DigitSeen)
    or a
    jr nz,.zero
    pop af
    ld a,' '
    jr .store
.zero:
    pop af
    jr .store
.seen:
    push af
    ld a,1
    ld (GameAuto_DigitSeen),a
    pop af
.store:
    ld (de),a
    inc de
    ret

GameAuto_PaintStatus:
    ; Paint into the boot back page after CPU detection, before publication.
    ; Its original8x8 glyph data lives in unused cold-bank padding.
    ld a,SESSION_COLD_BANK
    ld ($7000),a
    ld ix,GameAuto_MapperText
    ld de,$1012             ; x36,y32, below original ROM OK at y16.
    call .text
    ld ix,GameAuto_TurboOff
    IFDEF GameTurbo_Kind
    ; session_auto.py resolves this optional-backend conditional numerically.
    ; Do not infer backend availability from assembler EQU/IFDEF behavior alone.
    ld a,(GameTurbo_Kind)
    or a
    jr z,.turbo
    ld ix,GameAuto_TurboOn
.turbo:
    ENDIF
    ld de,$1812             ; x36,y48.
.text:
    ld a,(ix+0)
    or a
    ret z
    inc ix
    push de
    call .glyph
    pop de
    inc de
    inc de
    inc de
    inc de
    jr .text
.glyph:
    sub 32
    ld l,a
    ld h,0
    REPT 5
    add hl,hl
    ENDR
    ld bc,$9800
    add hl,bc
    ld b,8
.row:
    push bc
    push hl
    push de
    ex de,hl
    di
    ld a,($c0fa)            ; Shared boot-back alias, also when check is omitted.
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ei
    pop de
    pop hl
    ld c,$98
    REPT 4
    outi
    ENDR
    pop bc
    ld a,e
    add a,128
    ld e,a
    jr nc,.same_page
    inc d
.same_page:
    djnz .row
    ret
GameAuto_DigitSeen:
    db 0
GameAuto_MapperText:
    db "MAPPER 0000K",0
GameAuto_TurboOn:
    db "TURBO ON ",0
GameAuto_TurboOff:
    db "TURBO OFF",0
