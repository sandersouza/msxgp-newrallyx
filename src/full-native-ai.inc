; Bank-local memoization of the original zero-speed challenge AI transform.
; Both possible direction inputs are evaluated by the original code. Reuse is
; restricted to unchanged inputs, no smoke, and seven entirely stationary cars.
Full_AIValid EQU $e3f1
Full_AIKeys EQU $e3f2
Full_AITable0 EQU $d2a8
Full_AITable1 EQU $d2b6
Full_AIBefore EQU $d2c4
Full_AITick EQU $d2cb
Full_NativeAI:
    ld a,(Smoke_Valid)
    or a
    jp nz,.original
    ld hl,($e025)
    ld a,h
    or l
    jp nz,.original
    ld hl,($e029)
    ld a,h
    or l
    jp nz,.original
    ld a,($e24e)
    cp 7
    jp nz,.original
    ld ix,$e088
    ld iy,Full_AIBefore
    ld b,7
.guard:
    ld a,(ix+0)
    or (ix+1)
    or (ix+2)
    or (ix+19)
    or (ix+21)
    jp nz,.original
    ld a,($e070)
    cp (ix+8)
    jr nz,.not_same_cell
    ld a,($e072)
    cp (ix+10)
    jp z,.original          ; Original same-cell path also reads fine screen positions.
.not_same_cell:
    ld a,(ix+3)
    or a
    jr z,.axis
    inc a
    jp nz,.original
    dec a
.axis:
    ld (iy+0),a
    inc iy
    ld de,32
    add ix,de
    djnz .guard
    ld a,(Full_AIValid)
    cp 1
    jr z,.keys
    xor a
    ld (Full_AIValid),a
.keys:
    ld ix,Full_AIKeyAddresses
    ld de,Full_AIKeys
    ld b,6
.key:
    ld l,(ix+0)
    ld h,(ix+1)
    ld c,(hl)
    ld a,(de)
    cp c
    jr z,.same
    xor a
    ld (Full_AIValid),a
.same:
    ld a,c
    ld (de),a
    inc de
    inc ix
    inc ix
    djnz .key
    ld a,(Full_AIValid)
    or a
    jr nz,.apply
    ld a,($e022)
    ld (Full_AITick),a
    xor a
    call .force_axis
    call $8cd6
    ld hl,Full_AITable0
    call .copy_result
    ld a,255
    call .force_axis
    call $8cd6
    ld hl,Full_AITable1
    call .copy_result
    ld a,(Full_AITick)
    ld ($e022),a
    ld a,1
    ld (Full_AIValid),a
.apply:
    ld ix,$e088
    ld iy,Full_AIBefore
    ld b,7
.actor:
    ld hl,Full_AITable0
    ld a,(iy+0)
    or a
    jr z,.table
    ld hl,Full_AITable1
.table:
    ld a,7
    sub b
    add a,a
    ld e,a
    ld d,0
    add hl,de
    ld a,(hl)
    ld (ix+3),a
    inc hl
    ld a,(hl)
    ld (ix+20),a
    inc iy
    ld de,32
    add ix,de
    djnz .actor
    ld iy,$e068
    ld hl,$e022
    inc (hl)
    ret
.original:
    xor a
    ld (Full_AIValid),a
    jp $8cd6
.force_axis:
    ld hl,$e08b
    ld de,32
    ld b,7
.force:
    ld (hl),a
    add hl,de
    djnz .force
    ret
.copy_result:
    ld ix,$e088
    ld de,32
    ld b,7
.copy:
    ld a,(ix+3)
    ld (hl),a
    inc hl
    ld a,(ix+20)
    ld (hl),a
    inc hl
    add ix,de
    djnz .copy
    ret
Full_AIKeyAddresses:
    dw $e070,$e072,$e06b,$e06a,$e05b,$e28f
    ASSERT Full_AITick+1 <= $d2d2

    ASSERT $ <= $b740
    defs $b740-$,$ff
Full_EnemyTerminator:
    di
    vdp_write 14,7
    ld a,(Full_EnemySATCursor)
    out ($99),a
    ld a,$76
    out ($99),a
    ld a,216
    out ($98),a
    ei
    nop
    ret

; Decode the source's five virtual OAM pointers once per presentation snapshot.
; The seven radar anchors remain independent of native OAM visibility.
Full_BuildRegistrationNative:
    ld a,($e24e)
    cp 4
    ret c
    xor a
    ld (Full_RegisteredMask),a
    ld hl,$e004
    ld b,5
    ld c,0
.slot:
    ld e,(hl)
    inc hl
    ld a,(hl)
    inc hl
    sub $e0
    cp 2
    jr nc,.next
    add a,Full_RegistrationTable/256
    ld d,a
    ld a,(de)
    or c
    ld c,a
.next:
    djnz .slot
    ld a,c
    ld (Full_RegisteredMask),a
    ret

    ASSERT $ <= $b800
    defs $b800-$,$ff
Full_RegistrationTable:
    INCBIN "full-registration.bin"
Full_EnemyDrawNative:
    ld a,(driving)
    or a
    jr z,.hidden
    ld a,(ix+0)
    or a
    jr z,.hidden
    ld a,(Full_EnemySATCursor)
    ld (Full_EnemySATByte),a
    cp (ix+30)
    ld (ix+30),a
    jr z,.same_slot
    ld a,255
    ld (ix+18),a
    ld a,1
    jr .dirty
.same_slot:
    xor a
.dirty:
    ld (Full_EnemySATDirty),a
    ld a,(Full_EnemySATCursor)
    add a,8
    ld (Full_EnemySATCursor),a
    jp FullEnemy_DrawPrepared ; Tail call: drawing may switch the resource bank.
.hidden:
    ld (ix+30),255
    ret

    INCLUDE "full-enemy-prepare.inc"
