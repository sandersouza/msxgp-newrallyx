; Full-game enemy ABI, followed by MSX-native decisions and shared presentation.
Full_AIValid EQU $e3f1
Full_AIValid1 EQU $e3f8
Full_AIKeys EQU $e3f2
Full_AITable0 EQU $d2a8
Full_AITable1 EQU $d2b6
Full_AIBefore EQU $d2c4
Full_AITick EQU $d2cb
Full_NativeAI:
    jp Full_MSXAI
    jp Full_MSXContact       ; B603
    jp Full_MSXPan           ; B606
    jp Full_MSXAnimation     ; B609
    jp Full_PlayerInitialApply ; B60C, before the mapper overlay is installed.
    INCLUDE "full-msx-enemies.inc"
Full_EnemyTerminator:
    call Full_PresentTerminator
    ld a,(Full_PresentEnabled)
    or a
    ret nz
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

Full_MSXIdleTick:
    call $8069               ; Startup/spin retain their 60 Hz original dispatcher.
    call Smoke_Tick
    call Full_MSXAnimationTick
    call $b600               ; Odd AI pass advances its clock without decisions.
    call Enemy_CameraOnly
    jp Player_CountTick
Full_MSXAnimationTick:
    ld hl,player_animation
    inc (hl)
    ld a,(hl)
    cp 4
    ret c
    ld (hl),0
    jp $9ddf

Full_PresentTerminator:
    call Full_CacheEnter
    ld a,(Full_EnemySATCursor)
    sub 72
    ld e,a
    inc a
    ld (Full_PresentLength),a
    ld d,0
    ld hl,Full_PresentSAT
    add hl,de
    ld (hl),216
    jp Full_CacheLeave

Full_PresentSealNative:
    ld a,(Session_State)
    or a
    ret nz
    call Full_PoolPreloadNative
    ld hl,(scroll_high)
    ld (Full_PresentNextX),hl
    ld a,(scroll_y)
    ld (Full_PresentNextY),a
Full_PresentSealed:
    ld a,1
    ld (Full_PresentEnabled),a
    ld (Full_PresentReady),a
    ret

Full_EnemyDrawNative:
    ld a,(driving)
    or a
    jr z,.hidden
    ld a,(ix+0)
    or a
    jr z,.hidden
    ld a,(Full_CacheHeld)
    or a
    jr z,.map_assign
    push iy
    call Full_PoolAssign
    pop iy
    jr .assigned
.map_assign:
    call Full_PoolAssignNative
.assigned:
    ld a,(Full_PresentEnabled)
    or a
    call z,Full_TurboOff      ; Only scene setup uploads directly; packets own RAM.
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
    ld a,(Full_PresentEnabled)
    or a
    jr z,.draw
    ld a,(ix+13)
    or a
    jp z,Full_EnemySATNative
.draw:
    jp FullEnemy_DrawPrepared ; Tail call: drawing may switch the resource bank.
.hidden:
    ld (ix+30),255
    ret

; An unchanged complete mask needs only its two RAM SAT entries. Fixed OR
; colors were initialized for every destination; no VDP/resource-bank work.
Full_EnemySATNative:
    call Full_CacheEnter
    ld a,(ix+7)
    bit 7,a
    ld b,(ix+6)
    jr z,.x
    ld b,0
.x:
    ld a,(Full_EnemySATByte)
    sub 72
    add a,Full_PresentSAT & 255
    ld l,a
    ld h,Full_PresentSAT/256
    ld a,(ix+12)
    ld (hl),a
    inc hl
    ld (hl),b
    inc hl
    ld a,(ix+16)
    ld (hl),a
    inc hl
    ld (hl),0
    inc hl
    ld a,(ix+12)
    ld (hl),a
    inc hl
    ld (hl),b
    inc hl
    ld a,(ix+17)
    ld (hl),a
    inc hl
    ld (hl),0
    ld (ix+18),0
    ld (ix+22),216           ; A later full draw must rebuild its private SAT cache.
    jp Full_CacheLeave

; A complete gameplay packet touches only mapper RAM. Retain one mapping
; through reservation, assignment and queued masks/SAT, restoring nested owners.
; The terminator remaps PLAYER_BANK before the resident loop returns here.
Full_EnemyDrawBatch:
    ld a,(Full_PresentEnabled)
    or a
    jr nz,.packet
    call Enemy_Prepare
    call Full_PoolReserveNative
    jp Enemy_Draw
.packet:
    ld a,(Full_CacheHeld)
    push af
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    call Full_EnemyPrepareLoop
    call Full_PoolReserve
    call Full_EnemyDrawLoop
    pop af
    ld (Full_CacheHeld),a
    jp Full_CacheLeave

Full_PoolReserveNative:
    push iy
    call Full_TurboOn
    call Full_CacheEnter
    call Full_PoolReserve
    call Full_CacheLeave
    call Full_TurboOff
    pop iy
    ret
Full_PoolAssignNative:
    push iy
    call Full_TurboOn
    call Full_CacheEnter
    call Full_PoolAssign
    call Full_CacheLeave
    pop iy
    ret
Full_PoolPreloadNative:
    push ix
    push iy
    call Full_TurboOff
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    call Full_PoolPreload
    ei                       ; Upload loops leave no foreground control pair open.
    nop
    xor a
    ld (Full_CacheHeld),a
    call Full_CacheLeave
    pop iy
    pop ix
    ret

    INCLUDE "full-enemy-prepare.inc"

; World/radar coordinates depend only on these four native bytes. Camera scroll,
; facing, registration and contact still pass through ordinary pose preparation.
FullEnemyWorldNative:
    ld iy,(Full_EnemySource)
    ld a,(iy+0)
    cp $89
    jr nc,.stationary        ; Startup holds position despite a nonzero saved velocity.
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
    cp 1                    ; Tag 2 belongs to the far-radar sampling clock.
    jr nz,.changed
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

Full_PlayerInitialApply:
    ld hl,(player_pending_x)
    ld (player_x),hl
    ld de,-VIEWPORT_HALF
    add hl,de
    ld (world_x),hl
    ld hl,(player_pending_y)
    ld (player_y),hl
    ld de,-105
    add hl,de
    ld (world_y),hl
    ret

Full_EnemyRecordAddress:
    ld a,(Full_EnemyIndex)
    inc a
    rlca
    rlca
    rlca
    rlca
    rlca
    ld l,a
    ld h,Full_EnemyRecords/256
    ret

Full_CopyColdNative:
    ld hl,$a800
    ld de,$f000
    ld bc,Full_LoadEnd-Full_LoadStart
    ldir
    ld de,$c680
    ld bc,Full_EnemyHotEnd-Full_EnemyHotStart
    ldir
    ld de,Full_RadarIRQStart
    ld bc,Full_RadarIRQEnd-Full_RadarIRQStart
    ldir
    xor a
    ld (Full_Loading),a
    ld (Full_Transitions),a
    ld (Full_DebugHeld),a
    ld (Full_AttractClock),a
    ld (Full_AttractClock+1),a
    ld (Full_PresentEnabled),a
    ld (Full_PresentReady),a
    jp Full_CacheInitNative
