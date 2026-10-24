; Called after the maze scroll latch, before the first radar band is fetched.
; No mapper change. Publish each band in scan order, independent of actor load.
Full_RadarIRQ:
    push hl
    push de
    vdp_write 14,7
    xor a
    out ($99),a
    ld a,$76
    out ($99),a
    ld a,(scroll_y)
    add a,RADAR_Y-1
    ld d,a
    ld hl,Radar_PlayerPoint+1
    ld a,(Radar_PlayerPoint)
    cp 255
    jr nz,.point
    ld hl,Full_RadarHiddenPoint+1
.point:
    ld e,RADAR_PLAYER_PATTERN
    call .sprite
    ld e,20
    ld hl,Radar_Origins+1
    ld b,12
.body:
    call .sprite
    djnz .body
    pop de
    pop hl
    ret
.sprite:
    ld c,e
    ld a,(hl)
    add a,d
    cp 216
    jr nz,.y
    dec a
    push af
    ld a,e
    cp RADAR_PLAYER_PATTERN
    jr c,.map_phase
    add a,4
    jr .phase
.map_phase:
    add a,48
.phase:
    ld c,a
    pop af
.y:
    out ($98),a
    dec hl
    ld a,(hl)
    add a,RADAR_X
    out ($98),a
    inc hl
    inc hl
    inc hl
    ld a,c
    out ($98),a
    xor a
    nop
    nop
    out ($98),a
    ld a,e
    add a,4
    ld e,a
    ret
