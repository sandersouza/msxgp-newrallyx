; Authored synthetic foreground/IRQ only. No original game instructions/data.
Native_ClockProof EQU NATIVE_STATE+80
Native_PendingProof EQU NATIVE_STATE+84
Native_ProbePhase EQU NATIVE_STATE+127
Native_DrainSentinel EQU NATIVE_STATE+91

Native_TestScheduler:
    di
    call Native_ClearSchedule
    ld ix,50000
    ld iy,2
.clock:
    call Native_AdvanceClock
    dec ix
    ld a,ixh
    or ixl
    jr nz,.clock
    dec iy
    ld a,iyh
    or iyl
    jr z,.clock_done
    ld ix,50000
    jr .clock
.clock_done:
    ld hl,Native_Clock
    ld de,Native_ClockProof
    ld bc,4
    ldir
    ld hl,Native_Pending
    ld de,Native_PendingProof
    ld bc,4
    ldir
    call Native_ClearSchedule
    ld hl,Native_ForegroundImage
    ld de,$0100
    ld bc,Native_ForegroundImageEnd-Native_ForegroundImage
    ldir
    ld hl,Native_GameImage
    ld de,$01f0
    ld bc,Native_GameImageEnd-Native_GameImage
    ldir
    ld hl,Native_ResumeImage
    ld de,$0120
    ld bc,Native_ResumeImageEnd-Native_ResumeImage
    ldir
    ld (Native_ProbeReturnSP),sp
    xor a
    ld (Native_Suspended),a
    ld (Native_AssetMapped),a
    inc a
    ld (Native_VirtualIFF),a
    ld ($a181),a
    ld (Native_ProbePhase),a
    ld sp,$8400
    ld bc,$4034
    ld de,$5678
    ld hl,$9abc
    ld ix,$1357
    ld iy,$2468
    exx
    ld bc,$abcd
    ld de,$dcba
    ld hl,$4321
    exx
    ex af,af'
    ld a,$a5
    or a
    ex af,af'
    ld a,$5a
    or a
    jp $0100

Native_ClearSchedule:
    xor a
    ld hl,Native_Clock
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    ld hl,Native_Pending
    ld de,Native_Pending+1
    ld bc,12
    ld (hl),a
    ldir
    ret

Native_EndIRQProbe:
    di
    ld sp,(Native_ProbeReturnSP)
    xor a
    ld (Native_ProbePhase),a
    ld (Native_AssetMapped),a
    inc a
    ld (Native_Suspended),a
    ld hl,$0100
    ld de,$0101
    ld bc,Native_ForegroundImageEnd-Native_ForegroundImage-1
    ld (hl),0
    ldir
    ld hl,$0120
    ld de,$0121
    ld bc,Native_ResumeImageEnd-Native_ResumeImage-1
    ld (hl),0
    ldir
    ld hl,$01f0
    ld de,$01f1
    ld bc,Native_GameImageEnd-Native_GameImage-1
    ld (hl),0
    ldir
    ld hl,$8000
    ld de,$8001
    ld bc,$3fff
    ld (hl),0
    ldir
    ld a,$ff
    ld ($a200),a
    ld ($a201),a
    ld a,$c3
    ld ($a202),a
    ret

Native_DrainStart:
    xor a
    ld (Native_GameBusy),a
    ld (Native_Suspended),a
    ld (Native_AssetMapped),a
    inc a
    ld (Native_VirtualIFF),a
    ld ($a181),a
    inc a
    ld (Native_ProbePhase),a
Native_DrainNext:
    ld hl,(Native_Pending)
    ld de,(Native_Pending+2)
    ld a,h
    or l
    or d
    or e
    jr nz,.dispatch
    ld a,(Native_DrainSentinel)
    or a
    jp nz,Native_TestWaits
    inc a
    ld (Native_DrainSentinel),a
.dispatch:
    ld (Native_ProbeBefore),a
    jp Native_Checkpoint

; Independent HALT/POLL semantics with authored IRQ logic. Restore the preceding
; cadence result only after the harness has checked each synthetic wait event.
Native_TestWaits:
    di
    ld hl,Native_Clock
    ld de,NATIVE_STATE+104
    ld bc,4
    ldir
    ld hl,Native_Pending
    ld bc,4
    ldir
    ld hl,Native_GameTicks
    ld bc,4
    ldir
    ld a,3
    ld (Native_ProbePhase),a
    call Native_ClearSchedule
    ld a,1
    ld (Native_VirtualIFF),a
    ld (Native_GameBusy),a
    ld ($a181),a
    ld sp,$8400
    ld a,$5a
    or a
    ld (Native_ProbeBefore),a
    call Native_WaitTick
    ld (Native_ProbeAfter),a
    di
    ld hl,$0102 ; three claims cross $0100 -> $00ff without clearing Due
    ld (Native_Pending),hl
    ld a,1
    ld (Native_Due),a
    ld hl,0
    ld (Native_Pending+2),hl
    ld (Native_ProbeBefore),a
    call Native_WaitTick
    call Native_WaitTick
    call Native_WaitTick
    ld (Native_ProbeAfter),a
    di
    ld hl,0
    ld (Native_Pending),hl
    ld (Native_Pending+2),hl
    xor a
    ld (Native_Due),a
    ld (Native_ProbeBefore),a
    call Native_Poll
    ld (Native_ProbeAfter),a
    di
    ld hl,NATIVE_STATE+104
    ld de,Native_Clock
    ld bc,4
    ldir
    ld de,Native_Pending
    ld bc,4
    ldir
    ld de,Native_GameTicks
    ld bc,4
    ldir
    jp Native_EndIRQProbe

Native_EligibleIRQPCs:
    dw Native_WaitTick.afterDispatch,Native_WaitTick.afterHalt
    dw Native_Poll.resume,0

Native_ForegroundImage:
    PHASE $0100
Native_SyntheticForeground:
    ld (Native_ProbeBefore),a
    ei
    halt
    ld (Native_ProbeAfter),a
    djnz Native_SyntheticForeground
    jp Native_DrainStart
    DEPHASE
Native_ForegroundImageEnd:
Native_ResumeImage:
    PHASE $0120
Native_SyntheticResume:
    ld (Native_ProbeAfter),a
    jp Native_DrainNext
    DEPHASE
Native_ResumeImageEnd:
Native_GameImage:
    PHASE $01f0
Native_SyntheticGame:
    push hl
    push de
    push bc
    push af
    push ix
    push iy
    xor a
    ld ($a181),a
    ld hl,$8100
    inc (hl)
    ld a,1
    ld ($a181),a
    jp Native_PublishRuntime
    DEPHASE
Native_GameImageEnd:
