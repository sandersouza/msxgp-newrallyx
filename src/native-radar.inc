; Presentation of the original nine dot outputs and remaining collision flags.
; No entity position, flag ownership or game RAM byte is changed here.
Native_RadarIndex EQU $e630
Native_RadarTable EQU $e631
Native_RadarStep EQU $e633
Native_RadarX EQU $e634
Native_RadarY EQU $e635
Native_RadarW EQU $e636
Native_RadarH EQU $e637
Native_RadarXL EQU $e638
Native_RadarYL EQU $e639
Native_RadarXR EQU $e63a
Native_RadarYR EQU $e63b
Native_RadarQuadrant EQU $e63c
Native_RadarColor EQU $e63d
Native_RadarColumns EQU $e63e
Native_RadarRows EQU $e63f
Native_RadarEnemies EQU $e660
Native_RadarBackground EQU 3  ; original blue; bitmap fill consumes no sprites
Native_GutterCameras EQU $c7c9 ; previous world camera for each display page

; A stationary overlay needs no restoration. Only dirty its previous footprint
; when the page's next camera differs; ordinary changed tiles already dirty it.
Native_RestoreOldGutter:
    ld a,(Native_DrawPage)
    inc a
    ld b,a                    ; page-initialization bit1 or2
    dec a
    add a,a
    ld e,a
    ld d,0
    ld hl,Native_GutterCameras
    add hl,de
    ld a,(Native_PageInitialized)
    and b
    jr z,.save
    ld a,(Native_FrameScrollX)
    cp (hl)
    jr nz,.restore
    inc hl
    ld a,(Native_FrameScrollY)
    cp (hl)
    dec hl
    ret z
.restore:
    push hl
    ld a,(hl)
    add a,249
    and $fe
    ld (Native_RadarX),a
    inc hl
    ld a,(hl)
    add a,22
    ld (Native_RadarY),a
    ld a,10
    ld (Native_RadarW),a
    ld a,201
    ld (Native_RadarH),a
    call Native_MarkRadar
    pop hl
.save:
    ld a,(Native_FrameScrollX)
    ld (hl),a
    inc hl
    ld a,(Native_FrameScrollY)
    ld (hl),a
    ret

    IF !NATIVE_HUD
; Keep the fixed SAT actor offset, but move every unused HUD entry offscreen.
; No HUD patterns, colors, contents or raster-sharing updates are uploaded.
Native_BareHUD:
    ld a,(scroll_y)
    add a,211
    cp 216
    jr nz,.safe
    inc a
.safe:
    ld hl,sat
    ld de,4
    ld b,17
.hide:
    ld (hl),a
    add hl,de
    djnz .hide
    ld (hl),216
    ld hl,sat+56
    ld de,fuel_sat
    ld bc,12
    ldir
    ld hl,fuel_sat
    ld de,life_sat
    ld bc,12
    ldir
    ret
    ENDIF

; Radar output is absent outside gameplay/demo. Hide all fuel planes without
; using Y=216, which would terminate SAT and suppress following actor sprites.
Native_GateFuel:
    ld a,(Native_RadarVisible)
    or a
    ret nz
    ld a,(scroll_y)
    add a,211                 ; first sprite row is below the 212-line screen
    cp 216
    jr nz,.hide
    inc a
.hide:
    ld (fuel_sat),a
    ld (fuel_sat+4),a
    ld (fuel_sat+8),a
    ret

Native_SyncRadar:
    ld a,(Native_GameTicks)
    ld (radar_clock),a
    ld b,255
    ld c,255
    call HUD_SetNativeEnemy     ; all eight enemies use the bitmap plane below
    xor a
    ld (Native_RadarIndex),a
    ld (Native_RadarVisible),a
.dot:
    ld a,(Native_RadarIndex)
    add a,$34
    ld l,a
    ld h,$80
    ld d,(hl)
    ld h,$88
    ld c,(hl)
    ld a,(Native_RadarIndex)
    add a,4
    ld l,a
    ld h,$a0
    ld a,(hl)
    cpl
    and 1
    ld h,a
    ld l,d
    ld de,224
    or a
    sbc hl,de
    ld a,h
    or a
    jr nz,.hidden
    ld a,l
    cp 64
    jr nc,.hidden
    ld b,a
    ld a,157
    sub c
    cp 112
    jr nc,.hidden
    ld c,a
    jr .publish_dot
.hidden:
    ld b,255
    ld c,255
.publish_dot:
    ld a,b
    cp 255
    jr z,.dot_visibility
    ld a,1
    ld (Native_RadarVisible),a
.dot_visibility:
    ld a,(Native_RadarIndex)
    or a
    jr nz,.enemy
    call HUD_SetNativePlayer
    jr .next_dot
.enemy:
    call hud_project_native
    ld a,(Native_RadarIndex)
    dec a
    add a,a
    ld l,a
    ld h,0
    ld de,Native_RadarEnemies
    add hl,de
    ld (hl),b
    inc hl
    ld (hl),c
.next_dot:
    ld a,(Native_RadarIndex)
    inc a
    ld (Native_RadarIndex),a
    cp 9
    jr c,.dot
    ld hl,($8992)
    ld a,h
    cp $80
    jr c,.invalid_table
    cp $90
    jr nc,.invalid_table
    cp $8f
    jr c,.table
    ld a,l
    cp $ed
    jr c,.table
.invalid_table:
    ld hl,0
.table:
    ld (Native_RadarTable),hl
    xor a
    ld (Native_RadarIndex),a
.flag:
    ld b,255
    ld c,255
    ld a,(Native_RadarVisible)
    or a
    jr z,.publish_flag       ; initialized flag tables also exist on title screens
    ld hl,(Native_RadarTable)
    ld a,h
    or a
    jr z,.publish_flag
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld (Native_RadarTable),hl
    ld a,d
    cp $98
    jr c,.publish_flag
    cp $9f
    jr nc,.publish_flag
    ld a,(de)
    cp 1
    jr z,.visible_flag
    cp 2
    jr z,.visible_flag
    cp 4
    jr nz,.publish_flag
.visible_flag:
    ld a,d
    sub $98
    rlca
    rlca
    rlca
    rlca
    ld c,a
    ld a,e
    rrca
    rrca
    rrca
    rrca
    and 14
    or c
    ld c,a
    ld a,e
    and 31
    add a,a
    ld b,a
.publish_flag:
    ld a,(Native_RadarIndex)
    call HUD_SetNativePoint
    ld a,(Native_RadarIndex)
    inc a
    ld (Native_RadarIndex),a
    cp 10
    jr c,.flag
    ret

Native_DrawRadar:
    ei
    ld a,(Native_RadarStep)
    cp 255
    jr nz,.radar
    ; The final eight bitmap columns are outside the useful scene. A GPU fill
    ; replaces wrapped maze fragments; the radar is drawn over this afterwards.
    ld a,(Native_FrameScrollX)
    add a,249
    and $fe                   ; safe byte margin stays outside the 200px scene
    ld (Native_RadarX),a
    ld a,(Native_FrameScrollY)
    add a,22
    ld (Native_RadarY),a
    ld a,10                   ; extra pixels fall in the unused right/left edges
    ld (Native_RadarW),a
    ld a,201
    ld (Native_RadarH),a
    ld a,BLACK
    ld (Native_RadarColor),a
    call Native_RadarRectangle
    xor a
    ld (Native_RadarStep),a
    ret
.radar:
    ld a,(Native_RadarVisible)
    or a
    jr nz,.visible
    ld a,4                    ; no underlay on startup/title without radar data
    ld (Native_RenderStage),a
    ret
.visible:
    ld a,(Native_RadarStep)
    or a
    jr nz,.enemy
    ld a,(Native_FrameScrollX)
    add a,RADAR_X+1
    and $fe                   ; one byte-aligned opaque margin under the frame
    ld (Native_RadarX),a
    ld a,(Native_FrameScrollY)
    add a,31
    ld (Native_RadarY),a
    ld a,50
    ld (Native_RadarW),a
    ld a,60
    ld (Native_RadarH),a
    ld a,Native_RadarBackground
    ld (Native_RadarColor),a
    call Native_MarkRadar
    call Native_RadarRectangle
    jr .next
.enemy:
    dec a
    add a,a
    ld l,a
    ld h,0
    ld de,Native_RadarEnemies
    add hl,de
    ld a,(hl)
    cp 255
    jr z,.skip_enemy
    ld b,a
    inc hl
    ld c,(hl)
    ld a,(Native_FrameScrollX)
    add a,RADAR_X+1
    add a,b
    ld (Native_RadarX),a
    ld a,(Native_FrameScrollY)
    add a,31
    add a,c
    ld (Native_RadarY),a
    ld a,2
    ld (Native_RadarW),a
    ld (Native_RadarH),a
    ld a,13                   ; shared HUD palette red
    ld (Native_RadarColor),a
    call Native_RadarRectangle
.next:
    ld a,(Native_RadarStep)
    inc a
    ld (Native_RadarStep),a
    cp 9
    ret c
    ld a,4
    ld (Native_RenderStage),a
    ret
.skip_enemy:
    ld a,(Native_RadarStep)
    inc a
    ld (Native_RadarStep),a
    cp 9
    jp c,Native_DrawRadar      ; no GPU packet was submitted for the hidden dot
    ld a,4
    ld (Native_RenderStage),a
    ret

; Dirty the complete opaque underlay for restoration when either page is reused.
Native_MarkRadar:
    ld a,(Native_RadarW)
    add a,7
    ld b,a
    ld a,(Native_RadarX)
    and 7
    add a,b
    rrca
    rrca
    rrca
    and 15
    ld (Native_RadarColumns),a
    ld a,(Native_RadarH)
    add a,7
    ld b,a
    ld a,(Native_RadarY)
    and 7
    add a,b
    rrca
    rrca
    rrca
    and 31
    ld (Native_RadarRows),a
    ld a,(Native_RadarY)
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(Native_RadarX)
    rrca
    rrca
    rrca
    and 31
    or l
    ld l,a
.row:
    push hl
    ld a,(Native_RadarColumns)
    ld b,a
.column:
    push bc
    push hl
    ld (Native_TileIndex),hl
    call Native_DirtyBothPages
    pop hl
    pop bc
    ld a,l
    inc a
    xor l
    and 31
    xor l
    ld l,a
    djnz .column
    pop hl
    ld de,32
    add hl,de
    ld a,h
    and 3
    ld h,a
    ld a,(Native_RadarRows)
    dec a
    ld (Native_RadarRows),a
    jr nz,.row
    ret

; Split at both torus seams. HMMV clears even byte columns; tiny colored dots
; use LMMV so odd pixel anchors and individual edge pixels remain exact.
Native_RadarRectangle:
    ld a,(Native_RadarW)
    ld b,a
    ld a,(Native_RadarX)
    neg
    call .extent
    ld (Native_RadarXL),a
    ld c,a
    ld a,b
    sub c
    ld (Native_RadarXR),a
    ld a,(Native_RadarH)
    ld b,a
    ld a,(Native_RadarY)
    neg
    call .extent
    ld (Native_RadarYL),a
    ld c,a
    ld a,b
    sub c
    ld (Native_RadarYR),a
    xor a
    ld (Native_RadarQuadrant),a
.piece:
    ld hl,Native_RadarCommand
    ld de,Native_Command
    ld bc,15
    ldir
    ld a,(Native_RadarQuadrant)
    bit 0,a
    ld a,(Native_RadarXL)
    ld b,a
    ld a,(Native_RadarX)
    jr z,.x
    ld a,(Native_RadarXR)
    ld b,a
    xor a
.x:
    ld (Native_Command+4),a
    ld a,b
    or a
    jr z,.next
    ld (Native_Command+8),a
    ld a,(Native_RadarQuadrant)
    bit 1,a
    ld a,(Native_RadarYL)
    ld c,a
    ld a,(Native_RadarY)
    jr z,.y
    ld a,(Native_RadarYR)
    ld c,a
    xor a
.y:
    ld (Native_Command+6),a
    ld a,c
    or a
    jr z,.next
    ld (Native_Command+10),a
    ld a,(Native_DrawPage)
    ld (Native_Command+7),a
    ld a,(Native_RadarColor)
    cp 13                     ; only the tiny red dots require pixel addressing
    jr z,.dot
    ld b,a
    rlca
    rlca
    rlca
    rlca
    or b
    ld (Native_Command+12),a
    ld a,$c0
    ld (Native_Command+14),a
    jr .send
.dot:
    ld (Native_Command+12),a
.send:
    call Native_SendCommand
.next:
    ld a,(Native_RadarQuadrant)
    inc a
    ld (Native_RadarQuadrant),a
    cp 4
    jr c,.piece
    ret
.extent:
    or a
    jr z,.full
    cp b
    ret c
.full:
    ld a,b
    ret
Native_RadarCommand:
    db 0,0,0,0,0,0,0,0,2,0,2,0,13,0,$80
