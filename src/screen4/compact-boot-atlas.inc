; Cold-only experimental atlas worker, installed at3000 while the initial
; SCREEN5 clear runs. Its4096-byte navigation-RAM lifetime ends at first board
; construction. No active renderer/IRQ may call it. IY/IX unchanged; AF/BC/DE/HL
; scratch; returns EI/R15=0. Page2 lower is the frame stream, upper dictionary
; metadata/pixels. D5B0..D5D4 is state/command scratch; D600..D6FF is the
; up-to2048-slot loaded bitmap. Both die at boot exit and are cleared before
; native game/audio. Foreground only, no reentry, original stack/IRQ ownership.
; VRAM pages2/3 own the immutable atlas; display/back pages0/1 stay separate.
    INCLUDE "compact-atlas-config.inc"
CA_Loaded EQU $d600
CA_Cell EQU $d5b0
CA_Left EQU $d5b2
CA_Tile EQU $d5b4
CA_Mode EQU $d5b8
CA_Color EQU $d5b9
CA_Rows EQU $d5bb
CA_Address EQU $d5bc
CA_Command EQU $d5c0
CA_Next EQU $d5d0
CA_First EQU $d5d2
CA_RunLeft EQU $d5d4
CA_Run EQU $d5ba

CompactAtlas_Init:
    xor a
    ld hl,CA_Loaded
    ld de,CA_Loaded+1
    ld bc,255
    ld (hl),a
    ldir
    ld (CA_Next),a
    ld (CA_Next+1),a
    ld hl,.parameters
    ld de,CA_Command+8
    ld bc,7
    ldir
    ret
.parameters:
    db 8,0,8,0,0,0,$d0

; Cold prefetch spends only pre-existing clear/hold time. Tile decode bounds
; skip latency; no active game, visible bitmap or completed back page changes.
CompactAtlas_Prime:
    ld a,(GameSession_BootSkip)
    or a
    ret nz
    ld hl,(CA_Next)
    ld de,COMPACT_ATLAS_PRIME_COUNT
    or a
    sbc hl,de
    ret nc
    call CompactAtlas_Prefetch
    jr CompactAtlas_Prime

CompactAtlas_Prefetch:
    ld hl,(CA_Next)
    ld de,COMPACT_ATLAS_TILE_COUNT
    or a
    sbc hl,de
    jr nc,.complete
    ld hl,(CA_Next)
    ld (CA_Tile),hl
    inc hl
    ld (CA_Next),hl
    call CompactAtlas_Ensure
    ld a,1
    ret
.complete:
    xor a
    ret

CompactAtlas_Frame:
    ld c,(hl)
    inc hl
    ld b,(hl)
    inc hl
    ld (CA_Left),bc
    xor a
    ld (CA_Cell),a
    ld (CA_Cell+1),a
    inc a
    ld (CA_Run),a
.next:
    call CompactAtlas_Wait
    ld a,(GameSession_BootSkip)
    or a
    ret nz
    ld bc,(CA_Left)
    ld a,b
    or c
    ret z
    dec bc
    ld (CA_Left),bc
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,d
    rrca
    rrca
    rrca
    and 31
    ld c,a
    ld a,d
    and 7
    ld d,a
    cp 7
    jr nz,.tile
    ld a,e
    cp $ff
    jr z,.skip
    cp $fe
    jr nz,.tile
    ld a,c
    add a,2
    ld (CA_Run),a
    jr .next
.skip:
    push hl
    ld a,c
    inc a
    ld l,a
    ld h,0
    REPT 5
    add hl,hl
    ENDR
    ld de,(CA_Cell)
    add hl,de
    ld (CA_Cell),hl
    pop hl
    jr .next
.tile:
    ld (CA_Tile),de
    push hl
    ld hl,(CA_Cell)
    ld b,0
    add hl,bc
    ld (CA_Cell),hl
    call CompactAtlas_EnsureRun
    call CompactAtlas_Draw
    ld hl,(CA_Cell)
    ld a,(CA_Run)
    ld c,a
    ld b,0
    add hl,bc
    ld (CA_Cell),hl
    ld a,1
    ld (CA_Run),a
    pop hl
    jr .next

CompactAtlas_EnsureRun:
    ld hl,(CA_Tile)
    ld (CA_First),hl
    ld a,(CA_Run)
    ld (CA_RunLeft),a
.tile:
    call CompactAtlas_Ensure
    ld hl,(CA_Tile)
    inc hl
    ld (CA_Tile),hl
    ld a,(CA_RunLeft)
    dec a
    ld (CA_RunLeft),a
    jr nz,.tile
    ld hl,(CA_First)
    ld (CA_Tile),hl
    ret

CompactAtlas_Wait:
    di
    reg 15,2
    in a,($99)
    push af
    reg 15,0
    pop af
    ei
    and 1
    ret z
    ld a,(GameSession_BootSkip)
    or a
    jr z,CompactAtlas_Wait
    di
    reg 46,0
    ei
    ret

CompactAtlas_Ensure:
    ld hl,(CA_Tile)
    ld a,l
    and 7
    ld c,a
    ld b,0
    push hl
    ld hl,.bits
    add hl,bc
    ld b,(hl)
    pop hl
    REPT 3
    srl h
    rr l
    ENDR
    ld de,CA_Loaded
    add hl,de
    ld a,(hl)
    and b
    ret nz
    ld a,(hl)
    or b
    ld (hl),a
    ld hl,(CA_Tile)
    ld e,l
    ld d,h
    add hl,hl
    add hl,de
    ld de,COMPACT_ATLAS_TABLE_ADDRESS
    add hl,de
    ld a,COMPACT_ATLAS_TABLE_PAGE
    ld ($7800),a
    ld a,(hl)
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld ($7800),a
    ex de,hl
    ld a,(hl)
    inc hl
    ld (CA_Mode),a
    cp $c0
    jr nc,.special
    push hl
    and 63
    ld l,a
    ld h,0
    REPT 5
    add hl,hl
    ENDR
    ld de,CompactAtlas_Luts
    add hl,de
    ex de,hl
    pop hl
    jr .position
.special:
    and 15
    ld b,a
    REPT 4
    rlca
    ENDR
    or b
    ld (CA_Color),a
.position:
    push hl
    push de
    ld hl,(CA_Tile)
    ld a,h
    rrca
    and 3
    add a,4
    di
    out ($99),a
    ld a,$8e
    out ($99),a
    ei
    ld a,l
    and $e0
    rrca
    rrca
    rrca
    ld b,a
    ld a,h
    and 1
    rrca
    rrca
    rrca
    or b
    ld h,a
    ld a,l
    and 31
    rlca
    rlca
    ld l,a
    ld (CA_Address),hl
    pop de
    pop hl
    ld a,8
    ld (CA_Rows),a
.row:
    call .address
    ld a,(CA_Mode)
    cp $ff
    jr z,.raw
    cp $c0
    jr nc,.uniform
    call .packed
    ld a,(CA_Mode)
    bit 6,a
    jr nz,.row_done
    call .packed
    jr .row_done
.raw:
    ld b,4
.raw_byte:
    ld a,(hl)
    inc hl
    out ($98),a
    djnz .raw_byte
    jr .row_done
.uniform:
    ld a,(CA_Color)
    ld b,4
.fill:
    out ($98),a
    djnz .fill
.row_done:
    ld a,(CA_Rows)
    dec a
    ld (CA_Rows),a
    jr nz,.row
    ret
.packed:
    ld c,(hl)
    inc hl
    ld a,c
    REPT 4
    rrca
    ENDR
    and 15
    call .lookup
    ld a,c
    and 15
.lookup:
    ld b,a
    ld a,(CA_Mode)
    bit 6,a
    jr z,.index
    sla b
.index:
    ld a,e
    and $e0
    or b
    ld e,a
    ld a,(de)
    out ($98),a
    ld a,(CA_Mode)
    bit 6,a
    ret z
    inc e
    ld a,(de)
    out ($98),a
    ret
.address:
    push hl
    push de
    ld hl,(CA_Address)
    di
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    ei
    ld de,128
    add hl,de
    ld (CA_Address),hl
    pop de
    pop hl
    ret
.bits:
    db 1,2,4,8,16,32,64,128

CompactAtlas_Draw:
    ld a,(GameSession_BootSkip)
    or a
    ret nz
    ld hl,(CA_Tile)
    ld de,CA_Command
    call .xy
    ld a,h
    rrca
    rrca
    and 1
    add a,2
    ld (de),a
    ld hl,(CA_Cell)
    ld de,CA_Command+4
    call .xy
    ld a,(GameSession_BootBack)
    srl a
    ld (de),a
    ld a,(CA_Run)
    ld l,a
    ld h,0
    REPT 3
    add hl,hl
    ENDR
    ld (CA_Command+8),hl
    di
    reg 17,32
    ld hl,CA_Command
    ld bc,$0f9b
    otir
    ei
    ret
.xy:
    ld a,l
    and 31
    REPT 3
    rlca
    ENDR
    ld (de),a
    inc de
    xor a
    ld (de),a
    inc de
    ld a,l
    rrca
    rrca
    and $38
    ld b,a
    ld a,h
    and 3
    rrca
    rrca
    or b
    ld (de),a
    inc de
    ret
    ALIGN 32
CompactAtlas_Luts:
    INCBIN "compact-atlas-luts.bin"
