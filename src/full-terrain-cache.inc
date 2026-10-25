; Exact world-tile ownership in a spare 16KB mapper segment. Page0 is
; mapped only while executing this RAM-only overlay; BIOS mapping is restored.
Full_CachePrimary EQU $d2e1
Full_CacheSub EQU $d2e2
Full_CacheExpanded EQU $d2e3
Full_CacheMapper EQU $d2e4
Full_CacheRAMPrimary EQU $d2e5
Full_CacheRAMSub EQU $d2e6
Full_CacheSegment EQU $d2e7
Full_CacheWidth EQU $d2e8
Full_TurboEnabled EQU $d2e9
Full_TurboActive EQU $d2fb
Full_DirX EQU $d2fc
Full_DirY EQU $d2fd
Full_QueueDirty EQU $d2fe
Full_LoopTicks EQU $d2ff
Full_ScrollValid EQU $d2cd
Full_CellRejected EQU $d2ce
Full_CellRejectedValid EQU $d2d0
; Spread batched motion across physical refreshes without draining the newest
; snapshot immediately. Scene initialization still publishes its exact latch.
Full_LatchScrollY:
    push de
    ld a,(Full_ScrollValid)
    or a
    jr z,.snap
    ld a,(scroll_y)
    ld c,a
    ld a,(irq_scroll_y)
    ld b,a
    ld a,c
    sub b
    IF VDP_R9 == $80
    bit 7,a
    jr z,.magnitude
    neg
.magnitude:
    inc a
    srl a                    ; Half the distance, rounded up, at most four pixels.
    cp 5
    jr c,.distance_limit
    ld a,4
.distance_limit:
    ld d,a
    ELSE
    add a,8
    cp 17
    ld d,2
    jr c,.limit
    inc d
    inc d
    ENDIF
.limit:
    ld a,d
    add a,a
    inc a
    ld e,a
    ld a,c
    sub b
    add a,d
    cp e
    jr c,.snap
    ld a,c
    sub b
    bit 7,a
    ld a,b
    jr nz,.up
    add a,d
    jr .publish
.up:
    sub d
    jr .publish
.snap:
    ld a,1
    ld (Full_ScrollValid),a
    ld a,(scroll_y)
.publish:
    ld (irq_scroll_y),a
    pop de
    ret
Full_TurboOn:
    ld a,(Full_TurboEnabled)
    or a
    ret z
    di
    ld (Full_TurboActive),a
    xor a
    out ($41),a
    ei
    ret
Full_TurboOff:
    ld a,(Full_TurboActive)
    or a
    ret z
    di
    xor a
    ld (Full_TurboActive),a
    inc a
    out ($41),a
    ei
    ret
Full_CacheWorked EQU $d2eb
Full_CacheEnter:
    ld a,(Full_CacheHeld)
    or a
    ret nz
    ld a,(Full_CacheSegment)
    out ($fc),a
    ld a,(Full_CacheExpanded)
    or a
    jr z,.primary
    ld a,(Full_CacheRAMSub)
    ld ($ffff),a
.primary:
    ld a,(Full_CacheRAMPrimary)
    out ($a8),a
    ret
Full_CacheLeave:
    ld a,(Full_CacheHeld)
    or a
    ret nz
    ld a,(Full_CachePrimary)
    out ($a8),a
    ld a,(Full_CacheExpanded)
    or a
    jr z,.mapper
    ld a,(Full_CacheSub)
    ld ($ffff),a
.mapper:
    ld a,(Full_CacheMapper)
    out ($fc),a
    ret
Full_TargetTileX EQU $d2ec
Full_TargetTileY EQU $d2ed
Full_CacheReady EQU $d2ee
Full_CameraBlocked EQU $d2ef
Full_CellLeft EQU $d2f0
Full_CellTop EQU $d2f1
Full_QueuedX EQU $d2f2
Full_QueuedY EQU $d2f3
Full_Edge EQU $d2f4
Full_ClockLast EQU $d2f5
Full_ClockDue EQU $d2f6
Full_ClockDropped EQU $d2f7
Full_CheckCount EQU $d2f9
Full_CheckStep EQU $d2fa
Full_CacheHeld EQU $d2ea
Full_CacheClear:
    ld a,FULL_TERRAIN_BANK
    ld ($7000),a
    call Full_CacheEnter
    ld hl,$8000
    ld de,Full_CacheEngineStart
    ld bc,Full_CacheEngineEnd-Full_CacheEngineStart
    ldir
    ld hl,$2000
    ld de,$2001
    ld bc,4095
    ld (hl),128
    ldir
    ld a,1
    ld (Full_CacheReady),a
    ld a,(ticks)
    ld (Full_ClockLast),a
    xor a
    ld (Full_ClockDue),a
    ld (Full_ScrollValid),a
    ld (Full_ClockDropped),a
    ld (Full_ClockDropped+1),a
    ld (Full_DirX),a
    ld (Full_DirY),a
    inc a
    ld (Full_QueueDirty),a
    jp Full_CacheLeave
Full_ClockFrame:
    push iy
    call Full_CacheEnter
    jp Full_ClockAdvance
Full_SimulationIdle:
    push iy
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    ei                       ; Clock/input work owns no VDP latch or IRQ RAM.
    nop
    jp Full_SimulationIdleNative
Full_IdleExit:
    xor a
    ld (Full_CacheHeld),a
    jp Full_CacheExit
Full_StageQueue:
    ld a,(Full_CacheReady)
    or a
    ret z
    push iy
    call Full_CacheEnter
    jp Full_StageQueueNative
Full_CacheCommand:
    ld a,1
    ld (Full_CacheWorked),a
    ei                       ; Ownership bookkeeping does not own VDP ports.
    nop
    push iy
    call Full_CacheEnter
    jp Full_CacheRun
Full_CacheExit:
    call Full_TurboOff
    call Full_CacheLeave
    pop iy
    ld a,c
    or a
    ret nz
    scf
    ret
Full_CacheProbe:
    ld a,(Stage_RowBatch)
    or a
    ret z
    push iy
    call Full_CacheEnter
    jp Full_WorldProbe
Full_CameraCheck:
    ld a,(Full_CacheReady)
    or a
    ret z
    push iy
    call Full_CacheEnter
    jp Full_CameraValidate
Full_CameraExit:
    call Full_TurboOff
    call Full_CacheLeave
    pop iy
    ld a,(Full_CameraBlocked)
    or a
    ret z
    scf
    ret
