; Selected original smoke, with RAM tile rings and bounded bitmap repair jobs.
Smoke_Key EQU $c700
Smoke_Valid EQU $c701
Smoke_Left EQU $c702
Smoke_Top EQU $c703
Smoke_NewLeft EQU $c704
Smoke_NewTop EQU $c705
Smoke_X EQU $c706
Smoke_Y EQU $c707
Smoke_PreX EQU $c708
Smoke_PreY EQU $c70a
Smoke_Head EQU $c70c
Smoke_Tail EQU $c70d
Smoke_Count EQU $c70e
Smoke_Overflow EQU $c70f
Smoke_DrawCode EQU $c710
Smoke_Placements EQU $c711
Smoke_Recoveries EQU $c713
Smoke_RowCode EQU $c716
Smoke_RowWidth EQU $c717
Smoke_StreamCost EQU $c718
Smoke_RowX EQU $c719
Smoke_Queue EQU $c740          ; X,Y,next tile:0..8 full cloud,64..66 one dirty row
Smoke_Thunk EQU $c7b0
Smoke_Display EQU $d300        ; 2048 packed identity/ink bytes; IRQ stub D2D2 untouched
Smoke_DisplayRows EQU $db00    ; nonzero cells per physical cache row
    IF FULL_GAME
Smoke_LogicalRows EQU $d160    ; Conservative native smoke presence, modulo32.
    ENDIF
Smoke_HeldFrames EQU $c71d    ; temporal concession; never hide stale terrain

; A native refresh moves less than one tile. Retain a final guard tile rather
; than presenting an unfinished row/column; simulation and its clocks hold
; together, while the renderer continues draining the existing hidden jobs.
Smoke_CachePressure:
    IF FULL_GAME
    push iy
    call Full_CacheEnter
    jp Full_NativePressure
    ELSE
    ld hl,(world_y)
    call stage_div8
    ld a,(previous_y)
    sub l
    jp p,.vertical
    neg
.vertical:
    cp STAGE_CACHE_TOP_GUARD-1
    jr nc,.hold
    ld hl,(world_x)
    call stage_div8
    ld a,(previous_x)
    sub l
    jp p,.horizontal
    neg
.horizontal:
    cp STAGE_CACHE_GUARD-1
    jr nc,.hold
    xor a
    ret
    ENDIF
    IF !FULL_GAME
.hold:
    ld hl,(Smoke_HeldFrames)
    inc hl
    ld (Smoke_HeldFrames),hl
    ld a,1
    or a
    ret
    ENDIF

Smoke_Init:
    xor a
    ld hl,Smoke_Key
    ld de,Smoke_Key+1
    ld bc,63
    ld (hl),a
    ldir
    ld a,$c3
    ld (Smoke_Thunk),a
    ld hl,Smoke_ClearNotify
    ld (Smoke_Thunk+1),hl
    ld (Smoke_Thunk+3),a
    ld hl,Smoke_RecoveredNotify
    ld (Smoke_Thunk+4),hl
    xor a
    ld ($e290),a
    ld ($e291),a
    call Smoke_ClearRings
    ld hl,Smoke_Display
    ld de,Smoke_Display+1
    ld bc,2047
    ld (hl),a
    ldir
    ld hl,Smoke_DisplayRows
    ld de,Smoke_DisplayRows+1
    ld bc,31
    ld (hl),a
    ldir
    ret
Smoke_ClearRings:
    xor a
    ld hl,$e400
    ld de,$e401
    ld bc,1023
    ld (hl),a
    ldir
    ld hl,$ec00
    ld de,$ec01
    ld bc,1023
    ld (hl),a
    ldir
    IF FULL_GAME
    ld hl,Smoke_LogicalRows
    ld de,Smoke_LogicalRows+1
    ld bc,31
    ld (hl),a
    ldir
    ENDIF
    ret

; Called before $0069 changes world coordinates. The physical coordinates and
; camera fine offsets still describe this origin during smoke/expiry helpers.
Smoke_PreTick:
    ld a,(Smoke_Placements)
    ld b,a
    ld a,(Smoke_Placements+1)
    or b
    ld b,a
    ld a,(Smoke_Key)
    or b
    ld b,a
    ld a,($e291)
    or b
    ret z                    ; No ring maintenance before the first smoke request.
    ld a,($e070)
    ld hl,$e06d
    call Player_Axis
    ld (Smoke_PreX),hl
    ld de,-VIEWPORT_HALF
    add hl,de
    call stage_div8
    ld a,l
    ld (Smoke_NewLeft),a
    ld a,($e072)
    ld hl,$e06f
    call Player_AxisY
    ld (Smoke_PreY),hl
    ld de,-105
    add hl,de
    call stage_div8
    ld a,l
    ld (Smoke_NewTop),a
    ld a,(Smoke_Valid)
    or a
    jr z,.store
    ld a,(Smoke_Left)
    ld b,a
    ld a,(Smoke_NewLeft)
    sub b
    jr z,.y
    cp 1
    jr z,.column
    cp 255
    jr nz,.jumped
    ld a,(Smoke_NewLeft)
    ld b,a
.column:
    ld a,(Smoke_Top)
    ld c,a
    call Smoke_Address
    ld d,32
.clear_column:
    call Smoke_RetireCode
    ld a,l
    add a,32
    ld l,a
    jr nc,.column_next
    inc h
    ld a,h
    and 3
    or $e4
    ld h,a
.column_next:
    inc c
    dec d
    jr nz,.clear_column
.y:
    ld a,(Smoke_NewLeft)
    ld (Smoke_Left),a
    ld b,a
    ld a,(Smoke_Top)
    ld c,a
    ld a,(Smoke_NewTop)
    sub c
    jr z,.store
    cp 1
    jr z,.row
    cp 255
    jr nz,.jumped
    ld a,(Smoke_NewTop)
    ld c,a
.row:
    call Smoke_Address
    ld a,l
    and $e0
    ld e,a
    ld d,32
.clear_row:
    call Smoke_RetireCode
    ld a,l
    inc a
    and 31
    or e
    ld l,a
    inc b
    dec d
    jr nz,.clear_row
    IF FULL_GAME
    ld a,c
    sub 10
    and 31
    or Smoke_LogicalRows & 255
    ld l,a
    ld h,Smoke_LogicalRows/256
    ld (hl),0               ; Every native tile in this physical row was cleared.
    ENDIF
    jr .store
.jumped:
    ld a,2                   ; Diagnostic: normal movement cannot skip a tile.
    ld (Smoke_Overflow),a
    call Smoke_ClearRings
.store:
    ld a,(Smoke_NewLeft)
    ld (Smoke_Left),a
    ld a,(Smoke_NewTop)
    ld (Smoke_Top),a
    ld a,1
    ld (Smoke_Valid),a
    ret

; World tile B,C -> original modulo32 code ring. Preserve B,C.
Smoke_Address:
    ld a,c
    sub 10
    and 31
    rrca
    rrca
    rrca
    ld l,a
    and 3
    add a,$e4
    ld h,a
    ld a,l
    and $e0
    ld l,a
    ld a,b
    sub 3
    and 31
    or l
    ld l,a
    ret
; Zero code invalidates a retired cell. Its attribute is loaded on demand
; before a new eligible placement; no attribute scan is needed here.
Smoke_RetireCode:
    ld a,(hl)
    cp $bd
    jr c,.empty
    cp $c6
    jr nc,.empty
    push bc
    push de
    push hl
    call Smoke_DirtyTile
    pop hl
    pop de
    pop bc
.empty:
    ld (hl),0
    ret
Smoke_DirtyTile:
    sub $bd
.row:
    cp 3
    jr c,.column
    sub 3
    jr .row
.column:
    ld d,a
    ld a,b
    sub d
    ld b,a
    jp Smoke_EnqueueRow       ; Retiring one row must not repaint the other two.

; Native ring address HL -> world tile B,C in the retained viewport window.
Smoke_DecodeAddress:
    ld a,l
    and 31
    add a,3
    ld b,a
    ld a,(Smoke_Left)
    ld d,a
    ld a,b
    sub d
    and 31
    add a,d
    ld b,a
    ld a,l
    rlca
    rlca
    rlca
    and 7
    ld e,a
    ld a,h
    and 3
    rlca
    rlca
    rlca
    or e
    add a,10
    ld c,a
    ld a,(Smoke_Top)
    ld d,a
    ld a,c
    sub d
    and 31
    add a,d
    ld c,a
    ret

Smoke_Tick:
    ld hl,$e9f4
    res 4,(hl)
    ld a,(Smoke_Key)
    ld b,a
    ld a,($e291)
    or b
    call nz,Smoke_PreparePlacement
    call $8f64              ; Original debounce, fuel deduction, placement and request.
Smoke_AfterNative:
    ld a,($e9f4)
    bit 4,a
    ret z
    IF FULL_GAME
    call Full_MarkLogicalSmokeRows
    ENDIF
    ld hl,Smoke_Placements
    inc (hl)
    jr nz,.counted
    inc hl
    inc (hl)
.counted:
    ld a,(Smoke_X)
    ld b,a
    ld a,(Smoke_Y)
    ld c,a
    IF FULL_GAME
    jp Full_EnqueueSmoke      ; New visible ink must precede old cleanup jobs.
    ELSE
    jp Smoke_Enqueue
    ENDIF
Smoke_PreparePlacement:
    ld a,($e077)
    ld b,8
    ld c,$f0
    cp $f0
    jr z,.physical
    ld c,24
    cp $f2
    jr z,.physical
    ld b,32
    ld c,8
    cp $fc
    jr z,.physical
    ld b,$f0
    cp $fd
    ret nz
.physical:
    ld a,($e074)
    sub b
    ld b,a
    ld a,($e076)
    add a,c
    ld c,a
    call $9031
    call Smoke_DecodeAddress
    ld a,b
    ld (Smoke_X),a
    ld a,c
    ld (Smoke_Y),a
    ld a,(hl)
    cp $81
    ret z                    ; Preserve cleared-road attribute15 until reloaded.
    cp $bd
    jr c,.permission
    cp $c6
    ret c                    ; Existing cloud retains the source's placement block.
.permission:
    push hl
    ld a,b
    cp STAGE_COLUMNS
    jr nc,.denied
    ld a,c
    cp STAGE_ROWS
    jr nc,.denied
    IF FULL_GAME
    call Full_ObjectAtTile
    or a
    jr z,.base_permission
    cp 15
    jr z,.denied
    ld l,a
    ld h,Flag_Active/256
    ld a,(hl)
    or a
    jp z,.allowed
    jr .denied
.base_permission:
    ENDIF
    ld h,0
    ld l,c
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,b
    srl a
    srl a
    ld e,a
    ld d,0
    add hl,de
    IF FULL_GAME
    ld de,$9000
    ELSE
    ld de,$8700
    ENDIF
    add hl,de
    IF FULL_GAME
    ld a,(Full_ResourceBank)
    ELSE
    ld a,PLAYER_DATA_BANK
    ENDIF
    ld ($7000),a
    ld d,(hl)
    ld a,b
    and 3
    ld b,a
    ld a,d
    inc b
    jr .test
.shift:
    rrca
    rrca
.test:
    djnz .shift
    and 3
    push af
    ld a,PLAYER_BANK
    ld ($7000),a
    pop af
    bit 0,a
    jr nz,.allowed
    bit 1,a
    jr z,.denied
    call Smoke_FlagCollected
    jr nz,.denied
.allowed:
    pop hl
    ld (hl),$81
    set 3,h
    ld (hl),$95
    ret
.denied:
    pop hl
    ret
Smoke_FlagCollected:
    ld ix,Flag_Records
    ld b,10
    ld e,1
.next:
    ld a,(Smoke_X)
    sub (ix+4)
    cp 3
    jr nc,.miss
    ld a,(Smoke_Y)
    sub (ix+5)
    cp 3
    jr nc,.miss
    ld h,Flag_Active/256
    ld l,e
    ld a,(hl)
    or a
    ret
.miss:
    push de
    ld de,6
    add ix,de
    pop de
    inc e
    djnz .next
    or 1
    ret

; Replacement for original LD B,3 / LD D,H. All original registers/flags
; survive the notification, then those exact two instructions are reproduced.
Smoke_ClearNotify:
    push af
    push bc
    push de
    push hl
    ld a,(Smoke_Valid)
    or a
    jr z,.done
    call Smoke_DecodeAddress
    call Smoke_Enqueue
.done:
    pop hl
    pop de
    pop bc
    pop af
    ld b,3
    ld d,h
    ret
Smoke_RecoveredNotify:
    push af
    push hl
    ld hl,Smoke_Recoveries
    inc (hl)
    jr nz,.counted
    inc hl
    inc (hl)
.counted:
    pop hl
    pop af
    ld (ix+$15),0          ; Exact original instruction, including its flags contract.
    ret
; Original $19d9..$1a32 clears the flag's lower-left2x2 code tiles and leaves
; attributes unchanged. Preserve other cloud tiles when this region overlaps.
Smoke_CollectedFlag:
    push af
    ld a,(Smoke_Valid)
    or a
    jr z,.inactive
    push bc
    push de
    push hl
    xor a
    ld ($c715),a
    ld a,(Flag_Y)
    ld c,a
    ld d,0
.row:
    ld a,(Flag_X)
    ld b,a
    ld e,0
.column:
    ld a,(Smoke_Left)
    ld l,a
    ld a,b
    sub l
    cp 32
    jr nc,.next
    ld a,(Smoke_Top)
    ld l,a
    ld a,c
    sub l
    cp 32
    jr nc,.next
    call Smoke_Address
    ld a,(hl)
    push af
    cp $bd
    jr c,.checked
    cp $c6
    jr nc,.checked
    ld a,1
    ld ($c715),a
.checked:
    pop af
    or a
    jr z,.clear
    ld a,d
    or a
    jr z,.next
    ld a,e
    cp 2
    jr nc,.next
.clear:
    ld (hl),$81
.next:
    inc b
    inc e
    ld a,e
    cp 3
    jr nz,.column
    inc c
    inc d
    ld a,d
    cp 3
    jr nz,.row
    ld a,($c715)
    or a
    jr z,.done
    ld a,(Flag_X)
    ld b,a
    ld a,(Flag_Y)
    ld c,a
    call Smoke_Enqueue        ; Restore surviving cloud ink after the flag brush.
.done:
    pop hl
    pop de
    pop bc
    pop af
    ret
.inactive:
    pop af
    ret
Smoke_ClearPublishedRow:
    push af
    ld a,(Smoke_Valid)
    or a
    jr z,.inactive
    push bc
    push de
    push hl
    ld a,(Smoke_DrawCode)
    push af
    ld a,(tile_x)
    push af
    xor a
    ld (Smoke_DrawCode),a
    ld b,3
.tile:
    push bc
    call Smoke_RecordDisplay
    pop bc
    ld hl,tile_x
    inc (hl)
    djnz .tile
    pop af
    ld (tile_x),a
    pop af
    ld (Smoke_DrawCode),a
    pop hl
    pop de
    pop bc
    pop af
    ret
.inactive:
    pop af
    ret
Smoke_EnqueueRow:
    ld a,64
    jr Smoke_Enqueue.common
Smoke_Enqueue:
    xor a
.common:
    push af
    ld a,(Smoke_Count)
    or a
    jr z,.append
    ld a,(Smoke_Head)
    ld e,a
    ld d,0
    ld l,a
    ld h,d
    add hl,hl
    add hl,de
    ld de,Smoke_Queue
    add hl,de
    ld a,(Smoke_Count)
    ld d,a
    ld a,(Smoke_Head)
    ld e,a
.find:
    ld a,(hl)
    cp b
    jr nz,.next
    inc hl
    ld a,(hl)
    dec hl
    cp c
    jr nz,.next
    inc hl
    inc hl
    pop af
    bit 6,(hl)
    jr nz,.coalesced
    xor a                    ; An existing full region must stay a full region.
.coalesced:
    ld (hl),a                ; Restart the latest region, including a partial job.
    ret
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
.append:
    ld a,(Smoke_Count)
    cp 32
    jr c,.space
    pop af
    ld a,1
    ld (Smoke_Overflow),a
    ret                      ; Explicit failing diagnostic; never report a lost job as accepted.
.space:
    ld a,(Smoke_Tail)
    ld l,a
    ld h,0
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,Smoke_Queue
    add hl,de
    ld (hl),b
    inc hl
    ld (hl),c
    inc hl
    pop af
    ld (hl),a
    ld a,(Smoke_Tail)
    inc a
    and 31
    ld (Smoke_Tail),a
    ld hl,Smoke_Count
    inc (hl)
    ret

Smoke_CaptureCode:
    ld a,(tile_x)
    ld b,a
    ld a,(tile_y)
    ld c,a
    call Smoke_CodeAtBC
    ld (Smoke_DrawCode),a
    ret
Smoke_CodeAtBC:
    ld a,(Smoke_Valid)
    or a
    jr z,.none
    ld a,(Smoke_Left)
    ld e,a
    ld a,b
    sub e
    cp 32
    jr nc,.none
    ld a,(Smoke_Top)
    ld e,a
    ld a,c
    sub e
    cp 32
    jr nc,.none
    call Smoke_Address
    ld a,(hl)
    ret
.none:
    xor a
    ret
Smoke_Batchable:
    ld a,(Smoke_Valid)
    or a
    ret z
    push bc
    push de
    push hl
    call Smoke_CodeAtBC
    sub $bd
    cp 9
    jr c,.blocked
    ld a,c
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    ld a,(hl)
    or a
    jr z,.safe
    call Smoke_DisplayAddress
    ld a,(hl)
    and 15
    jr nz,.blocked
.safe:
    xor a
    jr .done
.blocked:
    ld a,1
    or a
.done:
    pop hl
    pop de
    pop bc
    ret
Smoke_Source:
    ld a,(Smoke_DrawCode)
    sub $bd
    cp 9
    jr nc,.none
    add a,a
    ld e,a
    ld d,0
    ld hl,Smoke_Sources
    add hl,de
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    scf
    ret
.none:
    or a
    ret
Smoke_RecordDisplay:
    IF SESSION_RUNTIME
    ei                      ; RAM bookkeeping follows a completed VDP packet.
    ENDIF
    ld a,(Smoke_DrawCode)
    sub $bd
    cp 9
    jr c,.smoke
    ld a,(tile_y)
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    ld a,(hl)
    or a
    ret z
    xor a
    jr .address
.smoke:
    inc a
    ld d,a
    ld a,(tile_x)
    and 64
    rlca
    or d
    ld d,a
    ld a,(tile_y)
    and $e0
    rrca
    or d
.address:
    ld d,a
    ld a,(tile_x)
    ld b,a
    ld a,(tile_y)
    ld c,a
    call Smoke_DisplayAddress
    ld a,(hl)
    and 15
    ld e,a
    ld a,d
    and 15
    jr z,.erase
    ld a,e
    or a
    jr nz,.store
    push hl
    ld a,c
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    inc (hl)
    pop hl
.store:
    ld (hl),d
    ret
.erase:
    ld a,e
    or a
    ret z
    push hl
    ld a,c
    and 31
    ld l,a
    ld h,Smoke_DisplayRows/256
    dec (hl)
    pop hl
    ld (hl),0
    ret
Smoke_DisplayAddress:
    ld a,c
    rrca
    rrca
    ld l,a
    and 7
    add a,Smoke_Display/256
    ld h,a
    ld a,l
    and $c0
    ld l,a
    ld a,b
    and 63
    or l
    ld l,a
    ret
Smoke_Stream:
    IF SESSION_RUNTIME
    ei                      ; Queue selection and cloud-row preparation own no latch.
    ENDIF
    ld a,(Smoke_Count)
    or a
    ret z
    ld a,b
    or a
    ret z
    IF !FULL_GAME
    ld a,(Stage_GuardClosed)
    or a
    ret nz
    ENDIF                   ; Visible effects retain their budget after the prefetch guard.
    push bc
    ld a,(Smoke_Head)
    ld l,a
    ld h,0
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,Smoke_Queue
    add hl,de
    push hl
    pop ix
    ld a,(ix+2)
    and $3f
    ld c,0
.row:
    cp 3
    jr c,.column
    sub 3
    inc c
    jr .row
.column:
    add a,(ix+0)
    ld (tile_x),a
    ld a,c
    add a,(ix+1)
    ld (tile_y),a
    ld a,1
    ld (Smoke_StreamCost),a
    IF FULL_GAME
    call Full_TrySmokeCell
    jr c,.grouped
    ENDIF
    call Smoke_TryStreamRow
    jr c,.grouped
    call stage_tile
    inc (ix+2)
    jr .tested
.grouped:
    ld a,(ix+2)
    add a,3
    ld (ix+2),a
.tested:
    ld a,(ix+2)
    bit 6,a
    jr z,.full_region
    cp 67
    jr .completed
.full_region:
    cp 9
.completed:
    jr nz,.remaining
    ld hl,Smoke_Count
    dec (hl)
    ld a,(Smoke_Head)
    inc a
    and 31
    ld (Smoke_Head),a
.remaining:
    pop bc
    ld a,(Smoke_StreamCost)
    ld c,a
    ld a,b
    sub c
    ld b,a
    ret c
    ret z
    jp Smoke_Stream

; Three live adjacent source tiles share one exact 24x8 copy. Partial or
; cleared rows fall back to ordinary terrain copies; no pixels are guessed.
Smoke_TryStreamRow:
    IF SESSION_RUNTIME
    ld a,(Death_DisplayState)
    dec a
    jp z,.no                ; Per-tile source selection gives explosions priority.
    ENDIF
    ld a,b
    cp 3
    jp c,.no
    ld a,(ix+2)
    and $3f
    or a
    jr z,.aligned
    cp 3
    jr z,.aligned
    cp 6
    jp nz,.no
.aligned:
    ld a,(tile_x)
    ld b,a
    ld a,(cache_left)
    ld c,a
    ld a,b
    sub c
    cp STAGE_CACHE_COLUMNS-2
    jp nc,.no
    ld a,(tile_y)
    ld c,a
    ld a,(cache_top)
    ld d,a
    ld a,c
    sub d
    cp 32
    jp nc,.no
    call Smoke_CodeAtBC
    ld (Smoke_RowCode),a
    cp $bd
    jr z,.live
    cp $c0
    jr z,.live
    cp $c3
    jp nz,.no
.live:
    inc b
    call Smoke_CodeAtBC
    ld hl,Smoke_RowCode
    sub (hl)
    cp 1
    jp nz,.no
    inc b
    call Smoke_CodeAtBC
    ld hl,Smoke_RowCode
    sub (hl)
    cp 2
    jp nz,.no
    ld a,(Smoke_RowCode)
    ld (Smoke_DrawCode),a
    call Smoke_Source
    ld a,(tile_x)
    ld (Smoke_RowX),a
    and 31
    ld c,24
    cp 30
    jr c,.width
    neg
    add a,32
    add a,a
    add a,a
    add a,a
    ld c,a
.width:
    ld a,c
    ld (Smoke_RowWidth),a
    ld (stage_command+8),a
    call stage_copy_destination
    ld a,(Smoke_RowWidth)
    cp 24
    jr z,.copied
    ld c,a
    ld a,(stage_command)
    add a,c
    ld (stage_command),a
    ld a,24
    sub c
    ld (stage_command+8),a
    ld a,c
    rrca
    rrca
    rrca
    ld c,a
    ld a,(tile_x)
    add a,c
    ld (tile_x),a
    call stage_copy_destination
.copied:
    ld a,8
    ld (stage_command+8),a
    ld a,(Smoke_RowX)
    ld (tile_x),a
    ld a,(Smoke_RowCode)
    ld (Smoke_DrawCode),a
    ld b,3
.published:
    push bc
    call Smoke_RecordDisplay
    pop bc
    ld hl,tile_x
    inc (hl)
    ld hl,Smoke_DrawCode
    inc (hl)
    djnz .published
    ld a,3
    ld (Smoke_StreamCost),a
    scf
    ret
.no:
    or a
    ret
Smoke_Sources:
    INCBIN "smoke-sources.bin"
