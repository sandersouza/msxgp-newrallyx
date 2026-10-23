; Experimental frozen-frame backend. Original logic and the bitmap fallback
; remain intact. Patterns use two disjoint banks of twelve 16x16 patterns;
; only SAT/colors are published in VBlank, so the old page stays coherent.
Native_HWCount EQU $c175
Native_HWActive EQU $c176
Native_HWStarted EQU $c177
Native_HWSAT EQU $c144
Native_HWColors0 EQU $c180
Native_HWColors1 EQU $c240
Native_HWMask EQU $e580
Native_HWPlanes EQU $e690
Native_HWPalette EQU $e691
Native_HWX EQU $e692
Native_HWY EQU $e693
Native_HWEC EQU $e694
Native_HWPlane EQU $e695
Native_HWTable EQU $e696
Native_HWPattern EQU $e697
Native_HWRows EQU $e698
Native_HWMinY EQU $e699
Native_HWMaxY EQU $e69a
Native_HWRowY EQU $e69b
Native_HWCacheTags EQU $e380    ; 24 pattern slots: flags, palette, full plane+1
Native_HWCacheTag EQU $e69c
Native_HWCacheFull EQU $e69e
Native_HWCacheHit EQU $e69f
Native_HWLookups:
    db $37,$38,0,$34,$35,$36,$34,$35,0
Native_HWColors:
    db 3,$49,0,13,1,11,6,14,0
Native_HWPatternBanks:
    db 0,4,8,12,16,180,184,188,192,196,200,204
    db 208,212,216,220,224,228,232,236,240,244,248,252
Native_HWPrefixes:
    dw $0000,$8000,$c000,$e000,$f000,$f800,$fc00,$fe00,$ff00
    dw $ff80,$ffc0,$ffe0,$fff0,$fff8,$fffc,$fffe,$ffff

Native_HWFallback:
    xor a
    ld (Native_HWActive),a
    ld (Native_HWCount),a
    ld (Native_FrameActor),a
    ld a,216
    ld (Native_HWSAT),a
    scf
    ret

Native_HWBeginFrame:
    xor a
    ld (Native_HWCount),a
    inc a
    ld (Native_HWActive),a
    ld a,216
    ld (Native_HWSAT),a
    ld hl,$3900
    ld de,$3901
    ld bc,255
    xor a
Native_HWLoadFirst:
    ld (hl),a
Native_HWLoadClear:
    ldir
    ld a,11
    ld (Native_HWMinY),a
    ld a,212
    ld (Native_HWMaxY),a
    IF NATIVE_HUD
    ld ix,sat
    ld b,14
.base:
    push bc
    call Native_HWCountHUD
    pop bc
    ld de,4
    add ix,de
    djnz .base
    ld a,176
    ld (Native_HWMaxY),a
    ld b,3
.fuel:
    push bc
    call Native_HWCountHUD
    pop bc
    ld de,4
    add ix,de
    djnz .fuel
    ld a,176
    ld (Native_HWMinY),a
    ld a,212
    ld (Native_HWMaxY),a
    ld ix,life_sat
    ld b,3
.life:
    push bc
    call Native_HWCountHUD
    pop bc
    ld de,4
    add ix,de
    djnz .life
    ENDIF
    ret
Native_HWCountHUD:
    ld a,(ix+0)
    inc a
    ld b,a
    ld a,(scroll_y)
    ld c,a
    ld a,b
    sub c
    ld l,a
    ld h,$39
    ld b,16
Native_HWCountHUDRow:
    ld a,(Native_HWMinY)
    cp l
    jr z,.upper
    jr nc,Native_HWCountHUDNext
.upper:
    ld a,(Native_HWMaxY)
    cp l
    jr c,Native_HWCountHUDNext
    jr z,Native_HWCountHUDNext
Native_HWLoadHUD:
    inc (hl)
Native_HWCountHUDNext:
    inc l
    djnz Native_HWCountHUDRow
    ret

Native_HWActorBegin:
    ld a,(iy+1)
    and 63
    cp 1
    jp c,Native_HWFallback
    cp 4
    jp nc,Native_HWFallback
    ld (Native_HWPalette),a
    ld b,2
    cp 2
    jr nz,.planes
    inc b
.planes:
    ld a,b
    ld (Native_HWPlanes),a
    ld hl,Native_HWMask
    ld de,Native_HWMask+1
    ld bc,31
    ld (hl),0
    ldir
    or a
    ret

Native_HWMaskPiece:
    ld a,(Native_ActorU)
    add a,a
    ld e,a
    ld d,0
    ld hl,Native_HWPrefixes
    add hl,de
    ld a,(hl)
    cpl
    ld c,a
    inc hl
    ld a,(hl)
    cpl
    ld b,a
    ld a,(Native_ActorU)
    ld e,a
    ld a,(Native_ActorW)
    add a,e
    add a,a
    ld e,a
    ld hl,Native_HWPrefixes
    add hl,de
    ld a,(hl)
    and c
    ld e,a
    inc hl
    ld a,(hl)
    and b
    ld d,a
    ld a,(Native_ActorV)
    add a,a
    add a,Native_HWMask&255
    ld l,a
    ld h,Native_HWMask/256
    ld a,(Native_ActorH)
    ld b,a
Native_HWMaskPieceRow:
    ld a,d
    or (hl)
    ld (hl),a
    inc hl
    ld a,e
    or (hl)
    ld (hl),a
    inc hl
    djnz Native_HWMaskPieceRow
    ret

Native_HWRadarMask:
    ld a,(Native_RadarVisible)
    or a
    ret z
    ld a,(Native_FrameScrollX)
    and 1
    add a,207
    sub (ix+1)
    jr nc,.cut
    xor a
.cut:
    cp 16
    ret nc
    add a,a
    ld e,a
    ld d,0
    ld hl,Native_HWPrefixes
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld a,219
    sub (iy+0)
    ld c,a
    ld b,16
    ld hl,Native_HWMask
Native_HWRadarMaskRow:
    ld a,c
    cp 9
    jr c,Native_HWRadarMaskNext
    cp 69
    jr nc,Native_HWRadarMaskNext
    ld a,(hl)
    and d
    ld (hl),a
    inc hl
    ld a,(hl)
    and e
    ld (hl),a
    dec hl
Native_HWRadarMaskNext:
    inc hl
    inc hl
    inc c
    djnz Native_HWRadarMaskRow
    ret

Native_HWFinishActor:
    call Native_HWRadarMask
    ld a,(Native_ActorY)
    dec a
    ld (Native_HWY),a
    ld a,(ix+1)
    sub 4
    ld b,0
    jr nc,.x
    add a,32
    ld b,$80
.x:
    ld (Native_HWX),a
    ld a,b
    ld (Native_HWEC),a
    IF NATIVE_ACTOR_CACHE
    call Native_HWTryCache
    ld a,(Native_HWCacheHit)
    or a
    jp nz,.validate
    ENDIF
    push ix
    push iy
    ld a,(Native_ActorFlags)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    set 7,h
    ld a,1
    call Native_HUDMapAssets
    ld de,Native_PackedBuffer
    ld bc,64
    ldir
    call Native_RestoreGame
    xor a
    ld (Native_HWPlane),a
.plane:
    ld a,(Native_HWPalette)
    dec a
    ld b,a
    add a,a
    add a,b
    ld b,a
    ld a,(Native_HWPlane)
    add a,b
    ld e,a
    ld d,0
    ld hl,Native_HWLookups
    add hl,de
    ld h,(hl)
    ld a,(Native_HWPlane)
    add a,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld e,a
    ld d,Native_PixelBuffer/256
    ld ix,Native_PackedBuffer
    ld iy,Native_HWMask
    ld a,16
    ld (Native_HWRows),a
.row:
    call .pair
    and (iy+0)
    ld (de),a
    ld a,e
    add a,16
    ld e,a
    inc ix
    inc ix
    call .pair
    and (iy+1)
    ld (de),a
    ld a,e
    sub 16
    ld e,a
    inc de
    inc ix
    inc ix
    inc iy
    inc iy
    ld a,(Native_HWRows)
    dec a
    ld (Native_HWRows),a
    jr nz,.row
    ld a,(Native_HWPlane)
    inc a
    ld (Native_HWPlane),a
    ld b,a
    ld a,(Native_HWPlanes)
    cp b
    jr nz,.plane
    pop iy
    pop ix
    ; Transparent source patterns allocate no hardware lines or SAT entries.
    ld a,(Native_HWPlanes)
    add a,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld b,a
    ld hl,Native_PixelBuffer
    xor a
.any:
    or (hl)
    inc hl
    djnz .any
    ret z
.validate:
    ld a,(Native_HWY)
    cp 216
    jp z,Native_HWFallback
    ld a,(Native_HWPlanes)
    ld b,a
    ld a,(Native_HWCount)
    add a,b
    cp 13
    jp nc,Native_HWFallback
    call Native_HWClaimLines
    jp c,Native_HWFallback
    xor a
    ld (Native_HWPlane),a
.publish:
    ld a,(Native_DrawPage)
    ld b,a
    add a,a
    add a,b
    add a,a
    add a,a                  ; page *12
    ld b,a
    ld a,(Native_HWCount)
    add a,b
    ld e,a
    ld d,0
    ld hl,Native_HWPatternBanks
    add hl,de
    ld a,(hl)
    ld (Native_HWPattern),a
    IF NATIVE_ACTOR_CACHE
    ld a,(Native_HWCacheHit)
    or a
    call z,Native_HWUploadPlane
    call Native_HWRecordCache
    ELSE
    call Native_HWUploadPlane
    ENDIF
    call Native_HWAppendSAT
    ld a,(Native_HWPlane)
    inc a
    ld (Native_HWPlane),a
    ld b,a
    ld a,(Native_HWPlanes)
    cp b
    jr nz,.publish
    or a
    ret
.pair:
    ld l,(ix+0)
    ld a,(hl)
    rlca
    rlca
    rlca
    rlca
    ld b,a
    ld l,(ix+1)
    ld a,(hl)
    or b
    ret

Native_HWClaimLines:
    ld a,(scroll_y)
    ld c,a
    ld a,(Native_HWY)
    inc a
    sub c
    ld l,a
    ld h,$39
    ld a,(Native_HWPlanes)
    ld c,a
    ld b,16
Native_HWClaimLinesRow:
    ld a,l
    cp 11
    jr c,Native_HWClaimLinesNext
    cp 212
    jr nc,Native_HWClaimLinesNext
    ld a,(hl)
    add a,c
    cp 9
    jr nc,Native_HWClaimLinesOverflow
Native_HWLoadActor:
    ld (hl),a
Native_HWClaimLinesNext:
    inc l
    djnz Native_HWClaimLinesRow
    or a
    ret
Native_HWClaimLinesOverflow:
    scf
    ret

    IF NATIVE_ACTOR_CACHE
; Exact reuse is allowed only for an all-FF geometric/priority/radar mask.
; Every occupied pattern has its own signature, so overlapping allocations
; invalidate a previous multi-plane actor without hashes or assumed identity.
Native_HWTryCache:
    xor a
    ld (Native_HWCacheHit),a
    ld (Native_HWCacheFull),a
    ld a,(Native_HWCount)
    ld b,a
    ld a,(Native_HWPlanes)
    add a,b
    cp 13
    ret nc
    ld a,(Native_DrawPage)
    ld b,a
    add a,a
    add a,b
    add a,a
    add a,a
    ld b,a
    ld a,(Native_HWCount)
    add a,b
    ld l,a
    ld h,0
    ld e,l
    ld d,h
    add hl,hl
    add hl,de
    ld de,Native_HWCacheTags
    add hl,de
    ld (Native_HWCacheTag),hl
    ld hl,Native_HWMask
    ld b,32
.mask:
    ld a,(hl)
    inc a
    ret nz
    inc hl
    djnz .mask
    ld a,1
    ld (Native_HWCacheFull),a
    ld hl,(Native_HWCacheTag)
    ld a,(Native_HWPlanes)
    ld b,a
    ld c,1
.tag:
    ld a,(Native_ActorFlags)
    cp (hl)
    ret nz
    inc hl
    ld a,(Native_HWPalette)
    cp (hl)
    ret nz
    inc hl
    ld a,c
    cp (hl)
    ret nz
    inc hl
    inc c
    djnz .tag
    ld a,1
    ld (Native_HWCacheHit),a
    ret
Native_HWRecordCache:
    ld hl,(Native_HWCacheTag)
    ld a,(Native_ActorFlags)
    ld (hl),a
    inc hl
    ld a,(Native_HWPalette)
    ld (hl),a
    inc hl
    ld a,(Native_HWCacheFull)
    or a
    jr z,.store
    ld a,(Native_HWPlane)
    inc a
.store:
    ld (hl),a
    inc hl
    ld (Native_HWCacheTag),hl
    ret
    ENDIF

Native_HWUploadPlane:
    ; Pattern number *8, within the existing 2KB mode-2 pattern table.
    ld a,(Native_HWPattern)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,h
    add a,$38
    ld (Native_HUDWriteAddress+1),a
    ld a,l
    ld (Native_HUDWriteAddress),a
    ld a,7
    ld (Native_HUDWriteBank),a
    ld a,(Native_HWPlane)
    add a,a
    add a,a
    add a,a
    add a,a
    add a,a
    ld l,a
    ld h,Native_PixelBuffer/256
    ld bc,$2098
    jp Native_HUDOTIR

Native_HWAppendSAT:
    ld a,(Native_HWCount)
    add a,a
    add a,a
    add a,Native_HWSAT&255
    ld l,a
    ld h,Native_HWSAT/256
    ld a,(Native_HWY)
    ld (hl),a
    inc hl
    ld a,(Native_HWX)
    ld (hl),a
    inc hl
    ld a,(Native_HWPattern)
    ld (hl),a
    inc hl
    ld (hl),0
    inc hl
    ld (hl),216
    ld a,(Native_HWPalette)
    dec a
    ld b,a
    add a,a
    add a,b
    ld b,a
    ld a,(Native_HWPlane)
    add a,b
    ld e,a
    ld d,0
    ld hl,Native_HWColors
    add hl,de
    ld a,(Native_HWEC)
    or (hl)
    ld c,a
    ld a,(Native_HWCount)
    cp 8
    jr c,.first
    sub 8
    rlca
    rlca
    rlca
    rlca
    add a,Native_HWColors1&255
    ld l,a
    ld h,Native_HWColors1/256
    jr .color
.first:
    rlca
    rlca
    rlca
    rlca
    add a,Native_HWColors0&255
    ld l,a
    ld h,Native_HWColors0/256
.color:
    ld b,16
    ld a,c
.fill:
    ld (hl),a
    inc hl
    djnz .fill
    ld a,(Native_HWCount)
    inc a
    ld (Native_HWCount),a
    ret

; Called under the existing physical-IRQ save; preserve DE/IX/IY/alternates.
Native_HWPublishColors:
    ld a,(Native_HWCount)
    or a
    ret z
    ld a,7
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,$10
    out ($99),a
    ld a,$75
    out ($99),a
    ld a,(Native_HWCount)
    cp 9
    jr nc,.two
    rlca
    rlca
    rlca
    rlca
    ld b,a
    ld c,$98
    ld hl,Native_HWColors0
    otir
    ret
.two:
    ld hl,Native_HWColors0
    ld bc,$8098
    otir
    ld a,(Native_HWCount)
    sub 8
    rlca
    rlca
    rlca
    rlca
    ld b,a
    ld c,$98
    ld hl,Native_HWColors1
    otir
    ret
