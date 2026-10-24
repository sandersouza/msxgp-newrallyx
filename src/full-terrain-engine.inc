; Page0 RAM overlay. Each torus tile owns a global X/Y pair at2000..2FFF.
; X=128 is an invalid sentinel and is never accepted as a cache hit.
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
    ld c,1
    bit 7,a
    jr z,.x_sign
    dec c
    dec c
.x_sign:
    ld a,1
    ld (Full_QueueDirty),a
    ld a,(Full_DirX)
    cp c
    jr z,.vertical
    ld a,c
    ld (Full_DirX),a
    xor a
    ld (Full_DirY),a
    ld (row_left),a
    ld (column_left),a
.vertical:
    ld a,(previous_y)
    ld b,a
    ld a,(Full_QueuedY)
    ld (previous_y),a
    sub b
    jr z,.pending
    ld c,1
    bit 7,a
    jr z,.y_sign
    dec c
    dec c
.y_sign:
    ld a,1
    ld (Full_QueueDirty),a
    ld a,(Full_DirY)
    cp c
    jr z,.pending
    ld a,c
    ld (Full_DirY),a
    xor a
    ld (Full_DirX),a
    ld (row_left),a
    ld (column_left),a
.pending:
    ld a,(row_left)
    ld b,a
    ld a,(column_left)
    or b
    jp nz,.done
    ld a,(Full_QueueDirty)
    or a
    jp z,.done
    ld a,(Full_DirY)
    or a
    jr z,.columns
    ld (Full_CheckStep),a
    inc a
    ld a,(Full_QueuedY)
    jr z,.up
    add a,26
    jr .row_start
.up:
    dec a
.row_start:
    ld (Full_Edge),a
    ld a,3
    ld (Full_CheckCount),a
.row_probe:
    ld a,(Full_Edge)
    ld d,a
    ld a,(Full_QueuedX)
    ld e,a
    call Full_CheckRow
    jr c,.row
    ld hl,Full_CheckCount
    dec (hl)
    jr z,.columns
    ld a,(Full_CheckStep)
    ld hl,Full_Edge
    add a,(hl)
    ld (hl),a
    jr .row_probe
.row:
    ld a,(Full_Edge)
    ld (row_y),a
    ld a,(Full_QueuedX)
    ld (row_x),a
    ld (Stage_RowLeft),a
    add a,32
    ld (Stage_RowEnd),a
    ld a,32
    ld (row_left),a
    jr .done
.columns:
    ld a,(Full_DirX)
    or a
    jr z,.ready
    ld (Full_CheckStep),a
    inc a
    ld a,(Full_QueuedX)
    jr z,.left
    add a,32
    jr .column_start
.left:
    dec a
.column_start:
    ld (Full_Edge),a
    ld a,4
    ld (Full_CheckCount),a
.column_probe:
    ld a,(Full_Edge)
    ld e,a
    ld a,(Full_QueuedY)
    ld d,a
    call Full_CheckColumn
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
    ld (column_y),a
    ld (Stage_ColumnTop),a
    add a,26
    ld (Stage_ColumnEnd),a
    ld a,26
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
    add hl,de
    ld a,(Full_ClockDue)
    adc a,1
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

Full_SimulationTail:
    ld a,(driving)
    or a
    ret z
    ld a,(paused)
    or a
    ret nz
    ld b,2
.tick:
    push bc
    ld hl,(player_pending_x)
    ld de,(player_x)
    call Full_NativePressure.distance
    jr nc,.done
    ld hl,(player_pending_y)
    call Full_VisibleCentre
    call Full_NativePressure.distance
    jr nc,.done
    call Full_CameraCheck
    jr c,.done
    call Full_ClockFrame
    ld a,(Full_ClockDue)
    or a
    jr z,.done
    dec a
    ld (Full_ClockDue),a
    ld a,1
    ld (player_steps),a
    call Player_Input
    ld a,PLAYER_BANK
    ld ($7000),a
    ei
    nop
    call Player_Tick
    call Player_Position
    pop bc
    djnz .tick
    ret
.done:
    pop bc
    ret

; Spend otherwise idle header synchronization time on at most two due ticks.
; Keep the prepared scroll/SAT and reserved post-header tick count unchanged.
Full_SimulationIdleNative:
    ld a,(driving)
    or a
    jr z,.done
    ld a,(paused)
    or a
    jr nz,.done
    ld a,(Full_IdleTicks)
    cp 2
    jr nc,.done
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
    ld hl,Full_IdleTicks
    inc (hl)
    call Player_Input
    ld a,PLAYER_BANK
    ld ($7000),a
    ei
    nop
    call Player_Tick
    call Player_Position
    ld c,0
    jp Full_IdleExit
.done:
    ld c,1
    jp Full_IdleExit

Full_CacheRun:
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
    ld a,(Full_CacheWidth)
    ld b,a
.tile:
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

Full_WorldProbe:
    call Full_TurboOn
    call Full_CacheTileSafe
    jr c,.safe
    ld c,0
    jp Full_CacheExit         ; Discard a stale job that aliases the live view.
.safe:
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
Full_CellPrefetch:
    call Full_TurboOn
    ld a,(tile_x)
    cp STAGE_COLUMNS
    jp nc,.none
    ld l,a
    ld h,$e3
    ld a,(hl)
    ld e,a
    add a,a
    add a,e
    ld (Full_CellLeft),a
    and 31
    cp 30
    jp nc,.none
    ld a,(tile_y)
    cp STAGE_ROWS
    jp nc,.none
    ld l,a
    ld h,$e3
    ld a,(hl)
    ld e,a
    add a,a
    add a,e
    ld (Full_CellTop),a
    and 31
    cp 30
    jp nc,.none
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
    jp nc,.none            ; Never alias a different world row onto the viewport.
    ld a,(Death_DisplayState)
    or a
    jp nz,.none
    ld a,(Full_CellLeft)
    ld b,a
    ld a,(Full_CellTop)
    ld c,a
    call Full_ObjectAtTile
    or a
    jp nz,.none
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
    jp nz,.none
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
    ld a,(Full_CellLeft)
    ld (tile_x),a
    call Full_Div3
    ld c,a
    ld a,(Full_CellTop)
    ld (tile_y),a
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
    ld a,(Full_WideHBank)
    ld ($7000),a
    call Stage_StripSource
    ld a,(stage_command)
    cp 1
    jr nz,.copy
    ld a,(stage_command+2)
    ld (stage_command+12),a
    ld a,$c0
    ld (stage_command+14),a
.copy:
    ld a,2
    ld (stage_command+3),a
    ld hl,24
    ld (stage_command+8),hl
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
    jp Full_TurboOff

; Validate the newly exposed edge before applying a camera step. Missing edges
; become urgent jobs while native clocks retain the last coherent snapshot.
Full_CameraValidate:
    call Full_TurboOn
    xor a
    ld (Full_CameraBlocked),a
    ld hl,(player_pending_x)
    ld de,-VIEWPORT_HALF
    add hl,de
    call stage_div8
    ld a,l
    ld (Full_TargetTileX),a
    ld hl,(player_pending_y)
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
    jr z,.horizontal
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
.horizontal:
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
    ; A horizontal turn can combine the new X with an interpolated older Y.
    ; Prepare that column for both views before publishing the X movement.
    call Full_VisibleCentre
    ex de,hl
    ld de,-105
    add hl,de
    call stage_div8
    ld a,l
    ld (Full_QueuedY),a
    ld d,a
    ld a,(Full_Edge)
    ld e,a
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
    jp z,.ready
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
.ready:
    ld a,(Full_CameraBlocked)
    or a
    jr z,Full_CameraValidated
    xor a
    ld (player_steps),a
    jp Full_CameraExit
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
Full_CameraValidated:
    ld hl,(player_pending_x)
    ld de,(player_x)
    or a
    sbc hl,de
    jr nz,.changed
    ld hl,(player_pending_y)
    ld de,(player_y)
    or a
    sbc hl,de
    jr z,.done
.changed:
    ld a,1
    ld (player_steps),a
.done:
    jp Full_CameraExit

Full_CheckRow:
    call Full_WorldAddress
    ld b,32
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
    ld a,l
    and 127
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
