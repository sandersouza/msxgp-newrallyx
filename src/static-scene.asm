; SCREEN 5 static composition cartridge. ASCII16, 128 KiB.
; Page 0: BIOS; page 1: fixed bank 0; page 2: bitmap bank; page 3: RAM.
    OUTPUT "static-scene.rom"
    ORG $4000
    db "AB"
    dw boot,0,0,0,0,0,0

boot:
    di
    ld sp,$f380
    ; Map the cartridge's (possibly expanded) page-1 slot into page 2.
    call $0138                  ; RSLREG
    rrca
    rrca
    and 3
    ld c,a
    ld b,0
    ld hl,$fcc1                ; EXPTBL
    add hl,bc
    ld a,(hl)
    and $80
    or c
    ld c,a
    inc hl
    inc hl
    inc hl
    inc hl                     ; SLTTBL
    ld a,(hl)
    and $0c
    or c
    ld h,$80
    call $0024                 ; ENASLT
    ld a,5
    call $005f                 ; CHGMOD
    di
    ; Disable display/interrupts during upload, sprites, YJK and interlace.
    ld b,1
    ld a,0
    call register
    ld b,8
    ld a,$0a                   ; VRAM enabled, sprites disabled
    call register
    ld b,9
    ld a,$80                   ; 212 lines, NTSC 60 Hz
    call register
    ld b,25
    xor a
    call register
    ld b,18
    xor a
    call register
    ld b,23
    xor a
    call register
    ld b,26
    xor a
    call register
    ld b,27
    xor a
    call register
    ld b,2
    ld a,$1f                   ; bitmap page 0
    call register
    ld b,7
    xor a
    call register
    ld b,16
    xor a
    call register
    ld hl,palette
    ld b,32
    ld c,$9a
    otir
    ; Silence PSG amplitudes; retain BIOS mixer/I/O direction configuration.
    ld a,8
.mute:
    out ($a0),a
    ld c,a
    xor a
    out ($a1),a
    ld a,c
    inc a
    cp 11
    jr nz,.mute
    ; Silence all nine OPLL channels (MSX-MUSIC machines).
    ld b,9
    ld a,$20
.fm:
    out ($7c),a
    push af
    pop af
    ld c,a
    xor a
    out ($7d),a
    defs 12,0                  ; OPLL data-to-address recovery time
    ld a,c
    inc a
    djnz .fm
    xor a
    ld ($c000),a               ; selected scene
    call show
.keys:
    xor a                      ; keyboard row 0: 1=bit1, 2=bit2
    call $0141                 ; SNSMAT
    di
    bit 1,a
    jr z,.normal
    bit 2,a
    jr nz,.keys
    ld a,1
    jr .select
.normal:
    xor a
.select:
    ld hl,$c000
    cp (hl)
    jr z,.keys
    ld (hl),a
    call show
    jr .keys

; Blank while copying, then display the complete image on a frame boundary.
show:
    ld b,1
    xor a
    call register
    ld b,14
    xor a
    call register
    xor a                      ; register helper clobbers A
    out ($99),a
    ld a,$40
    out ($99),a
    ld a,($c000)
    add a,a
    inc a
    ld ($7000),a
    push af
    ld hl,$8000
    ld de,$4000
    call upload
    pop af
    inc a
    ld ($7000),a
    ld hl,$8000
    ld de,10752                ; 27136 - 16384 bytes
    call upload
.vblank:
    in a,($99)
    and $80
    jr z,.vblank
    ld b,1
    ld a,$40
    jp register

; 3.58 MHz Z80: loop comfortably exceeds VDP bitmap access spacing.
upload:
    ld a,(hl)
    out ($98),a
    inc hl
    dec de
    ld a,d
    or e
    jr nz,upload
    ret

register:
    out ($99),a
    ld a,b
    or $80
    out ($99),a
    ret

palette:
    INCBIN "palette.bin"
    ASSERT $ <= $8000
    defs $8000-$,$ff
    INCBIN "normal.sc5"
    defs $10000-$,$ff          ; each scene occupies two 16 KiB banks
    INCBIN "overlap.sc5"
    defs $24000-$,$ff          ; file size 128 KiB (origin is $4000)
