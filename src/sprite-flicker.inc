; Alternate complete enemy pairs ahead of radar cells6..9. The first two radar
; bands stay fixed, keeping their earlier fetch deadline out of the rotation.
; Keep fuel/life and player indices fixed for the raster hooks. All uploads allow
; raster IRQs between <=16-byte chunks and reselect the VRAM address afterwards.
Flicker_Phase EQU $c7c0
Flicker_Upload EQU Sprite_Upload
Flicker_Init:
    xor a
    ld (Flicker_Phase),a
    IF FLICKER_STRESS
    jp Flicker_StressInit
    ENDIF
    ret
Flicker_Publish:
    ei
    nop
    ld a,(Enemy1_LastEC)
    and 128
    rrca
    ld b,a
    ld a,(Enemy2_LastEC)
    and 128
    or b
    ld l,a
    ld h,0
    ld de,Flicker_EnemyColors
    add hl,de
    ld a,(Flicker_Phase)
    xor 1
    ld (Flicker_Phase),a
    or a
    jr z,.canonical
    ld de,Flicker_White
    jr .colors
.canonical:
    ex de,hl
    ld hl,Flicker_White
.colors:
    push de
    ld de,$7460
    ld b,64
    call Flicker_Upload
    pop hl
    ld de,$7530
    ld b,64
    call Flicker_Upload
    ld de,$7600
    ld a,(Flicker_Phase)
    or a
    jr z,.normal_sat
    ld hl,sat
    ld b,24
    call Flicker_Upload
    ld hl,Enemy1_SAT
    ld b,8
    call Flicker_Upload
    ld hl,Enemy2_SAT
    ld b,8
    call Flicker_Upload
    ld hl,sat+40
    ld b,28
    call Flicker_Upload
    ld hl,player_sat
    ld b,8
    call Flicker_Upload
    ld hl,sat+24
    ld b,16
    call Flicker_Upload
    jr .extra
.normal_sat:
    ld hl,sat
    ld b,68
    call Flicker_Upload
    ld hl,player_sat
    ld b,8
    call Flicker_Upload
    ld hl,Enemy1_SAT
    ld b,8
    call Flicker_Upload
    ld hl,Enemy2_SAT
    ld b,8
    call Flicker_Upload
.extra:
    IF HUD_ENABLED
    ld hl,$c620
    ld b,4
    call Flicker_Upload
    ENDIF
    ld hl,Flicker_Terminator
    ld b,1
    call Flicker_Upload
Flicker_Done:
    ret

    INCLUDE "sprite-upload.inc"
Flicker_Terminator:
    db 216
    IF FLICKER_STRESS
; Explicit diagnostic setup only: park two original 16x16 cars over the radar,
; then freeze simulation. Space resumes the separate unaccepted moving test.
Flicker_StressInit:
    ld a,1
    ld (paused),a
    ld ix,$e088
    ld de,80
    call Flicker_SeedActor
    ld ix,$e0a8
    ld de,96
    call Flicker_SeedActor
    ld a,242
    ld ($e0b7),a
    ld hl,$e093
    ld ($e004),hl
    ld hl,$e0b3
    ld ($e006),hl
    ld hl,0
    ld ($e008),hl
    ld ($e00a),hl
    ld ($e00c),hl
    ret
Flicker_SeedActor:
    ld hl,(player_x)
    add hl,de
    call Flicker_SeedAxis
    ld (ix+8),b
    ld (ix+5),a
    ld hl,(player_y)
    ld de,-44
    add hl,de
    call Flicker_SeedAxis
    ld (ix+10),b
    neg
    ld (ix+7),a
    ld (ix+11),0
    ld (ix+15),240
    ret
Flicker_SeedAxis:
    ld de,-24                ; -36 world origin +12 nearest-cell rounding
    add hl,de
    ld de,24
    ld b,0
.divide:
    or a
    sbc hl,de
    jr c,.remainder
    inc b
    jr .divide
.remainder:
    add hl,de
    ld a,l
    sub 12
    ret
    ENDIF
Flicker_White:
    defs 64,WHITE|$20
Flicker_EnemyColors:
    defs 16,$26
    defs 16,$6a
    defs 16,$26
    defs 16,$6a
    defs 16,$a6
    defs 16,$ea
    defs 16,$26
    defs 16,$6a
    defs 16,$26
    defs 16,$6a
    defs 16,$a6
    defs 16,$ea
    defs 16,$a6
    defs 16,$ea
    defs 16,$a6
    defs 16,$ea
