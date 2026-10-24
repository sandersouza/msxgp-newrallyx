Full_EnemyFarNative:
    ld hl,(Full_EnemyAction)
    ld de,Full_EnemyFrameOne
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
    call Full_TurboOn
    call FullEnemy_WorldOne
    ld (ix+0),0
    call FullEnemy_RadarOne
    call Full_TurboOff
    jp Full_EnemyInactive.hide_only
