; Explicit loader test entry, never original gameplay or an initialization seed.
    OUTPUT "native.rom"
    INCLUDE "native.asm"
Native_Reset:
    ; Unsafe and nested mappings must be rejected without changing ownership.
    xor a
    ld (Native_Suspended),a
    call Native_MapAssets
    ld a,(Native_Error)
    cp $e2
    jp nz,.guard_fail
    ld a,(Native_AssetMapped)
    or a
    jp nz,.guard_fail
    ld a,1
    ld (Native_Suspended),a
    xor a
    ld (Native_Error),a
    call Native_MapAssets
    ld a,1
    call Native_MapAssets
    ld a,(Native_Error)
    cp $e2
    jp nz,.guard_fail
    ld a,(Native_Segments+4)
    ld b,a
    ld a,(Native_Mapped)
    cp b
    jp nz,.guard_fail
    call Native_RestoreGame
    xor a
    ld (Native_Error),a
    ld a,2
    ld (Native_GuardTests),a
    ld hl,256
    ld (Native_Loops),hl
.loop:
    ld a,(Native_AssetIndex)
    ld bc,$1234
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
    ei
    ld (Native_Before),a
    call Native_MapAssets
    halt                   ; Prove a host IRQ can run while an asset is mapped.
    ld (Native_After),a
    call Native_RestoreGame
    ld (Native_Restored),a
    ld a,(Native_AssetIndex)
    inc a
    and 3
    ld (Native_AssetIndex),a
    ld hl,(Native_Loops)
    dec hl
    ld (Native_Loops),hl
    ld a,h
    or l
    jp nz,.loop
.done:
    IF NATIVE_RUNTIME_PROBE
    call Native_TestGameStack
    di
    call Native_TestIncrement
    IF NATIVE_IRQ_PROBE
    call Native_TestScheduler
    ENDIF
    ENDIF
    ld a,2
    ld (Native_Status),a
.idle:
    ei
    halt
    jr .idle
.guard_fail:
    ld a,$e3
    jp Native_Fail
    IF NATIVE_RUNTIME_PROBE
    INCLUDE "native-runtime.inc"
; Prove host IRQ register/stack preservation with the interrupted SP inside
; the game window rather than the loader's normal host stack.
Native_TestGameStack:
    di
    ld (Native_ProbeReturnSP),sp
    ld sp,$8400
    ld bc,$1234
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
Native_TestIRQBefore:
    ld (Native_ProbeBefore),a
    ei
    halt
Native_TestIRQAfter:
    ld (Native_ProbeAfter),a
    di
    ld sp,(Native_ProbeReturnSP)
    xor a
    ld ($83fe),a
    ld ($83ff),a
    ret
; Exhaust every source byte, incoming carry and ROM/RAM target. Results stay
; in host RAM; restore the scratch game window before the loader proof ends.
Native_TestIncrement:
    ld iy,$e000
    ld d,0
.region:
    ld e,0
.carry:
    ld hl,0
    ld a,d
    or a
    jr z,.value
    ld h,$98
.value:
    ld a,h
    or a
    jr z,.seeded
    ld (hl),l
.seeded:
    push de
    push hl
    bit 0,e
    jr z,.clear_carry
    scf
    jr .invoke
.clear_carry:
    or a
.invoke:
    call Native_IncrementRead
    push af
    pop bc
    ld (iy+0),b
    ld (iy+1),c
    ld a,(hl)
    ld (iy+2),a
    ld (iy+3),h
    inc iy
    inc iy
    inc iy
    inc iy
    pop bc
    ld a,b
    cp h
    jr nz,.fail
    ld a,c
    cp l
    jr nz,.fail
    pop de
    inc l
    jr nz,.value
    inc e
    ld a,e
    cp 2
    jr nz,.carry
    inc d
    ld a,d
    cp 2
    jr nz,.region
    ld hl,$9800
    ld de,$9801
    ld bc,255
    ld (hl),0
    ldir
    ret
.fail:
    ld a,$e3
    jp Native_Fail
    ENDIF
    IF NATIVE_IRQ_PROBE
    INCLUDE "native-scheduler.inc"
    INCLUDE "native-irq.inc"
    ENDIF
    ASSERT $ <= $8000
    defs $8000-$,$ff
    INCBIN "native-program.bin"
    INCBIN "native-assets.bin"
    defs $24000-$,$ff
