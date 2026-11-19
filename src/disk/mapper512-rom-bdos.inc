; Diagnostic embedded-resource provider only. Same stopped Cold_Read protocol;
; never called in active gameplay. General registers/flags/IFF scratch.
; Uses existing OS5:C500 ROM-copy thunk and borrowed input2; no extra segment.
Mapper512_RomBdos:
    ld a,c
    cp $1a
    jr z,.dma
    cp $27
    jr z,.read
    cp $0f
    jr z,.ok
    cp $10
    jr z,.ok
    ld a,1
    ret
.dma:
    ld (Mapper512_RomDma),de
.ok:
    xor a
    ret
.read:
    ld (Mapper512_RomCount),hl
    ld (ROMIO_Count),hl
    ex de,hl
    ld bc,33
    add hl,bc
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,(hl)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,d
    REPT 5
    srl a
    ENDR
    or b
    inc a                  ; File begins in physical ROM bank1.
    ld (ROMIO_SourceBank),a
    ld a,d
    and $1f
    or $80
    ld d,a
    ld (ROMIO_Source),de
    ld hl,(Mapper512_RomDma)
    ld a,h
    cp $c0
    jr nc,.destination
    and $3f
    ld h,a                 ; RAM2 DMA8000 becomes Page0 alias0000.
.destination:
    ld (ROMIO_Destination),hl
    ld a,2
    ld (ROMIO_RamBank),a
    call ROMIO
    ld hl,(Mapper512_RomCount)
    xor a
    ret
Mapper512_RomDma: dw $c100
Mapper512_RomCount: dw 0
