; Stage 06. Original decimal consumption/gauge and empty-speed routines, plus
; a bounded replacement for the source converter's HALTs and busy waits.
    IF INCREMENTAL_STAGE >= 6
Fuel_Active EQU $c5b0
Fuel_Quota EQU $c5b1
Fuel_Phase EQU $c5b2
Fuel_Saved EQU $c5b3
Fuel_Mode EQU $c5b5
Fuel_Work EQU $c5b6
Fuel_SpeedClock EQU $c5b7
Fuel_ConsumeWork EQU $c5b8
Fuel_HudWork EQU $c5b9

Fuel_Init:
    xor a
    ld hl,Fuel_Active
    ld de,Fuel_Active+1
    ld bc,9
    ld (hl),a
    ldir
    ld ($e269),a            ; explicit fresh active clock, no boot/IRQ loop
    ret

Fuel_Tick:
    ld a,(Fuel_Active)
    or a
    jr nz,.bonus
    call $9ecc              ; original consume-before-clock-increment order
    ld a,($e269)
    or a
    jr nz,.clock
    ld a,1
    ld (Fuel_ConsumeWork),a
.clock:
    ld hl,$e269
    inc (hl)
    ld hl,Fuel_SpeedClock
    inc (hl)
    ld a,(hl)
    and 63
    call z,$8482            ; original empty deceleration, once per 64 ticks
    ld a,(Fuel_Work)
    or 1
    ld (Fuel_Work),a
    ret
.bonus:
    ld hl,$e269
    inc (hl)
    ld a,(Fuel_Phase)
    cp 2
    jr z,.wait
    ; The round 9..12 converter awards its second ten AFTER the HALT.
    ld a,($e1b0)
    cp 9
    jr c,.resumed
    cp 13
    call c,Fuel_Ten
.resumed:
    ld hl,Fuel_Quota
    dec (hl)
    jr nz,Fuel_Step
    ld a,2
    ld (Fuel_Phase),a
.wait:
    ld a,($e269)
    cp 5
    ret c
    jr Fuel_Chunk

Fuel_Begin:
    ld a,($e023)
    bit 1,a
    ret z
    res 1,a
    ld ($e023),a
    ld a,($e271)
    cp 10
    ret z                  ; source: lucky collected last has no conversion
    ld a,($e020)
    or a
    ret z
    ld (Fuel_Mode),a
    ld a,3
    ld ($e020),a
    ld (Fuel_Active),a
    ld hl,($e26a)
    ld (Fuel_Saved),hl
Fuel_Chunk:
    ld hl,($e26a)
    ld a,h
    or l
    jr z,Fuel_Finish
    xor a
    ld ($e269),a
    ld a,($e9f4)
    and 3
    or 2
    ld ($e9f4),a
    ld b,3
    ld a,($e1b0)
    cp 5
    jr c,.quota
    cp 9
    jr c,.five
    cp 13
    jr c,.quota
.five:
    ld b,5
.quota:
    ld a,b
    ld (Fuel_Quota),a
Fuel_Step:
    ld hl,($e26a)
    ld a,h
    or l
    jr z,Fuel_Finish
    ld a,($e1b0)
    cp 13
    jr nc,.late
    call $9f13
    call $9f13
    ld a,($e1b0)
    cp 5
    jr c,.third
    cp 9
    jr c,.award
.third:
    call $9f13
.award:
    call Fuel_Ten
    jr .yield
.late:
    call $9f13
    call Fuel_Ten
    call $9f13
    call Fuel_Ten
.yield:
    ld a,1
    ld (Fuel_Phase),a
    ld a,3
    ld (Fuel_Work),a
    ret
Fuel_Ten:
    call $a10f
    jp $a064
Fuel_Finish:
    ; Source INC fraction then decrement regenerates the gauge, with the
    ; saved amount unchanged (including a saved fractional digit of nine).
    ld hl,(Fuel_Saved)
    inc l
    ld ($e26a),hl
    call $9f13
    xor a
    ld ($e289),a
    ld ($e292),a
    ld ($e28a),a
    ld (Fuel_Active),a
    ld a,(Fuel_Mode)
    ld ($e020),a
    ld a,3
    ld (Fuel_Work),a
    ret

Fuel_Publish:
    IF HUD_ENABLED
    ld a,($e26b)
    jp HUD_SetFuel
    ELSE
    ret
    ENDIF
Fuel_Frame:
    ld a,(Fuel_Work)
    or a
    ret z
    push af
    call Fuel_Publish
    pop af
    push af
    bit 1,a
    call nz,Score_Publish
    xor a
    ld (Fuel_Work),a
    pop af
    bit 1,a
    ret z
    ld a,1
    ld (Score_Work),a       ; retain remaining guard jobs on a bonus frame
    ret
    ENDIF
