; Experimental native-bank stone reaction. Navigation bit4 tags immutable stone
; cells during cold load; low four road-exit bits are unchanged. No new RAM.
; AI calls this after native movement, on its existing even-tick pass. Empty
; stone lists return immediately. Probe uses the original +/-12 boundaries,
; native98xx cell IDs, portal sentinel and1885 rebound semantics.
GameSession_EnemyRocks:
    ld a,($e251)
    or a
    ret z
    ld a,($e24e)
    or a
    ret z
    ld b,a
    ld ix,$e088
.actor:
    push bc
    ld a,(ix+0)
    or a
    jr z,.probe
    cp $e0
    jr c,.next               ; Preserve existing startup/smoke ownership.
    ld a,(ix+19)
    or a
    jr z,.next
    dec (ix+19)              ; Rock recovery consumes two native clocks here.
    jr z,.next
    dec (ix+19)
    jr .next
.probe:
    call GameSession_EnemyRockProbe
.next:
    pop bc
    ld de,32
    add ix,de
    djnz .actor
    ret

; IX=native enemy descriptor. Caller-saved AF/BC/DE/HL; IX/IY preserved.
; Original181B guard and1821 cell projection; no scans over the stone list.
GameSession_EnemyRockProbe:
    ld a,(ix+19)
    or a
    ret nz
    ld h,(ix+18)
    ld l,(ix+17)
    ld a,(ix+5)
    add a,12
    cp 25
    jr c,.vertical
    bit 7,a
    jr nz,.left
    inc hl
    ld a,l
    and 31
    jr nz,.vertical
    ld hl,$9f00
    jr .vertical
.left:
    dec hl
    ld a,l
    or $e0
    inc a
    jr nz,.vertical
    ld hl,$9f00
.vertical:
    ld a,(ix+7)
    ld de,32
    add a,12
    cp 25
    jr c,.cell
    bit 7,a
    jr z,.up
    add hl,de
    jr .cell
.up:
    or a
    sbc hl,de
.cell:
    ld a,h
    sub $68                 ; Original98xx -> navigation30xx.
    ld h,a
    bit 4,(hl)
    ret z
GameSession_EnemyRockKick:
    ld (ix+0),$e0
    ld (ix+19),50
    ld hl,$0100
    bit 7,(ix+2)
    jr nz,.speed
    ld h,$ff
.speed:
    ld (ix+2),h
    ld (ix+1),l
    ld b,8
    push iy
    ld iyl,0
.recoil:
    ld h,(ix+2)
    ld l,(ix+1)
    ld a,(ix+3)
    call $80fc              ; Original one-pixel kinematics, no2x packet scaling.
    djnz .recoil
    pop iy
    ret
