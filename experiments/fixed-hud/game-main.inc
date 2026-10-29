; SCREEN4 integration glue. No BIOS calls after mapping independent Page0 RAM.
Game_WorldGeneration EQU $c080
Game_LastWorldGeneration EQU $c081
Game_SmokeCount EQU $c082
Game_PatchX EQU $c084
Game_PatchY EQU $c085
Game_PatchID EQU $c086
Game_RadarCount EQU $c087
Game_RadarX EQU $c088
Game_RadarY EQU $c089
Game_RadarIndex EQU $c08a
Game_RadarEraseFlag EQU $c08b
Game_RadarName EQU $c08c
Game_LastSmokeChanged EQU $c090
Game_PrevDeath EQU $c091
Game_PrevDeathX EQU $c092
Game_PrevDeathY EQU $c093
Game_LastPatchCol EQU $c094
Game_LastPatchRow EQU $c095
Game_RadarAddresses EQU $2300
Game_RadarPatterns EQU $2400
Game_RadarColors EQU $2500
Game_SmokeList EQU $0800

Game_Prepare:
    ld hl,(clock_ticks)
    ld de,(input_tick)
    ld (input_tick),hl
    or a
    sbc hl,de
    ld a,l
    ld (elapsed_ticks),a
    call Game_Frame
    ; Game_Frame already finishes through Game_Position, including zero ticks.
    call Game_Actors
    call GameSprites_Prepare
    jp GameHUD_Prepare

Game_Init:
    di
    ; Select the primary and secondary RAM slot already active in Page3.
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
    ; Probe an independent mapper segment by comparing two changing markers.
    ld hl,($c0fe)
    push hl
    ld b,0
.segment:
    ld a,b
    out ($fc),a
    ld hl,$55aa
    ld ($c0fe),hl
    ld de,($00fe)
    or a
    sbc hl,de
    jr nz,.allocated
    ld hl,$aa55
    ld ($c0fe),hl
    ld de,($00fe)
    or a
    sbc hl,de
    jr nz,.allocated
    inc b
    jr .segment
.allocated:
    pop hl
    ld ($c0fe),hl
    xor a
    ld hl,0
    ld de,1
    ld bc,$3fff
    ld (hl),a
    ldir
    ld a,GAME_RESOURCE_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$3000
    ld bc,2048
    ldir
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a000
    ld de,$e000
    ld bc,4096
    ldir
    ld a,$ff
    ld (Game_LastWorldGeneration),a
    call Game_InitCore
    call Game_Position
    call Game_Actors
    call GameSprites_Init
    call GameHUD_Init
    call GameSprites_Prepare
    call GameHUD_Prepare
    ret

Game_RingPatch:
    ld a,(Game_WorldGeneration)
    ld b,a
    ld a,(Game_LastWorldGeneration)
    cp b
    jr nz,.changed
    ld a,(Game_LastPatchCol)
    ld b,a
    ld a,(mapcol)
    cp b
    jr nz,.overlays
    ld a,(Game_LastPatchRow)
    ld b,a
    ld a,(maprow)
    cp b
    ret z
    jr .overlays
.changed:
    ld a,(Game_WorldGeneration)
    ld (Game_LastWorldGeneration),a
    ; Restore only old sparse effects. Persistent collected flags need no
    ; whole-cache rebuild; their nine names are repainted below.
    IF !GAME_RENDER_OPT
    ld a,$ff
    ld (seen),a
    ld (seen+2),a
    ENDIF
    ld a,(Game_SmokeChanged)
    ld b,a
    ld a,(Game_LastSmokeChanged)
    cp b
    jr z,.old_death
    ld a,b
    ld (Game_LastSmokeChanged),a
    ld ix,Game_SmokeList
    ld hl,(Game_SmokeCount)
.restore_smoke:
    ld a,h
    or l
    jr z,.cache_smoke
    push hl
    ld b,(ix+0)
    ld c,(ix+1)
    IF GAME_RENDER_OPT
    push bc
    call Smoke_CodeAtBC
    pop bc
    cp $bd
    jr c,.restore_old_tile
    cp $c6
    jr c,.old_tile_live
.restore_old_tile:
    ENDIF
    call Game_RestoreOne
.old_tile_live:
    ld de,3
    add ix,de
    pop hl
    dec hl
    jr .restore_smoke
.cache_smoke:
    IF GAME_RENDER_OPT
    call GameSmoke_BuildCache
    ELSE
    call Game_CacheSmoke
    ENDIF
.old_death:
    ld a,(Game_PrevDeath)
    cp 1
    jr nz,.overlays
    ld a,(Game_PrevDeathX)
    ld b,a
    ld a,(Game_PrevDeathY)
    ld c,a
    ld d,3
.restore_row:
    ld e,3
.restore_col:
    push bc
    push de
    call Game_RestoreOne
    pop de
    pop bc
    inc b
    dec e
    jr nz,.restore_col
    ld a,(Game_PrevDeathX)
    ld b,a
    inc c
    dec d
    jr nz,.restore_row
.overlays:
    ld ix,Flag_Records
    ld iy,Flag_Active+1
    ld b,10
.flags:
    push bc
    ld a,(iy+0)
    or a
    jr nz,.next_flag
    ld b,(ix+4)
    ld c,(ix+5)
    ld a,GAME_EMPTY_TILE
    call Game_PatchSquare
.next_flag:
    ld de,6
    add ix,de
    inc iy
    pop bc
    djnz .flags
    ld ix,Game_SmokeList
    ld hl,(Game_SmokeCount)
.smoke:
    ld a,h
    or l
    jr z,.death
    push hl
    ld b,(ix+0)
    ld c,(ix+1)
    ld a,(ix+2)
    call Game_PatchOne
    ld de,3
    add ix,de
    pop hl
    dec hl
    jr .smoke
.death:
    ld a,(Death_State)
    ld (Game_PrevDeath),a
    cp 1
    jr nz,.done
    ld a,(Death_X)
    ld (Game_PrevDeathX),a
    ld b,a
    ld a,(Death_Y)
    ld (Game_PrevDeathY),a
    ld c,a
    ld a,GAME_DEATH_TILE
    call Game_PatchSquare
.done:
    ld a,(mapcol)
    ld (Game_LastPatchCol),a
    ld a,(maprow)
    ld (Game_LastPatchRow),a
    ret

Game_RestoreOne:
    ; Original map bank/address at B,C. No VRAM read or map-wide copy.
    push bc
    ld a,c
    and $80
    rlca
    add a,2
    ld ($7000),a
    ld a,c
    and 127
    ld l,a
    ld h,0
    REPT 7
    add hl,hl
    ENDR
    ld e,b
    ld d,$80
    add hl,de
    ld a,(hl)
    pop bc
    jp Game_PatchOne

Game_PatchOne:
    ; World tile B,C and tileID A. Only the currently cached32x32 window.
    ld (Game_PatchID),a
    ld a,(mapcol)
    ld d,a
    ld a,b
    sub d
    cp 32
    ret nc
    ld e,a
    ld a,(maprow)
    ld d,a
    ld a,c
    sub d
    cp 32
    ret nc
    cp 28
    jr nc,.cache
    ld d,a
    ld a,e
    sub 24
    cp 2
    jr nc,.cache
    ld e,a
    ld a,d
    add a,a
    add a,d
    add a,e
    ld l,a
    ld h,0
    ld de,boundary_ids
    add hl,de
    ld a,(Game_PatchID)
    ld (hl),a
.cache:
    ld a,b
    call Ring_Position
    ld a,(Game_PatchID)
    IF GAME_RENDER_OPT
    cp (hl)
    ret z
    ld (hl),a
    jp GameDirty_Mark
    ELSE
    ld (hl),a
    ret
    ENDIF
Game_PatchSquare:
    ld (Game_PatchID),a
    ; Reject the complete 3x3 square before visiting nine individual cells.
    ld a,(mapcol)
    ld d,a
    ld a,b
    sub d
    add a,2
    cp 34
    ret nc
    ld a,(maprow)
    ld d,a
    ld a,c
    sub d
    add a,2
    cp 34
    ret nc
    ld a,b
    ld (Game_PatchX),a
    ld a,c
    ld (Game_PatchY),a
    IF GAME_RENDER_OPT
    ; PatchOne preserves BC/IX. Keep loop counters in IX instead of saving
    ; BC and DE for every cell; save the caller's IX only once per square.
    push ix
    ld ix,$0303
.fast_row:
    push bc
    ld ixl,3
.fast_col:
    ld a,(Game_PatchID)
    push af
    call Game_PatchOne
    pop af
    cp GAME_EMPTY_TILE
    jr z,.fast_same
    inc a
.fast_same:
    ld (Game_PatchID),a
    inc b
    dec ixl
    jr nz,.fast_col
    pop bc
    inc c
    dec ixh
    jr nz,.fast_row
    pop ix
    ret
    ENDIF
    ld d,3
.row:
    push de
    ld e,3
.col:
    push bc
    push de
    ld a,(Game_PatchID)
    push af
    call Game_PatchOne
    pop af
    cp GAME_EMPTY_TILE
    jr z,.same
    inc a
.same:
    ld (Game_PatchID),a
    pop de
    pop bc
    inc b
    dec e
    jr nz,.col
    ld a,(Game_PatchX)
    ld b,a
    inc c
    pop de
    dec d
    jr nz,.row
    ret

Game_CacheSmoke:
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
Game_DirtyTileUpload:
    IF GAME_RENDER_OPT
    jp GameDirty_Upload
    ELSE
    ret
    ENDIF

; Background radar uses up to32 copied character tiles. Only dots change;
; the static radar remains in the phase-compensated HUD character bank.
Game_Radar:
    IFDEF GAMEPLAY_CONFIGURED
    IF GAME_RENDER_OPT
    jp GameRadarFast_Draw
    ENDIF
    ENDIF
    xor a
    ld (Game_RadarCount),a
    ; Phase-local character variants retain exact collected-flag pixels.
    ; Only live actor dots still need a copied character in RAM.
    call $a700
    ld ix,$e068
    ld b,8
.actors:
    push bc
    ld a,b
    cp 8
    jr z,.actor
    ld a,8
    sub b
    ld c,a
    ld a,($e24e)
    cp c
    jr c,.next_actor
.actor:
    ; Original inactive descriptors may be parked below the maze. They have
    ; no radar position until entering the native 32x56 world bounds.
    ld a,(ix+10)
    cp 56
    jr nc,.next_actor
    ld a,(ix+8)
    cp 32
    jr nc,.next_actor
    add a,8
    ld (Game_RadarX),a
    ld a,(ix+10)
    call Game_RadarCellY
    call Game_RadarDot
.next_actor:
    ld de,32
    add ix,de
    pop bc
    djnz .actors
    ret
Game_RadarCellY:
    ld l,a
    ld h,0
    ld de,Game_RadarCellRows
    add hl,de
    ld a,(hl)
    ld (Game_RadarY),a
    ret
Game_RadarErase:
    ld a,1
    ld (Game_RadarEraseFlag),a
    jr Game_RadarPoint
Game_RadarDot:
    xor a
    ld (Game_RadarEraseFlag),a
Game_RadarPoint:
    ld a,(Game_RadarX)
    ld b,a
    ld a,(fx)
    add a,b
    ld (dotx),a
    ld a,(Game_RadarY)
    ld b,a
    ld a,(fy)
    add a,b
    ld (doty),a
    and $f8
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    ld a,(dotx)
    REPT 3
    rrca
    ENDR
    and 7
    add a,26
    ld e,a
    ld d,0
    add hl,de
    ld de,names
    add hl,de
    ld (Game_RadarName),hl
    ld a,(hl)
    cp 64
    jr c,.new
    cp 96
    jr nc,.new
    sub 64
    jr .index
.new:
    ld a,(Game_RadarCount)
    cp 32
    ret nc
    ld (Game_RadarIndex),a
    inc a
    ld (Game_RadarCount),a
    ld a,(hl)
    sub 96
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    push hl
    ld a,(Game_RadarIndex)
    ld l,a
    ld h,0
    add hl,hl
    ld de,Game_RadarAddresses
    add hl,de
    ld de,(Game_RadarName)
    ld (hl),e
    inc hl
    ld (hl),d
    ld a,(Game_RadarIndex)
    add a,64
    ex de,hl
    ld (hl),a
    pop hl
    push hl
    ld de,$8100
    add hl,de
    push hl
    ld a,(Game_RadarIndex)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Game_RadarPatterns
    add hl,de
    ex de,hl
    pop hl
    ld bc,8
    ldir
    pop hl
    ld de,$8500
    add hl,de
    push hl
    ld a,(Game_RadarIndex)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,Game_RadarColors
    add hl,de
    ex de,hl
    pop hl
    ld bc,8
    ldir
    ld a,(Game_RadarIndex)
.index:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(doty)
    and 7
    ld e,a
    ld d,0
    add hl,de
    ld de,Game_RadarPatterns
    add hl,de
    push hl
    ld a,(dotx)
    and 7
    ld b,a
    ld a,$80
    jr z,.mask
.rotate:
    rrca
    djnz .rotate
.mask:
    ld c,a
    ld a,GAME_RADAR_COLOR
    ld de,$100
    add hl,de
    cp (hl)
    ld (hl),a
    pop hl
    jr z,.merge
    ld (hl),0
.merge:
    ld a,(Game_RadarEraseFlag)
    or a
    ld a,(hl)
    jr z,.set
    ld b,a
    ld a,c
    cpl
    and b
    ld (hl),a
    ret
.set:
    or c
    ld (hl),a
    ret
Game_RadarUpload:
    ld a,(Game_RadarCount)
    or a
    ret z
    ld hl,$0200
    call GamePattern_Address
    ld hl,Game_RadarPatterns
    ld a,(Game_RadarCount)
    call tile_bytes
    call upload
    ld hl,$4200
    call GamePattern_Address
    ld hl,Game_RadarColors
    ld a,(Game_RadarCount)
    call tile_bytes
    jp upload

Game_RadarCellRows:
    INCBIN "game-radar-y.bin"
