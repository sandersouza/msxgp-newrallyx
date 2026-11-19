; Fixed64KiB world binding. Page0 main RAM2900..2AFF owns these workers;
; Page3 game/stack and relocated IRQ remain mapped throughout. World halves
; occupy physical RAM4000..7FFF and8000..BFFF beneath cartridge windows.
; IRQ ownership: unchanged clock/latch service; UI latch requires ROM visible.
; RAM windows are exposed only in active state0 or DI cold work. No NMI/reentry.
; General caller-saved ABI except CopyMap preserves IX/IY/IFF; PatchObject keeps
; IX, advances IY9 and C3. Cold scratchC100..10F ends before radarC110.
; Two3-byte slot writes patch once for primary/secondary switching. Source bank
; registers and slot ownership return before any resident/native ROM fetch.
; This image replaces the ended boot replay only after the start gate commits
; F10 and consumes held start keys. It must end before live turbo code at2B25.

GamePlain_Ram:
    ld a,(GamePlain_RamValue)
GamePlain_RamWrite:
    out ($a8),a
    nop
    ret
GamePlain_Rom:
    ld a,(GamePlain_RomValue)
GamePlain_RomWrite:
    out ($a8),a
    nop
    ret
GamePlain_RamValue: db 0
GamePlain_RomValue: db 0
GamePlain_Ppi: db 0
GamePlain_Secondary: db 0
GamePlain_RamSecondary: db 0
GamePlain_LowPpi: db 0
GamePlain_HighPpi: db 0
GamePlain_Upper: db 0
GamePlain_SourceBank: db 0
GamePlain_Entry: dw 0

; B=world X,C=full world Y -> HL=4000+Y*128+X; all RAM windows exposed.
GamePlain_Address:
    call GamePlain_Ram
    ld l,c
    ld h,0
    REPT 7
    add hl,hl
    ENDR
    ld e,b
    ld d,$40
    add hl,de
    ret

GamePlain_RunAddresses:
    ld a,(ring_y)
    ld c,a
    ld a,(ring_x)
    ld b,a
    call GamePlain_Address
    push hl
    ld a,(ring_y)
    ld c,a
    ld a,(ring_x)
    ; Inline the unchanged ring-address math; resident ROM is hidden.
    and 31
    ld e,a
    ld a,c
    and 31
    rrca
    rrca
    rrca
    ld l,a
    and 3
    or $d8
    ld h,a
    ld a,l
    and $e0
    or e
    ld l,a
    ex de,hl
    pop hl
    ret

GamePlain_LoadRun:
    call GamePlain_RunAddresses
    ld a,e
    and 31
    ld c,a
    ld a,32
    sub c
    ld c,a
    ld a,(ring_length)
    cp c
    jr nc,.split
    ld c,a
    ld b,0
    ldir
    jp GamePlain_Rom
.split:
    sub c
    push af
    ld b,0
    ldir
    pop af
    or a
    jp z,GamePlain_Rom
    ld c,a
    ld b,0
    ld a,e
    sub 32
    ld e,a
    jr nc,.rest
    dec d
.rest:
    ldir
    jp GamePlain_Rom

GamePlain_LoadColumns:
    ld a,(maprow)
    ld (ring_y),a
    ld a,(ring_x)
    and 31
    ld b,a
    ld a,(ring_length)
    add a,b
    cp 33
    jr nc,.wrapped
    call GamePlain_RunAddresses
    call .strides
    ld a,(ring_length)
    ld ixl,a
    ld ixh,32
.fast:
    ld c,ixl
    ld b,0
    ldir
    ld c,iyh
    add hl,bc
    ex de,hl
    ld c,iyl
    add hl,bc
    ld a,h
    and 3
    or $d8
    ld h,a
    ex de,hl
    dec ixh
    jr nz,.fast
    jp GamePlain_Rom
.wrapped:
    call GamePlain_RunAddresses
    call .strides
    ld a,iyl
    add a,32
    ld iyl,a
    ld a,e
    and 31
    neg
    add a,32
    ld ixl,a
    ld b,a
    ld a,(ring_length)
    sub b
    ld (ring_rest),a
    ld ixh,32
.row:
    ld c,ixl
    ld b,0
    ldir
    ld a,e
    sub 32
    ld e,a
    jr nc,.rest
    dec d
.rest:
    ld a,(ring_rest)
    ld c,a
    ldir
    ld c,iyh
    add hl,bc
    ex de,hl
    ld c,iyl
    add hl,bc
    ld a,h
    and 3
    or $d8
    ld h,a
    ex de,hl
    dec ixh
    jr nz,.row
    ld a,(maprow)
    add a,32
    ld (ring_y),a
    jp GamePlain_Rom
.strides:
    ld a,(ring_length)
    ld c,a
    ld a,128
    sub c
    ld iyh,a
    ld a,32
    sub c
    ld iyl,a
    ret

GamePlain_RestoreOne:
    push bc
    call GamePlain_Address
    ld a,(hl)
    push af
    call GamePlain_Rom
    pop af
    pop bc
    jp Game_PatchOne
