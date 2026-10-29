 OUTPUT "probe.rom"
Game_SmokeList EQU $0800
Game_SmokeCount EQU $c082
Game_WorldChanged EQU $c080
Game_SmokeChanged EQU $c051
GAME_SMOKE_TILE EQU $d0
Flag_X EQU $c510
Flag_Y EQU $c511
 ORG $4000
 db "AB"
 dw boot,0,0,0,0,0,0
boot:
 di
 ld sp,$f380
 ; Map independent Page0 RAM using the active Page3 primary/subslot.
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
main:
 jp main
Smoke_EnqueueRow:
 jp GameSmoke_MarkRow
Smoke_Enqueue:
 jp GameSmoke_MarkCloud
Probe_NoHook:
 ret
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
Smoke_HeldFrames EQU $c71d    ; temporal concession; never hide stale terrain

; A native refresh moves less than one tile. Retain a final guard tile rather
; than presenting an unfinished row/column; simulation and its clocks hold
; together, while the renderer continues draining the existing hidden jobs.
Smoke_ClearRings:
    call GameSmoke_ClearRows
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
    ret

; Called before $0069 changes world coordinates. The physical coordinates and
; camera fine offsets still describe this origin during smoke/expiry helpers.
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
GameSmoke_Baseline:
    ld ix,Game_SmokeList
    ld hl,0
    ld (Game_SmokeCount),hl
    ld hl,$e400
.next:
    ld a,(hl)
    sub $bd
    cp 9
    jr nc,.skip
    add a,GAME_SMOKE_TILE
    push hl
    push af
    call Smoke_DecodeAddress
    ld (ix+0),b
    ld (ix+1),c
    pop af
    ld (ix+2),a
    ld de,3
    add ix,de
    ld hl,(Game_SmokeCount)
    inc hl
    ld (Game_SmokeCount),hl
    pop hl
.skip:
    inc hl
    ld a,h
    cp $e8
    jr nz,.next
    ret

 INCLUDE "/Users/sandersouza/Developer/msx-gamePorts/newrallyx/references/experiments/stage-one-3-enemies/baseline-a5d318eb/adapter-source/game-smoke-cache.inc"
Probe_End:
 ASSERT $ < $8000
 defs $8000-$,$ff
