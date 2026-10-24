; Stage 05: selected original ordinal/special-flag points, digit carry, high
; score and bonus-life accounting. Lucky fuel conversion belongs to stage 06.
    IF INCREMENTAL_STAGE >= 5
Score_Seen EQU $c540
    IF FULL_GAME
Score_Digits EQU $d130
Score_HighDigits EQU $d138
    ELSE
Score_Digits EQU $c541
Score_HighDigits EQU $c547
    ENDIF
Score_Work EQU $c54d
Score_HudPairs EQU $c54e
Score_HighValid EQU $c54f
Score_HighShadow EQU $c5a0
Score_Old EQU $c550
Score_OldHigh EQU $c558
Score_Final EQU $c560
Score_Sorted EQU $c568
Score_Wrap EQU $c56e
Score_Index EQU $c56f
Score_Point EQU $c570
Score_Pass EQU $c572
Score_Remainder EQU $c573
Score_Init:
    xor a
    ld (Score_Seen),a
    ld (Score_HighValid),a
    ret
Score_Update:
    xor a
    ld (Score_Work),a
    ld a,(Flag_Count)
    ld hl,Score_Seen
    cp (hl)
    ret z
    ld (hl),a
    push af
    ld a,1
    ld (Score_Work),a
    ld a,PLAYER_BANK
    ld ($7000),a
    pop af
    IF INCREMENTAL_STAGE >= 7
    ld hl,$e250
    inc (hl)                 ; source resets this ordinal at a life restart
    ELSE
    ld ($e250),a             ; original current-life flag ordinal
    ENDIF
    ld ($e271),a             ; original current-stage collected count
    ld a,(Flag_Kind)
    cp 4
    call z,$9e62             ; original lucky request (bit 1), consumed in stage 06
    ld a,(Flag_Kind)
    cp 2
    jr nz,.points
    ld hl,$e023
    inc (hl)                 ; original special-flag multiplier toggle
.points:
    call Score_FastPoints     ; exact hundred-point groups and source boundary checks
    jp Score_Publish

; Run after dirty terrain, with raster interrupts enabled. A collection frame
; spends its remaining guard budget on scoring; pending guard jobs persist.
Score_Frame:
    push bc
    ei
    nop
    call Score_Update
    IF INCREMENTAL_STAGE >= 6
    call Fuel_Begin
Score_AfterFuelBegin:
    call Fuel_Frame
    ENDIF
    IF COMPLETION_RUNTIME
    call Parameters_Update
    ENDIF
Score_AfterUpdate:
    di
    pop bc
    ld a,(Score_Work)
    or a
    ret z
    ld b,0
    ret

    IF (RADAR_CELLS_ONLY && HUD_ENABLED) || (INCREMENTAL_STAGE >= 9 && ENEMY_COUNT >= 2)
; Reserve a collection's score transaction before optional radar/cache work.
; Preserve the established two-tick deferral and one fuel-frame service.
Score_ReservedFrame:
    ld a,(Flag_Count)
    ld hl,Score_Seen
    cp (hl)
    jr z,.execute
    ld a,(paused)
    or a
    jr nz,.execute
    ld a,(Death_State)
    or a
    jr nz,.execute
    ld a,(player_steps)
    cp 2
    ret z
.execute:
    jp Score_Frame
    ENDIF

Score_FastPoints:
    ld hl,$e0a0
    ld de,Score_Old
    ld bc,8
    ldir
    ld hl,$e060
    ld de,Score_OldHigh
    ld bc,8
    ldir
    ld a,($e020)
    or a
    ret z
    ; Ten original +10 operations normalize the tens digit, then increment the
    ; hundreds digit once with the identical original carry routine at $2119.
    ld a,($e250)
    ld b,a
    ld a,($e023)
    and 1
    jr z,.groups
    sla b
.groups:
    call Score_Hundreds
    ld hl,$e0a0
    ld de,Score_Final
    ld bc,8
    ldir
    ld hl,Score_Old
    ld de,$e0a0
    ld bc,8
    ldir
    call $a064               ; source checks before the first point increment
    ld hl,Score_OldHigh
    ld (Score_Sorted),hl
    ld hl,($e1b3)
    ld (Score_Sorted+2),hl
    ld hl,($e1b9)
    ld (Score_Sorted+4),hl
    ; Most awards are below every critical boundary. Check final values first
    ; and avoid sorting/reconstructing packets when none can be reached.
    xor a
    ld (Score_Index),a
    ld hl,Score_Final
    ld de,Score_Old
    call Score_Compare
    jr c,.sort
.quick:
    ld a,(Score_Index)
    add a,a
    ld l,a
    ld h,0
    ld de,Score_Sorted
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ex de,hl
    ld de,Score_Final
    call Score_Compare
    jr c,.maybe
    jr nz,.quick_next
.maybe:
    ld de,Score_Old
    call Score_Compare
    jr c,.quick_next
    jr nz,.sort
.quick_next:
    ld hl,Score_Index
    inc (hl)
    ld a,(hl)
    cp 3
    jr c,.quick
    jp .finish
.sort:
    ld hl,Score_Sorted
    ld de,Score_Sorted+2
    call Score_SortPair
    ld hl,Score_Sorted+2
    ld de,Score_Sorted+4
    call Score_SortPair
    ld hl,Score_Sorted
    ld de,Score_Sorted+2
    call Score_SortPair
    ld hl,Score_Final
    ld de,Score_Old
    call Score_Compare
    ld a,0
    adc a,0
    ld (Score_Wrap),a
    xor a
    ld (Score_Pass),a
.pass:
    xor a
    ld (Score_Index),a
.point:
    ld a,(Score_Index)
    add a,a
    ld l,a
    ld h,0
    ld de,Score_Sorted
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ex de,hl
    ld (Score_Point),hl
    ld a,(Score_Pass)
    or a
    jr nz,.upper
    ld de,Score_Old
    call Score_Compare
    jr c,.next
    jr z,.next
    ld a,(Score_Wrap)
    or a
    jr nz,.apply
.upper:
    ld de,Score_Final
    call Score_Compare
    jr c,.apply
    jr nz,.next
.apply:
    ; Eight-digit overflow in the source rotates the carry into the ones digit.
    ; A post-wrap value ending in 1 cannot hit an old threshold ending in 0.
    ld hl,Score_Old+3
    ld a,(Score_Pass)
    or a
    jr z,.ones
    ld hl,Score_Final+3
.ones:
    ld a,(hl)
    and 15
    ld c,a
    ld hl,(Score_Point)
    inc hl
    inc hl
    inc hl
    ld a,(hl)
    and 15
    cp c
    jr nz,.next
    call Score_ReachPoint
    call $a064               ; exact source high-score and bonus-life side effects
.next:
    ld hl,Score_Index
    inc (hl)
    ld a,(hl)
    cp 3
    jr c,.point
    ld a,(Score_Wrap)
    or a
    jr z,.finish
    ld a,(Score_Pass)
    or a
    jr nz,.finish
    inc a
    ld (Score_Pass),a
    jr .pass
.finish:
    ld hl,Score_Final
    ld de,$e0a0
    ld bc,8
    ldir
    jp $a064

Score_Hundreds:
    ld a,b
    or a
    ret z
    ld a,($e0a2)
    and 15
    ld ($e0a2),a
.group:
    push bc
    ld hl,$e0a1
    call $a119
    pop bc
    djnz .group
    ret

; Reconstruct the exact reachable source packet at a critical boundary. Only
; the low four digits are needed: a flag award spans at most 2,000 points.
Score_ReachPoint:
    ld de,(Score_Point)
    call Score_LowTens
    push hl
    ld de,Score_Old
    call Score_LowTens
    ex de,hl
    pop hl
    or a
    sbc hl,de
    jr nc,.delta
    ld de,1000
    add hl,de
.delta:
    ld a,l
    ld c,0
.divide:
    cp 10
    jr c,.remainder
    sub 10
    inc c
    jr .divide
.remainder:
    ld (Score_Remainder),a
    ld b,c
    push bc
    ld hl,Score_Old
    ld de,$e0a0
    ld bc,8
    ldir
    pop bc
    call Score_Hundreds
    ld a,(Score_Remainder)
    ld b,a
    or a
    ret z
.tens:
    push bc
    call $a10f
    pop bc
    djnz .tens
    ret
Score_LowTens:
    ld a,(de)
    and 15
    ld l,a
    ld h,0
    inc de
    call Score_TimesTen
    ld a,(de)
    and 15
    ld c,a
    ld b,0
    add hl,bc
    inc de
    call Score_TimesTen
    ld a,(de)
    and 15
    ld c,a
    ld b,0
    add hl,bc
    ret
Score_TimesTen:
    ld b,h
    ld c,l
    add hl,hl
    add hl,hl
    add hl,bc
    add hl,hl
    ret

; Sort two pointers in the three-entry boundary list, without changing packets.
Score_SortPair:
    push ix
    push iy
    push hl
    push de
    ld c,(hl)
    inc hl
    ld b,(hl)
    ld a,(de)
    ld l,a
    inc de
    ld a,(de)
    ld h,a
    push bc
    push hl
    pop de
    pop hl
    call Score_Compare
    pop iy
    pop ix
    jr c,.done
    jr z,.done
    ld (ix+0),e
    ld (ix+1),d
    ld (iy+0),l
    ld (iy+1),h
.done:
    pop iy
    pop ix
    ret

; Compare complete eight-digit values in original storage order; preserve inputs.
Score_Compare:
    push hl
    push de
    push bc
    inc l
    inc l
    inc l
    inc l
    inc e
    inc e
    inc e
    inc e
    ld b,4
.upper:
    ld a,(de)
    and 15
    ld c,a
    ld a,(hl)
    and 15
    cp c
    jr nz,.done
    inc hl
    inc de
    djnz .upper
    ld a,l
    sub 8
    ld l,a
    ld a,e
    sub 8
    ld e,a
    ld b,4
.lower:
    ld a,(de)
    and 15
    ld c,a
    ld a,(hl)
    and 15
    cp c
    jr nz,.done
    inc hl
    inc de
    djnz .lower
.done:
    pop bc
    pop de
    pop hl
    ret

Score_Publish:
    IF HUD_ENABLED
    IF SESSION_RUNTIME
    call Radar_AllowIRQ      ; Numeric RAM producers are never consumed by the ISR.
    ENDIF
    ld hl,$e0a0
    ld de,Score_Digits
    call Score_ReadDigits
    ld a,(Score_HighValid)
    or a
    jr z,.high
    ld hl,$e060
    ld de,Score_HighShadow
    ld b,8
.compare_high:
    ld a,(de)
    cp (hl)
    jr nz,.high
    inc hl
    inc de
    djnz .compare_high
    ld a,i
    push af
    IF !SESSION_RUNTIME
    di
    ENDIF
    ld hl,Score_Digits
    call HUD_SetScore
    jr .restore_irq
.high:
    ld hl,$e060
    ld de,Score_HighShadow
    ld bc,8
    ldir
    ld a,1
    ld (Score_HighValid),a
    ld hl,$e060
    ld de,Score_HighDigits
    call Score_ReadDigits
    ld a,i
    push af
    IF !SESSION_RUNTIME
    di
    ENDIF
    ld hl,Score_Digits
    call HUD_SetScore
    ld hl,Score_HighDigits
    call HUD_SetHiscore
.restore_irq:
    pop af
    ret po
    ei
    ret
    ELSE
    ret
    ENDIF
Score_ReadDigits:
    ld a,l
    IF FULL_GAME
    add a,4
    ld l,a
    ld b,4
    ELSE
    add a,6
    ld l,a
    ld b,2
    ENDIF
.upper:
    ld a,(hl)
    and 15
    ld (de),a
    inc de
    inc hl
    djnz .upper
    ld a,l
    sub 8
    ld l,a
    ld b,4
.lower:
    ld a,(hl)
    and 15
    ld (de),a
    inc de
    inc hl
    djnz .lower
    ret
    ENDIF
