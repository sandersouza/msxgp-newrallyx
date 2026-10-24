; Cooperative presentation. Source descriptors are captured once; each later
; step restores the game mapping/registers/stack before original logic resumes.
Native_RenderStage EQU $c79d
Native_WorkCursor EQU $c79e
Native_WorkLeft EQU $c79f
Native_RenderDirty EQU $cd80
Native_FrameScrollX EQU $e620
Native_FrameScrollY EQU $e621
Native_FrameActor EQU $e622
Native_FrameOAM EQU $e640
Native_FrameAttrs EQU $e650
Native_SnapshotDirtyBytes EQU $e62a

Native_PrepareFrame:
    di
    ld (Native_RenderSP),sp
    ld sp,NATIVE_STACK
    push af
    ei
    ld a,(Native_PresentationArmed+1)
    or a
    jp z,Native_PrepareSkip
    IF NATIVE_FREEZE_PRESENTATION
    ld a,(Native_RenderFrames)
    or a
    jp nz,Native_PrepareSkip
    ENDIF
    ld a,(Native_Due)
    or a
    jp nz,Native_PrepareSkip   ; publish queued game ticks before presentation
    ld a,(Native_RenderStage)
    or a
    jr z,.idle
    cp 4
    jr nz,.active
    ld a,(Native_RasterPhase)
    cp 1
    jp nz,Native_PrepareSkip
    jr .active
.idle:
    ld a,(Native_RenderDue)
    or a
    jp z,Native_PrepareSkip
    ld a,(Native_HUDReady)
    or a
    jp nz,Native_PrepareSkip
    push hl
    ld hl,Native_LastRenderTick
    ld a,(Native_GameTicks)
    sub (hl)
    pop hl
    cp 6
    jp c,Native_PrepareSkip
    ld a,(Native_RasterPhase)
    cp 1
    jp nz,Native_PrepareSkip
    ld a,($a181)
    and 1
    jp z,Native_PrepareSkip
.active:
    ; A busy VDP owns the previous packet; return immediately to game logic.
    di
    vdp_write 15,2
    in a,($99)
    push af
    vdp_write 15,0
    ei
    pop af
    and 1
    jp nz,Native_PrepareSkip
    pop af
    push af
    push bc
    push de
    push hl
    push ix
    push iy
    ex af,af'
    push af
    exx
    push bc
    push de
    push hl
    ld a,1
    ld (Native_Suspended),a
    ld (Native_FrameMapped),a
    ld a,(Native_Segments+7)
    out ($fc),a
    call Native_RenderJob
    ld a,(Native_Segments+2)
    out ($fc),a
    xor a
    ld (Native_FrameMapped),a
    call Native_RestoreGame
    xor a
    ld (Native_Suspended),a
    ld a,(Native_RenderStage)
    or a
    jr nz,Native_StepDone
    ld hl,(Native_RenderFrames)
    inc hl
    ld (Native_RenderFrames),hl
Native_FrameDone:
    nop
    ei
Native_StepDone:
    pop hl
    pop de
    pop bc
    exx
    pop af
    ex af,af'
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    di
    ld sp,(Native_RenderSP)
    ei
Native_FrameReturn:
    ret
Native_PrepareSkip:
    pop af
    di
    ld sp,(Native_RenderSP)
    ei
Native_SkipReturn:
    ret

Native_RenderJob:
    ld a,(Native_RenderStage)
    or a
    jp z,Native_DrawFrame
    cp 1
    jp z,Native_RenderTiles
    cp 2
    jr z,.page
    cp 3
    jr z,.actors
    cp 5
    jp z,Native_DrawRadar
    ; The fast gate has observed command completion, so this page is ready.
    ld a,(Native_RasterPhase)
    cp 1
    ret nz
    ei
    IF NATIVE_HUD && !NATIVE_HWACTORS
    call HUD_PrepareFrame
    ENDIF
    IF NATIVE_HUD
    call HUD_DrawContent
    ENDIF
    call Native_RestoreGame
    di                         ; publish page/camera/SAT as one VBlank handshake
    ld a,(Native_DrawPage)
    rrca
    rrca
    rrca
    or $1f
    ld (Native_PendingR2),a
    ld a,1
    ld (Native_HUDReady),a
    xor a
    ld (Native_RenderStage),a
    ret
.page:
    ei
    call Native_SyncPage
    ret c
    ld a,3
    ld (Native_RenderStage),a
    xor a
    ld (Native_FrameActor),a
    ret
.actors:
    ei
    IF NATIVE_HWACTORS
    ld a,(Native_HWStarted)
    or a
    jr nz,.actor_job
    inc a
    ld (Native_HWStarted),a
    IF NATIVE_HUD
    call HUD_PrepareFrame
    ENDIF
    IF NATIVE_ACTORS
    call Native_HWBeginFrame
    ENDIF
.actor_job:
    ENDIF
    IF NATIVE_ACTORS
    call Native_DrawActors
    ELSE
    ld a,6
    ld (Native_FrameActor),a
    ENDIF
    ld a,(Native_FrameActor)
    cp 6
    ret c
    IF NATIVE_EDGE_CLEAR
    ld a,255                  ; clear the right edge before drawing the radar
    ELSE
    xor a
    ENDIF
    ld (Native_RadarStep),a
    ld a,5
    ld (Native_RenderStage),a
    ret

Native_DrawFrame:
    ei
    IF NATIVE_HWACTORS
    xor a
    ld (Native_HWStarted),a
    ENDIF
    ld a,(Native_GameTicks)
    ld (Native_LastRenderTick),a
    xor a
    ld (Native_RenderDue),a
    ld hl,Native_RenderDirty
    ld de,Native_RenderDirty+1
    ld bc,127
    ld (hl),0
    ldir
    ld a,(Native_ActiveR2)
    and $20
    xor $20
    rlca
    rlca
    rlca
    ld (Native_DrawPage),a
    ld a,(Native_DirtyAllPending)
    or a
    jr z,.camera
    call Native_MarkAllTiles
    xor a
    ld (Native_DirtyAllPending),a
.camera:
    ld a,($a130)
    ld (Native_FrameScrollX),a
    add a,1
    ld b,a
    neg
    and 7
    ld (scroll_low),a
    ld a,b
    add a,7
    rrca
    rrca
    rrca
    and 31
    ld (scroll_high),a
    ld a,($a140)
    ld (Native_FrameScrollY),a
    add a,22-BODY_TOP
    ld (scroll_y),a
    ld hl,$8014
    ld de,Native_FrameOAM
    ld bc,12
    ldir
    ld hl,$8814
    ld de,Native_FrameAttrs
    ld bc,12
    ldir
    IF NATIVE_HUD
    call Native_SyncHUD
    call Native_SyncRadar
    ELSE
    xor a
    ld (Native_RadarVisible),a
    call Native_BareHUD
    ENDIF
    IF NATIVE_EDGE_CLEAR
    call Native_RestoreOldGutter
    ENDIF
    call Native_RestoreGame
    ei
Native_FrameAfterHUD:
    call Native_CaptureDirtyRows
    ; Asset bank 3 has 4,928 immutable HUD bytes. Its unused $2000..$27ff
    ; tail holds this job's complete immutable code/attribute snapshot.
    ; Map it in page 0 while resident code/IM2 and the game page remain fixed.
    ld a,1
    ld (Native_FrameMapped),a
    ld a,(Native_Segments+7)
    out ($fc),a
    ei
    ld a,(Native_SnapshotDirtyBytes)
    cp 80
    jr c,Native_FrameCopySparse
    ld hl,$8400
    ld de,$2000
    ld bc,1024
Native_FrameCopyCodes:
    ldir
    ld hl,$8c00
    ld de,$2400
    ld bc,1024
Native_FrameCopyAttrs:
    ldir
    jr Native_FrameCopyDone
Native_FrameCopySparse:
    ld a,(Native_WorkCursor)
    or $80
    ld l,a
    ld h,Native_RenderDirty/256
    ld b,104
.byte:
    ld a,(hl)
    or a
    jr z,.next
    call Native_CopySnapshotCell
.next:
    inc l
    set 7,l
    djnz .byte
Native_FrameCopyDone:
    di
    ld a,(Native_Segments+2)
    out ($fc),a
    xor a
    ld (Native_FrameMapped),a
    ei
    ld a,1
    ld (Native_RenderStage),a
    ret

Native_CopySnapshotCell:
    push af
    push bc
    push de
    push hl
    ld a,l
    and 127
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,$8400
    add hl,de
    ld e,l
    ld a,h
    sub $64
    ld d,a
    ld bc,8
Native_FrameCopyCodeCell:
    ldir
    ld bc,-8
    add hl,bc
    ex de,hl
    add hl,bc
    ex de,hl
    ld a,h
    add a,8
    ld h,a
    ld a,d
    add a,4
    ld d,a
    ld bc,8
Native_FrameCopyAttrCell:
    ldir
    pop hl
    pop de
    pop bc
    pop af
    ret

Native_CaptureDirtyRows:
    xor a
    ld (Native_SnapshotDirtyBytes),a
    ld a,(Native_FrameScrollY)
    add a,22
    and $f8
    rrca
    ld l,a
    ld (Native_WorkCursor),a
    ld b,104
    ld a,b
    ld (Native_WorkLeft),a
.row:
    ld a,l
    and 127
    ld l,a
    ld h,Native_DirtyTiles/256
    ld a,(hl)
    ld (hl),0
    or a
    jr z,.clean
    push af
    ld a,(Native_SnapshotDirtyBytes)
    inc a
    ld (Native_SnapshotDirtyBytes),a
    pop af
.clean:
    push hl
    ld h,Native_RenderDirty/256
    set 7,l
    ld (hl),a
    pop hl
    inc l
    djnz .row
    ret

Native_RenderTiles:
    ei
    ld a,16                   ; bounded cheap skips; yield after one GPU command
    ld (Native_TileBudget),a
    ld a,(Native_WorkLeft)
    ld b,a
    ld a,(Native_WorkCursor)
    ld l,a
.find:
    ld a,l
    and 127
    ld l,a
    add a,$80
    ld e,a
    ld d,Native_RenderDirty/256
    ld a,(de)
    or a
    jr nz,.dirty
    inc l
    djnz .find
    ld a,2
    ld (Native_RenderStage),a
    xor a
    ld (Native_PageCursor),a
.finish:
    ret
.dirty:
    push bc
    push hl
    ld c,0
.bit:
    rrca
    jr c,.found
    inc c
    jr .bit
.found:
    ld a,1
    ld b,c
    inc b
.mask:
    rlca
    djnz .mask
    rrca
    cpl
    ld h,d
    ld l,e
    and (hl)
    ld (hl),a
    ld a,l
    and 127
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld b,0
    add hl,bc
    ld (Native_TileIndex),hl
    call Native_DrawTile
    pop hl
    pop bc
    jr c,.yield
    ld a,(Native_TileBudget)
    dec a
    ld (Native_TileBudget),a
    jr nz,.find
.yield:
    ld a,l
    ld (Native_WorkCursor),a
    ld a,b
    ld (Native_WorkLeft),a
    ret
Native_FrameTilesDone EQU Native_RenderTiles.finish
