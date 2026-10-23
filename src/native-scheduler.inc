; Called only after the host IRQ has saved the full interrupted context.
; Four-byte arithmetic matches native_contract.advance_clock exactly.
Native_HostClock:
    IF NATIVE_LOGIC
    ld a,(Native_ClockArmed)
    or a
    jr nz,.accept
    ld a,(Native_AssetMapped)
    or a
    ret nz
    ld a,(Native_Suspended)
    or a
    ret nz
    ld a,(Native_VirtualIFF)
    or a
    ret z
    ld a,($a181)
    and 1
    ret z
    ld (Native_ClockArmed),a
.accept:
    ENDIF
Native_AdvanceClock:
    ld bc,NATIVE_FRAME_LO
    ld de,NATIVE_FRAME_HI
Native_AddClock:
    ld hl,(Native_Clock)
    add hl,bc
    ld (Native_Clock),hl
    ld hl,(Native_Clock+2)
    adc hl,de
    ld (Native_Clock+2),hl
.due:
    ld hl,(Native_Clock)
    ld bc,NATIVE_DIVISOR_LO
    or a
    sbc hl,bc
    ex de,hl
    ld hl,(Native_Clock+2)
    ld bc,NATIVE_DIVISOR_HI
    sbc hl,bc
    jr c,.finished
    ld (Native_Clock+2),hl
    ld (Native_Clock),de
    ld hl,Native_Pending
    call Native_Increment32
    ld a,1
    ld (Native_Due),a
    jr .due
.finished:
    ret
Native_ClockDone EQU Native_AddClock.finished

    IF NATIVE_FINE_IRQ
; One programmable line deadline per logical tick. 16.5ms is exactly
; 259 + 1399/30400 scanlines. Ceiling error is retained, never rounded away.
; Deadlines outside the safely available 0..212 comparator range are delivered
; at line0 of the following frame, retaining their original ideal phase.
Native_FineClock:
    ld a,1
    out ($99),a
    ld a,$8f
    out ($99),a
    in a,($99)
    and 1
    ld (Native_FineLine),a
    xor a
    out ($99),a
    ld a,$8f
    out ($99),a
    in a,($99)
    ld (Native_FineStatus),a
    ld a,(Native_FineStage)
    cp 2
    jr nc,.running
    ld a,(Native_FineStatus)
    and $80
    ret z
    ld a,(Native_FineStage)
    or a
    jr nz,.synchronized
    inc a
    ld (Native_FineStage),a
    ret
.synchronized:
    ; The first status may be stale after cold initialization. The next
    ; VBlank is a fresh edge; line0 of the next frame is still ahead.
    ld a,2
    ld (Native_FineStage),a
    xor a
    ld (Native_FineIndex),a
    out ($99),a
    ld a,$93
    out ($99),a
    ld a,($f3df)
    or $10
    out ($99),a
    ld a,$80
    out ($99),a
    ret
.running:
    ld a,(Native_FineLine)
    or a
    ret z
    ld a,(Native_FineStage)
    cp 2
    jr nz,Native_DeadlinePulse
    ld hl,0
    ld (Native_DeadlineLine),hl
    ld (Native_DeadlineError),hl
    ld a,3
    ld (Native_FineStage),a
Native_DeadlineSync:
    jr Native_DeadlineSchedule
Native_DeadlinePulse:
    ld a,(Native_ClockArmed)
    or a
    jr nz,Native_DeadlineQueue
    ld a,(Native_AssetMapped)
    or a
    jr nz,Native_DeadlineSchedule
    ld a,(Native_Suspended)
    or a
    jr nz,Native_DeadlineSchedule
    ld a,(Native_VirtualIFF)
    or a
    jr z,Native_DeadlineSchedule
    ld a,($a181)
    and 1
    jr z,Native_DeadlineSchedule
    ld (Native_ClockArmed),a
Native_DeadlineQueue:
    ld hl,Native_Pending
    call Native_Increment32
    ld a,1
    ld (Native_Due),a
Native_DeadlineSchedule:
    call Native_DeadlineNext
    out ($99),a
    ld a,$93
    out ($99),a
    ret

; Host-only pure arithmetic, also exercised independently for 100000 deadlines.
Native_DeadlineNext:
    ld hl,(Native_DeadlineError)
    ld de,1399
    or a
    sbc hl,de
    ld de,259
    jr nc,.fraction
    ld bc,30400
    add hl,bc
    inc de
.fraction:
    ld (Native_DeadlineError),hl
    ld hl,(Native_DeadlineLine)
    add hl,de
    ld de,NATIVE_FRAME_LINES
    or a
    sbc hl,de
    jr nc,.wrapped
    add hl,de
.wrapped:
    ld (Native_DeadlineLine),hl
    ld a,h
    or a
    ld a,l
    jr nz,.blank
    cp 213
    jr c,.ready
.blank:
    xor a
.ready:
    ld (Native_FineIndex),a
Native_DeadlineNextDone:
    ret
    ENDIF

; HL=four-byte little-endian counter. Refuse rollover rather than lose ticks.
Native_Increment32:
    inc (hl)
    ret nz
    inc hl
    inc (hl)
    ret nz
    inc hl
    inc (hl)
    ret nz
    inc hl
    inc (hl)
    ret nz
    ld a,$e4
    jp Native_Fail

; Return A=1 only when it is safe to enter original page-0 logic. Do not read
; either the interrupted game stack or hardware shadows while assets are mapped.
Native_SelectIRQ:
    IF NATIVE_VIDEO
    ld a,(Native_FrameMapped)
    or a
    jp nz,.blocked
    ENDIF
    ld a,(Native_Suspended)
    or a
    jr nz,.blocked
    ld a,(Native_AssetMapped)
    or a
    jr nz,.blocked
    ld a,(Native_GameBusy)
    or a
    jr nz,.blocked
    ld a,(Native_VirtualIFF)
    or a
    jr z,.blocked
    ld a,($a181)
    and 1
    jr z,.blocked
    ld hl,(Native_InterruptedSP)
    IF NATIVE_VIDEO + NATIVE_IRQ_PROBE
    ld a,(Native_SoftwareBusy)
    or a
    jr z,.frame
    ld hl,(Native_SoftwareSP)
.frame:
    ENDIF
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld a,d
    cp $40
    IF NATIVE_LOGIC + NATIVE_IRQ_PROBE
    jr c,.eligible
    ld hl,Native_EligibleIRQPCs
.find:
    ld c,(hl)
    inc hl
    ld b,(hl)
    inc hl
    ld a,b
    or c
    jr z,.blocked
    ld a,b
    cp d
    jr nz,.find
    ld a,c
    cp e
    jr nz,.find
.eligible:
    ELSE
    jr nc,.blocked
    ENDIF
    di                         ; the four-byte queue claim is atomic
    ld hl,(Native_Pending)
    ld de,(Native_Pending+2)
    ld a,h
    or l
    or d
    or e
    jr z,.blocked
    ld bc,1
    or a
    sbc hl,bc
    ld (Native_Pending),hl
    ex de,hl
    ld bc,0
    sbc hl,bc
    ld (Native_Pending+2),hl
    ld a,h
    or l
    or d
    or e
    jr nz,.still_due
    ld (Native_Due),a
.still_due:
    IF NATIVE_VIDEO
    ld hl,(Native_InputCache)
    ld ($a200),hl
    ld a,(Native_InputCache+2)
    ld ($a202),a
    ENDIF
    xor a
    ld (Native_VirtualIFF),a
    inc a
    ld (Native_GameBusy),a
.claimed:
    ret
.blocked:
    xor a
    ret
Native_ClaimGameIRQ EQU Native_SelectIRQ.claimed

; Entered after the game has saved HL,DE,BC,AF,IX,IY in the original order.
; Foreground PC is already on the interrupted stack, not a returning game tick.
Native_PublishRuntime:
    IF NATIVE_VIDEO && NATIVE_RENDER_IN_IRQ
    call Native_PrepareFrame
    ENDIF
    ld hl,Native_GameTicks
    call Native_Increment32
    xor a
    ld (Native_GameBusy),a
    ld (Native_PublishKind),a
    inc a
    ld (Native_VirtualIFF),a
    pop iy
    pop ix
    pop af
    pop bc
    pop de
    pop hl
    ld (Native_Published),a
    ei
    ret

; Replay the nonreturning foreground stack reset, retaining the original next
; instruction as return PC. Share dispatch without advancing the host clock.
Native_Checkpoint:
    ld sp,$8400
    IF NATIVE_TICK_FOREGROUND
    push af
    ld a,(Native_VirtualIFF)
    or a
    jr z,.unpaced
    ld a,($a181)
    and 1
    jr z,.unpaced
    pop af
    call Native_WaitTick       ; original logic stays active; spare time services VDP
    jp NATIVE_FOREGROUND_RESUME
.unpaced:
    pop af
    ENDIF
    IF NATIVE_VIDEO
    call Native_PrepareFrame
    ENDIF
    push af
    ld a,(Native_Due)
    or a
    jr nz,.due
    pop af
    jp NATIVE_FOREGROUND_RESUME
.due:
    pop af
    push hl
    ld hl,NATIVE_FOREGROUND_RESUME
    ex (sp),hl
    di
    jp Native_SoftwareIRQ

    IF NATIVE_LOGIC + NATIVE_IRQ_PROBE
Native_ReadyPoll EQU Native_Poll
; Preserve foreground progress while admitting queued ticks in busy-wait loops.
Native_Poll:
    IF NATIVE_VIDEO
    call Native_PrepareFrame
    ENDIF
    push af
    ld a,(Native_Due)
    or a
    jr nz,.due
    pop af
    ei
    ret
.due:
    pop af
    push hl
    ld hl,.resume
    ex (sp),hl
    di
    jp Native_SoftwareIRQ
.resume:
    ei
    ret

; A game HALT waits for a completed logical game interrupt. A host VBlank with
; no due tick must not release it; an already queued tick need not await VBlank.
; Only the two fully saved return boundaries below are IRQ-eligible.
Native_WaitTick:
    di
    push af
    push hl
    ld hl,(Native_GameTicks)
    ld (Native_WaitStart),hl
    ld hl,(Native_GameTicks+2)
    ld (Native_WaitStart+2),hl
    ei
.poll:
    ld a,(Native_Due)
    or a
    jr z,.afterDispatch
    di
    push hl
    ld hl,.afterDispatch
    ex (sp),hl
    jp Native_SoftwareIRQ
.afterDispatch:
    ei
    ld hl,(Native_WaitStart)
    ld a,(Native_GameTicks)
    cp l
    jr nz,.done
    ld a,(Native_GameTicks+1)
    cp h
    jr nz,.done
    ld hl,(Native_WaitStart+2)
    ld a,(Native_GameTicks+2)
    cp l
    jr nz,.done
    ld a,(Native_GameTicks+3)
    cp h
    jr nz,.done
    IF NATIVE_VIDEO
    call Native_PrepareFrame
    ld a,(Native_RenderStage)
    or a
    jp nz,.poll               ; use the original HALT wait for queued VDP work
    ENDIF
    di
    ld a,(Native_Due)
    or a
    jp nz,.poll
    ei
    halt
.afterHalt:
    jp .afterDispatch
.done:
    di
    pop hl
    pop af
    ei
    ret
    ENDIF
