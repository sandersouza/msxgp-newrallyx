; Stage 08: selected original enemy initialization, AI, virtual sprite slots
; and contact comparison. The MSX presentation adapter is a separate phase.
    IF ENEMY_COUNT
Enemy_Contact EQU $c5d0
Enemy_Drawn EQU $c5d1
Enemy_Visible EQU $c5d2
Enemy_Init:
    xor a
    ld (Enemy_Contact),a
    IF !FULL_GAME
    ld (Enemy_Visible),a
    ENDIF
    IF FULL_GAME
    ld ($e3f1),a
    ld ($e3f8),a
    ld hl,Full_MSXDecision
    ld de,Full_MSXDecision+1
    ld bc,13
    ld (hl),255
    ldir
    ENDIF
    dec a
    ld (Enemy_Drawn),a
    IF !FULL_GAME
    ld a,ENEMY_COUNT
    ld ($e24e),a
    ENDIF
    ld hl,$2d0a
    ld ($e052),hl
    ld hl,0
    ld ($e054),hl
    call $8ab5              ; original eight descriptors and six virtual slots
    IF !FULL_GAME
    call $95bd              ; original initial visible-slot registration
    ENDIF
Enemy_InitDone:
    ret
Enemy_PreMove:
    IF FULL_GAME
    ret                     ; MSX presentation/contact do not consume arcade OAM.
    ELSE
    ld ix,$e814
    ld hl,$e015
    ld iy,$e002
    ld b,6
    jp $822b                ; original RAM-only OAM cleanup, return before IRQ
    ENDIF
Enemy_AfterMove:
    xor a
    ld (Enemy_Contact),a
    IF FULL_GAME
    call $b603              ; World-space contact, including all active enemies.
    ELSE
    ld ix,$e068
    ld iy,$e004
    ld b,5
    call $838a              ; original strict +/-10 pixel contact on both axes
    ENDIF
    ld a,(Enemy_Contact)
    or a
    IF FULL_GAME
    call z,$b600            ; MSX decisions at cell centres; continuous native motion.
    ELSE
    call z,$8cd6            ; source AI does not run after a collision transfer
    ENDIF
Enemy_CameraOnly:
    ld a,($e050)
    add a,7
    cp 15
    call nc,$91bf           ; retain camera cells/fine phase, omit bitmap redraw
    ld a,($e051)
    add a,7
    cp 15
    call nc,$9207
    IF !FULL_GAME
    call $95bd              ; six original virtual sprite entries, not MSX SAT
    ENDIF
Enemy_AfterMoveDone:
    ret

    IF ENEMY_RENDER
; Presentation snapshots precede the early native tick. Never draw from the
; subsequently advanced descriptor. Two planes preserve all original pixels.
Enemy_Flag EQU $c5d3
Enemy_WorldX EQU $c5d4
Enemy_WorldY EQU $c5d6
Enemy_DrawX EQU $c5d8
Enemy_DrawY EQU $c5da
Enemy_Clip EQU $c5dc
Enemy_EC EQU $c5dd
Enemy_SatY EQU $c5de
Enemy_Work EQU $c5df
Enemy_Cache EQU $c5e0
Enemy_CacheClip EQU $c5e1
Enemy_Body EQU $c5e2
Enemy_Window EQU $c5e3
Enemy_LastEC EQU $c5e4
Enemy_Index EQU $c5e5
    IF FULL_GAME
Enemy_TopRow EQU $c5e6
Enemy_CacheTop EQU $c5e7
Enemy_SAT EQU $c5e8          ; Codegen field names only; FULL_GAME uses IX records.
    ELSE
Enemy_RadarWork EQU $c5e6
Enemy_GuardClosed EQU $c5e8
Enemy_RadarSource EQU $c5ea
Enemy_TopRow EQU $c5ec
Enemy_CacheTop EQU $c5ed
Enemy_SAT EQU $c600
    ENDIF
Enemy_Masks EQU $c620

; Eleven normal frames occupy otherwise unused pattern groups. The final group
; is a victim cache for frame 11 and horizontally clipped variants.
Enemy_InitPatterns:
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld ix,Enemy_Patterns
    ld hl,$8000
    ld d,11
.next:
    ld a,(ix)
    inc ix
    ld b,32
    call Enemy_Upload
    ld a,(ix)
    inc ix
    ld b,32
    call Enemy_Upload
    ld bc,64
    add hl,bc
    dec d
    jr nz,.next
    xor a
    ld (Enemy_CacheClip),a
    ld (Enemy_LastEC),a
    ld a,10
    ld (Enemy_Cache),a
    ld a,255
    ld (Enemy_CacheTop),a
    ret
; A=16x16 pattern number, B=32/64 bytes. Preserve DE/IX, advance HL.
Enemy_Upload:
    push de
    ld e,a
    ld d,0
    sla e
    rl d
    sla e
    rl d
    sla e
    rl d
    IF INCREMENTAL_STAGE >= 9
    ld a,d
    or $78
    ld d,a
    call Sprite_Upload
    pop de
    ret
    ENDIF
    vdp_write 14,7
    ld a,e
    out ($99),a
    ld a,d
    or $78
    out ($99),a
    ld c,$98
    otir
    pop de
    ret

Enemy_Prepare:
    IF INCREMENTAL_STAGE >= 9
    ei                      ; Death_Stream also invokes this RAM-only producer.
    nop
    ENDIF
    xor a
    ld (Enemy_Visible),a
    ld (Enemy_Work),a
    ld a,($e090)
    ld hl,$e08d
    call Player_Axis
    ld (Enemy_WorldX),hl
    ld de,(player_x)
    or a
    sbc hl,de
    ld de,PLAYER_X
    add hl,de
    ld (Enemy_DrawX),hl
    ld a,($e092)
    ld hl,$e08f
    call Player_AxisY
    ld (Enemy_WorldY),hl
    ld de,(player_y)
    or a
    sbc hl,de
    ld de,108
    add hl,de
    ld (Enemy_DrawY),hl
    ld a,($e097)
    ld (Enemy_Flag),a
    IF ENEMY_CONTACT
    ld a,(Death_State)
    or a
    jr z,.alive
    ld a,(Enemy_Contact)
    or a
    ret nz                    ; source hides the colliding car during the hold
.alive:
    ENDIF
    ld hl,$e004
    ld b,5
.registered:
    ld a,(hl)
    inc hl
    cp $93
    jr nz,.other
    ld a,(hl)
    cp $e0
    jr z,.bounds
.other:
    inc hl
    djnz .registered
    ret
.bounds:
    ld hl,(Enemy_DrawY)
    ld a,h
    or a
    jr z,.positive_y
    inc a
    ret nz
    ld a,l
    cp 252
    ret c
    jr .x_bounds
.positive_y:
    ld de,212
    or a
    sbc hl,de
    ret nc
    ld hl,(Enemy_DrawY)
    ld a,l
    add a,15
    cp BODY_TOP
    ret c
.x_bounds:
    ld hl,(Enemy_DrawX)
    ld a,h
    or a
    jr z,.positive
    inc a
    ret nz
    ld a,l
    cp 249                    ; x=-7 is the first partially visible anchor
    ret c
.positive:
    xor a
    ld (Enemy_Clip),a
    ld (Enemy_EC),a
    ld a,l
    bit 7,h
    jr nz,.left
    cp 8
    jr nc,.phase
.left:
    ld a,8
    sub l
    ld (Enemy_Clip),a
    bit 7,h
    jr z,.phase
    ld a,$80
    ld (Enemy_EC),a
.phase:
    ld a,(Enemy_DrawY)
    ld hl,scroll_y
    add a,(hl)
    dec a
    cp 216
    jr nz,.safe
    dec a                     ; declared one-pixel bias at forbidden SAT Y=216
    ld hl,(Enemy_DrawY)
    dec hl
    ld (Enemy_DrawY),hl
.safe:
    ld (Enemy_SatY),a
    ld a,(Enemy_DrawY)
    neg
    add a,11
    cp 16
    jr c,.top_row
    ld a,255
.top_row:
    ld (Enemy_TopRow),a
    ld a,(Enemy_Flag)
    ld l,a
    ld h,0
    ld de,player_flags
    add hl,de
    ld a,(hl)
    cp 12
    ret nc
    ld (Enemy_Index),a
    ld b,a
    ld a,(Enemy_TopRow)
    cp 255
    jr nz,.dynamic
    ld a,(Enemy_Clip)
    or a
    jr nz,.dynamic
    ld a,b
    cp 10
    jr nc,.dynamic
    add a,a
    ld l,a
    ld h,0
    ld de,Enemy_Patterns
    add hl,de
    ld a,(hl)
    ld (Enemy_Body),a
    inc hl
    ld a,(hl)
    ld (Enemy_Window),a
    jr .visible
.dynamic:
    ld a,248
    ld (Enemy_Body),a
    ld a,252
    ld (Enemy_Window),a
    ld a,(Enemy_Cache)
    cp b
    jr nz,.upload
    ld a,(Enemy_Clip)
    ld hl,Enemy_CacheClip
    cp (hl)
    jr nz,.upload
    ld a,(Enemy_TopRow)
    ld hl,Enemy_CacheTop
    cp (hl)
    jr z,.visible
.upload:
    ld a,1
    ld (Enemy_Work),a
.visible:
    ld a,1
    ld (Enemy_Visible),a
    ret

Enemy_Radar:
    ld hl,(Enemy_WorldX)
    call stage_div8
    ld de,102
    or a
    sbc hl,de
    jr nc,.hidden
    add hl,de
    ld de,player_radar_x
    add hl,de
    ld b,(hl)
    ld hl,(Enemy_WorldY)
    call stage_div8
    ld de,174
    or a
    sbc hl,de
    jr nc,.hidden
    add hl,de
    ld de,player_radar_y
    add hl,de
    ld c,(hl)
    jp HUD_SetEnemy
.hidden:
    ld bc,$ffff
    jp HUD_SetEnemy

Enemy_Draw:
    ld a,(driving)
    or a
    ret z
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    ENDIF
    ld a,(Enemy_Visible)
    or a
    jp z,.hidden
    ld a,(Enemy_Work)
    or a
    jp z,.colors
    ld a,(Enemy_Index)
    ld (Enemy_Cache),a
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$8000
    add hl,de
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld a,(Enemy_Clip)
    ld (Enemy_CacheClip),a
    or a
    jp z,.upload
    ; Exact masks are generated into one ROM bank: frame*1024+clip*64.
    ; Avoid computing pixels while the header interrupt is masked.
    and 3
    rrca
    rrca
    ld l,a
    ld a,(Enemy_Clip)
    srl a
    srl a
    ld h,a
    ld a,(Enemy_Index)
    add a,a
    add a,a
    add a,h
    or $80
    ld h,a
    ld a,ENEMY_MASK_BANK
    ld ($7000),a
.upload:
    ld a,248
    ld b,64
    call Enemy_Upload
    ld a,(Enemy_TopRow)
    ld (Enemy_CacheTop),a
    cp 16
    jr nc,.colors
    ; The first maze scanline is the VDP's sprite-enable/prefetch boundary.
    ; Clip that one sprite row consistently, retaining every other source pixel.
    ld c,a
    vdp_write 14,7            ; the preceding upload wraps $1ffff and advances R14
    ld a,c
    add a,$c0
    ld c,a
    ld b,4
.top_mask:
    ld a,c
    out ($99),a
    ld a,$7f
    out ($99),a
    xor a
    out ($98),a
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    di
    ENDIF
    ld a,c
    add a,16
    ld c,a
    djnz .top_mask
.colors:
    ld a,(Enemy_EC)
    ld b,a
    ld hl,Enemy_LastEC
    cp (hl)
    jr z,.attributes
    ld (hl),a
    IF SPRITE_FLICKER
    jp .attributes
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    di
    ENDIF
    vdp_write 14,7
    ld a,$30
    out ($99),a
    IF INCREMENTAL_STAGE >= 9
    ld e,a
    ENDIF
    ld a,$75
    out ($99),a
    IF INCREMENTAL_STAGE >= 9
    ld d,a
    ei
    nop
    push de
    ld a,(Enemy_EC)
    rrca
    rrca
    ld l,a
    ld h,0
    ld de,Sprite_EnemyColors
    add hl,de
    pop de
    ld b,32
    call Sprite_Upload
    jp .attributes
    ENDIF
    ld a,b
    or $26
    ld b,16
.bodycolor:
    out ($98),a
    djnz .bodycolor
    ld a,(Enemy_EC)
    or $6a
    ld b,16
.windowcolor:
    out ($98),a
    djnz .windowcolor
.attributes:
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    ENDIF
    ld a,(Enemy_DrawX)
    ld b,a
    ld a,(Enemy_EC)
    or a
    ld a,b
    jr z,.x
    add a,32
.x:
    ld b,a
    ld a,(Enemy_SatY)
    ld hl,Enemy_SAT
    ld (hl),a
    inc hl
    ld (hl),b
    inc hl
    ld a,(Enemy_Body)
    ld (hl),a
    inc hl
    ld (hl),0
    inc hl
    ld a,(Enemy_SatY)
    ld (hl),a
    inc hl
    ld (hl),b
    inc hl
    ld a,(Enemy_Window)
    ld (hl),a
    inc hl
    ld (hl),0
    jr .publish
.hidden:
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.hide
    inc a
.hide:
    ld (Enemy_SAT),a
    ld (Enemy_SAT+4),a
.publish:
    IF SPRITE_FLICKER
    ret
    ENDIF
    IF INCREMENTAL_STAGE >= 9
    di
    ENDIF
    vdp_write 14,7
    IF INCREMENTAL_STAGE >= 9
    ei
    nop
    ENDIF
    ld a,19*4
    IF INCREMENTAL_STAGE >= 9
    ld e,a
    ld d,$76
    ld hl,Enemy_SAT
    ld b,8
    call Sprite_Upload
    ld a,216
    out ($98),a
    ret
    ENDIF
    out ($99),a
    ld a,$76
    out ($99),a
    ld hl,Enemy_SAT
    ld bc,$0898
    otir
    ld a,216
    out ($98),a
Enemy_DrawDone:
    ret
Enemy_Patterns:
    db 0,4,8,12,16,188,192,196,200,204,208,212
    db 216,220,224,228,232,236,240,244,248,252
    ENDIF
    ENDIF
