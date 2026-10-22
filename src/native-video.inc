; Live original tile RAM -> SCREEN 5. Guest memory is never used as scratch.
    INCLUDE "native-video-config.inc"
    INCLUDE "hud-state.inc"
    MACRO vdp_write number,value
    ld a,value
    out ($99),a
    ld a,$80+number
    out ($99),a
    ENDM
    INCLUDE "hud-raster.inc"
ticks EQU $c00a
scroll_high EQU $c01a
scroll_low EQU $c01b
scroll_y EQU $c01c
Native_RenderSP EQU $c780
Native_RenderDue EQU $c782
Native_RasterPhase EQU $c783
Native_RenderFrames EQU $c784
Native_DirtyCursor EQU $c786
Native_TileIndex EQU $c788
Native_TileCode EQU $c78a
Native_TileAttr EQU $c78b
Native_TileBudget EQU $c78c
Native_ActiveY EQU $c78d
Native_ActiveHigh EQU $c78e
Native_ActiveLow EQU $c78f
Native_HUDReady EQU $c790
Native_DirtyAllPending EQU $c791
Native_HUDValid EQU $c792
Native_FrameMapped EQU $c793
Native_TileBlack EQU $c794
Native_ScanBudget EQU $c795
Native_DrawPage EQU $c796
Native_ActiveR2 EQU $c797
Native_PendingR2 EQU $c798
Native_PageInitialized EQU $c799
Native_TileSlot EQU $c79a
Native_PageRunPixels EQU $c79b
Native_PageRunFirst EQU $e62b
Native_PageRunHigh EQU $e62d
Native_LastRenderTick EQU $c79c
Native_PageDirty0 EQU $c880
Native_PageDirty1 EQU $cd00
Native_LifeSAT EQU $c7a0
Native_HUDPointers EQU $c7b0
Native_HUDValues EQU $c7b6
Native_TileTags EQU $e000
Native_TileValid EQU $e100
Native_TileCodes EQU $e700
Native_ShadowCodes EQU $c900
Native_ShadowAttrs EQU $e800
Native_ShadowBlack EQU $ec00
Native_PackedBuffer EQU $e400
Native_PixelBuffer EQU $e500
Native_DirtyTiles EQU $c800
Native_Command EQU $c460

Native_VideoInit:
    ld hl,$c000
    ld de,$c001
    ld bc,$473
    ld (hl),0
    ldir
    ld hl,$c780
    ld de,$c781
    ld bc,$ff
    ld (hl),0
    ldir
    ld hl,$ffff
    ld (Native_InputCache),hl
    ld a,$c3
    ld (Native_InputCache+2),a
    ld hl,$e000
    ld de,$e001
    ld bc,$fff
    ld (hl),0
    ldir
    ld hl,Native_ShadowCodes
    ld de,Native_ShadowCodes+1
    ld bc,1023
    ld (hl),$ff                 ; FF is always drawn, never an uninitialized hit
    ldir
    ld hl,Native_ShadowBlack
    ld de,Native_ShadowBlack+1
    ld bc,1023
    ld (hl),BLACK               ; boot HMMV creates a known opaque black surface
    ldir
    ld hl,Native_PageDirty0
    ld de,Native_PageDirty0+1
    ld bc,127
    ld (hl),0
    ldir
    ld hl,Native_PageDirty1
    ld de,Native_PageDirty1+1
    ld bc,127
    ld (hl),0
    ldir
    ld a,$1f
    ld (Native_ActiveR2),a
    vdp_write 0,6
    vdp_write 1,2
    vdp_write 7,BLACK
    vdp_write 8,$2a
    vdp_write 18,0
    vdp_write 16,0
    ld hl,Native_Palette
    ld bc,$209a
    otir
    vdp_write 5,$ef
    vdp_write 11,3
    vdp_write 6,$3f
    vdp_write 25,0
    vdp_write 26,0
    vdp_write 27,0
    vdp_write 23,0
    ; Clear all four bitmap pages with the real VDP command engine.
    ld hl,Native_ClearCommand
    ld de,Native_Command
    ld bc,15
    ldir
    call Native_SendCommand
    call Native_WaitCommand
    call HUD_Init
    call HUD_Prime
    call Native_RestoreGame
    call Native_WarmTiles
    call Native_MarkAllTiles
    vdp_write 2,$7f
    vdp_write 19,7
    vdp_write 0,$16
    vdp_write 1,$62
    ret

Native_ClearCommand:
    db 0,0,0,0,0,0,0,0,0,1,0,4,BLACK*17,0,$c0

; Called after the full host IRQ save. Return A=1 only for a real VBlank.
Native_RasterIRQ:
    vdp_write 15,1
    in a,($99)
    and 1
    jp z,.vertical
    ld a,(Native_RasterPhase)
    or a
    jr nz,.later
    vdp_write 1,$22
    vdp_write 8,$28
    vdp_write 0,6
    vdp_write 25,2
    vdp_write 26,(Native_ActiveHigh)
    vdp_write 27,(Native_ActiveLow)
    vdp_write 23,(Native_ActiveY)
    vdp_write 2,(Native_ActiveR2)
    vdp_write 1,$62
    ld a,(Native_ActiveY)
    add a,64
    ld b,19
    call register
    vdp_write 0,$16
    ld a,1
    ld (Native_RasterPhase),a
    jr .line_done
.later:
    cp 1
    jr nz,.footer
    ld a,(Native_ActiveY)
    add a,LIFE_SPLIT
    ld b,19
    call register
    ld a,2
    ld (Native_RasterPhase),a
    jr .line_done
.footer:
    HUD_FooterSprites
    ld a,3
    ld (Native_RasterPhase),a
.line_done:
    vdp_write 15,0
    xor a
    ret
.vertical:
    vdp_write 15,0
    in a,($99)
    and $80
    ret z
    push hl
    ld a,(Native_HUDReady)
    or a
    jr z,.no_hud
    ld a,(scroll_y)
    ld (Native_ActiveY),a
    ld a,(scroll_high)
    ld (Native_ActiveHigh),a
    ld a,(scroll_low)
    ld (Native_ActiveLow),a
    ld a,(Native_PendingR2)
    ld (Native_ActiveR2),a
    push de
    ld hl,life_sat
    ld de,Native_LifeSAT
    ld bc,12
    ldir
    pop de
    vdp_write 14,7
    xor a
    out ($99),a
    ld a,$76
    out ($99),a
    ld hl,sat
    ld bc,SAT_BYTES*256+$98
    otir
    xor a
    ld (Native_HUDReady),a
.no_hud:
    HUD_VBlankSprites
    vdp_write 8,$2a
    vdp_write 25,0
    vdp_write 26,0
    vdp_write 27,0
    vdp_write 23,0
    vdp_write 2,$7f
    vdp_write 19,7
    vdp_write 0,$16
    vdp_write 1,$62
    xor a
    ld (Native_RasterPhase),a
    inc a
    ld (Native_RenderDue),a
    ld hl,ticks
    inc (hl)
    pop hl
    ld a,1
    ret

    INCLUDE "native-presentation.inc"

; Revalidate only when a native pointer/value changes. Cache only after the
; shared validator accepts every pointer and digit; no game data is modified.
Native_SyncHUD:
    ld a,(Native_HUDValid)
    or a
    jr z,.sync
    ld hl,$8990
    ld de,Native_HUDPointers
    ld b,2
    call .equal
    jr nz,.sync
    ld hl,$8988
    ld de,Native_HUDPointers+2
    ld b,2
    call .equal
    jr nz,.sync
    ld hl,$898e
    ld de,Native_HUDPointers+4
    ld b,2
    call .equal
    jr nz,.sync
    ld hl,(Native_HUDPointers)
    ld de,Native_HUDValues
    ld b,8
    call .equal
    jr nz,.sync
    ld hl,$8060
    ld de,Native_HUDValues+8
    ld b,8
    call .equal
    jr nz,.sync
    ld hl,(Native_HUDPointers+2)
    ld a,(Native_HUDValues+16)
    cp (hl)
    jr nz,.sync
    ld hl,(Native_HUDPointers+4)
    ld de,Native_HUDValues+17
    ld b,2
    call .equal
    ret z
.sync:
    ld hl,$8000
    call HUD_SyncNative
    ret c
    ld hl,($8990)
    ld (Native_HUDPointers),hl
    ld de,Native_HUDValues
    ld bc,8
    ldir
    ld hl,$8060
    ld bc,8
    ldir
    ld hl,($8988)
    ld (Native_HUDPointers+2),hl
    ld a,(hl)
    ld (de),a
    inc de
    ld hl,($898e)
    ld (Native_HUDPointers+4),hl
    ld bc,2
    ldir
    ld a,1
    ld (Native_HUDValid),a
    ret
.equal:
    ld a,(de)
    cp (hl)
    ret nz
    inc hl
    inc de
    djnz .equal
    ret

Native_ReadFrameTile:
    ld hl,(Native_TileIndex)
    ; The cooperative step owns the asset-3 snapshot in page 0. Page 2 can
    ; independently borrow graphics resources without remapping every cell.
    ld de,$2000
    add hl,de
    ld a,(hl)
    ld (Native_TileCode),a
    ld de,$400
    add hl,de
    ld a,(hl)
    ld (Native_TileAttr),a
    ret

Native_DrawTile:
    call Native_ReadFrameTile
    ld hl,(Native_TileIndex)
    ld de,Native_ShadowCodes
    add hl,de
    ld a,(Native_TileCode)
    cp $ff
    jr z,.check_black
    cp (hl)
    jr nz,.check_black
    ld hl,(Native_TileIndex)
    ld de,Native_ShadowAttrs
    add hl,de
    ld a,(Native_TileAttr)
    cp (hl)
    jr nz,.check_black
    or a
    ret
.check_black:
    call Native_ClassifyTile
    cp $ff
    jr z,.draw
    ld hl,(Native_TileIndex)
    ld bc,Native_ShadowBlack
    add hl,bc
    cp (hl)
    jp nz,Native_DrawSolidRun
    call Native_RecordTile
    or a
    ret
.draw:
    ; Keep the common 32 maze codes x four flips x two palettes simultaneously.
    ; Full descriptors are still checked, so other codes/palettes may collide
    ; safely without ever reusing pixels from the wrong source pattern.
    ld a,(Native_TileAttr)
    and $c0
    rrca
    ld l,a
    ld a,(Native_TileAttr)
    and 2
    rrca
    rrca
    or l
    ld l,a
    ld a,(Native_TileCode)
    and 31
    or l
    ld (Native_TileSlot),a
    ld e,a
    ld d,Native_TileCodes/256
    ld a,(Native_TileCode)
    ld l,a
    ld a,(de)
    cp l
    jr nz,.upload
    ld a,(Native_TileAttr)
    ld l,a
    ld d,Native_TileTags/256
    ld a,(de)
    cp l
    jr nz,.upload
    inc d
    ld a,(de)
    or a
    jr nz,.cached
.upload:
    call Native_UploadTile
.cached:
    ld hl,Native_TileCommand
    ld de,Native_Command
    ld bc,15
    ldir
    ld a,(Native_TileSlot)
    and 31
    add a,a
    add a,a
    add a,a
    ld (Native_Command),a
    ld a,(Native_TileSlot)
    and $e0
    rrca
    rrca
    add a,16
    ld (Native_Command+2),a
    ld hl,(Native_TileIndex)
    ld a,l
    and 31
    add a,a
    add a,a
    add a,a
    ld (Native_Command+4),a
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,h
    add a,a
    add a,a
    add a,a
    ld (Native_Command+6),a
    ld a,2
    ld (Native_Command+7),a ; clean page2
    call Native_SendCommand
    call Native_DirtyBothPages
    call Native_RecordTile
    scf
    ret
Native_TileCommand:
    db 0,0,16,3,0,0,0,2,8,0,8,0,0,0,$d0

; Clean cache changes remain pending separately for each display page.
Native_DirtyBothPages:
    ld hl,(Native_TileIndex)
    ld a,l
    and 7
    ld b,a
    ld c,1
    jr z,.mask
.shift:
    sla c
    djnz .shift
.mask:
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l
    add a,$80
    ld l,a
    ld h,Native_PageDirty0/256
    ld a,c
    or (hl)
    ld (hl),a
    ld a,l
    sub $80
    ld l,a
    ld h,Native_PageDirty1/256
    ld a,c
    or (hl)
    ld (hl),a
    ret

Native_SyncPage:
    ld a,1                    ; the next cooperative entry observes GPU completion
    ld (Native_ScanBudget),a
    ld a,(Native_DrawPage)
    ld c,a
    inc a
    ld b,a
    ld a,(Native_PageInitialized)
    and b
    jr nz,.incremental
    ld a,(Native_PageInitialized)
    or b
    ld (Native_PageInitialized),a
    ld hl,Native_PageCommand
    ld de,Native_Command
    ld bc,15
    ldir
    ld a,(Native_DrawPage)
    ld (Native_Command+7),a
    call Native_SendCommand
    call .bitmap
    ld b,128
    xor a
.clear:
    ld (hl),a
    inc hl
    djnz .clear
    ret
.incremental:
    call .bitmap
    ld b,128
.find:
    ld a,(hl)
    or a
    jr nz,.dirty
    inc hl
    djnz .find
    ret
.dirty:
    push bc
    push hl
    ld c,0
.bit:
    rrca
    jr c,.found
    inc c
    jr .bit
.found:
    ld a,1
    ld b,c
    inc b
.shift:
    rlca
    djnz .shift
    rrca
    ld d,a
    ld e,0
    ld (Native_PageRunFirst),hl
.run:
    ld a,(hl)
    and d
    jr z,.run_done
    ld a,d
    cpl
    and (hl)
    ld (hl),a
    inc e
    sla d
    jr nz,.run
    ld a,l
    and 3
    cp 3
    jr z,.run_done            ; never merge past this 32-tile row
    inc hl
    ld d,1
    jr .run
.run_done:
    ld a,e
    add a,a
    add a,a
    add a,a
    ld (Native_PageRunPixels),a
    ld a,0
    adc a,0
    ld (Native_PageRunHigh),a
    ld hl,(Native_PageRunFirst)
    ld a,l
    and 127
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld b,0
    add hl,bc
    ld (Native_TileIndex),hl
    ld hl,Native_PageTileCommand
    ld de,Native_Command
    ld bc,15
    ldir
    ld hl,(Native_TileIndex)
    ld a,l
    and 31
    add a,a
    add a,a
    add a,a
    ld (Native_Command),a
    ld (Native_Command+4),a
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,h
    add a,a
    add a,a
    add a,a
    ld (Native_Command+2),a
    ld (Native_Command+6),a
    ld a,(Native_DrawPage)
    ld (Native_Command+7),a
    ld a,(Native_PageRunPixels)
    ld (Native_Command+8),a
    ld a,(Native_PageRunHigh)
    ld (Native_Command+9),a
    call Native_SendCommand
    pop hl
    pop bc
    ld a,(Native_ScanBudget)
    dec a
    ld (Native_ScanBudget),a
    jp nz,.find
    scf
    ret
.bitmap:
    ld hl,Native_PageDirty0
    ld a,(Native_DrawPage)
    or a
    ret z
    ld hl,Native_PageDirty1
    ret
Native_PageCommand:
    db 0,0,0,2,0,0,0,0,0,1,0,1,0,0,$d0
Native_PageTileCommand:
    db 0,0,0,2,0,0,0,0,8,0,8,0,0,0,$d0

Native_RecordDescriptors:
    ld hl,(Native_TileIndex)
    ld bc,Native_ShadowCodes
    add hl,bc
    ld a,(Native_TileCode)
    ld (hl),a
    ld hl,(Native_TileIndex)
    ld bc,Native_ShadowAttrs
    add hl,bc
    ld a,(Native_TileAttr)
    ld (hl),a
    ret
Native_RecordTile:
    call Native_RecordDescriptors
    ld hl,(Native_TileIndex)
    ld bc,Native_ShadowBlack
    add hl,bc
    ld a,(Native_TileBlack)
    ld (hl),a
    ret

Native_UploadTile:
    call Native_WaitCommand
    ; Capture descriptors before mapping page2 to the packed source bank.
    ld a,(Native_TileCode)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(Native_TileAttr)
    xor $40
    and $c0
    rrca
    rrca
    or l
    ld l,a
    set 7,h
    xor a
    call Native_HUDMapAssets
    ld de,Native_PackedBuffer
    ld bc,16
    ldir
    call Native_RestoreGame
    ld a,(Native_TileAttr)
    and 63
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Native_Lookup
    add hl,de
    ld de,Native_PixelBuffer
    ld ix,Native_PackedBuffer
    ld b,16
.convert:
    ld a,(ix+0)
    rrca
    rrca
    rrca
    rrca
    and 15
    call .pair
    ld a,(ix+0)
    and 15
    call .pair
    inc ix
    djnz .convert
    ; Atlas: 256 8x8 slots, starting at bitmap line784 (0x18800).
    ld a,(Native_TileSlot)
    ld c,a
    and 31
    add a,a
    add a,a
    ld e,a
    ld a,c
    and $e0
    rrca
    rrca
    add a,16
    ld d,a
    ld hl,Native_PixelBuffer
    ld a,8
.row:
    push af
    ld a,6
    ld (Native_HUDWriteBank),a
    ld a,d
    rrca
    and $80
    or e
    ld (Native_HUDWriteAddress),a
    ld a,d
    rrca
    and $3f
    ld (Native_HUDWriteAddress+1),a
    ld bc,$0498
    call Native_HUDOTIR
    inc d
    pop af
    dec a
    jr nz,.row
    ld a,(Native_TileSlot)
    ld l,a
    ld h,Native_TileTags/256
    ld a,(Native_TileAttr)
    ld (hl),a
    inc h
    ld (hl),1
    ld h,Native_TileCodes/256
    ld a,(Native_TileCode)
    ld (hl),a
    ret
.pair:
    push hl
    add a,l
    ld l,a
    jr nc,.no_carry
    inc h
.no_carry:
    ld a,(hl)
    ld (de),a
    inc de
    pop hl
    ret

; Preload the common maze alphabet in all flips and both live maze palettes.
; This is a graphics-resource cache, independent of any captured game state.
Native_WarmTiles:
    xor a
    ld (Native_TileSlot),a
.slot:
    ld a,(Native_TileSlot)
    and 31
    or $80
    ld (Native_TileCode),a
    ld a,(Native_TileSlot)
    and $60
    add a,a
    ld b,a
    ld a,(Native_TileSlot)
    and $80
    ld a,$0d
    jr z,.palette
    ld a,$16
.palette:
    or b
    ld (Native_TileAttr),a
    call Native_UploadTile
    ld a,(Native_TileSlot)
    inc a
    ld (Native_TileSlot),a
    jr nz,.slot
    ret

Native_MarkTileDE:
    ex de,hl
    call Native_MarkTileHL
    ex de,hl
    ret
Native_MarkTileHL:
    push af
    ld a,h
    and $f4
    cp $84
    jr nz,.done
    push bc
    push de
    push hl
    ld a,l
    and 7
    ld b,a
    ld c,1
    jr z,.mask_done
.shift:
    sla c
    djnz .shift
.mask_done:
    ld a,h
    and 3
    ld h,a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld h,Native_DirtyTiles/256
    ld a,c
    or (hl)
    ld (hl),a
    pop hl
    pop de
    pop bc
.done:
    pop af
    ret
Native_MarkTileRange:
    push af
    push bc
    push de
    push hl
    ; Mark only intersected groups of eight cells, including partial ends.
    ; The renderer checks complete descriptors, so the at-most-seven extra
    ; cells at either end do not cause pixels to be guessed or changed.
    ld a,b
    or c
    jr z,.all
    ld h,d
    ld l,e
    add hl,bc
    jr c,.all
    ex de,hl                  ; HL=start, DE=exclusive end
.loop:
    ld a,h
    cp d
    jr c,.inside
    jr nz,.done
    ld a,l
    cp e
    jr nc,.done
.inside:
    ld a,h
    cp $84
    jr nc,.codes
    ld hl,$8400
    jr .loop
.codes:
    cp $88
    jr c,.mark
    cp $8c
    jr nc,.attrs
    ld hl,$8c00
    jr .loop
.attrs:
    cp $90
    jr nc,.done
.mark:
    push hl
    ld a,h
    and 3
    ld h,a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld h,Native_DirtyTiles/256
    ld (hl),$ff
    pop hl
    ld a,l
    and $f8
    add a,8
    ld l,a
    jr nc,.loop
    inc h
    jr .loop
.all:
    call Native_RequestAllTiles
.done:
    pop hl
    pop de
    pop bc
    pop af
    ret
Native_MarkAllTiles:
    push af
    push bc
    push de
    push hl
    ld hl,Native_DirtyTiles
    ld de,Native_DirtyTiles+1
    ld bc,127
    ld (hl),$ff
    ldir
    pop hl
    pop de
    pop bc
    pop af
    ret
Native_RequestAllTiles:
    push af
    ld a,1
    ld (Native_DirtyAllPending),a
    pop af
    ret

Native_HUDMapAssets:
    push af
    call Native_RestoreGame
    pop af
    jp Native_MapAssets
Native_WaitCommand:
.busy:
    call Native_VDPWindow
    di
    vdp_write 15,2
    in a,($99)
    push af
    vdp_write 15,0
    pop af
    call Native_RenderEI
    and 1
    jr nz,.busy
    ret
Native_SendCommand:
    call Native_WaitCommand
    call Native_VDPWindow
    di
    vdp_write 17,32
    call Native_RenderEI    ; raster handlers never alter the indirect R17 cursor
    ld hl,Native_Command
    ld bc,$0f9b
    otir
    call Native_RenderEI
    ret
Native_VDPWindow:
    ; Each caller sets the complete VRAM address or command packet under DI.
    ; Host raster handlers may replace the VDP pointer between packets. The
    ; inactive bitmap/atlas writes are also safe during vertical blanking;
    ; waiting for the next body line here would block original game execution.
    ret
Native_RenderEI:
    push af
    ld a,(Native_ClockMode)
    or a
    jr z,.boot
    pop af
    ei
    ret
.boot:
    pop af
    ret
register:
    out ($99),a
    ld a,b
    or $80
    out ($99),a
    ret
upload:
    ld a,(hl)
    out ($98),a
    inc hl
    dec de
    ld a,d
    or e
    jr nz,upload
    ret
Native_Palette:
    INCBIN "native-palette.bin"
Native_Lookup:
    INCBIN "native-lookup.bin"
Native_TileMasks:
    INCBIN "native-tile-masks.bin"
Native_BlackMasks:
    INCBIN "native-black-masks.bin"
    INCLUDE "native-solid.inc"
    INCLUDE "native-actors.inc"
    INCLUDE "native-radar.inc"
    INCLUDE "native-hud-io.inc"
    INCLUDE "hud.inc"
