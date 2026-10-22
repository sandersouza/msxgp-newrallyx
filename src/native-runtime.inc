; Discard writes to the original program window while retaining INC flags.
; Input: HL=original address; carry is preserved. Output: A=readback value,
; F=INC flags, HL unchanged. Other main and alternate registers are untouched.
; Exercised independently by the synthetic probe and installed by the guarded
; original-program logic profile.
Native_IncrementRead:
    push af
    ld a,h
    cp $40
    jr nc,.ram
    pop af
    ld a,(hl)
    inc a
    ld a,(hl)
    ret
.ram:
    pop af
    inc (hl)
    ld a,(hl)
    ret

; Original indirect stores into ROM disappear on arcade hardware. Retain the
; source address/data/flags even when a generated table contains a null entry.
Native_WriteDE:
    push af
    ld a,d
    cp $40
    jr c,.discard
    pop af
    ld (de),a
    ret
.discard:
    pop af
    ret

    IF NATIVE_ORIGINAL_RESET_PROBE
; Retain the cold RAM initialization's own algorithm and data accesses. The
; cabinet mode/interrupt wait is replaced by the guarded host transition.
Native_Reset:
    di
    IF NATIVE_VIDEO
    call Native_VideoInit
    ENDIF
    IF NATIVE_FUNCTION_PROBE
    call Native_TestCoordinate
    IF NATIVE_FINE_IRQ
    call Native_TestFineClock
    ENDIF
    ENDIF
    IF NATIVE_LOGIC
    ld a,1
    ld (Native_ClockMode),a
    xor a
    ld (Native_Suspended),a
    ENDIF
    ; Match the reference CPU's device_start context, rather than inheriting
    ; BIOS registers. This is a boot contract, not a captured game-state seed.
    ; MAME f34f025 z80.cpp: device_start initializes alternate pairs to zero,
    ; IX/IY to FFFF and the main zero flag. Host I/IM remain host-owned.
    ld hl,0
    push hl
    pop af
    ex af,af'
    exx
    ld bc,0
    ld de,0
    ld hl,0
    exx
    ld bc,0
    ld de,0
    ld hl,$0040
    push hl
    pop af
    ld hl,0
    ld ix,$ffff
    ld iy,$ffff
    jp $0000
Native_ResetFinalize:
    call $3e1d
    ; Rejoin the original clear/entry sequence so its stack residue and
    ; return address have exactly the original values, not host addresses.
    jp $390b
    ENDIF

    IF NATIVE_LOGIC
Native_ReadBC:
    push hl
    ld h,b
    ld l,c
    call Native_ReadHL
    pop hl
    ret
Native_ReadHL:
    push af
    push hl
    ld a,h
    cp $a0
    jr nz,.dip
    ld a,l
    or a
    jr z,.p1
    cp $80
    jr nz,.read
    ld hl,$a201
    jr .read
.p1:
    ld hl,$a200
    jr .read
.dip:
    cp $a1
    jr nz,.read
    ld a,l
    or a
    jr nz,.read
    ld hl,$a202
.read:
    ld a,(hl)
    ld (Native_ReadValue),a
    pop hl
    pop af
    ld a,(Native_ReadValue)
    ret
Native_Transfer:
    ld sp,$8400
    ld (Native_TransferSP),sp
    jp $075d
; Collision leaves the saved original IRQ frame on the stack and continues in
; foreground death logic. It enables future IRQs instead of returning through
; the normal epilogue. Preserve every live register and the abandoned frame.
Native_PublishCollision:
    di
    push af
    push hl
    ld hl,Native_GameTicks
    call Native_Increment32
    xor a
    ld (Native_GameBusy),a
    inc a
    ld (Native_VirtualIFF),a
    inc a
    ld (Native_PublishKind),a
    pop hl
    pop af
    ld (Native_Published),a
    ei
    jp $18c1
Native_CompleteTransfer:
    push af
    push hl
    ld hl,(Native_TransferSP)
    ld a,h
    or l
    jr z,.done
    IF NATIVE_VIDEO
    call Native_PrepareFrame
    ENDIF
    ld hl,Native_GameTicks
    call Native_Increment32
    xor a
    ld (Native_GameBusy),a
    ld h,a
    ld l,a
    ld (Native_TransferSP),hl
    inc a
    ld (Native_PublishKind),a
    ld (Native_TransferPublish),a
    pop hl
    pop af
    ret
.done:
    pop hl
    pop af
    ret
    ENDIF
