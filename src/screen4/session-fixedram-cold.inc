; Cold stopped-game workers in0800..13FF; active smoke-list lifetime reuses this
; storage after world construction. Installed anew before every ColdLoad.
GamePlain_Init:
    di
    ; Main and Page3 already share the same full RAM slot. Existing mapper
    ; machines bind their hidden Page1/Page2 to the allocated world segments;
    ; on fixed RAM these writes have no effect and physical addresses suffice.
    ld a,(GameSession_MapSegments)
    out ($fd),a
    ld a,(GameSession_MapSegments+1)
    out ($fe),a
    in a,($a8)
    ld (GamePlain_Ppi),a
    ld (GamePlain_RomValue),a
    ld b,a
    and $c3
    ld c,a
    ld a,b
    and 3
    ld d,a
    rlca
    rlca
    or c
    ld a,d
    REPT 4
    rlca
    ENDR
    or c
    ld e,a
    ld a,d
    rlca
    rlca
    or e
    ld (GamePlain_RamValue),a
    ld a,b
    and $f3
    ld c,a
    ld a,d
    rlca
    rlca
    or c
    ld (GamePlain_LowPpi),a
    ld a,b
    and $cf
    ld c,a
    ld a,d
    REPT 4
    rlca
    ENDR
    or c
    ld (GamePlain_HighPpi),a
    ld l,d
    ld h,0
    ld bc,$fcc1
    add hl,bc
    bit 7,(hl)
    jp z,.separate
    ld a,($ffff)
    cpl
    ld (GamePlain_Secondary),a
    ld b,a
    and $c3
    ld c,a
    ld a,b
    REPT 4
    rrca
    ENDR
    and $0c
    or c
    ld e,a
    ld a,b
    rrca
    rrca
    and $30
    or e
    ld (GamePlain_RamSecondary),a
    ; Different-primary reference path. Shared-primary cartridges must use
    ; secondary writes instead; configure their values/bytecode below.
    ld c,a
    ld a,(GamePlain_Ppi)
    rrca
    rrca
    and 3
    cp d
    jr z,.shared
    ld a,(GamePlain_RamSecondary)
    ld ($ffff),a
    jr .mirror
.shared:
    ld a,(GamePlain_RamSecondary)
    ld (GamePlain_RamValue),a
    ld a,(GamePlain_Secondary)
    ld (GamePlain_RomValue),a
    ld ($ffff),a
    ld b,a
    and $f3
    ld c,a
    ld a,(GamePlain_RamSecondary)
    and $0c
    or c
    ld (GamePlain_LowPpi),a
    ld a,b
    and $cf
    ld c,a
    ld a,(GamePlain_RamSecondary)
    and $30
    or c
    ld (GamePlain_HighPpi),a
    ld a,$32
    ld (GamePlain_RamWrite),a
    ld (GamePlain_RomWrite),a
    ld (GamePlain_CopyRamWrite),a
    ld (GamePlain_CopyRomWrite),a
    ld hl,$ffff
    ld (GamePlain_RamWrite+1),hl
    ld (GamePlain_RomWrite+1),hl
    ld (GamePlain_CopyRamWrite+1),hl
    ld (GamePlain_CopyRomWrite+1),hl
    ld a,(GamePlain_Secondary)
.mirror:
    ld b,a
    ld l,d
    ld h,0
    ld de,$fcc5
    add hl,de
    ld (hl),b
.separate:
    ld hl,GamePlain_IRQ
    ld ($d2d3),hl
    ld hl,(GameAuto_MemoryKiB)
    ld a,h
    or a
    jr nz,.ready
    ld a,l
    cp 16
    jr nz,.ready
    ld hl,64
    ld (GameAuto_MemoryKiB),hl
    call GameAuto_FormatStatus
.ready:
    ret

GamePlain_PatchObject:
    push ix
    push bc
    push iy
    pop hl
    ld de,$c104
    ld bc,9
    ldir
    push hl
    pop iy
    pop bc
    push bc
    call GamePlain_Address
    ld de,$c104
    ld b,3
.row:
    ld c,3
.cell:
    ld a,(de)
    inc de
    ld (hl),a
    inc hl
    dec c
    jr nz,.cell
    push de
    ld de,125
    add hl,de
    pop de
    djnz .row
    call GamePlain_Rom
    pop bc
    inc c
    inc c
    inc c
    pop ix
    ret

; Cold: A=logical map bank,C=destination identity. Select lower/upper via its
; allocated identity; constructor chunks execute from the opposite ROM window.
; SP writes the complete hidden RAM half. Dictionary tail JP returns here.
GamePlain_CopyMap:
    push ix
    push iy
    ld e,a
    ld d,0
    ld a,i
    push af
    di
    ld a,(GameSession_MapSegments)
    cp c
    ld a,0
    jr z,.half
    inc a
.half:
    ld (GamePlain_Upper),a
    ld hl,Compact_Banks
    add hl,de
    ld a,(hl)
    and 127
    ld e,a
    add a,a
    add a,e
    ld e,a
    ld d,0
    ld hl,Compact_Maps
    add hl,de
    ld a,(hl)
    ld (GamePlain_SourceBank),a
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    ld a,(GamePlain_Upper)
    or a
    jr nz,.upper
    ld a,(GamePlain_SourceBank)
    ld (PLAIN_REG2),a
    ld a,(GamePlain_LowPpi)
    ld (GamePlain_ColdPpi+1),a
    ld hl,PLAIN_REG3
    ld (GamePlain_DictBank+1),hl
    ld a,0
    ld (GamePlain_EntryAdjust+1),a
    ld hl,$8000
    jr .start
.upper:
    ld a,d
    sub $40
    ld d,a
    ld a,(GamePlain_SourceBank)
    ld (PLAIN_REG0),a
    ld a,(GamePlain_HighPpi)
    ld (GamePlain_ColdPpi+1),a
    ld hl,PLAIN_REG1
    ld (GamePlain_DictBank+1),hl
    ld a,$40
    ld (GamePlain_EntryAdjust+1),a
    ld hl,$c000
.start:
    ld ($c100),sp
    ld sp,hl
    ld bc,1024
.chunk:
    ; Always restore cartridgePage1 before writing ASCII8 registers.
    ld a,(GamePlain_RomValue)
GamePlain_CopyRomWrite:
    out ($a8),a
    nop
    ld a,(de)
    inc de
GamePlain_DictBank:
    ld (PLAIN_REG3),a
    ld a,(de)
    inc de
    ld l,a
    ld a,(de)
    inc de
GamePlain_EntryAdjust:
    sub 0
    ld h,a
GamePlain_ColdPpi:
    ld a,0
GamePlain_CopyRamWrite:
    out ($a8),a
    nop
    jp (hl)
GamePlain_MapContinue:
    dec bc
    ld a,b
    or c
    jp nz,GamePlain_CopyMap.chunk
    ld sp,($c100)
    call GamePlain_Rom
    xor a
    ld (PLAIN_REG0),a
    inc a
    ld (PLAIN_REG1),a
    pop af
    pop iy
    pop ix
    jp po,.disabled
    ei
.disabled:
    ret
