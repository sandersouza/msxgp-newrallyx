; Read-only adapter for a stable 4KB copy of native $8000..$8fff RAM.
; NRALLYX version is fixed by scripts/graphics/nrallyx.json.
; Retain native scoring/bonus/fuel routines; call this AFTER they finish.
; HL=snapshot base. Preserves BC/DE/HL/IX/IY and alternate registers. AF scratch.
; C=1 rejects invalid pointers/digits before publishing any of these four values.
HUD_SyncNative:
    push bc
    push de
    push hl
    push ix
    push iy
    ld (hud_native_base),hl
    ld hl,$8990
    call hud_native_pointer
    jr c,.invalid
    ld iy,hud_native_stage
    call hud_native_number
    jr c,.invalid
    ld hl,$8060
    call hud_native_map
    ld iy,hud_native_stage+6
    call hud_native_number
    jr c,.invalid
    ld hl,$8988
    call hud_native_pointer
    jr c,.invalid
    ld a,(hl)
    or a
    jr z,.life
    dec a                    ; original count includes the currently driven car
    cp 10
    jr c,.life
    ld a,9                   ; presentation cap; original count is not modified
.life:
    ld (hud_native_stage+12),a
    ld hl,$898e
    call hud_native_pointer
    jr c,.invalid
    ld a,(hl)
    cp 10                    ; fractional decimal fuel digit
    jr nc,.invalid
    inc hl
    ld a,(hl)                ; native whole units; the original gauge clips at 54
    ld (hud_native_stage+13),a
    ld hl,hud_native_stage
    call HUD_SetScore
    ld hl,hud_native_stage+6
    call HUD_SetHiscore
    ld a,(hud_native_stage+12)
    call HUD_SetLives
    ld a,(hud_native_stage+13)
    call HUD_SetFuel
    or a
    jr .return
.invalid:
    scf
.return:
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    ret

hud_native_pointer:
    call hud_native_map
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld a,d
    cp $80
    jr c,.invalid
    cp $90
    jr nc,.invalid
    cp $8f
    jr nz,.valid
    ld a,e
    cp $f9
    jr nc,.invalid
.valid:
    ex de,hl
    call hud_native_map
    or a
    ret
.invalid:
    scf
    ret
hud_native_map:
    push de
    ld de,(hud_native_base)
    res 7,h
    add hl,de
    pop de
    ret
hud_native_number:
    ld (hud_native_source),hl
    ld ix,hud_native_digit_offsets
    ld b,6
.digit:
    ld l,(ix+0)
    ld h,0
    ld de,(hud_native_source)
    add hl,de
    ld a,(hl)
    and 15                   ; native $30 zero / $40 blank normalize to digit zero
    cp 10
    jr nc,.invalid
    ld (iy+0),a
    inc iy
    inc ix
    djnz .digit
    or a
    ret
.invalid:
    scf
    ret
hud_native_digit_offsets:
    db 6,7,0,1,2,3
