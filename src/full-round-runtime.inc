Full_IDBank EQU $dfbc
Full_ResourceBank EQU $dfbd
Full_HBank EQU $dfbe
Full_VBank EQU $dfbf
Full_HBytes EQU $dfc0
Full_VBytes EQU $dfc2
Full_VOffset EQU $dfc4
Full_Div3Address EQU $dfc6
Full_Loading EQU $dfc8
Full_Layout EQU $dfc9
Full_Transitions EQU $dfca
Full_RadarFlags EQU $dfd0

Full_CopyCold:
    ld a,PLAYER_BANK
    ld ($7000),a
    ld hl,$a800
    ld de,$f000
    ld bc,Full_LoadEnd-Full_LoadStart
    ldir
    ld de,$c680
    ld bc,Full_EnemyHotEnd-Full_EnemyHotStart
    ldir
    ld de,Full_RadarIRQStart
    ld bc,Full_RadarIRQEnd-Full_RadarIRQStart
    ldir
    xor a
    ld (Full_Loading),a
    ld (Full_Transitions),a
    ld (Full_AttractClock),a
    ld (Full_AttractClock+1),a
    ret

Full_NextRound:
    ld a,4
    ld (Session_State),a
    ld a,1
    ld (Full_Loading),a
    ld hl,Full_Transitions
    inc (hl)
    call show_scene
    xor a
    ld (Session_State),a
    ld (Session_Drawn),a
    ld a,(ticks)
    ld (frame_tick),a
    ret

; E300..E3EF is renderer scratch in the selected-routine build. The original
; bitmap HUD writers are excluded; E3F0 remains the native input byte.
Full_Div3:
    ld l,a
    ld h,$e3
    ld a,(hl)
    ret

; B/C=global tile X/Y. All input registers except AF survive; no bank change.
Full_ObjectAtTile:
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

Full_TileSource:
    ld a,(tile_x)
    ld b,a
    ld a,(tile_y)
    ld c,a
    call Full_ObjectAtTile
    or a
    ret z
    cp 15
    jr z,.rock
    ld e,a
    ld d,0
    ld hl,Flag_DisplayActive
    add hl,de
    ld a,(hl)
    or a
    jr z,.empty
    ld a,e
    cp 9
    ld a,0
    jr c,.kind
    ld a,e
    cp 9
    ld a,27
    jr z,.kind
    ld a,9
    jr .kind
.rock:
    ld a,18
.kind:
    push af
    ld h,0
    ld l,c
    ld de,stage_flower_phase
    add hl,de
    ld a,(hl)
    ld e,a
    add a,a
    add a,e
    ld e,a
    ld a,b
    ld l,a
    ld h,0
    ld bc,stage_flower_phase
    add hl,bc
    ld a,(hl)
    add a,e
    ld e,a
    pop af
    add a,e
    add a,a
    ld l,a
    ld h,0
    ld de,Full_ObjectSources
    add hl,de
    ld a,(hl)
    ld (stage_command),a
    inc hl
    ld a,(hl)
    ld (stage_command+2),a
    scf
    ret
.empty:
    ld a,FLAG_ROW_X
    ld (stage_command),a
    ld a,FLAG_ROW_Y
    ld (stage_command+2),a
    scf
    ret

Full_RestoreFlagCells:
    ld ix,Flag_Records
    ld hl,Flag_Cells
    ld de,Flag_Active+1
    ld b,10
.next:
    ld a,(de)
    or a
    ld a,0
    jr z,.cell
    ld a,(ix+0)
.cell:
    ld (hl),a
    inc hl
    ld a,(de)
    or a
    ld a,0
    jr z,.high
    ld a,(ix+1)
.high:
    ld (hl),a
    inc hl
    inc de
    push de
    ld de,6
    add ix,de
    pop de
    djnz .next
    ret
