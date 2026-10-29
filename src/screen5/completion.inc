; Resumable original $1fa9 remaining-fuel bonus. No foreground or HALTs.
Completion_BonusState EQU $c720 ; 0 idle, 1 converting, 2 complete
Completion_Quota EQU $c721
Completion_Phase EQU $c722     ; 1 source HALT, 2 source five-tick wait
Parameters_Seen EQU $c71c
Round_State EQU $c724          ; 0 gameplay, 1 settle, 2 bonus, 3 segment complete

Completion_Begin:
    ld a,1
    ld (Completion_BonusState),a
    ld a,($e020)
    or a
    jp z,Completion_Finish
Completion_Chunk:
    ld hl,($e26a)
    ld a,h
    or l
    jp z,Completion_Finish
    ld a,($e9f4)
    and 3
    or 2
    ld ($e9f4),a
    xor a
    ld ($e269),a
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
    ld (Completion_Quota),a
Completion_Step:
    ld hl,($e26a)
    ld a,h
    or l
    jr z,Completion_Finish
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
    ld (Completion_Phase),a
    ld a,3
    ld (Fuel_Work),a
    ret
Completion_Tick:
    ld a,(Completion_BonusState)
    cp 1
    ret nz
    ld hl,$e269
    inc (hl)
    ld a,(Completion_Phase)
    cp 2
    jr z,.wait
    ld a,($e1b0)
    cp 9
    jr c,.resumed
    cp 13
    call c,Fuel_Ten          ; Source rounds 9..12 award again AFTER HALT.
.resumed:
    ld hl,Completion_Quota
    dec (hl)
    jr nz,Completion_Step
    ld a,2
    ld (Completion_Phase),a
.wait:
    ld a,($e269)
    cp 5
    ret c
    jp Completion_Chunk
Completion_Finish:
    ld a,2
    ld (Completion_BonusState),a
    ld a,3
    ld (Fuel_Work),a
    ret                      ; No lucky fuel restoration or converter cleanup.

    IF COMPLETION_RUNTIME
Parameters_Update:
    ld a,(Fuel_Active)
    or a
    ret nz
    ld a,(Flag_Count)
    ld hl,Parameters_Seen
    cp (hl)
    ret z
    ld (hl),a
    ld a,PLAYER_BANK
    ld ($7000),a
    jp $9b1f                 ; Source dispatch follows the completed flag/lucky award.

Round_Frame:
    ld a,(driving)
    or a
    ret z
    ld a,(paused)
    ld hl,Round_State
    or (hl)
    ret nz
    ld a,(Death_State)
    ld hl,Fuel_Active
    or (hl)
    ld hl,Flag_Jobs
    or (hl)
    ret nz
    ld a,(Flag_Count)
    cp 10
    ret nz
    ld a,(Score_Seen)
    cp 10
    ret nz
    ld a,1
    ld (Round_State),a
    ld a,3
    ld ($e020),a
    ld ($e24b),a
    ld a,($e9f4)
    and $3f
    ld ($e9f4),a
    ld a,$28
    ld ($e9f5),a
    ret
Round_Tick:
    cp 1
    jr nz,.bonus
    ld hl,$e24b
    inc (hl)
    ld a,(hl)
    and 63
    ret nz
    ld a,2
    ld (Round_State),a
    jp Completion_Begin       ; Silent port omits the unimplemented sound-busy wait.
.bonus:
    cp 2
    ret nz
    call Completion_Tick
    ld a,(Completion_BonusState)
    cp 2
    ret nz
    ld a,3
    ld (Round_State),a
    ret                      ; Later rounds are outside the agreed segment.
    ENDIF
