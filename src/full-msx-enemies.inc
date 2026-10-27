; MSX-native enemy decisions. Kinematics, stun animation, smoke lifetime,
; parameters and phase clocks remain in the original selected core.
; No arcade virtual OAM maintenance or repeated mid-corridor wall probes.
Full_MSXDecision EQU Full_AITable0 ; seven last-decision X/Y pairs
Full_MSXHeading EQU Full_AIBefore
Full_MSXExits EQU Full_AIBefore+1
Full_MSXDX EQU Full_AIBefore+2
Full_MSXDY EQU Full_AIBefore+3
Full_MSXSpeed EQU Full_AIBefore+4
Full_MSXIndex EQU Full_AITick
Full_MSXNavigation EQU $3000
Full_MSXPlayerMaxSpeed EQU 512  ; Two pixels per native tick, four per packet.
Full_MSXEnemyMaxSpeed EQU 480   ; 1.875 pixels, with the original lower speeds.
Full_MSXEnemyMotionDivisor EQU 2

; Keep player terrain bandwidth bounded without changing fractional motion.
Full_MSXPlayerSpeed:
    ld hl,($e069)
    ld de,Full_MSXPlayerMaxSpeed
    call Full_MSXBoundVelocity
    ld ($e069),hl
    ret

; HL=signed velocity, DE=positive cap. Preserve BC and return bounded HL.
Full_MSXBoundVelocity:
    push bc
    push hl
    ld c,h
    bit 7,h
    jr z,.magnitude
    xor a
    sub l
    ld l,a
    sbc a,a
    sub h
    ld h,a
.magnitude:
    or a
    sbc hl,de
    jr c,.original
    jr z,.original
    pop hl
    ex de,hl
    bit 7,c
    jr z,.done
    xor a
    sub l
    ld l,a
    sbc a,a
    sub h
    ld h,a
.done:
    pop bc
    ret
.original:
    pop hl
    pop bc
    ret

Full_MSXAI:
    ld a,(player_native_ticks)
    and 1
    jr nz,.clock_only
    call Full_CacheEnter
    ld hl,($e025)
    ld de,($e029)
    ld a,h
    or l
    or d
    or e
    ld a,0
    jr nz,.moving_cohort
    ld a,32                  ; Exit masks use only bits0..3; bit5 parks the cohort.
.moving_cohort:
    ld (Full_MSXExits),a
    xor a
    ld (Full_MSXIndex),a
    ld ix,$e088
    ld a,($e24e)
    ld b,a
    or a
    jr z,.done
.actor:
    push bc
    call Full_MSXActor
    pop bc
    ld de,32
    add ix,de
    ld hl,Full_MSXIndex
    inc (hl)
    djnz .actor
.done:
    call Full_CacheLeave
.clock_only:
    ld hl,$e022
    inc (hl)                ; Keep the original AI-side animation clock contribution.
    ld iy,$e068
    ret

Full_MSXDecisionAddress:
    ld a,(Full_MSXIndex)
    add a,a
    add a,Full_MSXDecision & 255
    ld l,a
    ld h,Full_MSXDecision/256
    ret
Full_MSXInvalidate:
    call Full_MSXDecisionAddress
    ld (hl),255
    ret

Full_MSXActor:
    ld a,(ix+8)
    cp 32
    ret nc
    ld a,(ix+10)
    cp 56
    ret nc                  ; Parked descriptors do not consume navigation work.
    ld a,(ix+0)
    or a
    jp nz,Full_MSXInvalidate ; Original motion owns startup and spin recovery.
    ld a,(ix+19)
    or a
    jr z,.smoke
    dec (ix+19)             ; Immunity counts native ticks, independently of decisions.
    jr z,.heading
    dec (ix+19)             ; Enemy logic owns two native ticks on this pass.
    jr .heading
.smoke:
    ld a,(Smoke_Valid)
    or a
    jr z,.heading
    call Full_MSXSmoke
    sub $bd
    cp 9
    jr nc,.heading
    ld (ix+0),$88
    ld (ix+21),1
    ld (ix+19),$82
    jp Full_MSXInvalidate
.heading:
    ld a,(Full_MSXExits)
    bit 5,a
    jr z,.coasting
    xor a
    ld (ix+1),a
    ld (ix+2),a
    ret
.coasting:
    ld a,(ix+1)
    or (ix+2)
    jr z,.select_speed       ; A stationary challenge car activates immediately.
    ld a,(ix+5)
    add a,5
    cp 11
    ret nc
    ld a,(ix+7)
    add a,5
    cp 11
    ret nc                   ; Retain the current speed through the corridor.
.select_speed:
    ld c,0
    ld a,(ix+2)
    bit 7,a
    jr z,.axis
    ld c,2
.axis:
    ld a,(ix+3)
    or a
    jr z,.heading_ready
    inc c
.heading_ready:
    ld a,c
    ld (Full_MSXHeading),a
    ld a,($e070)
    sub (ix+8)
    ld (Full_MSXDX),a
    bit 7,a
    jr z,.abs_x
    neg
.abs_x:
    ld c,a
    ld a,($e072)
    sub (ix+10)
    ld (Full_MSXDY),a
    bit 7,a
    jr z,.abs_y
    neg
.abs_y:
    cp 7
    ld hl,($e029)
    jr nc,.speed
    ld a,c
    cp 7
    jr nc,.speed
    ld hl,($e025)
.speed:
    ld a,h
    cp Full_MSXEnemyMaxSpeed/256
    jr c,.speed_ready
    jr nz,.limit_speed
    ld a,l
    cp Full_MSXEnemyMaxSpeed & 255
    jr c,.speed_ready
.limit_speed:
    ld hl,Full_MSXEnemyMaxSpeed
.speed_ready:
    ld (Full_MSXSpeed),hl
    ld a,h
    or l
    jp z,.apply             ; Stationary challenge cars need no route calculation.
    ld a,(ix+5)
    add a,5
    cp 11
    jp nc,.apply
    ld a,(ix+7)
    add a,5
    cp 11
    jp nc,.apply
    call Full_MSXDecisionAddress
    ld a,(ix+8)
    cp (hl)
    jr nz,.new_cell
    inc l
    ld a,(ix+10)
    cp (hl)
    jp z,.apply
    dec l
.new_cell:
    ld a,(ix+8)
    ld (hl),a
    inc l
    ld a,(ix+10)
    ld (hl),a
    ; Current-cell exits are copied once per scene into spare mapper RAM.
    ld a,(ix+10)
    ld c,a
    rrca
    rrca
    rrca
    and 7
    add a,Full_MSXNavigation/256
    ld h,a
    ld a,c
    and 7
    rrca
    rrca
    rrca
    or (ix+8)
    ld l,a
    ld a,(hl)
    or a
    jr nz,.roads
    ld hl,0
    ld (Full_MSXSpeed),hl
    jr .apply
.roads:
    ld b,a
    ld a,(Full_MSXHeading)
    xor 2
    ld e,a
    ld d,0
    ld hl,Full_MSXDirectionBits
    add hl,de
    ld a,(hl)
    cpl
    and b
    jr nz,.allowed
    ld a,b                  ; Only a dead end permits an immediate reversal.
.allowed:
    ld (Full_MSXExits),a
    ld a,(Full_MSXDX)
    bit 7,a
    jr z,.distance_x
    neg
.distance_x:
    ld c,a
    ld a,(Full_MSXDY)
    bit 7,a
    jr z,.distance_y
    neg
.distance_y:
    cp c
    ld c,0
    jr c,.horizontal_first
    jr nz,.priority
.horizontal_first:
    inc c
.priority:
    ld a,(Full_MSXIndex)
    and 1
    xor c
    or a
    jr z,.vertical_first
    call .horizontal
    jr c,.chosen
    call .vertical
    jr c,.chosen
    jr .forward
.vertical_first:
    call .vertical
    jr c,.chosen
    call .horizontal
    jr c,.chosen
.forward:
    ld a,(Full_MSXHeading)
    call Full_MSXTryDirection
    jr c,.chosen
    xor a
.fallback:
    call Full_MSXTryDirection
    jr c,.chosen
    inc a
    jr .fallback            ; Nonempty exits guarantee one of these four choices.
.chosen:
    ld (Full_MSXHeading),a
.apply:
    ld hl,(Full_MSXSpeed)
    ld a,(Full_MSXHeading)
    cp 2
    jr c,.positive
    xor a
    sub l
    ld l,a
    sbc a,a
    sub h
    ld h,a
.positive:
    ld (ix+1),l
    ld (ix+2),h
    ld a,(Full_MSXHeading)
    and 1
    neg
    ld (ix+3),a
    ret
.horizontal:
    ld a,(Full_MSXDX)
    bit 7,a
    ld a,1
    jr z,.try
    ld a,3
    jr .try
.vertical:
    ld a,(Full_MSXDY)
    bit 7,a
    ld a,2
    jr z,.try
    xor a
.try:
    jp Full_MSXTryDirection

Full_MSXTryDirection:
    ld c,a
    ld e,a
    ld d,0
    ld hl,Full_MSXDirectionBits
    add hl,de
    ld a,(Full_MSXExits)
    and (hl)
    ld a,c
    ret z
    scf
    ret
Full_MSXDirectionBits:
    db 1,2,4,8

Full_MSXSmoke:
    ; Probe the native smoke ring directly from world cells/fine coordinates.
    ld a,(ix+5)
    add a,3
    sra a
    sra a
    sra a
    add a,4
    ld c,a
    ld a,(ix+8)
    ld b,a
    add a,a
    add a,b
    add a,c
    ld b,a
    ld a,(ix+7)
    neg
    add a,4
    sra a
    sra a
    sra a
    add a,4
    ld d,a
    ld a,(ix+10)
    ld c,a
    add a,a
    add a,c
    add a,d
    ld c,a
    jp Smoke_CodeAtBC

Full_MSXContact:
    ld ix,$e088
    ld a,($e24e)
    ld b,a
    or a
    ret z
.actor:
    ld a,(ix+8)
    ld hl,$e070
    sub (hl)
    add a,2
    cp 5                     ; Opposite fine offsets can bridge two coarse cells.
    jr nc,.next
    sub 2
    ld d,a
    add a,a
    add a,d
    add a,a
    add a,a
    add a,a
    ld d,a
    ld c,10
    ld e,21
    ld a,(ix+0)
    cp $89
    jr c,.bounds
    ld a,($e1b0)
    and 3
    jr z,.bounds             ; Challenge parked cars retain the established bound.
    ld c,14                  ; Normal startup silhouettes must not overlap freely.
    ld e,29
.bounds:
    ld a,(ix+5)
    add a,d
    ld hl,$e06d
    sub (hl)
    add a,c
    cp e
    jr nc,.next
    ld a,(ix+10)
    ld hl,$e072
    sub (hl)
    add a,2
    cp 5
    jr nc,.next
    sub 2
    ld d,a
    add a,a
    add a,d
    add a,a
    add a,a
    add a,a
    ld d,a
    ld a,(ix+7)
    ld hl,$e06f
    sub (hl)
    sub d
    add a,c
    cp e
    jr nc,.next
    push ix
    pop hl
    ld de,14
    add hl,de
    ld (Enemy_HitAddress),hl
    ld a,1
    ld (Enemy_Contact),a
    ret
.next:
    ld de,32
    add ix,de
    djnz .actor
    ret

Full_MSXPan:
    ; Keep only the player's arcade camera coordinates. Enemy presentation,
    ; contact and smoke no longer read arcade screen-coordinate/OAM fields.
    ld d,a
    ld e,0
    inc hl
    bit 7,a
    jr z,.low
    dec hl
    inc (hl)
    inc hl
.low:
    add a,(hl)
    ld (hl),a
    jr nc,.done
    dec hl
    inc (hl)
    inc hl
.done:
    ld a,d
    ret

Full_MSXAnimation:
    ld ix,$e068
    ld a,($e24e)
    inc a
    ld b,a
    ld hl,$a53a
    jp $9de8
