; Cold preparation executes with PLAYER_BANK mapped. Native object tables keep
; original world-cell identifiers, while their RAM pointers are relocated.
Full_PrepareFirst:
    jp Full_FirstBody
Full_PrepareNext:
    jp Full_NextBody
Full_PrepareRestore:
    jp Full_RestoreBody
Full_FirstBody:
    xor a
    ld (Full_Player),a
    ld a,(Full_Players)
    or a
    jr z,.seed_ready
    ld hl,Session_High
    ld de,$e060
    ld bc,8
    ldir                    ; Retained record is visible on the first gameplay header.
.seed_ready:
    ld hl,1
    ld ($e000),hl
    ld a,1
    ld ($e1b0),a
Full_NextBody:
    call $88bf
Full_RestoreBody:
    call $88e7              ; Selected player owns the refilled fuel/phase state.
    call $9b1f              ; Rebuild its map/colors before choosing renderer banks.
    call $ac00
    ld hl,$e300
    ld b,80
    xor a
.div3:
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    ld (hl),a
    inc l
    inc a
    djnz .div3
    ld ix,($e992)
    ld iy,$df80
    ld b,10
    ld c,0
.flag:
    ld l,(ix+0)
    ld h,(ix+1)
    ld (iy+0),l
    ld (iy+1),h
    ld a,1
    cp b
    jr nz,.not_special
    ld a,2
    jr .kind
.not_special:
    ld a,b
    cp 2
    ld a,1
    jr nz,.kind
    ld a,4
.kind:
    ld (iy+2),a
    ld (iy+3),c
    ld a,l
    and 31
    ld e,a
    add a,a
    add a,e
    add a,3
    ld (iy+4),a
    ld a,h
    sub $98
    add a,a
    add a,a
    add a,a
    ld e,a
    ld a,l
    rlca
    rlca
    rlca
    and 7
    or e
    ld e,a
    add a,a
    add a,e
    add a,3
    ld (iy+5),a
    push bc
    ld a,(ix+0)
    and 31
    ld e,a
    ld d,0
    ld hl,Full_FlagRadarX
    add hl,de
    ld a,(hl)
    push af
    ld a,(ix+0)
    rlca
    rlca
    rlca
    and 7
    ld e,a
    ld a,(ix+1)
    sub $98
    add a,a
    add a,a
    add a,a
    or e
    ld e,a
    ld d,0
    ld hl,Full_FlagRadarY
    add hl,de
    ld e,(hl)
    pop af
    ld d,a
    ld a,c
    add a,a
    add a,Full_RadarFlags & 255
    ld l,a
    ld h,Full_RadarFlags/256
    ld (hl),d
    inc hl
    ld (hl),e
    pop bc
    inc ix
    inc ix
    ld de,6
    add iy,de
    inc c
    dec b
    jp nz,.flag
    ld a,($e28f)
    and 3
    ld (Full_Layout),a
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,de
    ld de,Full_ProfileRecords
    add hl,de
    ld de,Full_IDBank
    ld bc,12
    ldir
    ld a,(Full_Layout)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Full_WideProfiles
    add hl,de
    ld de,Full_WideHBank
    ld bc,8
    ldir
    ld a,1
    ld ($e28b),a
    ld ($e020),a
    xor a
    ld ($e2d0),a
    ld (Round_State),a
    ld (Completion_BonusState),a
    ld (Full_Loading),a
    ld a,(Full_Attract)
    or a
    ret z
    xor a
    ld ($e020),a
    ld ($e021),a
    inc a
    ld ($e00f),a
    ret
Full_ProfileRecords:
    INCBIN "full-profiles.bin"

Full_FlagRadarX:
    INCBIN "full-flag-radar-x.bin"
Full_FlagRadarY:
    INCBIN "full-flag-radar-y.bin"
Full_WideProfiles:
    INCBIN "full-wide-profiles.bin"
