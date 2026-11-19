; Standalone disk takeover loader. DOS entry C100, Disk BASIC entry C104.
; Inputs: main-slot 4 MiB mapper, V9958/128 KiB VRAM, NRALLYX.DAT in current dir.
; Outputs: all banks installed; BIOS Page0, resident Page1, bank1 Page2,
; state/stack segment255 Page3; tail-call cartridge-derived boot at4010.
; Clobbers all CPU registers/IFF/mapper/slots. Never returns after takeover.
; Before takeover: disk calls restore the original Page2 mapping and use a
; fixed Page3 DMA buffer. Code C100..CEFF, stack CF00, DMA D000..D1FF,
; probe D100..D1FF, reservation bitmap D200..D2FF are loader-only lifetimes.
; Game working segments250..255 and staging200..203 never overlap ROM0..124.
    OUTPUT "loader.bin"
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
    ld hl,$0005
    jr z,.bdos
    ld hl,$f37d
.bdos:
    ld (Bdos+1),hl
    di
    ; Identify the original Page2 segment without assuming readable mapper ports.
    ld hl,$bfe0
    ld de,SavedTag
    ld bc,16
    ldir
    ld hl,Tag
    ld de,$bfe0
    ld bc,16
    ldir
    ld c,0
.find:
    ld a,c
    out ($fe),a
    ld hl,$bfe0
    ld ix,Tag
    ld b,16
.compare:
    ld a,(ix+0)
    cp (hl)
    jr nz,.next
    inc ix
    inc hl
    djnz .compare
    ld a,c
    ld (OriginalP2),a
.next:
    inc c
    jr nz,.find
    ld a,(OriginalP2)
    out ($fe),a
    ld hl,SavedTag
    ld de,$bfe0
    ld bc,16
    ldir
    ; Require 256 independent segments with a reversible byte probe.
    ld ix,$d100
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
    jr nz,.save
    ld hl,0
    ld c,0
.count:
    ld a,c
    out ($fe),a
    ld a,($bff0)
    cp c
    jr nz,.count_next
    inc hl
.count_next:
    inc c
    jr nz,.count
    push hl
    ld c,255
    dec ix
.restore:
    ld a,c
    out ($fe),a
    ld a,(ix+0)
    ld ($bff0),a
    dec ix
    dec c
    ld a,c
    cp 255
    jr nz,.restore
    ld a,(OriginalP2)
    out ($fe),a
    pop hl
    ld a,h
    cp 1
    ld de,MemoryError
    jp nz,Fail
    ; Respect DOS2's allocator if available. Reserve the exact low bank IDs
    ; and four staging IDs before any payload write can affect live OS RAM.
    xor a
    ld hl,$d200
    ld de,$d201
    ld bc,255
    ld (hl),a
    ldir
    ld de,$0402
    call $ffca
    or a
    jr z,.reserved
    ld (MapperAPI),hl
.allocate:
    xor a
    ld b,a
    call Allocate
    ld de,BusyError
    jp c,Fail
    push af
    ld a,b
    ld (MapperSlot),a
    pop af
    ld l,a
    ld h,$d2
    ld (hl),1
    cp 203
    jr c,.allocate
    ld hl,$d204
    ld b,121
.check:
    ld a,(hl)
    or a
    ld de,BusyError
    jp z,Fail
    inc hl
    djnz .check
    ld hl,$d2c8
    ld b,4
.check_stage:
    ld a,(hl)
    or a
    jp z,Fail
    inc hl
    djnz .check_stage
.reserved:
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
    ld (FCB+14),hl          ; Byte records allow bounded random block reads.
    ld de,$d000
    ld c,$1a
    call Bdos
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
    cp 125
    jp nz,Fail
    xor a
    ld (Bank),a
.bank:
    ld a,(Bank)
    cp 4
    jr nc,.destination
    add a,200
.destination:
    ld (Target),a
    call GetByte
    ld l,a
    call GetByte
    ld h,a
    ld (Remaining),hl
    call GetByte
    ld l,a
    call GetByte
    ld h,a
    ld (Expected),hl
    di
    ld a,(Target)
    out ($fe),a
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
    jp c,BadData            ; Reject underflow before an address can wrap to Page3.
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
    cp 125
    jp nz,.bank
    ld a,(OriginalP2)
    out ($fe),a
    ei
    ld de,FCB
    ld c,$10
    call Bdos
    di
    ; Move the full Page3 image, including BIOS variables and current stack,
    ; before switching its mapper segment. No OS calls after this boundary.
    ld a,255
    out ($fe),a
    ld hl,$c000
    ld de,$8000
    ld bc,$4000
    ldir
    ld a,255
    out ($ff),a
    ld c,0
.install_low:
    ld a,c
    add a,200
    out ($fe),a
    ld a,c
    out ($fd),a
    ; Page1 may still be BASIC ROM: select the main RAM slot through ENASLT
    ; while BIOS Page0 is available (DOS has the standard interslot entries).
    push bc
    ld a,($f342)
    ld h,$40
    call $0024
    pop bc
    ld hl,$8000
    ld de,$4000
    push bc
    ld bc,$4000
    ldir
    pop bc
    inc c
    ld a,c
    cp 4
    jr nz,.install_low
    xor a
    out ($fd),a
    ld a,1
    out ($fe),a
    ; Main MSX BIOS is primary0/subslot0; its slot state survives disk use.
    in a,($a8)
    and $fc
    out ($a8),a
    jp $4010

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
    ld a,(OriginalP2)
    out ($fe),a
    ei
    ld de,FCB
    ld hl,512              ; Stay below the DOS1 kernel, which starts at D606.
    ld c,$27
    call Bdos
    di
    ; A partial last block is valid; HL is the actual number of byte records.
    ld a,h
    or l
    jp z,BadData
    ld de,$d000
    add hl,de
    ld (BufferEnd),hl
    ld hl,$d000
    ld (BufferPtr),hl
    ld a,(Target)
    out ($fe),a
.cached:
    ld hl,(BufferPtr)
    ld a,(hl)
    inc hl
    ld (BufferPtr),hl
    pop hl
    pop de
    pop bc
    ret
Allocate:
    ld hl,(MapperAPI)
    jp (hl)
Bdos:
    jp $0005
BadData:
    ld de,DataError
Fail:
    ld (ErrorPointer),de
    ld a,(OriginalP2)
    out ($fe),a
    ; Disk BASIC may also expose DOS2's mapper API. Release every segment
    ; reserved by this attempt before returning to the caller on failure.
    ld hl,(MapperAPI)
    ld a,h
    or l
    jr z,.print
    ld c,0
.free:
    ld h,$d2
    ld l,c
    ld a,(hl)
    or a
    jr z,.free_next
    ld a,c
    push bc
    ld a,(MapperSlot)
    ld b,a
    ld a,c
    ld hl,(MapperAPI)
    inc hl
    inc hl
    inc hl
    call Free
    pop bc
.free_next:
    inc c
    jr nz,.free
.print:
    ei
    ld de,(ErrorPointer)
    ld c,9
    call Bdos
    ld a,(Mode)
    or a
    jr nz,.basic
    ld c,0
    jp Bdos
.basic:
    ld sp,(OriginalSP)
    ret
Free:
    jp (hl)

Magic: db "NRXDSK1"
Tag: db "NRX4M-MAPPER-TAG!"
SavedTag: ds 16
OriginalSP: dw 0
OriginalP2: db 1
Mode: db 0
MapperAPI: dw 0
MapperSlot: db 0
Target: db 200
BufferPtr: dw $d000
BufferEnd: dw $d000
Remaining: dw 0
Expected: dw 0
ErrorPointer: dw 0
Bank: db 0
FCB: db 0,"NRALLYX DAT"
    ds 25
Loading: db "New Rally-X: loading into 4 MiB mapper RAM...",13,10,"$"
MemoryError: db "4 MiB main-slot RAM mapper required.",13,10,"$"
BusyError: db "Required mapper segments are busy. Boot clean and retry.",13,10,"$"
FileError: db "NRALLYX.DAT not found in current directory.",13,10,"$"
DataError: db "NRALLYX.DAT is truncated or corrupt.",13,10,"$"
    ASSERT $ < $ce00
