Full_EnemyFarNative:
    ld hl,(Full_EnemyAction)
    ld de,Full_EnemyPrepareRadar
    or a
    sbc hl,de
    jr z,.frame
    or a
    ret
.frame:
    ld a,(Full_RegisteredCurrent)
    or a
    jr z,.far               ; Unregistered cars still retain their exact radar anchors.
    ld hl,(Full_EnemySource)
    ld de,8
    add hl,de
    ld a,($e070)
    sub (hl)
    add a,7
    cp 15
    jr nc,.far
    inc hl
    inc hl
    ld a,($e072)
    sub (hl)
    add a,6
    cp 13
    jr nc,.far
    or a
    ret
.far:
    ld a,(Full_PresentEnabled)
    or a
    jr z,.update
    ld hl,(Radar_Cleanup)
    ld de,(Radar_Urgent)
    ld a,h
    or l
    or d
    or e
    jr nz,.hide              ; Radar consumer is still publishing its prior snapshot.
    ld hl,(Full_EnemySource)
    ld de,8
    add hl,de
    ld a,(hl)
    cp 32
    jr nc,.update
    inc hl
    inc hl
    ld a,(hl)
    cp 56
    jr nc,.update
    ld a,(ix+31)
    cp 2
    jr nz,.update
    call .clock_address
    ld a,(ticks)
    sub (hl)
    cp 6
    jr c,.hide              ; Offscreen anchors sample at 10 Hz; world simulation is unchanged.
.update:
    call FullEnemyWorldNative
    call FullEnemyRadarNative
    ld a,(iy+0)
    or a
    jr nz,.hide
    ld a,(iy+1)
    or (iy+2)
    jr z,.hide
    call .clock_address
    ld a,(ticks)
    ld (hl),a
    ld (ix+31),2
.hide:
    ld (ix+0),0
    jp Full_EnemyInactive.hide_only
.clock_address:
    ld a,(Full_EnemyIndex)
    add a,a
    add a,a
    add a,Full_EnemyWorldKeys & 255
    ld l,a
    ld h,Full_EnemyWorldKeys/256
    ret
