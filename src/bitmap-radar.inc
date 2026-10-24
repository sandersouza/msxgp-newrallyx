; Experimental 48x80 opaque radar, deliberately separate from the accepted HUD.
; Both byte phases use HMMM; odd X restores the two outside edge pixels.
; Full save-under copies remain expensive: do not assume raster acceptance.
RadarBitmap_X EQU $c740
RadarBitmap_Y EQU $c742
RadarBitmap_Valid EQU $c743
RadarBitmap_Last EQU $c744
RadarBitmap_Bank EQU $c748
RadarBitmap_Rows EQU $c749
RadarBitmap_Work EQU $c74a
RadarBitmap_Colors EQU $c74c
RadarBitmap_UploadWidth EQU $c74f
RadarBitmap_Flags EQU $c750

BitmapRadar_FrameRestore:
    xor a
    ld (RadarBitmap_Work),a
    call BitmapRadar_Base
    ld a,(RadarBitmap_Work)
    or a
    jr nz,.changed
    ld a,(RadarBitmap_Valid)
    or a
    jr z,.changed
    ld hl,(world_x)
    ld de,RADAR_X-8
    add hl,de
    ld de,(RadarBitmap_X)
    or a
    sbc hl,de
    ld a,h
    or l
    jr nz,.changed
    ld a,(world_y)
    add a,RADAR_Y-BODY_TOP
    ld b,a
    ld a,(RadarBitmap_Y)
    cp b
    jr nz,.changed
    ld a,(hud_enemy_x)
    ld b,a
    ld a,(hud_enemy_y)
    call BitmapRadar_Project
    ld hl,RadarBitmap_Last
    ld a,b
    cp (hl)
    jr nz,.changed
    inc hl
    ld a,c
    cp (hl)
    jr nz,.changed
    ret z
.changed:
    ld a,1
    ld (RadarBitmap_Work),a
    jp BitmapRadar_Restore
BitmapRadar_FrameDraw:
    ld a,(RadarBitmap_Work)
    or a
    ret z
    jp BitmapRadar_Draw

BitmapRadar_Init:
    xor a
    ld (RadarBitmap_Valid),a
    ld hl,RadarBitmap_Flags
    ld de,RadarBitmap_Flags+1
    ld bc,39
    ld (hl),254
    ldir
    ld a,255
    ld hl,RadarBitmap_Last
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    ld a,5
    ld de,$6000             ; mutable bitmap at y704
    call BitmapRadar_Upload
    ld a,6
    ld de,$7800             ; pristine flags/background at y880
    jp BitmapRadar_Upload
BitmapRadar_Upload:
    ld (RadarBitmap_Bank),a
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$8e00
    ld a,24
    ld (RadarBitmap_UploadWidth),a
    push de
    call BitmapRadar_UploadRows
    pop de
    ld a,e
    add a,32                ; shifted 50-pixel phase at X64, same Y
    ld e,a
    ld a,25
    ld (RadarBitmap_UploadWidth),a
    ; The source pointer follows the unshifted 1920 bytes.
    ; Restore the original page after the first upload crosses a 16KiB bank.
    ld a,d
    cp $78
    ld a,5
    jr nz,.bank
    inc a
.bank:
    ld (RadarBitmap_Bank),a
BitmapRadar_UploadRows:
    ld a,80
    ld (RadarBitmap_Rows),a
.row:
    ld a,(RadarBitmap_Bank)
    ld b,14
    call register
    ld a,e
    out ($99),a
    ld a,d
    out ($99),a
    ld a,(RadarBitmap_UploadWidth)
    ld b,a
    ld c,$98
    otir
    ld a,e
    add a,128
    ld e,a
    jr nc,.next
    inc d
    ld a,d
    cp $80
    jr nz,.next
    ld d,$40
    ld a,(RadarBitmap_Bank)
    inc a
    ld (RadarBitmap_Bank),a
.next:
    ld a,(RadarBitmap_Rows)
    dec a
    ld (RadarBitmap_Rows),a
    jr nz,.row
    ret

BitmapRadar_Restore:
    ld a,(RadarBitmap_Valid)
    or a
    ret z
    ld hl,(RadarBitmap_X)
    ld (Blit_X),hl
    ld a,(RadarBitmap_Y)
    ld (Blit_Y),a
    call BitmapRadar_Parameters
    xor a
    ld (Blit_Save),a
    call Bitmap_Rect
    xor a
    ld (RadarBitmap_Valid),a
    ret
BitmapRadar_Draw:
    call BitmapRadar_Base
    call BitmapRadar_Points
    ld hl,(world_x)
    ld de,RADAR_X-8
    add hl,de
    ld (RadarBitmap_X),hl
    ld (Blit_X),hl
    ld a,(world_y)
    add a,RADAR_Y-BODY_TOP
    ld (RadarBitmap_Y),a
    ld (Blit_Y),a
    call BitmapRadar_Parameters
    ld a,1
    ld (Blit_Save),a
    call Bitmap_Rect
    ld hl,(RadarBitmap_X)
    ld (Blit_X),hl
    ld hl,0
    ld (Blit_LinearX),hl
    ld hl,704
    ld (Blit_LinearY),hl
    ld a,48
    ld (Blit_Width),a
    xor a
    ld (Blit_Save),a
    ld a,(Blit_X)
    and 1
    jr z,.even
    ld hl,(Blit_X)
    dec hl
    ld (Blit_X),hl
    ld hl,64
    ld (Blit_LinearX),hl
    ld a,50
    ld (Blit_Width),a
.even:
    ld a,$d0                ; Full bytes, using the matching source phase.
    ld (Blit_Code),a
    call Bitmap_Rect
    ld a,(RadarBitmap_X)
    and 1
    jr z,.done
    ; HMMM's odd phase includes two neighboring pixels. Restore both from the
    ; freshly saved background rather than overwriting the surrounding maze.
    ld a,1
    ld (Blit_Width),a
    ld hl,800
    ld (Blit_LinearY),hl
    ld hl,0
    ld (Blit_LinearX),hl
    ld a,$90
    ld (Blit_Code),a
    call Bitmap_Rect
    ld hl,(Blit_X)
    ld de,49
    add hl,de
    ld (Blit_X),hl
    ld hl,49
    ld (Blit_LinearX),hl
    call Bitmap_Rect
.done:
    ld a,1
    ld (RadarBitmap_Valid),a
    ret
BitmapRadar_Parameters:
    ld a,(Blit_X)
    and 1
    add a,a
    add a,48
    ld (Blit_Width),a
    ld a,(Blit_X)
    and $fe
    ld (Blit_X),a
    ld a,80
    ld (Blit_Height),a
    ld hl,0
    ld (Blit_LinearX),hl
    ld hl,800
    ld (Blit_LinearY),hl
    ld a,$d0
    ld (Blit_Code),a
    ret

; Only the enemy lives in the bitmap. The player's blinking dot remains a
; separate sprite so it never makes the large bitmap dirty by itself.
BitmapRadar_Points:
    ld hl,RadarBitmap_Last
    call BitmapRadar_ClearPoint
    ld a,(hud_enemy_x)
    ld b,a
    ld a,(hud_enemy_y)
    call BitmapRadar_Project
    ld a,b
    ld (RadarBitmap_Last),a
    ld a,c
    ld (RadarBitmap_Last+1),a
    ld a,RED
    jp BitmapRadar_FillPoint

; Rebuild the off-screen base only when the public flag list changes. This
; includes collection, life restart and hidden flags, without sprite cells.
BitmapRadar_Base:
    ld hl,hud_flags
    ld de,RadarBitmap_Flags
    ld b,40
.compare:
    ld a,(de)
    cp (hl)
    jr nz,.changed
    inc hl
    inc de
    djnz .compare
    ret
.changed:
    ld hl,hud_flags
    ld de,RadarBitmap_Flags
    ld bc,40
    ldir
    ld a,1
    ld (RadarBitmap_Work),a
    ld hl,Blit_Packet
    ld de,Blit_Packet+1
    ld bc,14
    ld (hl),0
    ldir
    ld hl,880
    ld (Blit_Packet+6),hl
    ld a,114               ; both phases, including their untouched padding
    ld (Blit_Packet+8),a
    ld a,80
    ld (Blit_Packet+10),a
    ld a,RADAR_BLUE*17
    ld (Blit_Packet+12),a
    ld a,$c0
    ld (Blit_Packet+14),a
    call BitmapRadar_Submit
    ld hl,RadarBitmap_Flags
    ld d,20
.flag:
    push de
    push hl
    ld b,(hl)
    inc hl
    ld a,(hl)
    call BitmapRadar_Project
    ld a,b
    cp 255
    jr z,.next
    call BitmapRadar_PointPacket
    ld hl,(Blit_Packet+6)
    ld de,176
    add hl,de
    ld (Blit_Packet+6),hl
    ld a,WHITE
    ld (Blit_Packet+12),a
    ld a,$80
    ld (Blit_Packet+14),a
    call BitmapRadar_FillPair
.next:
    pop hl
    inc hl
    inc hl
    pop de
    dec d
    jr nz,.flag
    ld hl,0
    ld (Blit_Packet),hl
    ld (Blit_Packet+4),hl
    ld hl,880
    ld (Blit_Packet+2),hl
    ld hl,704
    ld (Blit_Packet+6),hl
    ld hl,114
    ld (Blit_Packet+8),hl
    ld hl,80
    ld (Blit_Packet+10),hl
    ld a,$d0
    ld (Blit_Packet+14),a
    call BitmapRadar_Submit
    ld a,255
    ld (RadarBitmap_Last),a
    ld (RadarBitmap_Last+1),a
    ret

; HL=SAT entry, returned at the following fuel entry. Native eight-tick
; white/black cadence and shifted pattern avoid the Y=216 terminator exactly.
BitmapRadar_Player:
    push hl
    ld a,(hud_player_x)
    ld b,a
    ld a,(hud_player_y)
    call BitmapRadar_Project
    pop hl
    ld a,b
    cp 255
    jr z,.hidden
    ld a,(scroll_y)
    add a,RADAR_Y-1
    add a,c
    jr .position
.hidden:
    ld a,(scroll_y)
    add a,211
.position:
    ld c,116
    cp 216
    jr nz,.safe
    dec a
    ld c,120
.safe:
    ld (hl),a
    inc hl
    ld a,b
    add a,RADAR_X
    ld (hl),a
    inc hl
    ld (hl),c
    inc hl
    ld (hl),0
    inc hl
    push hl
    ld a,(player_native_ticks)
    and 8
    ld a,WHITE
    jr z,.color
    ld a,BLACK
.color:
    or $20
    ld hl,RadarBitmap_Colors
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    ld hl,RadarBitmap_Colors
    IF INCREMENTAL_STAGE >= 9
    ld de,$7400
    ld b,3
    call Sprite_Upload
    ELSE
    vdp_write 14,7
    xor a
    out ($99),a
    ld a,$74
    out ($99),a
    ld bc,$0398
    otir
    ENDIF
    pop hl
    ret
BitmapRadar_Project:
    ; B=x, A=old 58-pixel Y. Preserve the original two-pixel marker dimensions.
    ld l,a
    ld h,0
    ld de,BitmapRadar_YTable
    add hl,de
    ld c,(hl)
    ret
BitmapRadar_ClearPoint:
    ld b,(hl)
    inc hl
    ld c,(hl)
    ld a,b
    cp 255
    ret z
    push bc
    call BitmapRadar_PointPacket
    pop bc
    ld hl,880
    ld e,c
    ld d,0
    add hl,de
    ld (Blit_Packet+2),hl
    ld a,b
    ld (Blit_Packet),a
    ld a,$90
    ld (Blit_Packet+14),a
    call BitmapRadar_Submit
    ld a,(Blit_Packet)
    add a,65
    ld (Blit_Packet),a
    jr BitmapRadar_SecondPoint
BitmapRadar_FillPoint:
    ld e,a
    ld a,b
    cp 255
    ret z
    push de
    call BitmapRadar_PointPacket
    pop de
    ld a,e
    ld (Blit_Packet+12),a
    ld a,$80
    ld (Blit_Packet+14),a
BitmapRadar_FillPair:
    call BitmapRadar_Submit
BitmapRadar_SecondPoint:
    ld a,(Blit_Packet+4)
    add a,65
    ld (Blit_Packet+4),a
    jp BitmapRadar_Submit
BitmapRadar_PointPacket:
    push bc
    ld hl,Blit_Packet
    ld de,Blit_Packet+1
    ld bc,14
    ld (hl),0
    ldir
    pop bc
    ld a,b
    ld (Blit_Packet+4),a
    ld hl,704
    ld e,c
    ld d,0
    add hl,de
    ld (Blit_Packet+6),hl
    ld a,2
    ld (Blit_Packet+8),a
    ld (Blit_Packet+10),a
    ret
BitmapRadar_Submit:
    di
    call stage_wait_command
    vdp_write 17,32
    ld hl,Blit_Packet
    ld bc,$0f9b
    otir
    jp stage_wait_command
BitmapRadar_YTable:
    INCBIN "radar-bitmap-y.bin"
