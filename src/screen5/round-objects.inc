; Sparse dynamic objects fit beside smoke state without using the Z80 stack.
; These entry points execute with PLAYER_BANK mapped, during round preparation.
Round_Objects EQU $dc00      ; 896 bytes, ends at DF80; source video begins E000
Round_ObjectsBuild:
    jp Round_ObjectsBuildBody
Round_ObjectsAt:
    jp Round_ObjectsAtBody
Round_ObjectsScan:
    jp Round_ObjectsScanBody

Round_ObjectsBuildBody:
    xor a
    ld hl,Round_Objects
    ld de,Round_Objects+1
    ld bc,895
    ld (hl),a
    ldir
    ld ix,($e992)
    ld b,10
    ld d,1
.flag:
    ld l,(ix+0)
    ld h,(ix+1)
    push bc
    call Round_ObjectsPut
    pop bc
    inc ix
    inc ix
    inc d
    djnz .flag
    ld a,($e251)
    or a
    ret z
    ld b,a
    ld d,15
    ld ix,($e996)
.rock:
    ld l,(ix+0)
    ld h,(ix+1)
    push bc
    call Round_ObjectsPut
    pop bc
    inc ix
    inc ix
    djnz .rock
    ret

; Input HL = original 9800..9EFF cell identifier. C retains nibble parity.
Round_ObjectsAddress:
    ld a,l
    and 1
    ld c,a
    ld a,h
    sub $98
    ld h,a
    srl h
    rr l
    ld a,h
    add a,Round_Objects/256
    ld h,a
    ret
Round_ObjectsPut:
    call Round_ObjectsAddress
    ld a,c
    or a
    jr nz,.odd
    ld a,(hl)
    and $f0
    or d
    ld (hl),a
    ret
.odd:
    ld a,d
    rlca
    rlca
    rlca
    rlca
    ld c,a
    ld a,(hl)
    and 15
    or c
    ld (hl),a
    ret
Round_ObjectsAtBody:
    push bc
    push hl
    call Round_ObjectsAddress
    ld a,c
    or a
    ld a,(hl)
    jr z,.even
    rrca
    rrca
    rrca
    rrca
.even:
    and 15
    pop hl
    pop bc
    ret

; Component probe: all 1792 cells, including both nibbles and every row edge.
; Output uses otherwise idle video rings; native object inputs remain untouched.
Round_ObjectsScanBody:
    ld hl,$9800
    ld de,$e400
    ld bc,1792
.cell:
    call Round_ObjectsAtBody
    ld (de),a
    inc de
    inc hl
    dec bc
    ld a,b
    or c
    jr nz,.cell
    ret
