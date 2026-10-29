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
Full_CellObject EQU $d2d1    ; low bits: source kind; bit4/5: single-column/row copy
Full_CameraPlanX EQU $d2b6
Full_CameraPlanY EQU $d2b8
Full_CameraAppliedTick EQU $d2ba
Full_CameraAppliedValid EQU $d2bb
Full_PresentEnabled EQU $d2bc
Full_PresentReady EQU $d2bd
Full_PresentNextX EQU $d2be
Full_PresentNextY EQU $d2c0
Full_PresentLength EQU $d2c1
Full_PresentActiveX EQU $d2c2
Full_IdlePrefetch EQU $c67f
Full_RenderRestart EQU $e3f1
Full_PoolFault EQU $e3f8
Full_FrameOriginX EQU $e3f2
Full_FrameOriginY EQU $e3f4
Full_PlayerPose EQU $d158
Full_PlayerNextPose EQU $d15a
Full_PlayerActivePose EQU $d15c
Full_CameraCentreX EQU $d15e
Full_CameraCentreY EQU $e3f6
Full_SealedFrame EQU $c678
; Signed origin HL, unsigned maximum BC. Preserve BC for both axes.
Full_ClampWorldAxis:
    bit 7,h
    jr nz,.zero
    or a
    sbc hl,bc
    jr c,.restore
    ld hl,0
.restore:
    add hl,bc
    ret
.zero:
    ld hl,0
    ret
; Initialization publishes immediately. Gameplay scroll changes only with the
; complete deferred packet, so both axes share the same physical frame.
Full_LatchScrollY:
    ld a,(Full_PresentEnabled)
    or a
    ret nz
    ld bc,(scroll_high)
    ld (Full_PresentActiveX),bc
    ld a,(scroll_y)
    ld (irq_scroll_y),a
    ret

; Spend safe idle intervals on due native clocks or one hidden terrain command.
Full_PresentIdle:
    ld hl,Full_PresentIdleEngine
    jr Full_EnterFrame
Full_WarmCamera:
    ld hl,Full_WarmCameraEngine
    jr Full_EnterFrame
Full_AdvanceClock:
    ld hl,Full_AdvanceClockEngine
Full_EnterFrame:
    push iy
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    ei
    nop
    jp (hl)
Full_PresentBegin:
    ld a,(Full_PresentEnabled)
    or a
    jr z,.initial
    call Full_TurboOn        ; Cache metadata owns no VDP latch.
.initial:
    call Full_CacheEnter
    push ix
    push iy
    ld a,(Full_CacheReady)
    or a
    call nz,Full_PoolBegin
    pop iy
    pop ix
    ld hl,Full_PresentDirty
    ld b,7
    xor a
.clear:
    ld (hl),a
    inc hl
    djnz .clear
    jp Full_CacheLeave
Full_PresentSeal:
    ld a,PLAYER_BANK
    ld ($7000),a
    jp Full_PresentSealNative
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
    IF FLAG_POPUPS
    xor a
    ld (Popup_Active),a
    ld (Popup_Pending),a
    ENDIF
    ld a,FULL_TERRAIN_BANK
    ld ($7000),a
    call Full_CacheEnter
    ld hl,$8000
    ld de,Full_CacheEngineStart
    ld bc,Full_CacheEngineEnd-Full_CacheEngineStart
    ldir
    ld a,(Full_Layout)
    and 3
    add a,a
    add a,a
    add a,a
    add a,$a0
    ld h,a
    ld l,0
    ld de,Full_MSXNavigation
    ld bc,1792
    ldir
    call Full_InitializeColorDestinations
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
    ld (Full_CameraAppliedValid),a
    inc a
    ld (Full_QueueDirty),a
    jp Full_CacheLeave
Full_ClockFrame:
    push iy
    call Full_CacheEnter
    jp Full_ClockAdvance
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
    ld hl,(player_pending_x)
    ld (Full_CameraPlanX),hl
    ld hl,(player_pending_y)
    ld (Full_CameraPlanY),hl
    ld a,(Full_CacheReady)
    or a
    ret z
    push iy
    call Full_CacheEnter
    jp Full_CameraValidate
Full_PlayerApply:
    push iy
    call Full_CacheEnter
    jp Full_PlayerApplyNative
Full_TrySmokeCell:
    push iy
    push bc
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    jp Full_SmokeCellNative
Full_EnqueueSmoke:
    push iy
    call Full_CacheEnter
    jp Full_EnqueueSmokeNative
Full_RadarDeparture:
    ld hl,Full_RadarDepartureNative
    jr Full_RadarExecute
Full_RadarCommit:
    ld hl,Full_RadarCommitNative
    jr Full_RadarExecute
Full_RadarBegin:
    ld hl,Full_RadarBeginNative
Full_RadarExecute:
    push iy
    call Full_CacheEnter
    jp (hl)
Full_RadarRAMExit:
    call Full_CacheLeave
    pop iy
    ret
Full_SmokeCellExit:
    ld a,c
    pop bc
    ld c,a
    xor a
    ld (Full_CacheHeld),a
    jp Full_CacheExit
Full_CameraExit:
    call Full_TurboOff
    call Full_CacheLeave
    pop iy
    ld a,(Full_CameraBlocked)
    or a
    ret z
    scf
    ret
