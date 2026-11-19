; DOS1/BASIC diagnostic installer, never a supported game executable.
; Copy only this small loader to C100; keep bridge bytes in original TPA.
; DOS source lies below4000; BASIC source lies in original Page2, never switched
; during bridge copy into RAM Page1=30. KernelD606..FFFF is never overwritten.
; Requires main RAM in Page3, >=32 independent16KiB segments, no DOS2 allocator.
; DI probe restores all touched tags. General registers/IFF/mapper scratch.
; Takes over on success. Failure prints a diagnostic and waits for reset.
    INCLUDE "cold-size.inc"
    OUTPUT "cold-loader.bin"
    ORG $c100
DosEntry:
    xor a
    jp Entry
BasicEntry:
    ld a,1
Entry:
    ld (Mode),a
    ld sp,$cf00
    di
    ld de,$0402
    xor a
    call $ffca
    di
    or a
    ld de,Unsupported
    jp nz,Fail
    ; Find original Page2 without assuming readable mapper ports.
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
    ld de,Tag
    ld b,16
.compare:
    ld a,(de)
    cp (hl)
    jr nz,.next
    inc hl
    inc de
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
    ld ix,SavedBytes
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
    jr nz,.count_next
    inc e
.count_next:
    inc c
    ld a,c
    cp 32
    jr c,.count
    ld c,31
    dec ix
.restore:
    ld a,c
    out ($fe),a
    ld a,(ix+0)
    ld ($bff0),a
    dec ix
    dec c
    jp p,.restore
    ld a,(OriginalP2)
    out ($fe),a
    ld a,e
    cp 32
    ld de,MemoryError
    jp nz,Fail
    ; Main RAM is selected in Page1 through BIOS while Page0 is still valid.
    ld a,($f342)
    ld h,$40
    call $0024
    di
    ld a,30
    out ($fd),a
    ld hl,$0111+LoaderEnd-DosEntry
    ld a,(Mode)
    or a
    jr z,.source
    ld hl,$8011+LoaderEnd-DosEntry
.source:
    ld de,$5000
    ld bc,COLD_BYTES
    ldir
    ld a,(Mode)
    jp $5000
Fail:
    ld a,(Mode)
    or a
    ld hl,$0005
    jr z,.bdos
    ld hl,$f37d
.bdos:
    ld (Bdos+1),hl
    ei
    ld c,9
    call Bdos
.stop:
    di
    halt
    jr .stop
Bdos: jp $0005
Mode: db 0
OriginalP2: db 1
Tag: db "NRX-COLD-PROBE!!"
SavedTag: ds 16
SavedBytes: ds 32
MemoryError: db "512 KiB main mapper required.",13,10,"$"
Unsupported: db "DOS2 cold takeover is not supported by this diagnostic.",13,10,"$"
LoaderEnd:
    ASSERT $ < $c600
