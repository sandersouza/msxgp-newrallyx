; Keep all three bodies ahead of outlines/radar. Fuel/life stay in slots14..16.
; Canonical RAM remains untouched; only the assembled hardware SAT is reordered.
Outline_Colors EQU $c800
Outline_Attrs EQU $c980
Outline_Canonical EQU $c9e0
Outline_SourceColors EQU $ca40
Outline_OrderPtr EQU $cbc0
Outline_Count EQU $cbc2
Outline_ColorDest EQU $cbc3
Outline_AttrDest EQU $cbc5
Outline_Front EQU $c7c1
Outline_DisplayPhase EQU $c7ca
Outline_Ready EQU $c7cb

Outline_Init:
    xor a
    ld (Outline_Front),a
    ld (Outline_Ready),a
    ld (Outline_DisplayPhase),a
    vdp_write 5,$ef
    ld hl,sprite_colors
    ld de,Outline_SourceColors
    ld bc,384
    ldir
    ret

Flicker_Publish:
    ei
    nop
    ld hl,sat
    ld de,Outline_Canonical
    ld bc,68
    ldir
    ld hl,player_sat
    ld bc,8
    ldir
    ld hl,Enemy1_SAT
    ld bc,8
    ldir
    ld hl,Enemy2_SAT
    ld bc,8
    ldir
    ld hl,$c620
    ld bc,4
    ldir
    ; Each body row chooses the majority original blue/yellow ink. Its
    ; independent black plane contains only original black pixels (no CC).
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld a,(player_drawn)
    ld l,a
    ld h,0
    ld de,player_flags
    add hl,de
    ld a,(hl)
    ld de,Outline_SourceColors+17*16
    ld b,0
    call Outline_Body
    ld a,(scroll_y)
    add a,107
    cp 216
    jr nz,.player_colors
    ld hl,Outline_SourceColors+17*16+14
    ld de,Outline_SourceColors+17*16+15
    ld bc,15
    lddr                   ; Match the player's one-row shifted sentinel mask.
.player_colors:
    ld a,(Enemy1_Index)
    ld de,Outline_SourceColors+19*16
    ld b,$c0
    call Outline_Body
    ld a,(Enemy2_Index)
    ld de,Outline_SourceColors+21*16
    ld b,$c0
    call Outline_Body
    ld a,(Enemy1_LastEC)
    ld hl,Outline_SourceColors+19*16
    call Outline_EC
    ld a,(Enemy2_LastEC)
    ld hl,Outline_SourceColors+21*16
    call Outline_EC
    ld a,BLACK|$20
    ld hl,Outline_SourceColors+18*16
    ld b,16
.black:
    ld (hl),a
    inc hl
    djnz .black
    ld a,(point_color)
    or $20
    ld hl,Outline_SourceColors+12*16
    ld b,16
.point:
    ld (hl),a
    inc hl
    djnz .point
    ld a,(Flicker_Phase)
    inc a
    and 3
    ld (Flicker_Phase),a
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl              ; phase*8
    ld d,h
    ld e,l
    add hl,hl
    add hl,de              ; phase*24
    ld de,Outline_Orders
    add hl,de
    ld (Outline_OrderPtr),hl
    ld hl,Outline_Colors
    ld (Outline_ColorDest),hl
    ld hl,Outline_Attrs
    ld (Outline_AttrDest),hl
    ld a,24
    ld (Outline_Count),a
.entry:
    ld hl,(Outline_OrderPtr)
    ld a,(hl)
    inc hl
    ld (Outline_OrderPtr),hl
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    push hl
    ld de,Outline_Canonical
    add hl,de
    ld de,(Outline_AttrDest)
    ld bc,4
    ldir
    ld (Outline_AttrDest),de
    pop hl
    add hl,hl
    add hl,hl
    ld de,Outline_SourceColors
    add hl,de
    ld de,(Outline_ColorDest)
    ld bc,16
    ldir
    ld (Outline_ColorDest),de
    ld a,(Outline_Count)
    dec a
    ld (Outline_Count),a
    jr nz,.entry
    ld hl,Outline_Colors
    ld de,$7400
    ld a,(Outline_Front)
    xor 1
    jr z,.color_address
    ld d,$6c
.color_address:
    ld b,128
    call Flicker_Upload
    ld b,128
    call Flicker_Upload
    ld b,128
    call Flicker_Upload
    ld hl,Outline_Attrs
    ld de,$7600
    ld a,(Outline_Front)
    xor 1
    jr z,.sat_address
    ld d,$6e
.sat_address:
    ld b,96
    call Flicker_Upload
    ld hl,Flicker_Terminator
    ld b,1
    call Flicker_Upload
Flicker_Done:
    ld a,1
    ld (Outline_Ready),a
    ret

; VBlank only: publish a complete inactive table, never half a transaction.
Outline_Commit:
    ld a,(Outline_Ready)
    or a
    ret z
    xor a
    ld (Outline_Ready),a
    ld a,(Outline_Front)
    xor 1
    ld (Outline_Front),a
    ld b,$ef
    or a
    jr z,.select
    ld b,$df
.select:
    ld a,b
    ld b,5
    call register
    ld a,(Flicker_Phase)
    ld (Outline_DisplayPhase),a
    ret

; Adjust the bank7 pointer high byte, preserving BC/DE/HL.
Outline_ColorAddress:
    push bc
    ld c,a
    ld a,(Outline_Front)
    or a
    ld a,c
    jr z,.done
    sub 8
.done:
    pop bc
    ret

; A=pose, B=enemy table offset, DE=canonical body colors.
Outline_Body:
    cp 12
    jr c,.valid
    xor a
.valid:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,l
    add a,b
    ld l,a
    jr nc,.base
    inc h
.base:
    ld bc,$9800
    add hl,bc
    ld bc,16
    ldir
    ret

; OR EC into body rows, then create the independent black contour rows.
Outline_EC:
    and 128
    ld c,a
    ld b,16
.body:
    ld a,(hl)
    or c
    ld (hl),a
    inc hl
    djnz .body
    ld a,c
    or $2e
    ld b,16
.outline:
    ld (hl),a
    inc hl
    djnz .outline
    ret
Outline_Orders:
    INCBIN "outline-orders.bin"
