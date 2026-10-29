; Candidate physical rows for the native $e400..$e7ff smoke code ring.
; A row stays a candidate while any native $bd..$c5 cell remains. Placement,
; native cloud clear and flag brushes conservatively mark all three rows;
; viewport retirement marks its single physical row. No native byte changes.
GameSmoke_Rows EQU $2800
GameSmoke_Touched EQU $c0b0
GameSmoke_RowStart EQU $c0b1

GameSmoke_ClearRows:
    ; Called by Smoke_ClearRings before the native rings are cleared. Keep the
    ; old sparse list intact until Game_RingPatch restores its terrain names.
    push af
    push bc
    push de
    push hl
    xor a
    ld (GameSmoke_Touched),a
    ld hl,GameSmoke_Rows
    ld de,GameSmoke_Rows+1
    ld bc,31
    ld (hl),a
    ldir
    ld hl,Game_WorldChanged
    inc (hl)
    ld hl,Game_SmokeChanged
    inc (hl)
    pop hl
    pop de
    pop bc
    pop af
    ret

GameSmoke_MarkRow:
    ; World tile B,C. Preserve AF/BC/DE/HL, including the native flags.
    push af
    push hl
    ld a,c
    sub 10
    and 31
    ld l,a
    ld h,GameSmoke_Rows/256
    ld (hl),1
    ld a,1
    ld (GameSmoke_Touched),a
    pop hl
    pop af
    ret

GameSmoke_MarkCloud:
    ; Top-left world tile B,C. Marking empty rows is harmless and bounded.
    push af
    push bc
    ld b,3
.row:
    call GameSmoke_MarkRow
    inc c
    djnz .row
    pop bc
    pop af
    ret

GameSmoke_BuildCache:
    ; Same sparse record order/content as the full physical-address scan.
    ; Only run after the parent has restored the preceding sparse list.
    ld ix,Game_SmokeList
    ld hl,0
    ld (Game_SmokeCount),hl
    ld a,(GameSmoke_Touched)
    or a
    ret z                    ; Both rings cleared and no subsequent row mark.
    push iy
    ld iy,GameSmoke_Rows
    ld hl,$e400
.row:
    ld a,(iy+0)
    or a
    jr z,.empty_row
    ld a,ixl
    ld (GameSmoke_RowStart),a
    ; Decode the retained world Y once per physical row. Only world X varies
    ; among its live cells; avoid the complete address decoder for each cell.
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
.cell:
    ld a,(hl)
    sub $bd
    cp 9
    jr nc,.skip
    add a,GAME_SMOKE_TILE
    ld (ix+2),a
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
    ld (ix+0),a
    ld (ix+1),c
    ld de,3
    add ix,de
    ld a,(Game_SmokeCount)
    inc a
    ld (Game_SmokeCount),a
    jr nz,.skip
    ld a,(Game_SmokeCount+1)
    inc a
    ld (Game_SmokeCount+1),a
.skip:
    inc hl
    ld a,l
    and 31
    jr nz,.cell
    ; At most 32 records * 3 bytes: the low pointer byte can wrap once, but
    ; cannot return to its starting value unless the row produced no records.
    ld a,(GameSmoke_RowStart)
    xor ixl
    jr nz,.next_row
    ld (iy+0),0
    jr .next_row
.empty_row:
    ld de,32
    add hl,de
.next_row:
    inc iy
    ld a,h
    cp $e8
    jr nz,.row
    pop iy
    ret
