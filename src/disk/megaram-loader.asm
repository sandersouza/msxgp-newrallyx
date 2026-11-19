; DOS1/Disk BASIC takeover loader, executing only from main Page3 RAM.
; Requires64 KiB system RAM and the generated MegaRAM capacity tier.
; Detects primary/expanded slots; restores probe bytes, including aliases.
; Reads bounded16 KiB LZ blocks directly into two writable MegaRAM windows.
; Before DOS calls restores original Page2 slot; no OS calls after takeover.
; Owns AF/BC/DE/HL/IX/IY/IFF, slot/8E mapping, C100..CEFF code, CF00 stack,
; D000..D1FF DMA. Does not allocate main-mapper segments or hold a full image.
    OUTPUT "loader.bin"
    INCLUDE "megaram-layout.inc"
    ORG $c100
DosEntry:
    xor a
    jp Entry
BasicEntry:
    ld a,1
Entry:
    ld (Mode),a
    ld (OriginalSP),sp
    ld sp,$cf00
    or a
    ld hl,5
    jr z,.bdos
    ld hl,$f37d
.bdos:
    ld (Bdos+1),hl
    ; Capture actual Page2 primary/subslot while DOS/BASIC owns its mapping.
    in a,($a8)
    REPT 4
    rrca
    ENDR
    and 3
    ld e,a
    ld d,0
    ld hl,$fcc1
    add hl,de
    ld a,(hl)
    and $80
    or e
    ld c,a
    ld de,4
    add hl,de
    ld a,(hl)
    and $30
    rrca
    rrca
    or c
    ld (OriginalSlot),a
    xor a
    ld (Primary),a
.primary:
    ld a,(Primary)
    ld e,a
    ld d,0
    ld hl,$fcc1
    add hl,de
    bit 7,(hl)
    ld a,e
    jr z,.unexpanded
    or $80
    ld (MegaSlot),a
    ld b,4
.secondary:
    push bc
    call Probe
    pop bc
    jr c,.found
    ld a,(MegaSlot)
    add a,4
    ld (MegaSlot),a
    djnz .secondary
    jr .next
.unexpanded:
    ld (MegaSlot),a
    call Probe
    jr c,.found
.next:
    ld a,(Primary)
    inc a
    ld (Primary),a
    cp 4
    jr c,.primary
    ld de,MemoryError
    jp Fail
.found:
    call RestoreSlot
    ei
    ld de,Loading
    ld c,9
    call Bdos
    ld de,FCB
    ld c,$0f
    call Bdos
    inc a
    ld de,FileError
    jp z,Fail
    ld hl,1
    ld (FCB+14),hl
    ld de,$d000
    ld c,$1a
    call Bdos
    call SelectSlot
    xor a
    out ($8e),a
    ld ($8000),a
    inc a
    ld ($a000),a
    in a,($8e)
    ld hl,Magic
    ld b,7
.header:
    call GetByte
    cp (hl)
    ld de,DataError
    jp nz,Fail
    inc hl
    djnz .header
    call GetByte
    cp EXPECTED_PAGES
    jp nz,Fail
    ld (Pages),a
    inc a
    srl a
    ld (Blocks),a
    xor a
    ld (Bank),a
.bank:
    call GetByte
    ld l,a
    call GetByte
    ld h,a
    ld (Remaining),hl
    ld a,h
    or l
    jp z,BadData
    call GetByte
    ld l,a
    call GetByte
    ld h,a
    ld (Expected),hl
    out ($8e),a
    ld a,(Bank)
    add a,a
    ld ($8000),a
    inc a
    ld ($a000),a
    in a,($8e)
    ld de,$8000
.token:
    ld a,d
    cp $c0
    jr z,.complete
    call TokenByte
    bit 7,a
    jr nz,.match
    inc a
    ld b,a
.literal:
    call TokenByte
    call Store
    djnz .literal
    jr .token
.match:
    and 127
    add a,3
    ld b,0
    ld c,a
    call TokenByte
    ld l,a
    call TokenByte
    ld h,a
    ld a,h
    or l
    jp z,BadData
    push de
    ex de,hl
    or a
    sbc hl,de
    pop de
    jp c,BadData
    ld a,h
    cp $80
    jp c,BadData
.copy:
    ld a,(hl)
    call Store
    inc hl
    dec c
    jr nz,.copy
    jr .token
.complete:
    ld hl,(Remaining)
    ld a,h
    or l
    jp nz,BadData
    ld hl,$8000
    ld de,0
    ld bc,$4000
.sum:
    ld a,(hl)
    add a,e
    ld e,a
    jr nc,.sum_nc
    inc d
.sum_nc:
    inc hl
    dec bc
    ld a,b
    or c
    jr nz,.sum
    ld hl,(Expected)
    or a
    sbc hl,de
    jp nz,BadData
    ld a,(Bank)
    inc a
    ld (Bank),a
    ld c,a
    ld a,(Blocks)
    cp c
    jp nz,.bank
    call RestoreSlot
    ei
    ld de,FCB
    ld c,$10
    call Bdos
    di
    ; CHGMOD must precede MegaRAM Page1 execution: its BIOS interslot bridge
    ; may otherwise disturb the bank registers containing the return address.
    in a,($a8)
    and $fc
    out ($a8),a
    ld a,4
    call $005f
    di
    xor a
    out ($8e),a
    ld a,(MegaSlot)
    ld h,$40
    call $0024
    call SelectSlot
    xor a
    out ($8e),a
    ld ($4000),a
    inc a
    ld ($6000),a
    inc a
    ld ($8000),a
    inc a
    ld ($a000),a
Takeover:
    jp $4010

; Reversible0/generated-address-bit/last-bank tag test. Ordinary RAM fails
; restoration also unwinds aliases on256/512 KiB devices. Preserve A000 RAM
; bytes changed by register writes when the candidate is ordinary system RAM.
Probe:
    call SelectSlot
    ld a,($a000)
    ld (SavedRegister),a
    xor a
    out ($8e),a
    ld ($a000),a
    in a,($8e)
    ld a,($bff0)
    ld (Saved0),a
    ld a,$a5
    ld ($bff0),a
    out ($8e),a
    ld a,MEGA_PROBE_MIDDLE
    ld ($a000),a
    in a,($8e)
    ld a,($bff0)
    ld (SavedMiddle),a
    ld a,$5a
    ld ($bff0),a
    out ($8e),a
    ld a,MEGA_PROBE_LAST
    ld ($a000),a
    in a,($8e)
    ld a,($bff0)
    ld (SavedLast),a
    ld a,$c3
    ld ($bff0),a
    out ($8e),a
    xor a
    ld ($a000),a
    ld a,($bff0)
    cp $a5
    jr nz,.failed
    ld a,MEGA_PROBE_MIDDLE
    ld ($a000),a
    ld a,($bff0)
    cp $5a
    jr nz,.failed
    ld a,MEGA_PROBE_LAST
    ld ($a000),a
    ld a,($bff0)
    cp $c3
    jr nz,.failed
    ld a,1
    jr .result
.failed:
    xor a
.result:
    ld (ProbeResult),a
    ld a,MEGA_PROBE_LAST
    ld ($a000),a
    in a,($8e)
    ld a,(SavedLast)
    ld ($bff0),a
    out ($8e),a
    ld a,MEGA_PROBE_MIDDLE
    ld ($a000),a
    in a,($8e)
    ld a,(SavedMiddle)
    ld ($bff0),a
    out ($8e),a
    xor a
    ld ($a000),a
    in a,($8e)
    ld a,(Saved0)
    ld ($bff0),a
    out ($8e),a
    ; Ordinary RAM interpreted the bank-register stores as data writes. Only
    ; restore its A000 byte when write protection demonstrably does not work;
    ; a failed smaller MegaRAM must not copy another bank's byte into bank0.
    ld a,(Saved0)
    xor $ff
    ld ($bff0),a
    ld a,($bff0)
    ld b,a
    ld a,(Saved0)
    cp b
    jr z,.protected
    ld ($bff0),a
    ld a,(SavedRegister)
    ld ($a000),a
.protected:
    ld a,(ProbeResult)
    or a
    ret z
    scf
    ret

SelectSlot:
    ld a,(MegaSlot)
    jr SetSlot
RestoreSlot:
    ld a,(OriginalSlot)
SetSlot:
    ld h,$80
    call $0024
    di
    ret
Store:
    push af
    ld a,d
    cp $c0
    jp nc,BadData
    pop af
    ld (de),a
    inc de
    ret
TokenByte:
    push hl
    ld hl,(Remaining)
    ld a,h
    or l
    jp z,BadData
    dec hl
    ld (Remaining),hl
    pop hl
GetByte:
    push bc
    push de
    push hl
    ld hl,(BufferPtr)
    ld de,(BufferEnd)
    or a
    sbc hl,de
    jr nz,.cached
    call RestoreSlot
    ei
    ld de,FCB
    ld hl,512
    ld c,$27
    call Bdos
    di
    ld a,h
    or l
    jp z,BadData
    ld de,$d000
    add hl,de
    ld (BufferEnd),hl
    ld hl,$d000
    ld (BufferPtr),hl
    call SelectSlot
.cached:
    ld hl,(BufferPtr)
    ld a,(hl)
    inc hl
    ld (BufferPtr),hl
    pop hl
    pop de
    pop bc
    ret
Bdos:
    jp 5
BadData:
    ld de,DataError
Fail:
    push de
    xor a
    out ($8e),a
    call RestoreSlot
    pop de
    ei
    ld c,9
    call Bdos
    ld sp,(OriginalSP)
    ld a,(Mode)
    or a
    ret nz
    jp 0

Mode: db 0
Primary: db 0
MegaSlot: db 0
OriginalSlot: db 0
OriginalSP: dw 0
ProbeResult: db 0
SavedRegister: db 0
Saved0: db 0
SavedMiddle: db 0
SavedLast: db 0
Bank: db 0
Pages: db 0
Blocks: db 0
Remaining: dw 0
Expected: dw 0
BufferPtr: dw $d000
BufferEnd: dw $d000
Magic: db "NRXMGR1"
Loading: db "Loading New Rally-X into MegaRAM...",13,10,"$"
MemoryError:
    IF MEGA_REQUIRED_KIB = 1024
    db "1 MiB MegaRAM required",13,10,"$"
    ELSE
    IF MEGA_REQUIRED_KIB = 768
    db "768 KiB MegaRAM required",13,10,"$"
    ELSE
    IF MEGA_REQUIRED_KIB = 512
    db "512 KiB MegaRAM required",13,10,"$"
    ELSE
    IF MEGA_REQUIRED_KIB = 256
    db "256 KiB MegaRAM required",13,10,"$"
    ELSE
    db "128 KiB MegaRAM required",13,10,"$"
    ENDIF
    ENDIF
    ENDIF
    ENDIF
FileError: db "NRXMEGA.DAT not found",13,10,"$"
DataError: db "NRXMEGA.DAT is truncated or corrupt",13,10,"$"
FCB: db 0,"NRXMEGA DAT"
     defs 25,0
    ASSERT $ <= $cf00
