; Standalone ASCII8 diagnostic carrier for the current512KiB RAM game.
; Boot/provider only: no hot code/graphics/audio/rules changes. Requires32 RAM
; segments in Page3's main slot, initial Page3 physical0. No filesystem proof.
; Page3 C100..C7FF bootstrap/ROM-copy thunk survives in the existing OS snapshot.
; ROMIO runs DI, owns Page0 temporary RAM and cartridgePage1/Page2; restores
; slots/mapper and BIOS slot mirrors, returnsEI. AF/BC/DE/HL/IX/IY scratch.
    INCLUDE "rom-config.inc"
    OUTPUT "rom-head.bin"
    ORG $4000
    db "AB"
    dw RomEntry,0,0,0,0,0,0
RomEntry:
    di
    ld sp,$f380
    in a,($a8)
    rrca
    rrca
    and 3
    ld c,a
    ld b,0
    ld hl,$fcc1
    add hl,bc
    ld a,(hl)
    and $80
    or c
    ld e,a
    ld hl,$fcc5
    add hl,bc
    ld a,(hl)
    and $0c
    or e
    push af
    ld h,$80
    call $0024
    di
    ld a,ROM_TAIL_BANK
    ld ($7000),a
    ld hl,ROM_TAIL_ADDRESS
    ld de,Boot
    ld bc,BootEnd-Boot
    ldir
    pop af
    ld (ROMIO_CartSlot),a
    jp Boot
PackedBridge:
    INCBIN "bridge-packed.bin"
PackedBridgeEnd:
    ASSERT $ <= $6000
    defs $6000-$,$ff

    OUTPUT "boot-image.bin"
    ORG $c100
Boot:
    di
    ld sp,$cf00
    in a,($a8)
    ld (BootPrimary),a
    ld a,($ffff)
    cpl
    ld (BootSecondary),a
    ; Cartridge INIT precedes BIOS RAMAD initialization. Derive the live Page3
    ; slot instead; the bootstrap is already executing in its physical RAM0.
    ld a,(BootPrimary)
    rlca
    rlca
    and 3
    ld c,a
    ld b,0
    ld hl,$fcc1
    add hl,bc
    ld a,(hl)
    and $80
    or c
    ld b,a
    ld a,(BootSecondary)
    rrca
    rrca
    rrca
    rrca
    and $0c
    or b
    ld (ROMIO_RamSlot),a
    ld h,$80
    call $0024
    di
    in a,($ff)
    and 31
    jp nz,BootFail
    in a,($fe)
    and 31
    ld (BootP2),a
    ld ix,BootTags
    ld c,0
.save:
    ld a,c
    out ($fe),a
    ld a,($bff0)
    ld (ix+0),a
    ld a,c
    ld ($bff0),a
    inc ix
    inc c
    ld a,c
    cp 32
    jr c,.save
    ld e,0
    ld c,0
.count:
    ld a,c
    out ($fe),a
    ld a,($bff0)
    cp c
    jr nz,.next
    inc e
.next:
    inc c
    ld a,c
    cp 32
    jr c,.count
    dec ix
    ld c,31
.restore:
    ld a,c
    out ($fe),a
    ld a,(ix+0)
    ld ($bff0),a
    dec ix
    dec c
    jp p,.restore
    ld a,(BootP2)
    out ($fe),a
    ld a,e
    cp 32
    jp nz,BootFail
    ld a,2
    out ($fe),a
    ld hl,PackedBridge
    ld de,$8000
    ld bc,PackedBridgeEnd-PackedBridge
    ldir
    ld a,30
    out ($fc),a
    ld a,(ROMIO_RamSlot)
    and $0c
    rrca
    rrca
    ld b,a
    ld a,($ffff)
    cpl
    and $fc
    or b
    ld ($ffff),a
    in a,($a8)
    and $fc
    ld b,a
    ld a,(ROMIO_RamSlot)
    and 3
    or b
    out ($a8),a
    ld hl,$8000
    ld bc,PackedBridgeEnd-PackedBridge
    ld de,0
    call Boot_Decode
    jp c,BootFail
    ld a,(BootSecondary)
    ld ($ffff),a
    in a,($a8)
    and $fc
    ld b,a
    ld a,(BootPrimary)
    and 3
    or b
    out ($a8),a
    ld a,(ROMIO_RamSlot)
    ld h,$40
    call $0024
    di
    ld a,30
    out ($fd),a
    ld a,1
    jp $5000
BootFail:
    di
    ld a,6
    out ($99),a
    ld a,$87
    out ($99),a
    halt
    jr BootFail
BootPrimary: db 0
BootSecondary: db 0
BootP2: db 0
BootTags: ds 32
Boot_Cursor: dw 0
    INCLUDE "boot-decoder.inc"
    ASSERT $ <= $c500
    defs $c500-$,0

; BIOS Page0/OS Page3 entry. Parameters live here across BIOS slot calls.
; ROMIO_RamBank/SourceBank/Source/Destination/Count define one bounded copy.
ROMIO:
    di
    in a,($a8)
    ld (ROMIO_Primary),a
    ld a,($ffff)
    cpl
    ld (ROMIO_Secondary),a
    in a,($fc)
    ld (ROMIO_P0),a
    in a,($fe)
    ld (ROMIO_P2),a
    ld hl,$fcc5
    ld de,ROMIO_SlotMirror
    ld bc,4
    ldir
    ld a,(ROMIO_CartSlot)
    ld h,$40
    call $0024
    ld a,(ROMIO_CartSlot)
    ld h,$80
    call $0024
    di
    ld a,(ROMIO_RamBank)
    out ($fc),a
    ld a,(ROMIO_RamSlot)
    and $0c
    rrca
    rrca
    ld b,a
    ld a,($ffff)
    cpl
    and $fc
    or b
    ld ($ffff),a
    in a,($a8)
    and $fc
    ld b,a
    ld a,(ROMIO_RamSlot)
    and 3
    or b
    out ($a8),a
    ld a,(ROMIO_SourceBank)
    ld ($7000),a
    ld hl,(ROMIO_Source)
    ld de,(ROMIO_Destination)
    ld bc,(ROMIO_Count)
.copy:
    ld a,(hl)
    ld (de),a
    inc hl
    inc de
    dec bc
    ld a,b
    or c
    jr z,.done
    ld a,h
    cp $a0
    jr nz,.copy
    ld hl,$8000
    ld a,(ROMIO_SourceBank)
    inc a
    ld (ROMIO_SourceBank),a
    ld ($7000),a
    jr .copy
.done:
    ld a,(ROMIO_Secondary)
    ld ($ffff),a
    ld a,(ROMIO_Primary)
    out ($a8),a
    ld a,(ROMIO_P0)
    out ($fc),a
    ld a,(ROMIO_P2)
    out ($fe),a
    ld hl,ROMIO_SlotMirror
    ld de,$fcc5
    ld bc,4
    ldir
    ei
    ret
ROMIO_CartSlot: db 0
ROMIO_RamSlot: db 0
ROMIO_SourceBank: db 0
ROMIO_RamBank: db 2
ROMIO_Source: dw 0
ROMIO_Destination: dw 0
ROMIO_Count: dw 0
ROMIO_Primary: db 0
ROMIO_Secondary: db 0
ROMIO_P0: db 0
ROMIO_P2: db 0
ROMIO_SlotMirror: ds 4
BootEnd:
    ASSERT $ < $c800
