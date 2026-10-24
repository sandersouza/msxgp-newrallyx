; Exhaustive differential microprobe. The reference bytes come exclusively
; from the locally validated contributor program, never from a checked-in copy.
Native_CoordinateReference:
    INCBIN "native-source.bin",$18b1,16

Native_TestCoordinate:
    xor a
    ld (Native_FunctionCarry),a
Native_FunctionNext:
    ld hl,(Native_FunctionIndex)
    ld a,(Native_FunctionCarry)
    rrca
    ld a,h
    ld h,$9a
    ld bc,$3cc3
    ld de,$a55a
Native_FunctionReferenceCall:
    call Native_CoordinateReference
Native_FunctionReferenceDone:
    ld (Native_FunctionHL),hl
    push af
    pop hl
    ld (Native_FunctionAF),hl
    ld hl,(Native_FunctionIndex)
    ld a,(Native_FunctionCarry)
    rrca
    ld a,h
    ld h,$9a
    ld bc,$3cc3
    ld de,$a55a
Native_FunctionOptimizedCall:
    call $18b1
Native_FunctionOptimizedDone:
    push af
    push hl
    ld a,b
    cp $3c
    jp nz,.failed
    ld a,c
    cp $c3
    jp nz,.failed
    ld a,d
    cp $a5
    jp nz,.failed
    ld a,e
    cp $5a
    jp nz,.failed
    ld de,(Native_FunctionHL)
    or a
    sbc hl,de
    jp nz,.failed
    pop hl
    pop af
    push af
    pop hl
    ld de,(Native_FunctionAF)
    or a
    sbc hl,de
    jp nz,.failed
    ld hl,Native_FunctionCases
    call Native_Increment32
    ld hl,(Native_FunctionIndex)
    inc hl
    ld (Native_FunctionIndex),hl
    ld a,h
    or l
    jr nz,Native_FunctionNext
    ld a,(Native_FunctionCarry)
    inc a
    ld (Native_FunctionCarry),a
    cp 2
    jr nz,Native_FunctionNext
    ld a,1
    ld (Native_FunctionDone),a
    ret
.failed:
    ld a,$e5
    jp Native_Fail
