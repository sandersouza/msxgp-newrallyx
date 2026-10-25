; Bank-local memoization of the original zero-speed challenge AI transform.
; Cache only results produced by actual original calls. Reuse is
; restricted to unchanged inputs, no smoke, and seven entirely stationary cars.
Full_AIValid EQU $e3f1
Full_AIValid1 EQU $e3f8
Full_AIKeys EQU $e3f2
Full_AITable0 EQU $d2a8
Full_AITable1 EQU $d2b6
Full_AIBefore EQU $d2c4
Full_AITick EQU $d2cb
Full_NativeAI:
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
    ld a,(Smoke_Valid)
    or a
    jr z,.no_smoke
    ld hl,Smoke_LogicalRows
    ld b,32
.smoke_row:
    ld a,(hl)
    or a
    jp nz,.original
    inc l
    djnz .smoke_row
.no_smoke:
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
    ld (Full_AIValid1),a
.same:
    ld a,c
    ld (de),a
    inc de
    inc ix
    inc ix
    djnz .key
    ld iy,Full_AIBefore
    ld b,7
    ld d,1
.available:
    ld a,(iy+0)
    or a
    ld a,(Full_AIValid)
    jr z,.valid_mask
    ld a,(Full_AIValid1)
.valid_mask:
    and d
    jr z,.miss
    rlc d
    inc iy
    djnz .available
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
    ld (Full_AIValid1),a
    jp $8cd6
.miss:
    call $8cd6              ; One real call on a miss; its state is already final.
    ld ix,$e088
    ld iy,Full_AIBefore
    ld hl,Full_AITable0
    ld b,7
    ld c,1
.remember:
    push hl
    ld a,(iy+0)
    or a
    jr z,.remember0
    ld de,14
    add hl,de
    ld a,(Full_AIValid1)
    or c
    ld (Full_AIValid1),a
    jr .result
.remember0:
    ld a,(Full_AIValid)
    or c
    ld (Full_AIValid),a
.result:
    ld a,(ix+3)
    ld (hl),a
    inc hl
    ld a,(ix+20)
    ld (hl),a
    pop hl
    inc hl
    inc hl
    inc iy
    rlc c
    ld de,32
    add ix,de
    djnz .remember
    ld iy,$e068
    ret
Full_AIKeyAddresses:
    dw $e070,$e072,$e06b,$e06a,$e05b,$e28f
    ASSERT Full_AITick+1 <= $d2d2

    ASSERT $ <= $b770
    defs $b770-$,$ff
Full_EnemyTerminator:
    call Full_TurboOff
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
    call Full_TurboOff        ; Drawing may write VRAM directly or via Sprite_Upload.
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

Full_EnemyRegisteredNative:
    ld a,($e24e)
    cp 4
    jr nc,.mask
    ld hl,(Full_EnemySource)
    ld de,11
    add hl,de
    ex de,hl
    ld hl,$e004
    ld b,5
.slot:
    ld a,(hl)
    inc hl
    cp e
    jr nz,.other
    ld a,(hl)
    cp d
    jr z,.found
.other:
    inc hl
    djnz .slot
    xor a
    ret
.found:
    ld a,1
    or a
    ret
.mask:
    ld a,(Full_EnemyIndex)
    ld e,a
    ld d,0
    ld hl,Full_EnemyBits
    add hl,de
    ld a,(Full_RegisteredMask)
    and (hl)
    ret
    INCLUDE "full-enemy-prepare.inc"

; World/radar coordinates depend only on these four native bytes. Camera scroll,
; facing, registration and contact still pass through ordinary pose preparation.
FullEnemyWorldNative:
    ld iy,(Full_EnemySource)
    ld a,(iy+1)
    or (iy+2)
    jr z,.stationary
    xor a
    ld (ix+31),a
    inc a
    ld (Full_EnemyWorldChanged),a
    jr .calculate
.stationary:
    ld a,(Full_EnemyIndex)
    add a,a
    add a,a
    add a,Full_EnemyWorldKeys & 255
    ld l,a
    ld h,Full_EnemyWorldKeys/256
    ld a,(ix+31)
    or a
    jr z,.changed
    ld a,(iy+5)
    cp (hl)
    jr nz,.changed
    inc l
    ld a,(iy+7)
    cp (hl)
    jr nz,.changed
    inc l
    ld a,(iy+8)
    cp (hl)
    jr nz,.changed
    inc l
    ld a,(iy+10)
    cp (hl)
    jr nz,.changed
    xor a
    ld (Full_EnemyWorldChanged),a
    ret
.changed:
    ld a,l
    and $fc
    ld l,a
    ld a,(iy+5)
    ld (hl),a
    inc l
    ld a,(iy+7)
    ld (hl),a
    inc l
    ld a,(iy+8)
    ld (hl),a
    inc l
    ld a,(iy+10)
    ld (hl),a
    ld a,1
    ld (ix+31),a
    ld (Full_EnemyWorldChanged),a
.calculate:
    ld hl,(Full_EnemySource)
    ld de,8
    add hl,de
    ld a,(hl)
    dec hl
    dec hl
    dec hl
    call Player_Axis
    ld (ix+2),l
    ld (ix+3),h
    ld hl,(Full_EnemySource)
    ld de,10
    add hl,de
    ld a,(hl)
    dec hl
    dec hl
    dec hl
    call Player_AxisY
    ld (ix+4),l
    ld (ix+5),h
    ret
    INCLUDE "full-wide-native.inc"

; Reuse an unchanged, already-published full mask. Camera-relative coordinates
; still advance every frame; clipping, contact and sentinel cases take the
; complete adapter below. No pattern/color reduction or deferred actor motion.
FullEnemyFastPose:
    ld a,(ix+0)
    or a
    jp z,.none
    ld a,(ix+13)
    or (ix+10)
    jp nz,.none
    ld a,(ix+20)
    inc a
    jp nz,.none
    ld a,(Full_RegisteredCurrent)
    or a
    jp z,.none
    ld a,(Death_State)
    or a
    jp nz,.none
    ld a,(iy+15)
    cp (ix+1)
    jp nz,.none
    ld l,(ix+2)
    ld h,(ix+3)
    ld de,(player_x)
    or a
    sbc hl,de
    ld de,PLAYER_X
    add hl,de
    ld a,h
    or a
    jr nz,.none
    ld a,l
    cp 8
    jr c,.none
    ld (ix+6),l
    ld (ix+7),h
    ld l,(ix+4)
    ld h,(ix+5)
    ld de,(player_y)
    or a
    sbc hl,de
    ld de,108
    add hl,de
    ld a,h
    or a
    jr nz,.none
    ld a,l
    cp 12
    jr c,.none
    cp 212
    jr nc,.none
    ld a,(scroll_y)
    add a,l
    dec a
    cp 216
    jr z,.none
    ld (ix+12),a
    ld (ix+8),l
    ld (ix+9),h
    scf
    ret
.none:
    or a
    ret
    INCLUDE "full-enemy-far-native.inc"
