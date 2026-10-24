; Experimental player save-under renderer. All coordinates retain 1:1 scale.
; C700..C73f is private scratch, below the compact-radar cache and IM2 table.
Blit_Valid EQU $c700
Blit_OldX EQU $c701
Blit_OldY EQU $c703
Blit_X EQU $c704
Blit_Y EQU $c706
Blit_Width EQU $c707
Blit_Height EQU $c708
Blit_LinearX EQU $c709
Blit_LinearY EQU $c70b
Blit_Save EQU $c70d
Blit_Code EQU $c70e
Blit_DX EQU $c70f
Blit_DY EQU $c710
Blit_W EQU $c711
Blit_H EQU $c712
Blit_Fast EQU $c713
Blit_ForceSlow EQU $c714
Blit_RoadX EQU $c715
Blit_RoadY EQU $c716
Blit_RoadRows EQU $c717
Blit_Packet EQU $c720

Bitmap_Init:
    xor a
    ld (Blit_Valid),a
    IF PLAYER_FAST_BLITTER
    ld (Blit_Fast),a
    ld (Blit_ForceSlow),a
    ENDIF
    ld (player_patch_work),a ; Sprite sentinel repair no longer reserves guard jobs.
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ; Twelve poses in a 192x16 atlas at (0,640), far from HUD/terrain/SAT.
    ld hl,$8800
    ld a,16
    ld (Blit_H),a
    ld de,$4000
.row:
    vdp_write 14,5
    ld a,e
    out ($99),a
    ld a,d
    out ($99),a
    ld bc,$6098
    otir
    ld a,e
    add a,128
    ld e,a
    jr nc,.next
    inc d
.next:
    ld a,(Blit_H)
    dec a
    ld (Blit_H),a
    jr nz,.row
    IF PLAYER_FAST_BLITTER
    ld hl,$8e00
    ld de,$4800             ; even-X opaque poses at y656,18x16 each
    call Bitmap_FastAtlas
    ld hl,$94c0
    ld de,$5800             ; odd-X opaque poses at y688
    jp Bitmap_FastAtlas
    ENDIF
    ret

    IF PLAYER_FAST_BLITTER
Bitmap_FastAtlas:
    ld a,16
    ld (Blit_H),a
.row:
    vdp_write 14,5
    ld a,e
    out ($99),a
    ld a,d
    out ($99),a
    ld bc,$6c98
    otir
    ld a,e
    add a,128
    ld e,a
    jr nc,.next
    inc d
.next:
    ld a,(Blit_H)
    dec a
    ld (Blit_H),a
    jr nz,.row
    ret
    ENDIF

Bitmap_Restore:
    ld a,(Blit_Valid)
    or a
    ret z
    ld hl,(Blit_OldX)
    ld (Blit_X),hl
    ld a,(Blit_OldY)
    ld (Blit_Y),a
    xor a
    ld (Blit_Save),a
    call Bitmap_BackupParameters
    IF PLAYER_FAST_BLITTER
    ld a,(Blit_Fast)
    or a
    jr z,.copy
    ld a,18
    ld (Blit_Width),a
    ld a,$c0                ; Only certified unchanged road can use a fill.
    ld (Blit_Code),a
.copy:
    ENDIF
    call Bitmap_Rect
    xor a
    ld (Blit_Valid),a
    ret

Bitmap_Draw:
    ld a,(driving)
    or a
    ret z
    IF INCREMENTAL_STAGE >= 3
    ld a,(Death_DisplayState)
    or a
    ret nz
    ENDIF
    ld hl,(world_x)
    ld de,PLAYER_X-8
    add hl,de
    ld (Blit_OldX),hl
    ld (Blit_X),hl
    ld a,(world_y)
    add a,97
    ld (Blit_OldY),a
    ld (Blit_Y),a
    IF PLAYER_FAST_BLITTER
    xor a
    ld (Blit_Fast),a
    call Bitmap_Road
    or a
    jp nz,Bitmap_DrawRoad
    ENDIF
    ld a,1
    ld (Blit_Save),a
    call Bitmap_BackupParameters
    call Bitmap_Rect
    ld hl,(Blit_OldX)
    ld (Blit_X),hl
    ld a,16
    ld (Blit_Width),a
    IF INCREMENTAL_STAGE >= 9
    ld a,(player_drawn)
    ELSE
    ld a,($e077)
    ENDIF
    ld l,a
    ld h,0
    ld de,player_flags
    add hl,de
    ld a,(hl)
    ld (player_index),a
    IF INCREMENTAL_STAGE >= 9
    ld a,(player_drawn)
    ELSE
    ld a,($e077)
    ENDIF
    ld (player_drawn),a
    ld a,(player_index)
    add a,a
    add a,a
    add a,a
    add a,a
    ld l,a
    ld h,0
    ld (Blit_LinearX),hl
    ld hl,640
    ld (Blit_LinearY),hl
    xor a
    ld (Blit_Save),a
    ld a,$98                ; LMMM TIMP: source color zero preserves the maze.
    ld (Blit_Code),a
    call Bitmap_Rect
    ld a,1
    ld (Blit_Valid),a
    ret

    IF PLAYER_FAST_BLITTER
; Conservative whole-tile proof: all nine8x8 tiles around the aligned18x16
; footprint must be static color-zero road. Flags/rocks/walls always fall back
; to exact save-under, including collected-flag locations in the static map.
Bitmap_Road:
    ld a,(Blit_ForceSlow)
    or a
    jr nz,.unsafe
    ld a,(Flag_Jobs)
    or a
    jr nz,.unsafe           ; A collected flag must be fully replaced first.
    ld hl,(Blit_OldX)
    call stage_div8
    ld a,h
    or a
    jr nz,.unsafe
    ld a,l
    cp STAGE_COLUMNS-2
    jr nc,.unsafe
    ld (Blit_RoadX),a
    ld hl,(world_y)
    ld de,97
    add hl,de
    call stage_div8
    ld a,h
    or a
    jr nz,.unsafe
    ld a,l
    cp STAGE_ROWS-2
    jr nc,.unsafe
    ld (Blit_RoadY),a
    ld a,3
    ld (Blit_RoadRows),a
.row:
    ld a,(Blit_RoadY)
    rlca
    ld l,a
    and 1
    add a,PLAYER_ROAD_BANK
    ld ($7000),a
    ld a,l
    rrca
    and $7f
    ld b,a
    srl a
    or $80
    ld h,a
    ld a,b
    and 1
    rrca
    ld b,a
    ld a,(Blit_RoadX)
    or b
    ld l,a
    ld b,3
.column:
    ld a,(hl)
    or a
    jr z,.unsafe
    dec a
    jr z,.road
    push hl
    add a,Flag_DisplayActive&255
    ld l,a                  ; Static owner2..11 maps to logical flag1..10.
    ld h,Flag_DisplayActive/256
    ld a,(hl)
    pop hl
    or a
    jr nz,.unsafe
.road:
    inc hl
    djnz .column
    ld hl,Blit_RoadY
    inc (hl)
    ld hl,Blit_RoadRows
    dec (hl)
    jr nz,.row
    ld a,1
    ret
.unsafe:
    xor a
    ret

Bitmap_DrawRoad:
    ld a,(player_drawn)
    ld l,a
    ld h,0
    ld de,player_flags
    add hl,de
    ld a,(hl)
    ld (player_index),a
    ld l,a
    ld h,0
    add hl,hl
    ld d,h
    ld e,l
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,de               ; index*18, always an even source X
    ld (Blit_LinearX),hl
    ld hl,656
    ld a,(Blit_OldX)
    and 1
    jr z,.phase
    ld hl,688
.phase:
    ld (Blit_LinearY),hl
    ld hl,(Blit_OldX)
    res 0,l
    ld (Blit_X),hl
    ld a,18
    ld (Blit_Width),a
    ld a,16
    ld (Blit_Height),a
    xor a
    ld (Blit_Save),a
    ld a,$d0
    ld (Blit_Code),a
    call Bitmap_Rect
    ld a,1
    ld (Blit_Fast),a
    ld (Blit_Valid),a
    ret
    ENDIF

Bitmap_BackupParameters:
    ld a,(Blit_X)
    and 1
    add a,a
    add a,16
    ld (Blit_Width),a
    ld a,(Blit_X)
    and $fe
    ld (Blit_X),a
    ld a,16
    ld (Blit_Height),a
    ld hl,208
    ld (Blit_LinearX),hl
    ld hl,672
    ld (Blit_LinearY),hl
    ld a,$d0
    ld (Blit_Code),a
    ret

; Split either direction between the 512x256 ring and a linear VRAM rectangle.
; HMMM copies always use even aligned X/width; transparent LMMM allows odd X.
Bitmap_Rect:
    ei
    nop
    xor a
    ld (Blit_DY),a
.row:
    ld a,(Blit_Height)
    ld b,a
    ld a,(Blit_DY)
    ld c,a
    ld a,b
    sub c
    ld b,a
    ld a,(Blit_Y)
    add a,c
    ld e,a
    neg
    jr z,.height
    cp b
    jr nc,.height
    ld b,a
.height:
    ld a,b
    ld (Blit_H),a
    xor a
    ld (Blit_DX),a
.column:
    ld a,(Blit_DX)
    ld c,a
    ld b,0
    ld hl,(Blit_X)
    add hl,bc
    ld a,h
    and 1
    ld h,a
    push hl
    ld a,(Blit_Width)
    sub c
    ld b,a
    ld a,l
    neg
    jr z,.width
    cp b
    jr nc,.width
    ld b,a
.width:
    ld a,b
    ld (Blit_W),a
    ld hl,Blit_Packet
    ld de,Blit_Packet+1
    ld bc,14
    ld (hl),0
    ldir
    pop hl
    ld a,(Blit_Save)
    or a
    ld de,Blit_Packet
    jr nz,.ring
    ld de,Blit_Packet+4
.ring:
    ld a,l
    ld (de),a
    inc de
    inc de
    ld a,(Blit_DY)
    ld b,a
    ld a,(Blit_Y)
    add a,b
    ld (de),a
    inc de
    ld a,h
    ld (de),a
    ld a,(Blit_Save)
    or a
    ld de,Blit_Packet+4
    jr nz,.linear
    ld de,Blit_Packet
.linear:
    ld a,(Blit_DX)
    ld c,a
    ld b,0
    ld hl,(Blit_LinearX)
    add hl,bc
    ex de,hl
    ld (hl),e
    inc hl
    ld (hl),d
    inc hl
    ld a,(Blit_DY)
    ld c,a
    ld de,(Blit_LinearY)
    ex de,hl
    add hl,bc
    ex de,hl
    ld (hl),e
    inc hl
    ld (hl),d
    ld a,(Blit_W)
    ld (Blit_Packet+8),a
    ld a,(Blit_H)
    ld (Blit_Packet+10),a
    ld a,(Blit_Code)
    ld (Blit_Packet+14),a
    di
    call stage_wait_command
    vdp_write 17,32
    ld hl,Blit_Packet
    ld bc,$0f9b
    otir
    ei
    nop
    ld a,(Blit_W)
    ld b,a
    ld a,(Blit_DX)
    add a,b
    ld (Blit_DX),a
    ld b,a
    ld a,(Blit_Width)
    cp b
    jp nz,.column
    ld a,(Blit_H)
    ld b,a
    ld a,(Blit_DY)
    add a,b
    ld (Blit_DY),a
    ld b,a
    ld a,(Blit_Height)
    cp b
    jp nz,.row
    di
    jp stage_wait_command
