 OUTPUT "probe.rom"
 MACRO reg number,value
 ld a,value
 out ($99),a
 ld a,$80+number
 out ($99),a
 ENDM
cx EQU $c000
cy EQU $c002
fx EQU $c004
fy EQU $c005
back EQU $c006
count EQU $c007
maprow EQU $c008
mapcol EQU $c009
speed EQU $c00a
keys EQU $c00b
ready EQU $c00c
frames EQU $c00d
oldcol EQU $c00e
oldrow EQU $c00f
hudptr EQU $c010
dotx EQU $c012
doty EQU $c013
seen EQU $c018
phase EQU $c01d
loaded_phase EQU $c01e
prior_phase EQU $c020
clock_ticks EQU $c022
input_tick EQU $c024
elapsed_ticks EQU $c026
ring_x EQU $c030
ring_y EQU $c031
ring_length EQU $c032
ring_dx EQU $c033
ring_dy EQU $c034
ring_first EQU $c035
ring_rest EQU $c036
ring_target EQU $c038
ring_seen_ptr EQU $c03a
world_ids EQU $d800
ring_pointers EQU $ce00
hud_page EQU $c03e
boundary_ids EQU $c920
names EQU $d400
dotpat EQU $c900
Probe_MarkCount EQU $e100
Probe_Marks EQU $e200
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 in a,($a8)
 rlca
 rlca
 and 3
 ld c,a
 ld b,0
 ld hl,$fcc1
 add hl,bc
 bit 7,(hl)
 jr z,.primary
 ld a,($ffff)
 cpl
 ld b,a
 rlca
 rlca
 and 3
 ld d,a
 ld a,b
 and $fc
 or d
 ld ($ffff),a
.primary:
 in a,($a8)
 and $fc
 or c
 out ($a8),a
 ld a,4
 out ($fc),a
 reg 0,4
 reg 1,$42
 reg 8,$28
 reg 9,$80
main:
 jp main
Probe_RunMarks:
 ld bc,(Probe_MarkCount)
 ld a,b
 or c
 ret z
 ld ix,Probe_Marks
.loop:
 ld l,(ix+0)
 ld h,(ix+1)
 inc ix
 inc ix
 call GameDirty_Mark
 dec bc
 ld a,b
 or c
 jr nz,.loop
 ret
Probe_Baseline:
 di
 call Probe_RunMarks
 call GameDirty_Plan
 call Baseline_Ring_UploadNames
Probe_Baseline_AfterRing:
 call GameDirty_Upload
 jp Probe_Done
Probe_Candidate:
 di
 call Probe_RunMarks
 call GameDirty_Plan
 call Ring_UploadNames
Probe_Candidate_AfterRing:
 call GameDirty_Upload
Probe_Done:
 jp main
; Two bitplanes queue changed physical name cells for each back table.
; No VRAM reads or copies; fixed HUD/edge names are published by the ring first.
GameDirty_Lengths EQU $c096
GameDirty_Mask EQU $c098
GameDirty_Covered EQU $c099
GameDirty_Address EQU $c09a
GameDirty_Bits EQU $2600          ; two128-byte bitsets
GameDirty_Queues EQU $2700        ; two128-byte nonzero-byte queues

GameDirty_Mark:
    ; HL=changed world_ids address; preserve all caller registers.
    push af
    push bc
    push de
    push hl
    push hl
    ld a,l
    and 7
    ld e,a
    ld d,0
    ld hl,GameDirty_Masks
    add hl,de
    ld c,(hl)
    pop hl
    ld a,h
    and 3
    rrca
    rrca
    rrca
    ld d,a
    ld a,l
    srl a
    srl a
    srl a
    or d
    ld b,a
    ld e,a
    ld d,GameDirty_Bits>>8
    ld a,(de)
    or a
    jr nz,.first_present
    ld a,(GameDirty_Lengths)
    ld l,a
    ld h,GameDirty_Queues>>8
    ld (hl),b
    ld hl,GameDirty_Lengths
    inc (hl)
.first_present:
    ld a,(de)
    or c
    ld (de),a
    set 7,e
    ld a,(de)
    or a
    jr nz,.second_present
    ld a,(GameDirty_Lengths+1)
    or $80
    ld l,a
    ld h,GameDirty_Queues>>8
    ld (hl),b
    ld hl,GameDirty_Lengths+1
    inc (hl)
.second_present:
    ld a,(de)
    or c
    ld (de),a
    pop hl
    pop de
    pop bc
    pop af
    ret

GameDirty_Plan:
    ; Prefer one sequential refill when individual writes would cost more.
    xor a
    ld (GameDirty_Covered),a
    ld hl,GameDirty_Lengths
    ld de,seen
    ld a,(back)
    or a
    jr z,.selected
    inc hl
    inc de
    inc de
.selected:
    ld a,(hl)
    or a
    ret z
    cp 24
    jr nc,.full
    ld a,(de)
    cp $ff
    ret nz
.full:
    ld a,$ff
    ld (de),a
    ld (GameDirty_Covered),a
    ret

GameDirty_Upload:
    ld a,(back)
    or a
    ld hl,GameDirty_Lengths
    ld ix,GameDirty_Queues
    ld iy,GameDirty_Bits
    jr z,.selected
    inc hl
    ld ix,GameDirty_Queues+128
    ld iy,GameDirty_Bits+128
.selected:
    ld a,(hl)
    or a
    ret z
    ld b,a
    ld (hl),0
    ld a,(GameDirty_Covered)
    or a
    jr z,.sparse
    push iy
    pop hl
    ld (hl),0
    ld d,h
    ld e,l
    inc de
    ld bc,127
    ldir
    ret
.sparse:
    di
    reg 14,0
    ei
.group:
    ld e,(ix+0)
    inc ix
    ld d,0
    push iy
    pop hl
    add hl,de
    ld a,(hl)
    ld (hl),0
    ld (GameDirty_Mask),a
    ld l,e
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,world_ids
    add hl,de
    ld (GameDirty_Address),hl
.bit:
    ld a,(GameDirty_Mask)
    srl a
    ld (GameDirty_Mask),a
    call c,GameDirty_One
    ld hl,(GameDirty_Address)
    inc hl
    ld (GameDirty_Address),hl
    ld a,(GameDirty_Mask)
    or a
    jr nz,.bit
    djnz .group
    ret

GameDirty_One:
    ld hl,(GameDirty_Address)
    ld a,(mapcol)
    ld e,a
    ld a,l
    and 31
    sub e
    and 31
    cp 1
    ret c
    cp 24
    ret nc
    ld a,h
    and 3
    rlca
    rlca
    rlca
    ld d,a
    ld a,l
    rrca
    rrca
    rrca
    rrca
    rrca
    and 7
    or d
    ld e,a
    ld a,(maprow)
    ld d,a
    ld a,e
    sub d
    and 31
    cp 28
    ret nc
    ld a,(back)
    add a,a
    add a,a
    ld d,a
    ld a,h
    and 3
    or $60
    or d
    ld d,a
    di
    ld a,l
    out ($99),a
    ld a,d
    out ($99),a
    ei
    ld a,(hl)
    out ($98),a
    ret
GameDirty_Masks:
    db 1,2,4,8,16,32,64,128
; Game-only persistent 32x32 name ring. Keep ring.inc unchanged for the camera
; laboratory. Original IDs, HUD names and their VRAM destinations are identical.
Ring_Position:
    ; A=world tile X, C=world tile Y -> HL=original-ID cache address.
    and 31
    ld e,a
    ld a,c
    and 31
    rrca
    rrca
    rrca
    ld l,a
    and 3
    or $d8
    ld h,a
    ld a,l
    and $e0
    or e
    ld l,a
    ld d,$d8
    ret

Ring_RunAddresses:
    ld a,(ring_y)
    ld l,a
    and $80
    rlca
    add a,2
    ld ($7000),a
    ld a,l
    and 127
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(ring_x)
    ld e,a
    ld d,$80
    add hl,de
    push hl
    ld a,(ring_y)
    ld c,a
    ld a,(ring_x)
    call Ring_Position
    ex de,hl
    pop hl
    ret

Ring_LoadRun:
    ; Copy ring_length fresh ROM IDs from (ring_x,ring_y) into the RAM ring.
    call Ring_RunAddresses
    ld a,e
    and 31
    ld c,a
    ld a,32
    sub c
    ld c,a
    ld a,(ring_length)
    cp c
    jr nc,.split
    ld c,a
    ld b,0
    ldir
    ret
.split:
    sub c
    push af
    ld b,0
    ldir
    pop af
    or a
    ret z
    ld c,a
    ld b,0
    ld a,e
    sub 32
    ld e,a
    jr nc,.rest
    dec d
.rest:
    ldir
    ret

Ring_LoadColumns:
    ld a,(maprow)
    ld (ring_y),a
    ld a,(ring_x)
    and 31
    ld b,a
    ld a,(ring_length)
    add a,b
    cp 33
    jr nc,.wrapped
    call Ring_RunAddresses
    call .strides
    ld a,(ring_length)
    ld ixl,a
    ld ixh,32
.fast:
    ld c,ixl
    ld b,0
    ldir
    ld c,iyh
    add hl,bc
    ld a,h
    cp $c0
    jr c,.bank
    sub $40
    ld h,a
    ld a,3
    ld ($7000),a
.bank:
    ex de,hl
    ld c,iyl
    add hl,bc
    ld a,h
    and 3
    or $d8
    ld h,a
    ex de,hl
    dec ixh
    jr nz,.fast
    ret
.wrapped:
    ; Split at the cache row boundary, but walk ROM/cache rows incrementally.
    ; The original per-row Ring_LoadRun recalculated both addresses 32 times.
    call Ring_RunAddresses
    call .strides
    ld a,iyl
    add a,32
    ld iyl,a
    ld a,e
    and 31
    neg
    add a,32
    ld ixl,a
    ld b,a
    ld a,(ring_length)
    sub b
    ld (ring_rest),a
    ld ixh,32
.split_row:
    ld c,ixl
    ld b,0
    ldir
    ld a,e
    sub 32
    ld e,a
    jr nc,.split_rest
    dec d
.split_rest:
    ld a,(ring_rest)
    ld c,a
    ldir
    ld c,iyh
    add hl,bc
    ld a,h
    cp $c0
    jr c,.split_bank
    sub $40
    ld h,a
    ld a,(maprow)
    and $80
    rlca
    xor 3
    ld ($7000),a
.split_bank:
    ex de,hl
    ld c,iyl
    add hl,bc
    ld a,h
    and 3
    or $d8
    ld h,a
    ex de,hl
    dec ixh
    jr nz,.split_row
    ; Preserve the original helper's final ring_y scratch value.
    ld a,(maprow)
    add a,32
    ld (ring_y),a
    ret
.strides:
    ld a,(ring_length)
    ld c,a
    ld a,128
    sub c
    ld iyh,a
    ld a,32
    sub c
    ld iyl,a
    ret

Ring_Prepare:
    ld a,(oldrow)
    cp $ff
    jr z,.full
    ld b,a
    ld a,(maprow)
    sub b
    ld (ring_dy),a
    inc a
    cp 3
    jr nc,.full
    ld a,(oldcol)
    ld b,a
    ld a,(mapcol)
    sub b
    ld (ring_dx),a
    inc a
    cp 3
    jr nc,.full
    ld a,(ring_dx)
    ld b,a
    ld a,(ring_dy)
    or b
    ret z
    ld a,(ring_dx)
    or a
    jr z,.vertical
    ld a,(mapcol)
    ld b,2
    ld c,a
    ld a,(ring_dx)
    cp 1
    ld a,c
    jr nz,.columns
    add a,23
    inc b
.columns:
    ld (ring_x),a
    ld a,b
    ld (ring_length),a
    call Ring_LoadColumns
.vertical:
    ld a,(ring_dy)
    or a
    jr z,.refresh
    ld b,a
    ld a,(maprow)
    inc b
    jr z,.row
    add a,31
.row:
    ld (ring_y),a
    ld a,(mapcol)
    ld (ring_x),a
    ld a,32
    ld (ring_length),a
    call Ring_LoadRun
    jr .refresh
.full:
    ld a,(mapcol)
    ld (ring_x),a
    ld a,32
    ld (ring_length),a
    call Ring_LoadColumns
.refresh:
    ld a,(mapcol)
    ld (oldcol),a
    ld a,(maprow)
    ld (oldrow),a
    ld c,a
    ld a,(mapcol)
    call Ring_Position
    ld ix,boundary_ids
    ld de,ring_pointers
    ld b,28
.ids:
    ld a,l
    ld (de),a
    inc e
    ld a,h
    sub $b8
    ld (de),a
    inc e
    ld a,(hl)
    ld (ix+2),a
    push hl
    ld a,l
    add a,24
    and 31
    ld c,a
    ld a,l
    and $e0
    or c
    ld l,a
    ld (de),a
    inc e
    ld a,h
    sub $b8
    ld (de),a
    inc e
    ld a,(hl)
    ld (ix+0),a
    ld a,l
    inc a
    and 31
    ld c,a
    ld a,l
    and $e0
    or c
    ld l,a
    ld a,(hl)
    ld (ix+1),a
    pop hl
    ld a,l
    add a,32
    ld l,a
    jr nc,.same_page
    inc h
    ld a,h
    and 3
    or $d8
    ld h,a
.same_page:
    inc ix
    inc ix
    inc ix
    djnz .ids
    ret

Ring_Address:
    ; Original-ID cache address -> corresponding inactive name-table address.
    ld a,h
    and 3
    or $20
    ld h,a
    ld a,(back)
    or a
    jr z,.set
    set 2,h
.set:
    jp address

Ring_UploadColumn:
    ; A is an absolute world column; upload original IDs in every physical row.
    ld c,0
    call Ring_Position
    ld e,l
    ld a,(back)
    add a,a
    add a,a
    or $60
    ld d,a
    di
    reg 14,0
    ei
    ld b,32
.row:
    di
    ld a,e
    out ($99),a
    ld a,d
    out ($99),a
    ei
    ld a,(hl)
    out ($98),a
    ld a,l
    add a,32
    ld l,a
    ld e,a
    jr nc,.same_page
    inc h
    inc d
.same_page:
    djnz .row
    ret

Ring_UploadRow:
    ; A is an absolute world row; upload 32 original IDs before HUD overrides.
    ld c,a
    xor a
    call Ring_Position
    push hl
    call Ring_Address
    pop hl
    ld de,32
    jp upload

Ring_UploadNames:
    ld hl,seen
    ld a,(back)
    or a
    jr z,.seen
    inc hl
    inc hl
.seen:
    ld (ring_seen_ptr),hl
    ld a,(hl)
    cp $ff
    jr z,.full
    ld b,a
    ld a,(mapcol)
    sub b
    ld (ring_dx),a
    inc a
    cp 3
    jp nc,GameNameStream_Wide
    inc hl
    ld a,(hl)
    ld b,a
    ld a,(maprow)
    sub b
    ld (ring_dy),a
    inc a
    cp 3
    jp nc,GameNameStream_Wide
    ld a,(ring_dx)
    or a
    jr z,.vertical
    ld b,a
    ld a,(mapcol)
    inc b
    jr z,.left
    add a,23
    jr .column
.left:
    inc a
.column:
    call Ring_UploadColumn
.vertical:
    ld a,(ring_dy)
    or a
    jr z,.ready
    ld b,a
    ld a,(maprow)
    inc b
    jr z,.row
    add a,27
.row:
    call Ring_UploadRow
    jr .ready
.full:
    ld hl,world_ids
    push hl
    call Ring_Address
    pop hl
    ld de,1024
    call upload
.ready:
    ld hl,(ring_seen_ptr)
    ld a,(mapcol)
    ld (hl),a
    inc hl
    ld a,(maprow)
    ld (hl),a
    ; Two edge names, six HUD names and one left-edge name per visible row.
    ld a,(mapcol)
    add a,24
    and 31
    ld b,a
    ld a,32
    sub b
    cp 9
    jr c,.split
    ld a,8
.split:
    ld (ring_first),a
    ld b,a
    ld a,8
    sub b
    ld (ring_rest),a
    ; Dispatch once for the physical row split. DE walks pointer records and
    ; HL walks RAM names directly, including the eight unrolled OUTI writes.
    ; A two-row loop retains the same DI/EI and port-write ordering.
    ld a,(ring_rest)
    add a,a
    ld l,a
    ld h,0
    ld de,Ring_HudTargets
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    push de
    di
    reg 14,0
    ei
    ld a,(back)
    add a,a
    add a,a
    or $40
    ld ixl,a
    ld ixh,14
    ld de,ring_pointers
    ld hl,names
    ld c,$98
    ret

    MACRO game_ring_hud_rows label,first
label:
.row:
    DUP 2
    di
    ld a,(de)
    out ($99),a
    inc e
    ld a,(de)
    or ixl
    out ($99),a
    inc e
    ei
    ld a,(hl)
    out ($98),a
    di
    ld a,(de)
    out ($99),a
    IF first < 8
    and $e0
    ld iyl,a
    ENDIF
    inc e
    ld a,(de)
    or ixl
    out ($99),a
    IF first < 8
    ld iyh,a
    ENDIF
    inc e
    ei
    ld a,l
    add a,24
    ld l,a
    ld b,first
    ; Counts are fixed by this macro. Retain OUTI's pointer/B/port order while
    ; removing only OTIR's five-cycle repeat overhead between output bytes.
    DUP first
    outi
    EDUP
    IF first < 8
    di
    ld a,iyl
    out ($99),a
    ld a,iyh
    out ($99),a
    ei
    ld b,8-first
    DUP 8-first
    outi
    EDUP
    ENDIF
    EDUP
    dec ixh
    jp nz,.row
    ex de,hl             ; Preserve the previous helper's returned pointers.
    ret
    ENDM

    game_ring_hud_rows Ring_Hud8,8
    game_ring_hud_rows Ring_Hud7,7
    game_ring_hud_rows Ring_Hud6,6
    game_ring_hud_rows Ring_Hud5,5
    game_ring_hud_rows Ring_Hud4,4
    game_ring_hud_rows Ring_Hud3,3
    game_ring_hud_rows Ring_Hud2,2
    game_ring_hud_rows Ring_Hud1,1
Ring_HudTargets:
    dw Ring_Hud8,Ring_Hud7,Ring_Hud6,Ring_Hud5
    dw Ring_Hud4,Ring_Hud3,Ring_Hud2,Ring_Hud1
Baseline_Ring_UploadNames:
    ld hl,seen
    ld a,(back)
    or a
    jr z,.seen
    inc hl
    inc hl
.seen:
    ld (ring_seen_ptr),hl
    ld a,(hl)
    cp $ff
    jr z,.full
    ld b,a
    ld a,(mapcol)
    sub b
    ld (ring_dx),a
    inc a
    cp 3
    jr nc,.full
    inc hl
    ld a,(hl)
    ld b,a
    ld a,(maprow)
    sub b
    ld (ring_dy),a
    inc a
    cp 3
    jr nc,.full
    ld a,(ring_dx)
    or a
    jr z,.vertical
    ld b,a
    ld a,(mapcol)
    inc b
    jr z,.left
    add a,23
    jr .column
.left:
    inc a
.column:
    call Ring_UploadColumn
.vertical:
    ld a,(ring_dy)
    or a
    jr z,.ready
    ld b,a
    ld a,(maprow)
    inc b
    jr z,.row
    add a,31
.row:
    call Ring_UploadRow
    jr .ready
.full:
    ld hl,world_ids
    push hl
    call Ring_Address
    pop hl
    ld de,1024
    call upload
.ready:
    ld hl,(ring_seen_ptr)
    ld a,(mapcol)
    ld (hl),a
    inc hl
    ld a,(maprow)
    ld (hl),a
    ; Two edge names, six HUD names and one left-edge name per visible row.
    ld a,(mapcol)
    add a,24
    and 31
    ld b,a
    ld a,32
    sub b
    cp 9
    jr c,.split
    ld a,8
.split:
    ld (ring_first),a
    ld b,a
    ld a,8
    sub b
    ld (ring_rest),a
    ; Dispatch once for the physical row split. DE walks pointer records and
    ; HL walks RAM names directly, including the eight unrolled OUTI writes.
    ; A two-row loop retains the same DI/EI and port-write ordering.
    ld a,(ring_rest)
    add a,a
    ld l,a
    ld h,0
    ld de,Ring_HudTargets
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    push de
    di
    reg 14,0
    ei
    ld a,(back)
    add a,a
    add a,a
    or $40
    ld ixl,a
    ld ixh,14
    ld de,ring_pointers
    ld hl,names
    ld c,$98
    ret


 INCLUDE "/Users/sandersouza/.codex/worktrees/fixed-hud-lab/newrallyx/experiments/fixed-hud/game-name-stream.inc"
address:
    di
    ld a,h
    rlca
    rlca
    and 3
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    and $3f
    or $40
    out ($99),a
    ei
    ret

clock_irq:
    push af
    in a,($99)
    bit 7,a
    jr z,.done
    push hl
    ld hl,(clock_ticks)
    inc hl
    ld (clock_ticks),hl
    pop hl
.done:
    pop af
    ei
    reti
upload:
    ld c,$98
    ld a,d
    or a
    jr z,.tail
.page:
    ld b,0
    otir
    dec d
    jr nz,.page
.tail:
    ld a,e
    or a
    ret z
    ld b,e
    otir
    ret

Probe_End:
 ASSERT $ < $8000
 defs $8000-$,$ff
