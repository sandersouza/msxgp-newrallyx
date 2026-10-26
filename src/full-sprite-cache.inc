; Twelve complete two-plane masks. The compact radar leaves patterns116..131
; free; at most two front-referenced masks need replacing at VBlank.
Full_PoolFront EQU $0300
Full_PoolBack EQU $0310
Full_PoolKeys EQU $0320
Full_PoolActors EQU $0350
Full_PoolSaved EQU $0360
Full_PoolBody:
    db 0,8,16,192,200,208,216,224,232,248,116,124
Full_PoolWindow:
    db 4,12,188,196,204,212,220,228,236,252,120,128

Full_PoolInit:
    ld hl,Full_PoolKeys
    ld de,Full_PoolKeys+1
    ld bc,35
    ld (hl),255
    ldir
    ld hl,Full_PoolKeys
    ld b,3
    xor a
.common:
    ld (hl),a
    inc hl
    ld (hl),0
    inc hl
    inc hl
    inc a
    djnz .common
    ld hl,Full_PoolKeys
    ld de,Full_PoolSaved
    ld bc,36
    ldir
    ld hl,Full_PoolFront
    ld de,Full_PoolFront+1
    ld bc,27
    ld (hl),0
    ldir
    xor a
    ld (Full_PoolFault),a
    ret

Full_PoolBegin:
    ld a,(Full_RenderRestart)
    or a
    jr nz,.back
    ld hl,Full_PoolKeys
    ld de,Full_PoolSaved
    ld bc,36
    ldir
    ld hl,Full_PoolFront
    ld de,Full_PoolFront+1
    ld bc,11
    ld (hl),0
    ldir
    ld ix,Full_EnemyRecords
    ld b,7
.actor:
    ld a,(ix+0)
    or a
    jr z,.next
    ld a,(ix+16)
    cp 116
    ld a,10
    jr z,.mark_front
    ld a,(ix+16)
    cp 124
    ld a,11
    jr z,.mark_front
    ld a,(ix+16)
    cp 192
    jr c,.common_slot
    cp 248
    ld a,9
    jr z,.mark_front
    ld a,(ix+16)
    sub 192
    rrca
    rrca
    rrca
    add a,3
    jr .mark_front
.common_slot:
    rrca
    rrca
    rrca
.mark_front:
    ld l,a
    ld h,Full_PoolFront/256
    ld (hl),1
.next:
    ld de,32
    add ix,de
    djnz .actor
.back:
    ld hl,Full_PoolSaved
    ld de,Full_PoolKeys
    ld bc,36
    ldir
    ld hl,Full_PoolBack
    ld de,Full_PoolBack+1
    ld bc,11
    ld (hl),0
    ldir
    xor a
    ld (Full_RenderRestart),a
    ret

; IX=pose. Carry reports a hit; D is the slot. Keys are frame/clip/top-row.
Full_PoolFind:
    ld hl,Full_PoolKeys
    ld d,0
    ld b,12
.slot:
    ld a,(hl)
    cp (ix+19)
    jr nz,.next
    inc hl
    ld a,(hl)
    cp (ix+10)
    dec hl
    jr nz,.next
    inc hl
    inc hl
    ld a,(hl)
    cp (ix+20)
    dec hl
    dec hl
    jr nz,.next
    scf
    ret
.next:
    inc hl
    inc hl
    inc hl
    inc d
    djnz .slot
    or a
    ret

Full_PoolReserve:
    ld ix,Full_EnemyRecords
    ld a,($e24e)
    ld b,a
    or a
    ret z
.actor:
    ld a,(ix+0)
    or a
    jr z,.next
    push bc
    call Full_PoolFind
    pop bc
    jr nc,.next
    ld a,d
    add a,Full_PoolBack & 255
    ld l,a
    ld h,Full_PoolBack/256
    ld (hl),1
.next:
    ld de,32
    add ix,de
    djnz .actor
    ret

Full_PoolAssign:
    call Full_PoolFind
    jr nc,.missing
    ld c,d
    ld (ix+13),0
    jr .pose
.missing:
    ld hl,Full_PoolBack
    ld iy,Full_PoolFront
    ld b,12
    ld c,0
.unused_front:
    ld a,(hl)
    or a
    jr nz,.next_slot
    ld a,(iy+0)
    or a
    jr z,.replace
.next_slot:
    inc hl
    inc iy
    inc c
    djnz .unused_front
    ld hl,Full_PoolBack
    ld b,12
    ld c,0
.unused_back:
    ld a,(hl)
    or a
    jr z,.replace
    inc hl
    inc c
    djnz .unused_back
    ld a,1                  ; Unreachable with seven requests and twelve slots.
    ld (Full_PoolFault),a
    ld c,0
.replace:
    ld l,c
    ld h,0
    add hl,hl
    ld e,c
    ld d,0
    add hl,de
    ld de,Full_PoolKeys
    add hl,de
    ld a,(ix+19)
    ld (hl),a
    inc hl
    ld a,(ix+10)
    ld (hl),a
    inc hl
    ld a,(ix+20)
    ld (hl),a
    ld (ix+13),1
.pose:
    ld a,c
    add a,Full_PoolBack & 255
    ld l,a
    ld h,Full_PoolBack/256
    ld (hl),1
    ld a,(Full_EnemyIndex)
    add a,Full_PoolActors & 255
    ld l,a
    ld h,Full_PoolActors/256
    ld (hl),c
    ld e,c
    ld d,0
    ld hl,Full_PoolBody
    add hl,de
    ld a,(hl)
    ld (ix+16),a
    ld (Full_EnemyPattern),a
    ld hl,Full_PoolWindow
    add hl,de
    ld a,(hl)
    ld (ix+17),a
    ld (Full_EnemyWindowPattern),a
    ret

; Only slots absent from the actual front can be prepared before VBlank.
; Sprite_Upload services raster IRQs and restores its stream pointer afterward.
Full_PoolPreload:
    ld ix,Full_PresentDirty
    ld iy,Full_PresentPatterns
    ld b,7
    ld c,0
.actor:
    ld a,(ix+0)
    or a
    jr z,.next
    ld a,c
    add a,Full_PoolActors & 255
    ld l,a
    ld h,Full_PoolActors/256
    ld l,(hl)
    ld h,Full_PoolFront/256
    ld a,(hl)
    or a
    jr nz,.next
    push bc
    push iy
    pop hl
    ld a,(ix+8)
    cp 16
    jr z,.split
    call .address
    ld b,64
    call Sprite_Upload
    ei
    nop
    jr .uploaded
.split:
    ld de,$7880
    ld b,32
    call Sprite_Upload
    ei
    nop
    ld de,$7de0
    ld b,32
    call Sprite_Upload
    ei
    nop
.uploaded:
    pop bc
    ld (ix+0),0
.next:
    ld de,64
    add iy,de
    inc ix
    inc c
    djnz .actor
    ret
.address:
    ld e,a
    ld d,0
    sla e
    rl d
    sla e
    rl d
    sla e
    rl d
    ld a,d
    or $78
    ld d,a
    ret
