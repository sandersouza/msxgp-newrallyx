; Exact cached display preparation, measured on FS-A1WSX_NR128/3,579,545Hz:
; unchanged fields/cy: Prepare985+Commit82=1067cycles (baseline2813);
; normal scroll:2064+1634=3698 (baseline3824). Fuel-only native-value sweep
; Preparemean2544 (baseline16586). Synthetic numbers exclude synchronization,
; game logic, rendering and audio; integrated workload remains authoritative.
; Raw snapshots trigger only the changed field's decoder. Packed-value keys
; skip unchanged/saturated slots. Camera motion updates14SATYbytes separately;
; entering/leaving sentinel216 revisits only its affected vertical group.
; Four life records share two immutable complete native pattern variants.
; Commit uploads only dirty patterns and skips an unchanged SAT. No cadence or
; point/fuel rule changes. Snapshot22a0..22b4, SATdirty22b5, offsets22c0..22cd;
; radar2300+ untouched. Differential contracts:test_game_hud.py --emulator --bios.
; Dynamic native sprite HUD. Caller owns page0 RAM and the shared palette.
; Init must run DI/display-off; Prepare is pure CPU foreground; Commit is DI.
; Require Init -> (Prepare -> Commit)*, cy low matching the next R23 publication.
; Complete native16x16 life source must have transparent final row (helper
; validates it). Sentinel216 shifts contents down1 and moves SAT anchor up1,
; retaining every source pixel. HUD SAT never contains216: world slots follow.
; No resizing, partial native car, RGB change, or scanline-limit override.
GH_Patterns EQU $2000
GH_SAT EQU $2200
GH_Keys EQU $2240
GH_Dirty EQU $2260
GH_Slot EQU $2262
GH_Value EQU $2263
GH_Shift EQU $2264
GH_SatY EQU $2265
GH_Hidden EQU $2266
GH_CurrentBit EQU $2267
GH_Values EQU $2280
GH_Snapshot EQU $22a0
GH_LastCY EQU $22b3
GH_Valid EQU $22b4
GH_SATDirty EQU $22b5
GH_Offset EQU $2269
GH_Offsets EQU $22c0

GameHUD_Init:
    ld hl,GH_Keys
    ld de,GH_Keys+1
    ld bc,27
    ld (hl),$ff
    ldir
    xor a
    ld (GH_Valid),a
    ld hl,$1800
    call GH_Address
    ld hl,GameHUD_Colors
    ld de,224
    call GH_Upload
    ; All four life SAT records share exact normal/shifted native patterns.
    ; These two immutable groups make life-count and sentinel changes SAT-only.
    ld hl,$2d60
    call GH_Address
    ld hl,GameHUD_Life
    ld de,64
    jp GH_Upload

GameHUD_Prepare:
    ; Native counters are read only. Each changed field is decoded separately;
    ; camera compensation stays independent from logical display changes.
    ld hl,0
    ld (GH_Dirty),hl
    xor a
    ld (GH_SATDirty),a
    ld a,(cy)
    add a,211
    cp 216
    jr nz,.hidden
    inc a
.hidden:
    ld (GH_Hidden),a
    ld a,(GH_Valid)
    or a
    jr nz,.cached
    ld hl,$e060
    ld de,GH_Values
    call GH_ReadScore
    ld hl,$e0a0
    call GH_ReadScore
    call GH_ReadRound
    call GH_ReadLives
    call GH_ReadFuel
    call GH_PrepareAll
    jp GH_RefreshSnapshot
.cached:
    call GH_UpdateFields
    ld a,(GH_LastCY)
    ld hl,cy
    cp (hl)
    ret z
    push af
    ld a,1
    ld (GH_SATDirty),a
    ld a,(cy)
    ld (GH_LastCY),a
    ld c,a
    DUP 14, slot
    ld a,(GH_Offsets+slot)
    add a,c
    cp 216
    jr nz,$+3
    inc a
    ld (GH_SAT+slot*4),a
    EDUP
    pop af
    call GH_PrepareSentinel
    ld a,(cy)
    jp GH_PrepareSentinel

GH_UpdateFields:
    ld hl,$e060
    ld de,GH_Snapshot
    call GH_CompareEight
    jr z,.score
    ld hl,$e060
    ld de,GH_Snapshot
    ld bc,8
    ldir
    ld hl,$e060
    ld de,GH_Values
    call GH_ReadScore
    xor a
    ld hl,1
    ld b,3
    call GH_PrepareChangedRange
.score:
    ld hl,$e0a0
    ld de,GH_Snapshot+8
    call GH_CompareEight
    jr z,.round
    ld hl,$e0a0
    ld de,GH_Snapshot+8
    ld bc,8
    ldir
    ld hl,$e0a0
    ld de,GH_Values+3
    call GH_ReadScore
    ld a,3
    ld hl,8
    ld b,3
    call GH_PrepareChangedRange
.round:
    ld a,($e1b0)
    ld hl,GH_Snapshot+16
    cp (hl)
    jr z,.lives
    ld (hl),a
    ld de,GH_Values+6
    call GH_ReadRound
    ld a,6
    ld hl,64
    ld b,1
    call GH_PrepareChangedRange
.lives:
    ld a,($e00f)
    ld hl,GH_Snapshot+17
    cp (hl)
    jr z,.fuel
    ld (hl),a
    ld de,GH_Values+7
    call GH_ReadLives
    ld a,7
    ld hl,128
    ld b,4
    call GH_PrepareChangedRange
.fuel:
    ld a,($e26b)
    ld hl,GH_Snapshot+18
    cp (hl)
    ret z
    ld (hl),a
    ld de,GH_Values+11
    call GH_ReadFuel
    ld a,11
    ld hl,2048
    ld b,3
GH_PrepareChangedRange:
    ld (GH_Slot),a
    ld (GH_CurrentBit),hl
.loop:
    push bc
    ld a,(GH_Slot)
    ld e,a
    ld d,0
    ld hl,GH_Values
    add hl,de
    ld c,(hl)
    ex de,hl
    add hl,hl
    ld de,GH_Keys
    add hl,de
    ld a,c
    cp (hl)
    call nz,GH_PrepareSlot
    ld hl,(GH_CurrentBit)
    add hl,hl
    ld (GH_CurrentBit),hl
    ld a,(GH_Slot)
    inc a
    ld (GH_Slot),a
    pop bc
    djnz .loop
    ret

GH_PrepareAll:
    ld hl,1
    ld (GH_CurrentBit),hl
    xor a
    ld (GH_Slot),a
.slot:
    call GH_PrepareSlot
    ld hl,(GH_CurrentBit)
    add hl,hl
    ld (GH_CurrentBit),hl
    ld a,(GH_Slot)
    inc a
    ld (GH_Slot),a
    cp 14
    jr nz,.slot
    ret

GH_ReadRound:
    ld a,($e1b0)
    cp 2
    jr nc,.round_source
    ld a,2
.round_source:
    dec a
    cp 100
    jr c,.round_tens
    ld a,99
.round_tens:
    ld b,0
.tens:
    cp 10
    jr c,.round_digits
    sub 10
    inc b
    jr .tens
.round_digits:
    ld c,a
    ld a,b
    or a
    jr nz,.round_pack
    ld a,10
.round_pack:
    rlca
    rlca
    rlca
    rlca
    or c
    ld (de),a
    inc de
    ret
GH_ReadLives:
    ld a,($e00f)
    or a
    jr z,.lives_count
    dec a
    cp 5
    jr c,.lives_count
    ld a,4
.lives_count:
    ld c,a
    ld b,4
.life_key:
    ld a,c
    or a
    ld a,0
    jr z,.life_store
    ld a,1
    dec c
.life_store:
    ld (de),a
    inc de
    djnz .life_key
    ret
GH_ReadFuel:
    ld a,($e26b)
    cp 61
    jr c,.fuel_source
    ld a,60
.fuel_source:
    ld l,a
    ld h,0
    push de
    ld de,GameHUD_FuelScale
    add hl,de
    ld c,(hl)
    pop de
    ld b,3
.fuel_key:
    ld a,c
    cp 17
    jr c,.fuel_last
    sub 16
    ld c,a
    ld a,16
    jr .fuel_store
.fuel_last:
    ld c,0
.fuel_store:
    ld (de),a
    inc de
    djnz .fuel_key
    ret

GH_CompareEight:
    ; Both source/snapshot spans stay inside a single page; no byte wrap.
    DUP 7
    ld a,(de)
    cp (hl)
    ret nz
    inc l
    inc e
    EDUP
    ld a,(de)
    cp (hl)
    ret
GH_PrepareSentinel:
    ; Only one vertical group can enter/leave sentinel216 per camera phase.
    ; Arbitrary camera jumps still prepare both the old and new phase groups.
    cp 13
    jr nz,.lives
    ld a,6
    ld hl,64
    ld b,1
    jr GH_PrepareRange
.lives:
    cp 33
    jr nz,.fuel
    ld a,7
    ld hl,128
    ld b,4
    jr GH_PrepareRange
.fuel:
    cp 157
    jr nz,.score
    ld a,11
    ld hl,2048
    ld b,3
    jr GH_PrepareRange
.score:
    cp 185
    jr nz,.high
    ld a,3
    ld hl,8
    ld b,3
    jr GH_PrepareRange
.high:
    cp 209
    ret nz
    xor a
    ld hl,1
    ld b,3
GH_PrepareRange:
    ld (GH_Slot),a
    ld (GH_CurrentBit),hl
.loop:
    push bc
    call GH_PrepareSlot
    ld hl,(GH_CurrentBit)
    add hl,hl
    ld (GH_CurrentBit),hl
    ld a,(GH_Slot)
    inc a
    ld (GH_Slot),a
    pop bc
    djnz .loop
    ret
GH_RefreshSnapshot:
    ld hl,$e060
    ld de,GH_Snapshot
    ld bc,8
    ldir
    ld hl,$e0a0
    ld bc,8
    ldir
    ld a,($e1b0)
    ld (de),a
    inc de
    ld a,($e00f)
    ld (de),a
    inc de
    ld a,($e26b)
    ld (de),a
    ld a,(cy)
    ld (GH_LastCY),a
    ld a,1
    ld (GH_Valid),a
    ret

; Native eight digit order is4,5,6,7,0,1,2,3; retain six after saturation.
GH_ReadScore:
    push hl
    inc l
    inc l
    inc l
    inc l
    ld a,(hl)
    and 15
    ld b,a
    inc hl
    ld a,(hl)
    and 15
    or b
    pop hl
    jr z,.six
    ld a,$99
    ld (de),a
    inc de
    ld (de),a
    inc de
    ld (de),a
    inc de
    ret
.six:
    ld a,l
    add a,6
    ld l,a
    call GH_ReadPair
    ld a,l
    sub 8
    ld l,a
    call GH_ReadPair
GH_ReadPair:
    ld a,(hl)
    and 15
    cp 10
    jr c,.first
    ld a,9
.first:
    rlca
    rlca
    rlca
    rlca
    ld b,a
    inc hl
    ld a,(hl)
    and 15
    cp 10
    jr c,.second
    ld a,9
.second:
    or b
    ld (de),a
    inc hl
    inc de
    ret

GH_PrepareSlot:
    ld a,1
    ld (GH_SATDirty),a
    ld a,(GH_Slot)
    ld l,a
    ld h,0
    ld de,GH_Values
    add hl,de
    ld a,(hl)
    ld (GH_Value),a
    ld a,(GH_Slot)
    ld l,a
    ld h,0
    ld de,GameHUD_YS
    add hl,de
    ld a,(hl)
    dec a
    ld (GH_Offset),a
    ld a,(cy)
    add a,(hl)
    dec a
    ld (GH_SatY),a
    cp 216
    ld a,0
    jr nz,.shift
    inc a
    ld b,215
    ld a,b
    ld (GH_SatY),a
    ld a,1
.shift:
    ld (GH_Shift),a
    ; Stable per-slot SAT uses one complete16x16 group at fixed1:1 geometry.
    ld a,(GH_Slot)
    add a,a
    add a,a
    ld l,a
    ld h,0
    ld de,GH_SAT
    add hl,de
    ld a,(GH_SatY)
    ld (hl),a
    ld a,(GH_Slot)
    cp 7
    jr c,.visible
    ld a,(GH_Value)
    or a
    jr nz,.visible
    ld a,(GH_Hidden)
    ld (hl),a
    ld a,211
    ld (GH_Offset),a
.visible:
    push hl
    ld a,(GH_Slot)
    ld l,a
    ld h,0
    ld de,GH_Offsets
    add hl,de
    ld a,(GH_Offset)
    ld (hl),a
    pop hl
    inc hl
    push hl
    ld a,(GH_Slot)
    ld l,a
    ld h,0
    ld de,GameHUD_XS
    add hl,de
    ld a,(hl)
    pop hl
    ld (hl),a
    inc hl
    ld a,(GH_Slot)
    add a,a
    add a,a
    add a,144
    ld (hl),a
    inc hl
    ld (hl),0
    ld a,(GH_Slot)
    cp 7
    jr c,.dynamic
    cp 11
    jr nc,.dynamic
    dec hl
    ld a,(GH_Shift)
    add a,a
    add a,a
    add a,172
    ld (hl),a
    ld a,(GH_Slot)
    add a,a
    ld l,a
    ld h,0
    ld de,GH_Keys
    add hl,de
    ld a,(GH_Value)
    ld (hl),a
    ret
.dynamic:
    ; Compare packed value and sentinel shift against current visible patterns.
    ld a,(GH_Slot)
    add a,a
    ld l,a
    ld h,0
    ld de,GH_Keys
    add hl,de
    ld a,(GH_Value)
    cp (hl)
    jr nz,.changed_value
    inc hl
    ld a,(GH_Shift)
    cp (hl)
    ret z
    jr .changed_shift
.changed_value:
    ld (hl),a
    inc hl
.changed_shift:
    ld a,(GH_Shift)
    ld (hl),a
    ld hl,(GH_Dirty)
    ld de,(GH_CurrentBit)
    ld a,h
    or d
    ld h,a
    ld a,l
    or e
    ld l,a
    ld (GH_Dirty),hl
    ; Clear exactly this changed32-byte group before building its contents.
    ld a,(GH_Slot)
    ld l,a
    ld h,0
    DUP 5
    add hl,hl
    EDUP
    ld de,GH_Patterns
    add hl,de
    push hl
    push hl
    pop de
    inc de
    ld (hl),0
    ld bc,31
    ldir
    pop hl
    ld a,(GH_Shift)
    ld e,a
    ld d,0
    add hl,de
    push hl
    pop iy
    ld a,(GH_Slot)
    cp 7
    jr c,.digits
    ; Fuel has four complete rows, up to16columns per segment.
    ld a,(GH_Value)
    add a,a
    ld l,a
    ld h,0
    ld de,GameHUD_FuelMasks
    add hl,de
    ld a,(hl)
    inc hl
    ld b,(hl)
    DUP 4, row
    ld (iy+row),a
    ld (iy+16+row),b
    EDUP
    ret
.digits:
    ld a,(GH_Value)
    rrca
    rrca
    rrca
    rrca
    and 15
    call GH_CopyGlyph
    push iy
    pop hl
    ld de,16
    add hl,de
    push hl
    pop iy
    ld a,(GH_Value)
    and 15
GH_CopyGlyph:
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld de,GameHUD_Digits
    add hl,de
    push iy
    pop de
    ld bc,8
    ldir
    ret

GameHUD_Commit:
    ld hl,(GH_Dirty)
    ld a,h
    or l
    jr z,.sat
    xor a
    ld (GH_Slot),a
.upload:
    ld hl,(GH_Dirty)
    srl h
    rr l
    ld (GH_Dirty),hl
    jr nc,.next
    ld a,(GH_Slot)
    ld l,a
    ld h,0
    DUP 5
    add hl,hl
    EDUP
    push hl
    ld de,$2c80
    add hl,de
    call GH_Address
    pop hl
    ld de,GH_Patterns
    add hl,de
    ld de,32
    call GH_Upload
.next:
    ld a,(GH_Slot)
    inc a
    ld (GH_Slot),a
    cp 14
    jr nz,.upload
.sat:
    ld a,(GH_SATDirty)
    or a
    ret z
    ld hl,$1a00
    call GH_Address
    ld hl,GH_SAT
    ld de,56
    jp GH_Upload

GH_Address:
    xor a
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ret
GH_Upload:
    ld c,$98
    ld a,d
    or a
    jr z,.tail
.page:
    ld b,0
    otir
    dec d
    jr nz,.page
.tail:
    ld a,e
    or a
    ret z
    ld b,e
    otir
    ret

GameHUD_XS:
    db 208,224,240,208,224,240,240,208,219,230,241,208,224,240
GameHUD_YS:
    db 8,8,8,32,32,32,204,184,184,184,184,60,60,60
GameHUD_FuelScale:
    DUP 61, units
    db units*48/60
    EDUP
GameHUD_FuelMasks:
    DUP 17, width
    dw ((($ffff << (16-width)) & $ffff) >> 8) | ((($ffff << (16-width)) & $ff) << 8)
    EDUP
GameHUD_Digits:
    INCBIN "game-hud-digits.bin"
GameHUD_Life:
    INCBIN "game-hud-life.bin"
GameHUD_Colors:
    INCBIN "game-hud-colors.bin"
