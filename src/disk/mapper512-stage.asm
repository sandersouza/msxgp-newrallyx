; Experimental cold-stage decoder, not a standalone game/disk loader.
; HL=bounded compressed Page1 stream, BC=length, DE=8000 output Page2.
; Output: CF=0 and DE=C000 on exact16KiB success; CF=1 for malformed input.
; AF/BC/DE/HL scratch; IX/IY preserved. Entry requires DI and returns DI.
; Caller owns Page1/Page2 mapper/slots, Page3 code/stack and stopped gameplay.
; No VDP/PSG/mapper writes, OS calls or active decompression. Source and output
; must be separate physical segments; neither may alias code, stack or Page0.
; Scratch Cursor is private for this call; not reentrant/IRQ/NMI safe. A failed
; decode may leave partial output, which the caller must not install as a stage.
; This C700 diagnostic address destroys game state and is not a production ABI.
    OUTPUT "decoder.bin"
    ORG $c700
Mapper512Stage_Decode:
    push ix
    ld a,d
    cp $80
    jp nz,.fail
    ld a,e
    or a
    jp nz,.fail
    ld a,h
    cp $40
    jr c,.fail
    cp $80
    jr nc,.fail
    ld a,b
    or c
    jr z,.fail
    push hl
    pop ix
    add ix,bc
    jr c,.fail
    ld a,ixh
    cp $80
    jr c,.loop
    jr nz,.fail
    ld a,ixl
    or a
    jr nz,.fail
.loop:
    ld a,d
    cp $c0
    jr z,.done
    call GetByte
    jr c,.fail
    bit 7,a
    jr nz,.match
    ld c,a
    inc c
    ld b,0
    call CheckSpace
    jr c,.fail
    call CheckInput
    jr c,.fail
    ldir
    jr .loop
.match:
    and 127
    add a,3
    ld c,a
    ld b,0
    call CheckSpace
    jr c,.fail
    push bc
    call GetByte
    jr c,.pop_fail
    ld c,a
    call GetByte
    jr c,.pop_fail
    ld b,a
    ld a,b
    or c
    jr z,.pop_fail
    ld (Cursor),hl
    ld h,d
    ld l,e
    or a
    sbc hl,bc
    jr c,.pop_fail
    ld a,h
    cp $80
    jr c,.pop_fail
    pop bc
    ldir
    ld hl,(Cursor)
    jr .loop
.done:
    ld a,h
    cp ixh
    jr nz,.fail
    ld a,l
    cp ixl
    jr nz,.fail
    pop ix
    or a
    ret
.pop_fail:
    pop bc
.fail:
    pop ix
    scf
    ret

; HL cursor -> A byte; CF on exhaustion. BC/DE/IX/IY preserved.
GetByte:
    ld a,h
    cp ixh
    jr c,.ok
    jr nz,.fail
    ld a,l
    cp ixl
    jr nc,.fail
.ok:
    ld a,(hl)
    inc hl
    or a
    ret
.fail:
    scf
    ret

; BC requested output length; CF if it would cross C000. All pairs preserved.
CheckSpace:
    push hl
    ld h,d
    ld l,e
    add hl,bc
    ld a,h
    cp $c0
    jr c,.ok
    jr nz,.fail
    ld a,l
    or a
    jr nz,.fail
.ok:
    pop hl
    or a
    ret
.fail:
    pop hl
    scf
    ret

; HL+BC must not cross the compressed end in IX. All pairs preserved.
CheckInput:
    push hl
    add hl,bc
    ld a,h
    cp ixh
    jr c,.ok
    jr nz,.fail
    ld a,l
    cp ixl
    jr c,.ok
    jr nz,.fail
.ok:
    pop hl
    or a
    ret
.fail:
    pop hl
    scf
    ret
Cursor: dw 0
