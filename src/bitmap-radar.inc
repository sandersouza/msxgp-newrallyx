; Full-copy diagnostic, deliberately separate from the accepted fast renderer.
; This tests the whole 48x80 opaque overlay cost, including terrain restoration.
RadarBitmap_X EQU $c740
RadarBitmap_Y EQU $c742
RadarBitmap_Valid EQU $c743
RadarBitmap_Last EQU $c744
RadarBitmap_Bank EQU $c748
RadarBitmap_Rows EQU $c749
RadarBitmap_Work EQU $c74a

BitmapRadar_FrameRestore:
    xor a
    ld (RadarBitmap_Work),a
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
    ld a,(hud_player_x)
    ld b,a
    ld a,(hud_player_y)
    call BitmapRadar_Project
    ld hl,RadarBitmap_Last+2
    ld a,b
    cp (hl)
    jr nz,.changed
    inc hl
    ld a,c
    cp (hl)
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
    ld bc,$1898
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
    ld a,$90                ; IMP includes palette zero: radar is fully opaque.
    ld (Blit_Code),a
    call Bitmap_Rect
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

; Restore both old marker footprints from the pristine source, then add red
; enemy / black player in that priority order. No game sprites are involved.
BitmapRadar_Points:
    ld hl,RadarBitmap_Last
    call BitmapRadar_ClearPoint
    ld hl,RadarBitmap_Last+2
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
    call BitmapRadar_FillPoint
    ld a,(hud_player_x)
    ld b,a
    ld a,(hud_player_y)
    call BitmapRadar_Project
    ld a,b
    ld (RadarBitmap_Last+2),a
    ld a,c
    ld (RadarBitmap_Last+3),a
    ld a,BLACK
    jp BitmapRadar_FillPoint
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
    jp BitmapRadar_Submit
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
