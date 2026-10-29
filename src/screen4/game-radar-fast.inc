; Exact SCREEN4 actor-dot radar path. The flag variants remain phase-local ROM
; data. At most eight native actor descriptors allocate dynamic characters.
; Each first use copies all eight original pattern/color rows in native order.
    ASSERT LOW names == 0
    ASSERT LOW Game_RadarAddresses == 0
    ASSERT LOW Game_RadarPatterns == 0
    ASSERT LOW Game_RadarColors == 0
    ASSERT HIGH Game_RadarColors == HIGH Game_RadarPatterns+1
GameRadarFast_Draw:
    xor a
    ld (Game_RadarCount),a
    call $a700
    ld a,($e24e)
    cp 7
    jr c,.count
    ld a,7
.count:
    inc a
    ld b,a
    ld ix,$e068
.actors:
    push bc
    ld a,(ix+10)
    cp 56
    jp nc,.next
    ld l,a
    ld h,0
    ld de,Game_RadarCellRows
    add hl,de
    ld a,(fy)
    add a,(hl)
    ld c,a
    ld a,(ix+8)
    cp 32
    jp nc,.next
    add a,8
    ld b,a
    ld a,(fx)
    add a,b
    ld b,a                  ; B=phase-adjusted X, C=phase-adjusted Y.
    ld a,c
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,b
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
    cp 32
    IFDEF GAME_RADAR_UNIFORM_SOURCE
    jp c,.point
    ELSE
    jr c,.point
    ENDIF
    ; Preserve point coordinates while allocating the first use of this name.
    push bc
    sub 32                  ; Original phase-local character minus 96.
    ld c,a
    ld a,(Game_RadarCount)
    ld b,a
    inc a
    ld (Game_RadarCount),a
    ld a,b
    add a,a
    ld e,a
    ld d,HIGH Game_RadarAddresses
    ex de,hl
    ld (hl),e
    inc hl
    ld (hl),d
    ex de,hl
    ld a,b
    add a,64
    ld (hl),a
    IFDEF GAME_RADAR_UNIFORM_SOURCE
    ; The phase-local metadata proves all sixteen original bytes exactly.
    ; A zero entry takes the original clone, including all flag variants.
    ld a,c
    add a,$40
    ld l,a
    ld h,$a9
    ld a,(hl)
    or a
    jr z,.clone
    ld c,a
    ld a,b
    add a,a
    add a,a
    add a,a
    ld l,a
    ld h,HIGH Game_RadarPatterns
    ld a,$ff
    REPT 7
    ld (hl),a
    inc l
    ENDR
    ld (hl),a
    inc h
    REPT 7
    ld (hl),c
    dec l
    ENDR
    ld (hl),c
    ld a,(Game_RadarCount)
    dec a
    pop bc
    jr .point
.clone:
    ENDIF
    ld l,c
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$8100
    add hl,de
    push hl
    ld a,b
    add a,a
    add a,a
    add a,a
    ld e,a
    ld d,HIGH Game_RadarPatterns
    REPT 8
    ldi
    ENDR
    pop hl
    ld a,h
    add a,4
    ld h,a
    ld a,e
    sub 8
    ld e,a
    inc d
    REPT 8
    ldi
    ENDR
    ld a,(Game_RadarCount)
    dec a
    pop bc
.point:
    add a,a
    add a,a
    add a,a
    ld l,a
    ld a,c
    and 7
    or l
    ld l,a
    ld h,HIGH Game_RadarPatterns
    ld a,b
    and 7
    add a,LOW GameRadarFast_Masks
    ld e,a
    ld d,HIGH GameRadarFast_Masks
    ld a,(de)
    ld c,a
    inc h
    ld a,GAME_RADAR_COLOR
    cp (hl)
    ld (hl),a
    ld h,HIGH Game_RadarPatterns
    jr z,.merge
    ld (hl),0
.merge:
    ld a,(hl)
    or c
    ld (hl),a
.next:
    ld de,32
    add ix,de
    pop bc
    djnz .again
    ret
.again:
    jp .actors
    ALIGN 8
GameRadarFast_Masks:
    db $80,$40,$20,$10,$08,$04,$02,$01
