; Share the original red radar marker when both 2x2 dots fit one pattern.
; Two ROM tables contain every diagonal/delta; no per-pixel CPU work.
Enemy_PairMode EQU $c660
Enemy_PairX EQU $c661
Enemy_PairY EQU $c662
Enemy_PairDX EQU $c663
Enemy_PairDY EQU $c664
Enemy_PairDiagonal EQU $c665
Enemy_PairActualX EQU $c666
Enemy_PairActualY EQU $c667
Enemy_PairBank EQU $c668
Enemy_PairSource EQU $c669
Enemy_PairLastBank EQU $c66b
Enemy_PairLastSource EQU $c66c
Enemy_PairLastMode EQU $c66e

Enemy_PairRadar:
    xor a
    ld (Enemy_PairMode),a
    ld (Enemy_PairDiagonal),a
    ld a,(hud_enemy_x)
    ld (Enemy_PairActualX),a
    ld a,(hud_enemy_y)
    ld (Enemy_PairActualY),a
    ld a,(Enemy_PairActualX)
    cp 255
    jp z,.finish
    ld b,a
    ld a,(Enemy2_PointX)
    cp 255
    jp z,.finish
    ld c,a
    ld a,b
    sub c
    jr c,.left
    ld d,a
    ld a,c
    ld (Enemy_PairX),a
    ld a,1
    ld (Enemy_PairDiagonal),a
    jr .dx
.left:
    neg
    ld d,a
    ld a,b
    ld (Enemy_PairX),a
.dx:
    ld a,d
    cp 15
    jp nc,.finish
    ld (Enemy_PairDX),a
    ld a,(Enemy_PairActualY)
    ld b,a
    ld a,(Enemy2_PointY)
    ld c,a
    ld a,b
    sub c
    jr c,.above
    ld d,a
    ld a,c
    ld (Enemy_PairY),a
    ld a,(Enemy_PairDiagonal)
    xor 1
    ld (Enemy_PairDiagonal),a
    jr .dy
.above:
    neg
    ld d,a
    ld a,b
    ld (Enemy_PairY),a
.dy:
    ld a,d
    cp 14                    ; leave room for the lossless shifted Y phase
    jp nc,.finish
    ld (Enemy_PairDY),a
    ld a,(Enemy_PairDX)
    and 3
    rrca
    rrca
    ld l,a
    ld a,(Enemy_PairDX)
    srl a
    srl a
    ld h,a
    ld a,(Enemy_PairDY)
    add a,a
    add a,a
    add a,h
    or $80
    ld h,a
    ld (Enemy_PairSource),hl
    ld a,(Enemy_PairDiagonal)
    add a,ENEMY_PAIR_BANK
    ld (Enemy_PairBank),a
    ld a,(Enemy_PairX)
    ld (hud_enemy_x),a
    ld a,(Enemy_PairY)
    ld (hud_enemy_y),a
    ld a,1
    ld (Enemy_PairMode),a
.finish:
    ld a,(Enemy_PairMode)
    ld hl,Enemy_PairLastMode
    cp (hl)
    jr nz,.dirty
    or a
    ret z
    ld a,(Enemy_PairBank)
    ld hl,Enemy_PairLastBank
    cp (hl)
    jr nz,.dirty
    ld hl,(Enemy_PairSource)
    ld de,(Enemy_PairLastSource)
    or a
    sbc hl,de
    ret z
.dirty:
    ld a,255
    ld (hud_enemy_drawn_x),a
    ld a,(Enemy_PairMode)
    ld (Enemy_PairLastMode),a
    ld a,(Enemy_PairBank)
    ld (Enemy_PairLastBank),a
    ld hl,(Enemy_PairSource)
    ld (Enemy_PairLastSource),hl
    ret

Enemy_PairPattern:
    ld a,(Enemy_PairMode)
    or a
    jp z,draw_point
    ld hl,(Enemy_PairSource)
    ld (Enemy_RadarSource),hl
    ld a,(Enemy_PairBank)
    ld ($7000),a
    ret

Enemy_PairAttribute:
    ld a,(Enemy_PairMode)
    or a
    jp z,point_attribute
    ld a,e
    add a,RADAR_Y-1
    ld e,a
    ld a,(scroll_y)
    add a,e
    cp 216
    jr nz,.safe
    dec a
    inc c
    inc c
    inc c
    inc c
.safe:
    ld (hl),a
    inc hl
    ld a,d
    add a,RADAR_X
    ld (hl),a
    inc hl
    ld (hl),c
    inc hl
    ld (hl),0
    inc hl
    ret
