; Page0 RAM overlay. Each torus tile owns a global X/Y pair at2000..2FFF.
; X=128 is an invalid sentinel and is never accepted as a cache hit.
; Scene setup uploads the same red/blue OR pair into all seven destinations.
Full_InitializeColorDestinations:
    ld hl,Full_PresentEC
    ld b,7
    xor a
.clear:
    ld (hl),a
    inc hl
    djnz .clear
    jp Full_PoolInit

Full_WorldAddress:
    ld a,d
    rrca
    ld l,a
    and 15
    or $20
    ld h,a
    ld a,l
    and $80
    ld l,a
    ld a,e
    and 63
    add a,a
    or l
    ld l,a
    ret

; Finish the nearest incomplete hidden edge before preparing a farther one.
; Exact ownership skips ready guard rows/columns without rebuilding queue debt.
Full_StageQueueNative:
    ld a,(Session_PositionIRQ)
    or a
    jr nz,.running
    ld a,(scroll_y)
    ld (irq_scroll_y),a
    ld a,1
    ld (Full_ScrollValid),a
.running:
    call Full_TurboOn
    ld a,(Full_CameraBlocked)
    or a
    jp nz,.done
    ld hl,(world_x)
    call stage_div8
    ld a,l
    ld (Full_QueuedX),a
    ld hl,(world_y)
    call stage_div8
    ld a,l
    ld (Full_QueuedY),a
    ld a,(previous_x)
    ld b,a
    ld a,(Full_QueuedX)
    ld (previous_x),a
    sub b
    jr z,.vertical
    ld a,1
    ld (Full_QueueDirty),a
.vertical:
    ld a,(previous_y)
    ld b,a
    ld a,(Full_QueuedY)
    ld (previous_y),a
    sub b
    jr z,.predict
    ld a,1
    ld (Full_QueueDirty),a
.predict:
    ; Native movement predicts the next exposed edge. Camera catch-up can
    ; still move on the previous axis; it must not cancel the new axis's job.
    ld a,($e06a)
    ld c,1
    bit 7,a
    jr z,.velocity
    dec c
    dec c
.velocity:
    ld a,($e06b)
    or a
    jr z,.predict_y
    ld a,(Full_DirX)
    cp c
    jr z,.pending
    ld a,c
    ld (Full_DirX),a
    xor a
    ld (column_left),a
    jr .direction_changed
.predict_y:
    xor a
    sub c
    ld c,a
    ld a,(Full_DirY)
    cp c
    jr z,.pending
    ld a,c
    ld (Full_DirY),a
    xor a
    ld (row_left),a
.direction_changed:
    ld a,1
    ld (Full_QueueDirty),a
.pending:
    ; A turn can leave the previous axis's guard job alive. It must not
    ; prevent forecasting the current axis before its first edge is exposed.
    ld a,($e06b)
    or a
    ld a,(row_left)
    jr z,.current_queue
    ld a,(column_left)
.current_queue:
    or a
    jp nz,.done
    ld a,(Full_QueueDirty)
    or a
    jp z,.done
    ld a,($e06b)
    or a
    jr nz,.columns
    ld a,(Full_DirY)
    or a
    jr z,.columns
    neg
    ld (Full_CheckStep),a
    ld a,(Full_DirY)
    inc a
    ld a,(Full_QueuedY)
    jr z,.up
    add a,28
    jr .row_start
.up:
    sub 3
.row_start:
    ld (Full_Edge),a
    ld a,3
    ld (Full_CheckCount),a
.row_probe:
    ld a,(Full_Edge)
    ld d,a
    ld a,(Full_QueuedX)
    ld e,a
    call Full_CheckGuardRow
    jr c,.row
    ld hl,Full_CheckCount
    dec (hl)
    jp z,.ready
    ld a,(Full_CheckStep)
    ld hl,Full_Edge
    add a,(hl)
    ld (hl),a
    jr .row_probe
.row:
    ld a,(Full_Edge)
    ld (row_y),a
    ld a,(Full_QueuedX)
    sub 3
    ld (row_x),a
    ld (Stage_RowLeft),a
    add a,38
    ld (Stage_RowEnd),a
    ld a,38
    ld (row_left),a
    jr .done
.columns:
    ld a,(Full_DirX)
    or a
    jr z,.ready
    neg
    ld (Full_CheckStep),a
    ld a,(Full_DirX)
    inc a
    ld a,(Full_QueuedX)
    jr z,.left
    add a,34
    jr .column_start
.left:
    sub 3
.column_start:
    ld (Full_Edge),a
    ld a,3                   ; One complete cell ahead; turns discard less work.
    ld (Full_CheckCount),a
.column_probe:
    ld a,(Full_Edge)
    ld e,a
    ld a,(Full_QueuedY)
    ld d,a
    call Full_CheckGuardColumn
    jr c,.column
    ld hl,Full_CheckCount
    dec (hl)
    jr z,.ready
    ld a,(Full_CheckStep)
    ld hl,Full_Edge
    add a,(hl)
    ld (hl),a
    jr .column_probe
.column:
    ld a,(Full_Edge)
    ld (column_x),a
    ld a,(Full_QueuedY)
    sub 3
    ld (column_y),a
    ld (Stage_ColumnTop),a
    add a,32
    ld (Stage_ColumnEnd),a
    ld a,32
    ld (column_left),a
    jr .done
.ready:
    xor a
    ld (Full_QueueDirty),a
.done:
    ld c,1
    jp Full_CacheExit

; Elapsed physical refreshes, not foreground loop iterations, own simulation
; time. Retain a small bounded debt so a late rendering loop can recover.
Full_ClockAdvance:
    ld a,(Full_ClockLast)
    ld b,a
    ld a,(ticks)
    ld (Full_ClockLast),a
    sub b
    ld b,a
    ld a,(paused)
    or a
    jr nz,.reset
    ld a,b
    or a
    jr z,.done
    cp 9
    jr c,.elapsed
    ld b,8
.elapsed:
    ld hl,(player_rate)
    ld de,PLAYER_RATE
.refresh:
    IF VDP_R9 == $80
    ; One logical tick per NTSC refresh. The authored MSX cadence is about
    ; 60 Hz; do not inject the arcade's extra 0.68 ticks/s into render deadlines.
    ld a,(Full_ClockDue)
    inc a
    ELSE
    add hl,de
    ld a,(Full_ClockDue)
    adc a,1
    ENDIF
    cp 13
    jr c,.retain
    sub 12
    ld c,a
    push hl
    ld hl,(Full_ClockDropped)
.dropped:
    inc hl
    dec c
    jr nz,.dropped
    ld (Full_ClockDropped),hl
    pop hl
    ld a,12
.retain:
    ld (Full_ClockDue),a
    djnz .refresh
    ld (player_rate),hl
.done:
    ld c,1
    jp Full_CacheExit
.reset:
    xor a
    ld (Full_ClockDue),a
    jr .done

; Bitmap effects always draw. Ownership only suppresses guard-prefetch work.
; The final hidden copy can execute alongside one elapsed-time native tick.
; The caller retains this overlay until the resident continuation returns.
Full_NativePressure:
    ld hl,(player_pending_x)
    ld de,(player_x)
    call .distance
    jr nc,.hold
    ld hl,(player_pending_y)
    call Full_VisibleCentre
    call .distance
    jr nc,.hold
.allow:
    ld c,0
    jp Full_CacheExit
.hold:
    ld hl,(Smoke_HeldFrames)
    inc hl
    ld (Smoke_HeldFrames),hl
    ld c,1
    jp Full_CacheExit
.distance:
    or a
    sbc hl,de
    ld de,16
    add hl,de
    ld a,h
    or a
    ret nz
    ld a,l
    cp 33
    ret

; Execute a due native tick without changing the sealed packet.
Full_TryIdleTick:
    ld a,(driving)
    or a
    jr z,.done
    ld a,(paused)
    or a
    jr nz,.done
    ld a,(Full_LoopTicks)
    cp 3                     ; A sealed packet may also repay one delayed tick.
    jr nc,.done
    cp 2
    jr c,.clock
    ld a,(row_left)
    ld hl,column_left
    or (hl)
    jr nz,.done              ; Recovery cannot starve the terrain needed to move.
.clock:
    call Full_ClockFrame
    ld a,(Full_ClockDue)
    or a
    jr z,.done
    ld hl,(player_pending_x)
    ld de,(player_x)
    call Full_NativePressure.distance
    jr nc,.done
    ld hl,(player_pending_y)
    call Full_VisibleCentre
    call Full_NativePressure.distance
    jr nc,.done
    ld a,(Full_ClockDue)
    dec a
    ld (Full_ClockDue),a
    call Player_Input
    ld a,PLAYER_BANK
    ld ($7000),a
    ei
    nop
    call Player_Tick
    call Player_Position
    scf
    ret
.done:
    or a
    ret

Full_PresentIdleEngine:
    xor a
    ld (Full_CacheWorked),a
    ld a,(raster_phase)
    cp 6
    jr z,.terrain
    cp 1
    jr z,.cpu_first          ; Complete the other tick before the final VBlank margin.
    cp 2
    jr z,.tail
    cp 3
    jr z,.work
    cp 5
    jr z,.work
    cp 4
    jr z,.work
    jr .nothing
.cpu_first:
    call Full_TryIdleTick
    jr c,.worked
    jr .nothing             ; No command can begin in the footer reservation.
.tail:
    call Full_TryIdleTick
    jr c,.worked
    ld a,(Stage_GuardClosed)
    or a
    jr nz,.nothing           ; End at the guard, with a full VBlank margin.
    jr .terrain              ; Footer is published; run copies, not a long tick.
.work:
    ld a,(row_left)
    ld hl,column_left
    or (hl)
    jr nz,.terrain
    call Full_TryIdleTick  ; Retain 60 Hz logic outside the packet deadline.
    jr c,.worked
.terrain:
    call Stage_PrefetchOne
    jr nc,.nothing
.worked:
    ld c,0
    jp Full_IdleExit
.nothing:
    ld c,1
    jp Full_IdleExit

Full_WarmCameraEngine:
    call Stage_QueuePriority
    ld b,4                   ; Urgent edges precede a packet; optional guards follow it.
.copy:
    push bc
    xor a
    ld (Full_CacheWorked),a
    call Stage_PrefetchOne
    pop bc
    djnz .copy
    ld c,1
    jp Full_IdleExit

; Record the exact rectangle owned by the command, clearing old smoke tags.
Full_CacheRun:
    call Full_TurboOn
    ld a,(stage_command+8)
    srl a
    srl a
    srl a
    ld (Full_CacheWidth),a
    ld a,(tile_x)
    ld e,a
    ld a,(tile_y)
    ld d,a
    push de
    call Full_WorldAddress
    pop iy
    ld a,(stage_command+10)
    srl a
    srl a
    srl a
    ld d,a
.row:
    push hl
    push iy
    push hl
    ld a,iyh
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    ld c,(hl)
    pop hl
    ld a,(Full_CacheWidth)
    ld b,a
.tile:
    ld a,c
    or a
    call nz,.erase_old_smoke
    ld a,iyl
    ld (hl),a
    inc l
    ld a,iyh
    ld (hl),a
    inc l
    inc iyl
    djnz .tile
    pop iy
    pop hl
    dec d
    jr z,.done
    inc iyh
    ld a,l
    add a,128
    ld l,a
    jr nc,.row
    inc h
    jr .row
.done:
    ld c,1
    jp Full_CacheExit
.erase_old_smoke:
    push hl
    push bc
    push de
    ld b,iyl
    ld c,iyh
    call Smoke_DisplayAddress
    ld a,(hl)
    and 15
    jr z,.smoke_done
    ld (hl),0
    ld a,iyh
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    dec (hl)
.smoke_done:
    pop de
    pop bc
    pop hl
    ret

Full_WorldProbe:
    call Full_TurboOn
    ld a,(tile_x)
    ld e,a
    ld a,(tile_y)
    ld d,a
    call Full_WorldAddress
    ld a,(hl)
    cp 128
    jr z,.miss
    cp e
    jr nz,.miss
    inc l
    ld a,(hl)
    cp d
    jr nz,.miss
    jr Full_WorldOwned
.miss:
    ; A cache hit performs no copy. Only a replacement needs the planned/live
    ; alias checks, which otherwise repeat for already-owned queue entries.
    call Full_CacheTileSafe
    jr c,.safe
    ld c,0
    jp Full_CacheExit         ; Discard a stale job that aliases the live view.
.safe:
    call Full_CellPrefetch
    ld c,1
    jp nc,Full_CacheExit
Full_WorldOwned:
    call Full_TurboOn
    ei                       ; A preceding cell command returns with DI.
    nop
    ld a,(Stage_RowBatch)
    cp 1
    jr nz,.column
.row:
    ld a,(row_left)
    or a
    jr z,.done
    ld a,(row_x)
    ld e,a
    ld a,(row_y)
    ld d,a
    call .owned
    jr c,.done
    ld hl,row_left
    dec (hl)
    ld a,(row_x)
    inc a
    ld hl,Stage_RowEnd
    cp (hl)
    jr nz,.row_cursor
    ld a,(Stage_RowLeft)
.row_cursor:
    ld (row_x),a
    jr .row
.column:
    ld a,(column_left)
    or a
    jr z,.done
    ld a,(column_x)
    ld e,a
    ld a,(column_y)
    ld d,a
    call .owned
    jr c,.done
    ld hl,column_left
    dec (hl)
    ld a,(column_y)
    inc a
    ld hl,Stage_ColumnEnd
    cp (hl)
    jr nz,.column_cursor
    ld a,(Stage_ColumnTop)
.column_cursor:
    ld (column_y),a
    jr .column
.owned:
    call Full_WorldAddress
    ld a,(hl)
    cp 128
    jr z,.bad
    cp e
    jr nz,.bad
    inc l
    ld a,(hl)
    cp d
    ret z
.bad:
    scf
    ret
.done:
    ld c,0
    jp Full_CacheExit

; Legacy queue bounds can lag a reversal. A different global tile must never
; replace the same physical tile while that physical location is on screen.
Full_CacheTileSafe:
    ld hl,(world_y)
    call .view
    ret nc
    call Full_VisibleCentre
    ex de,hl
    ld de,-105
    add hl,de
.view:
    call stage_div8
    ld a,(tile_y)
    sub l
    ld c,a
    and 31
    cp 26
    jr nc,.safe
    ld hl,(world_x)
    call stage_div8
    ld a,(tile_x)
    sub l
    ld e,a
    and 63
    cp 32
    jr nc,.safe
    ld a,c
    cp 26
    jr nc,.unsafe
    ld a,e
    cp 32
    jr nc,.unsafe
.safe:
    scf
    ret
.unsafe:
    or a
    ret

; Draw all nine exact tiles of a clean original cell. Neighboring queue entries
; then hit their ownership records, including the next two row/column jobs.
Full_CellCopyLeft EQU $0224
Full_CellCopyTop EQU $0225
Full_CellCopyWidth EQU $0226
Full_CellCopyHeight EQU $0227
Full_CellPrefetch:
    call Full_TurboOn
    xor a
    ld (Full_CellObject),a
    ld a,(tile_x)
    call Full_CellStart
    ld (Full_CellLeft),a
    ld a,(tile_y)
    call Full_CellStart
    ld (Full_CellTop),a
    ; A rejected batch still takes the ordinary exact tile path. Remember only
    ; failures within this stream call; native smoke/object state cannot change
    ; between its commands. Never cache acceptance across ownership changes.
    ld a,(Full_CellRejectedValid)
    or a
    jr z,.check
    ld hl,(Full_CellRejected)
    ld a,(Full_CellLeft)
    cp l
    jr nz,.check
    ld a,(Full_CellTop)
    cp h
    jp z,.failed
.check:
    ld a,(tile_x)
    ld b,a
    ld a,(Full_CellLeft)
    call Full_CellClipSpan
    ld (Full_CellCopyLeft),a
    ld a,c
    ld (Full_CellCopyWidth),a
    ld a,(tile_y)
    ld b,a
    ld a,(Full_CellTop)
    call Full_CellClipSpan
    ld (Full_CellCopyTop),a
    ld a,c
    ld (Full_CellCopyHeight),a
    ld hl,(world_y)
    call stage_div8
    ld a,(Full_CellTop)
    sub l
    add a,6
    cp 36
    jp nc,.none
    call Full_VisibleCentre
    ex de,hl
    ld de,-105
    add hl,de
    call stage_div8
    ld a,(Full_CellTop)
    sub l
    add a,6
    cp 36
    jp nc,.none
    ld a,(Death_DisplayState)
    or a
    jp nz,.none
    ld a,(Full_CellLeft)
    ld b,a
    ld a,(Full_CellTop)
    ld c,a
    call Full_ObjectAtTile
    or a
    jr z,.object_ready
    cp 15
    ld d,3
    jr z,.object_kind
    ld e,a
    ld d,0
    ld hl,Flag_DisplayActive
    add hl,de
    ld a,(hl)
    or a
    jr z,.object_ready
    ld a,e
    ld d,1
    cp 9
    jr c,.object_kind
    ld d,4
    jr z,.object_kind
    ld d,2
.object_kind:
    ld a,(Full_CellObject)
    or d
    ld (Full_CellObject),a
.object_ready:
    ld a,(Smoke_Valid)
    or a
    jr z,.source
    ld a,(Full_CellTop)
    ld c,a
    ld d,3
.empty_row:
    ld a,c
    sub 10
    and 31
    or Smoke_LogicalRows & 255
    ld l,a
    ld h,Smoke_LogicalRows/256
    ld a,(hl)
    or a
    jr nz,.smoke_present
    ld a,c
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    ld a,(hl)
    or a
    jr nz,.smoke_present
    inc c
    dec d
    jr nz,.empty_row
    jr .source
.smoke_present:
    ld a,(Full_CellTop)
    ld c,a
    ld iyh,3
.smoke_row:
    ld a,(Full_CellLeft)
    ld b,a
    ld iyl,3
.smoke_tile:
    call Smoke_CodeAtBC
    sub $bd
    cp 9
    jp c,.none
    ld a,c
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    ld a,(hl)
    or a
    jr z,.smoke_next
    call Smoke_DisplayAddress
    ld a,(hl)
    and 15
    jr z,.smoke_next
    ; Display entries retain their global high-coordinate tag. A cloud from
    ; an older torus lap must not disable batching for unrelated new scenery.
    ld a,b
    and 64
    rlca
    ld e,a
    ld a,c
    and $e0
    rrca
    or e
    ld e,a
    ld a,(hl)
    and $f0
    cp e
    jp z,.none
.smoke_next:
    inc b
    dec iyl
    jr nz,.smoke_tile
    inc c
    dec iyh
    jr nz,.smoke_row
.source:
    ld a,(tile_x)
    ld (Full_QueuedX),a
    ld a,(tile_y)
    ld (Full_QueuedY),a
    ld a,(Full_CellObject)
    and 7
    jr z,.terrain_source
    dec a
    add a,a
    ld l,a
    ld h,$9f
    jr .source_ready
.terrain_source:
    ld a,(Full_CellLeft)
    cp STAGE_COLUMNS
    jr nc,.flower_source
    call Full_Div3
    ld c,a
    ld a,(Full_CellTop)
    cp STAGE_ROWS
    jr nc,.flower_source
    call Full_Div3
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,c
    add a,a
    ld e,a
    ld d,0
    add hl,de
    ld de,$8000
    add hl,de
    jr .source_ready
.flower_source:
    ; The first complete world cell is the exact repeating 24x24 flower cell.
    ; Keep destination coordinates global while selecting that source entry.
    ld hl,$8000
.source_ready:
    ld a,(Full_WideHBank)
    ld ($7000),a
    call Stage_StripSource
    ld a,(stage_command)
    cp 1
    jr nz,.textured
    ld a,(stage_command+2)
    ld (stage_command+12),a
    ld a,$c0
    ld (stage_command+14),a
    jr .copy
.textured:
    ld a,(Full_CellCopyLeft)
    ld hl,Full_CellLeft
    sub (hl)
    add a,a
    add a,a
    add a,a
    ld hl,stage_command
    add a,(hl)
    ld (hl),a
.source_y:
    ld a,(Full_CellCopyTop)
    ld hl,Full_CellTop
    sub (hl)
    add a,a
    add a,a
    add a,a
    ld hl,stage_command+2
    add a,(hl)
    ld (hl),a
.copy:
    ld a,2
    ld (stage_command+3),a
    ld a,(Full_CellCopyWidth)
    ld l,a
    ld h,0
    ld a,(Full_CellCopyLeft)
    ld (tile_x),a
    ld (stage_command+8),hl
    ld a,(Full_CellCopyHeight)
    ld l,a
    ld h,0
    ld a,(Full_CellCopyTop)
    ld (tile_y),a
    ld (stage_command+10),hl
    call stage_copy_destination
    ld a,$d0
    ld (stage_command+14),a
    ld hl,8
    ld (stage_command+8),hl
    ld (stage_command+10),hl
    ld a,(Full_QueuedX)
    ld (tile_x),a
    ld a,(Full_QueuedY)
    ld (tile_y),a
    scf
    ret
.none:
    ld hl,(Full_CellLeft)
    ld (Full_CellRejected),hl
    ld a,1
    ld (Full_CellRejectedValid),a
.failed:
    jp Full_TurboOff

; A=cell start, B=requested tile. Return its contiguous physical fragment
; in A/C (global start/pixel extent). Keep both tiles on the wider side of
; a 32-tile seam instead of reducing every seam copy to one tile.
Full_CellClipSpan:
    ld e,a
    and 31
    cp 30
    ld c,24
    ld a,e
    ret c
    and 31
    cp 30
    jr z,.two_before
    ld a,b
    sub e
    ld a,e
    ld c,8
    ret z
    inc a
    ld c,16
    ret
.two_before:
    ld a,b
    sub e
    cp 2
    ld a,e
    ld c,16
    ret c
    add a,2
    ld c,8
    ret

; The flower phase table also covers negative coordinates encoded as bytes.
; Align with that phase instead of treating the wrapped coordinate as unsigned.
Full_CellStart:
    push af
    call Stage_StripMod3
    ld c,a
    pop af
    sub c
    ret

; Validate the newly exposed edge before applying a camera step. Missing edges
; become urgent jobs while native clocks retain the last coherent snapshot.
Full_CameraValidate:
    call Full_CameraValidateCore
    jp Full_CameraExit
Full_CameraValidateCore:
    call Full_TurboOn
    ld hl,(Full_CameraPlanX)
    ld de,(Full_FrameOriginX)
    call Full_CameraStep
    ld (Full_CameraPlanX),hl
    ld hl,(Full_CameraPlanY)
    ld de,(Full_FrameOriginY)
    call Full_CameraStep
    ld (Full_CameraPlanY),hl
    xor a
    ld (Full_CameraBlocked),a
    ; Validate Y against the current X, then X against the accepted Y. A
    ; missing edge on the previous turn's axis must not freeze both axes.
    ld hl,(world_x)
    call stage_div8
    ld a,l
    ld (Full_TargetTileX),a
    ld hl,(Full_CameraPlanY)
    ld de,-105
    add hl,de
    call stage_div8
    ld a,l
    ld (Full_TargetTileY),a
    ld b,a
    ld hl,(world_y)
    call stage_div8
    ld a,b
    sub l
    jr z,.horizontal
    call .delta
    ld a,(Full_CheckStep)
    inc a
    ld a,b
    jr nz,.row_edge
    add a,25
.row_edge:
    ld (Full_Edge),a
.check_row:
    ld a,(Full_Edge)
    ld d,a
    ld a,(Full_TargetTileX)
    ld e,a
    call Full_CheckRow
    jr c,.missing_row
    ld hl,Full_CheckCount
    dec (hl)
    jr z,.horizontal
    ld a,(Full_CheckStep)
    ld hl,Full_Edge
    add a,(hl)
    ld (hl),a
    jr .check_row
.missing_row:
    ld a,1
    ld (Full_CameraBlocked),a
    ld a,(row_left)
    or a
    jr z,.queue_row
    ld a,(row_y)
    ld hl,Full_Edge
    cp (hl)
    jr nz,.queue_row
    ld a,(Stage_RowLeft)
    ld hl,Full_TargetTileX
    cp (hl)
    jr z,.row_blocked
.queue_row:
    ld a,(Full_Edge)
    ld (row_y),a
    ld a,(Full_TargetTileX)
    ld (row_x),a
    ld (Stage_RowLeft),a
    add a,32
    ld (Stage_RowEnd),a
    ld a,32
    ld (row_left),a
.row_blocked:
    ld hl,(player_y)
    ld (Full_CameraPlanY),hl
    ld hl,(world_y)
    call stage_div8
    ld a,l
    ld (Full_TargetTileY),a
.horizontal:
    ld hl,(Full_CameraPlanX)
    ld de,-VIEWPORT_HALF
    add hl,de
    call stage_div8
    ld a,l
    ld (Full_TargetTileX),a
    ld a,(Full_TargetTileX)
    ld b,a
    ld hl,(world_x)
    call stage_div8
    ld a,b
    sub l
    jp z,.ready
    call .delta
    ld a,(Full_CheckStep)
    inc a
    ld a,b
    jr nz,.column_edge
    add a,31
.column_edge:
    ld (Full_Edge),a
.check_column:
    ld a,(Full_Edge)
    ld e,a
    ld a,(Full_TargetTileY)
    ld (Full_QueuedY),a
    ld d,a
    call Full_CheckColumn
    jr c,.missing_column
    ld hl,Full_CheckCount
    dec (hl)
    jp z,.ready
    ld a,(Full_CheckStep)
    ld hl,Full_Edge
    add a,(hl)
    ld (hl),a
    jr .check_column
.missing_column:
    ld a,(Full_CameraBlocked)
    or 2
    ld (Full_CameraBlocked),a
    ld a,(column_left)
    or a
    jr z,.queue_column
    ld a,(column_x)
    ld hl,Full_Edge
    cp (hl)
    jr nz,.queue_column
    ld a,(Stage_ColumnTop)
    ld hl,Full_QueuedY
    cp (hl)
    jr z,.column_blocked
.queue_column:
    ld a,(Full_Edge)
    ld (column_x),a
    ld a,(Full_QueuedY)
    ld (column_y),a
    ld (Stage_ColumnTop),a
    add a,26
    ld (Stage_ColumnEnd),a
    ld a,26
    ld (column_left),a
.column_blocked:
    ld hl,(player_x)
    ld (Full_CameraPlanX),hl
    ld hl,(world_x)
    call stage_div8
    ld a,l
    ld (Full_TargetTileX),a
.ready:
    jp Full_CameraValidated
.delta:
    ld c,255
    bit 7,a
    jr z,.magnitude
    neg
    ld c,1
.magnitude:
    ld (Full_CheckCount),a
    ld a,c
    ld (Full_CheckStep),a
    ret

; A late foreground iteration and the following early iteration must not
; publish two camera steps before the same physical maze latch.
Full_PlayerApplyNative:
    ld a,(Full_CacheReady)
    or a
    jr z,.plan
    ld a,(Full_CameraAppliedValid)
    or a
    jr z,.plan
    ld a,(frame_tick)
    ld hl,Full_CameraAppliedTick
    cp (hl)
    jr nz,.plan
    ld c,1
    jp Full_CacheExit
.plan:
    ld hl,(player_pending_x)
    ld (Full_CameraPlanX),hl
    ld hl,(player_pending_y)
    ld (Full_CameraPlanY),hl
    xor a
    ld (Full_CameraBlocked),a
    ld a,(Full_CacheReady)
    or a
    call nz,Full_CameraValidateCore
    ld hl,(Full_CameraPlanX)
    ld (player_x),hl
    ld de,-VIEWPORT_HALF
    add hl,de
    ld (world_x),hl
    ld hl,(Full_CameraPlanY)
    ld (player_y),hl
    ld de,-105
    add hl,de
    ld (world_y),hl
    ld a,(frame_tick)
    ld (Full_CameraAppliedTick),a
    ld a,1
    ld (Full_CameraAppliedValid),a
    jp Full_CameraExit

Full_CameraValidated:
    ld hl,(Full_CameraPlanX)
    ld de,(player_x)
    or a
    sbc hl,de
    jr nz,.changed
    ld hl,(Full_CameraPlanY)
    ld de,(player_y)
    or a
    sbc hl,de
    jr z,.done
.changed:
    ld a,1
    ld (player_steps),a
.done:
    ret

Full_CheckRow:
    call Full_WorldAddress
    ; The invalid X sentinel must reject even an otherwise matching Y.
    ; Check its entire requested range once, rather than on every tile.
    ld a,e
    sub 97
    cp 32
    jr c,.bad
    ld a,e
    and 63
    cp 33
    ld c,0
    ld b,32
    jr c,.tile
    ; Split a row at the physical 64-column seam. Each part is contiguous.
    neg
    add a,64
    ld b,a
    neg
    add a,32
    ld c,a
.tile:
    ld a,(hl)
    cp e
    jr nz,.bad
    inc l
    ld a,(hl)
    cp d
    jr nz,.bad
    inc l
    inc e
    djnz .tile
    ld a,c
    or a
    ret z
    ld b,c
    ld c,0
    ld a,l
    xor 128
    ld l,a
    jr .tile
.bad:
    scf
    ret

; Keep the complete perpendicular cache margin. Camera catch-up can move both
; axes after a turn; their directions and pending queues remain independent.
Full_CheckGuardRow:
    ld a,e
    sub 3
    ld e,a
    call Full_WorldAddress
    ld b,38
.tile:
    ld a,(hl)
    cp 128
    jr z,.bad
    cp e
    jr nz,.bad
    inc l
    ld a,(hl)
    cp d
    jr nz,.bad
    inc l
    inc e
    ld a,e
    and 63
    jr nz,.next
    ld a,l
    xor 128
    ld l,a
.next:
    djnz .tile
    or a
    ret
.bad:
    scf
    ret
Full_CheckGuardColumn:
    ld a,d
    sub 3
    ld d,a
    call Full_WorldAddress
    ld b,32
    jr Full_CheckColumn.tile
Full_CheckColumn:
    call Full_WorldAddress
    ld b,26
.tile:
    ld a,(hl)
    cp 128
    jr z,.bad
    cp e
    jr nz,.bad
    inc l
    ld a,(hl)
    cp d
    jr nz,.bad
    dec l
    inc d
    ld a,l
    add a,128
    ld l,a
    jr nc,.next
    inc h
    ld a,h
    and 15
    or $20
    ld h,a
.next:
    djnz .tile
    or a
    ret
.bad:
    scf
    ret

Full_ObjectAtTileNative:
    push de
    push hl
    ld a,b
    cp 3
    jr c,.none
    cp 99
    jr nc,.none
    ld a,c
    cp 3
    jr c,.none
    cp 171
    jr nc,.none
    ld l,c
    ld h,$e3
    ld a,(hl)
    dec a
    ld d,a
    ld l,b
    ld e,(hl)
    dec e
    ld a,d
    rrca
    rrca
    rrca
    rrca
    and 3
    add a,$dc
    ld h,a
    ld a,d
    and 15
    rlca
    rlca
    rlca
    rlca
    ld l,a
    ld a,e
    srl a
    or l
    ld l,a
    ld d,(hl)
    ld a,e
    and 1
    ld a,d
    jr z,.even
    rrca
    rrca
    rrca
    rrca
.even:
    and 15
    jr .done
.none:
    xor a
.done:
    pop hl
    pop de
    ret

; DE = centre of the currently latched view; preserve pending coordinates HL.
Full_VisibleCentre:
    push hl
    ld de,(player_y)
    ld a,(Full_ScrollValid)
    or a
    jr z,.done
    ld a,(irq_scroll_y)
    ld hl,scroll_y
    sub (hl)
    ld l,a
    ld h,0
    bit 7,a
    jr z,.offset
    dec h
.offset:
    add hl,de
    ex de,hl
.done:
    pop hl
    ret

; A successful native placement keeps the same bounded/deduplicated queue, but
; swaps its job to the head. Retired rows cannot delay new visible clouds.
; The displaced cleanup retains its coordinates and partial progress.
Full_EnqueueSmokeNative:
    push bc
    call Smoke_Enqueue
    pop bc
    ld a,(Smoke_Count)
    or a
    jr z,.done
    ld d,a
    ld a,(Smoke_Head)
    ld e,a
    ld l,a
    ld h,0
    add hl,hl
    ld a,l
    add a,e
    ld l,a
    ld a,h
    adc a,0
    ld h,a
    push de
    ld de,Smoke_Queue
    add hl,de
    pop de
    push hl
.find:
    ld a,(hl)
    cp b
    jr nz,.next
    inc hl
    ld a,(hl)
    dec hl
    cp c
    jr z,.found
.next:
    inc hl
    inc hl
    inc hl
    inc e
    ld a,e
    and 31
    ld e,a
    jr nz,.linear
    ld hl,Smoke_Queue
.linear:
    dec d
    jr nz,.find
    pop hl                   ; Overflow is still reported by Smoke_Enqueue.
    jr .done
.found:
    pop de
    ld b,3
.swap:
    ld a,(de)
    ld c,(hl)
    ld (hl),a
    ld a,c
    ld (de),a
    inc hl
    inc de
    djnz .swap
.done:
    ld c,1
    jp Full_CacheExit

; One exact live cloud replaces nine tile transactions. Overlap, expiry,
; explosions, partial queues and physical seams retain the ordinary row path.
Full_SmokeCellNative:
    ld a,b
    cp 3
    jp c,.no
    ld a,(ix+2)
    or a
    jp nz,.no
    ld a,(Death_DisplayState)
    or a
    jp nz,.no
    ld a,(tile_x)
    and 31
    cp 30
    jp nc,.no
    ld a,(tile_y)
    and 31
    cp 30
    jp nc,.no
    ld a,(tile_x)
    ld hl,cache_left
    sub (hl)
    cp STAGE_CACHE_COLUMNS-2
    jp nc,.no
    ld a,(tile_y)
    ld hl,cache_top
    sub (hl)
    cp 30
    jp nc,.no
    call Full_TurboOn
    ld a,(tile_y)
    ld c,a
    ld d,$bd
    ld iyh,3
.row:
    ld a,(tile_x)
    ld b,a
    ld iyl,3
.tile:
    push de
    call Smoke_CodeAtBC
    pop de
    cp d
    jp nz,.no
    inc b
    inc d
    dec iyl
    jr nz,.tile
    inc c
    dec iyh
    jr nz,.row
    ld a,(Full_WideHBank)
    ld ($7000),a
    ld hl,$9f08
    call Stage_StripSource
    ld a,2
    ld (stage_command+3),a
    ld hl,24
    ld (stage_command+8),hl
    ld (stage_command+10),hl
    call stage_copy_destination
    ld hl,8
    ld (stage_command+8),hl
    ld (stage_command+10),hl
    call Full_TurboOn
    ld a,$bd
    ld (Smoke_DrawCode),a
    ld iyh,3
.publish_row:
    ld a,(ix+0)
    ld (tile_x),a
    ld iyl,3
.publish_tile:
    call Smoke_RecordDisplay
    ld hl,tile_x
    inc (hl)
    ld hl,Smoke_DrawCode
    inc (hl)
    dec iyl
    jr nz,.publish_tile
    ld hl,tile_y
    inc (hl)
    dec iyh
    jr nz,.publish_row
    ld (ix+2),6              ; The caller consumes the final three queue units.
    ld a,3
    ld (Smoke_StreamCost),a
    ld c,0
    jp Full_SmokeCellExit
.no:
    ld c,1
    jp Full_SmokeCellExit

    INCLUDE "full-sprite-cache.inc"

; HL=desired centre, DE=last presented centre. Validate at most one new tile
; per axis, so an unfinished edge never becomes a moving three-column target.
Full_CameraStep:
    push hl
    or a
    sbc hl,de
    bit 7,h
    jr nz,.negative
    ld bc,8
    or a
    sbc hl,bc
    jr c,.small
    jr z,.small
    pop hl
    ex de,hl
    add hl,bc
    ret
.negative:
    ld bc,-8
    or a
    sbc hl,bc
    bit 7,h
    jr z,.small
    pop hl
    ex de,hl
    add hl,bc
    ret
.small:
    pop hl
    ret
