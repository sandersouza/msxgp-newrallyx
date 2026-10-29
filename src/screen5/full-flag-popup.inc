; A single world-anchored 24x8 award, without occupying any car/radar sprites.
; Erasure regenerates current terrain, never restores a stale saved bitmap.
Full_PopupFrame:
    ei
    nop
    call Full_CacheEnter
    ld a,1
    ld (Full_CacheHeld),a
    ld a,(Popup_Active)
    or a
    jr z,.pending
.erase:
    xor a
    ld (Popup_Column),a
.erase_tile:
    call Full_PopupOwned
    jr nz,.next_erase
    xor a
    ld (Stage_RowBatch),a
    call Popup_RestoreTile
.next_erase:
    ld hl,Popup_Column
    inc (hl)
    ld a,(hl)
    cp 3
    jr c,.erase_tile
    call stage_wait_command
    ei
    nop
    xor a
    ld (Popup_Active),a
.pending:
    ld a,(Popup_Pending)
    or a
    jp z,.exit
    ld a,(Flag_Jobs)
    or a
    jp nz,.exit
    xor a
    ld (Popup_Pending),a
    ld a,(Death_State)
    or a
    jp nz,.exit
    ld a,(Flag_X)
    ld (Popup_X),a
    ld a,(Flag_Y)
    inc a
    ld (Popup_Y),a
    xor a
    ld (Popup_Column),a
.check:
    call Full_PopupOwned
    jp nz,.exit
    ld a,(Popup_Y)
    and 31
    ld h,0
    ld l,a
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(tile_x)
    and 63
    ld e,a
    ld d,0
    add hl,de
    ld de,Smoke_Display
    add hl,de
    ld a,(hl)
    and 15
    jp nz,.exit              ; Smoke owns foreground priority.
    ld hl,Popup_Column
    inc (hl)
    ld a,(hl)
    cp 3
    jr c,.check
    ld a,($e250)
    dec a
    cp 10
    jp nc,.exit
    ld b,a
    ld a,($e023)
    and 1
    jr z,.index
    ld a,10
.index:
    add a,b
    add a,a
    ld e,a
    ld d,0
    ld hl,Popup_Images
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld (Popup_Source),de
    call stage_wait_command
    ei
    nop
    xor a
    ld (Popup_Column),a
    ld (Popup_Age),a
    ld a,(ticks)
    ld (Popup_Tick),a
    ld a,1
    ld (Popup_Active),a       ; IRQ observers may see a partly painted, valid label.
    ld a,4
    ld (Popup_Width),a
    ld a,(Popup_X)
    and 31
    cp 30
    jr nc,.paint
    ld a,12
    ld (Popup_Width),a
    call Full_PopupPaintTile  ; Ordinary flags use eight12-byte rows, not24 four-byte rows.
    jr .exit
.paint:
    call Full_PopupPaintTile
    ld hl,Popup_Column
    inc (hl)
    ld a,(hl)
    cp 3
    jr c,.paint
.exit:
    xor a
    ld (Full_CacheHeld),a
    call Full_CacheLeave
    ei
    ret

; Z iff the physical cell still contains this exact world tile. Also set the
; standard tile coordinates for authoritative terrain regeneration.
Full_PopupOwned:
    ld a,(Popup_X)
    ld b,a
    ld a,(Popup_Column)
    add a,b
    ld (tile_x),a
    ld e,a
    ld a,(Popup_Y)
    ld (tile_y),a
    ld d,a
    call Full_WorldAddress
    ld a,(hl)
    cp e
    ret nz
    inc hl
    ld a,(hl)
    cp d
    ret

Full_PopupPaintTile:
    call Full_PopupOwned
    ld a,e
    and 32
    rrca
    rrca
    rrca
    rrca
    ld b,a
    ld a,d
    and 16
    rrca
    rrca
    rrca
    rrca
    or b
    ld (Popup_Bank),a
    ld a,d
    and 15
    add a,a
    add a,a
    or $40
    ld d,a
    ld a,e
    and 31
    add a,a
    add a,a
    ld e,a
    ld (Popup_Destination),de
    ld a,(Popup_Column)
    add a,a
    add a,a
    ld e,a
    ld d,0
    ld hl,(Popup_Source)
    add hl,de
    ld a,8
    ld (Popup_Rows),a
.row:
    ld de,(Popup_Destination)
    ld a,(Popup_Width)
    ld b,a
    ld a,(Popup_Bank)
    call Full_PopupUpload
    ei                       ; Pixel transfer ended; coordinate arithmetic owns no VDP latch.
    nop
    ld a,12
    ld de,Popup_Width
    ex de,hl
    sub (hl)
    ex de,hl
    ld e,a
    ld d,0
    add hl,de
    push hl
    ld hl,(Popup_Destination)
    ld de,128
    add hl,de
    ld (Popup_Destination),hl
    pop hl
    ld a,(Popup_Rows)
    dec a
    ld (Popup_Rows),a
    jr nz,.row
    ei
    ret

; Dedicated bitmap transfer. Keep the very frequent sprite uploader unchanged;
; IRQ return uses active=2 to resume this stream in its actual bitmap bank.
Full_PopupUpload:
    ld (Sprite_UploadBank),a
    ei
    nop
    ld (Sprite_UploadSource),hl
    ld (Sprite_UploadDestination),de
    ld a,b
    ld (Sprite_UploadCount),a
    ld a,2
    ld (Sprite_UploadActive),a
    di
    ld a,(Sprite_UploadBank)
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,e
    out ($99),a
    ld a,d
    out ($99),a
    ld c,$98
    ei
    nop
    otir
    di
    xor a
    ld (Sprite_UploadActive),a
    ret
