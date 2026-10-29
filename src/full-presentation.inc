; Complete 30 Hz presentation packets. Native simulation keeps its own clock.
; Copied into the selected core's unused sound workspace, preserving pointers.
Full_PresentPatterns EQU $0000
Full_PresentSAT EQU $01c0
Full_PresentEC EQU $0200
Full_PresentDirty EQU $0208
Full_PresentPatternIDs EQU $0210
Full_QueueCount EQU $0220
Full_QueueVDP EQU $0222

; Same source/destination progress as Sprite_Upload. Initialization also writes
; directly while the display is hidden; gameplay queues complete unchanged art.
Full_QueueSprite:
    ld a,d
    cp $78
    jr c,.private
    cp $7e
    jr nc,.private
    ld a,(Full_PresentEnabled)
    or a
    jp z,Sprite_Upload       ; Initial common masks precede actor allocation.
.private:
    ld a,(Full_PresentEnabled)
    or a
    jr nz,.queue
    push hl
    push de
    push bc
    call Sprite_Upload
    pop bc
    pop de
    pop hl
.queue:
    ei                       ; Packet copies own no VDP latch or front pattern.
    nop
    call Full_CacheEnter
    ld a,b
    ld (Full_QueueCount),a
    ld (Full_QueueVDP),de
    push hl
    ld a,d
    cp $76
    jr z,.sat
    cp $75
    jr z,.colors
    ld a,(Full_EnemyIndex)
    ld e,a
    ld d,0
    ld hl,Full_PresentDirty
    add hl,de
    ld (hl),1
    ld hl,Full_PresentPatternIDs
    add hl,de
    ld a,(Full_EnemyPattern)
    ld (hl),a
    ld l,e
    ld h,0
    REPT 6
    add hl,hl
    ENDR
    ASSERT Full_PresentPatterns == 0
    ld a,(Full_EnemyPattern)
    REPT 3
    add a,a
    ENDR
    ld d,a
    ld a,(Full_QueueVDP)
    sub d
    and 63
    ld e,a
    ld d,0
    add hl,de
    ex de,hl
    jr .copy
.sat:
    ld a,e
    sub 72
    add a,Full_PresentSAT & 255
    ld e,a
    ld d,Full_PresentSAT/256
.copy:
    pop hl
    ld a,(Full_QueueCount)
    ld c,a
    ld b,0
    ldir
    jr .advance
.colors:
    pop hl
    ; Exact negative-X masks use anchor zero. All destinations retain the
    ; same initialized red/blue OR colors, with no EC color transaction.
    ld a,(Full_QueueCount)
    ld e,a
    ld d,0
    add hl,de
.advance:
    ld de,(Full_QueueVDP)
    ld a,(Full_QueueCount)
    add a,e
    ld e,a
    jr nc,.done
    inc d
.done:
    call Full_CacheLeave
    ei
    nop
    ret

Full_QueueTopMask:
    ld c,a
    ld a,(Full_EnemyPattern)
    call .plane
    ld a,(Full_EnemyWindowPattern)
.plane:
    ld d,a
    REPT 3
    add a,a
    ENDR
    add a,c
    ld e,a
    ld a,d
    REPT 5
    rrca
    ENDR
    and 7
    or $78
    ld d,a
    ld b,2
.row:
    push bc
    ld hl,.zero
    ld b,1
    call Full_QueueSprite
    pop bc
    ld a,e
    add a,15
    ld e,a
    jr nc,.next
    inc d
.next:
    djnz .row
    ret
.zero:
    db 0

; VBlank-only transaction. Publish no sooner than two refreshes, after the entire
; packet is prepared. The ISR owns all ports; no bank switch is required.
Full_PresentCommit:
    ld a,(Radar_Ready)
    ld b,a
    ld a,(Radar_Ready+1)
    or b
    ld b,a
    ld a,(Full_PresentReady)
    or b
    ret z
    push hl
    push de
    push ix
    push iy
    ; A VBlank can interrupt a foreground overlay even when CacheHeld=0.
    ; Preserve the actual mapping, rather than restoring the BIOS underneath
    ; the interrupted Page0 instruction stream.
    in a,($a8)
    push af
    in a,($fc)
    push af
    ld a,($ffff)
    cpl
    push af
    call Full_CacheEnter
    ld a,(Full_TurboEnabled)
    or a
    jr z,.io_ready
    xor a
    out ($41),a              ; OTIR remains slower than the VDP access interval.
.io_ready:
    call Full_RadarVBlank
    ld a,(Full_PresentReady)
    or a
    jp z,.finish
    ld a,(Full_PresentClockValid)
    or a
    jr z,.first
    ld a,(Full_PresentLastTick)
    ld b,a
    ld a,(ticks)
    sub b
    cp 2
    jp c,.finish             ; A late packet may shift phase, never exceed 30 Hz.
    jr .ready
.first:
    ld a,(ticks)
    and 1
    jp z,.finish
.ready:
.clock_ready:
    ld ix,Full_PresentDirty
    ld iy,Full_PresentPatterns
    ld e,7
.pattern:
    ld a,(ix+0)
    or a
    jr z,.next_pattern
    vdp_write 14,7
    ld a,(ix+8)
    cp 16
    jr z,.split_pattern
    ld d,a
    REPT 3
    add a,a
    ENDR
    out ($99),a
    ld a,d
    REPT 5
    rrca
    ENDR
    and 7
    or $78
    out ($99),a
    push iy
    pop hl
    ld bc,$4098
.pattern_bytes:
    REPT 8
    outi
    ENDR
    jp nz,.pattern_bytes
    jr .pattern_done
.split_pattern:
    push de
    ld a,$80
    out ($99),a
    ld a,$78
    out ($99),a
    push iy
    pop hl
    ld bc,$2098
    otir
    ld a,$e0
    out ($99),a
    ld a,$7d
    out ($99),a
    ld bc,$2098
    otir
    pop de
.pattern_done:
.next_pattern:
    ld bc,64
    add iy,bc
    inc ix
    dec e
    jr nz,.pattern
.sat:
    vdp_write 14,7
    ld a,72
    out ($99),a
    ld a,$76
    out ($99),a
    ld a,(Full_PresentLength)
    dec a
    or a
    jr z,.end_marker
    ld b,a
    ld c,$98
    ld hl,Full_PresentSAT
.attributes:
    REPT 8
    outi
    ENDR
    jp nz,.attributes
.end_marker:
    ld a,216
    out ($98),a
    call Full_CommitCamera
    xor a
    ld (Full_PresentReady),a
    ld a,(ticks)
    ld (Full_PresentLastTick),a
    ld a,1
    ld (Full_PresentClockValid),a
.finish:
    ld a,(Full_TurboEnabled)
    or a
    jr z,.restore
    ld a,1
    out ($41),a
.restore:
    pop af
    ld b,a
    ld a,(Full_CacheExpanded)
    or a
    jr z,.primary_restore
    ld a,b
    ld ($ffff),a
.primary_restore:
    pop af
    out ($fc),a
    pop af
    out ($a8),a
    pop iy
    pop ix
    pop de
    pop hl
    ret
