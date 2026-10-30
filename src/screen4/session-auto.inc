; Boot-only mapper survey. Main Page0 workers and persistent state stay below0800.
; Probe executes from Page3 D500; D600..D6FF is temporary saved-byte storage.
; Every candidate's byte is restored in reverse order, including aliased banks.
GameAuto_MemoryKiB EQU $07e0
GameAuto_Expanded EQU $07e2
GameAuto_MapperMask EQU $07e3
GameAuto_FlagsValid EQU $07e4
GameAuto_Init:
    ; Page0 is the memory being surveyed, so execute the probe from Page3.
    ; The caller already owns DI; an IRQ must not fetch code from a probe bank.
    ld hl,GameAuto_ProbeImage
    ld de,$d500
    ld bc,GameAuto_ProbeEnd-GameAuto_ProbeImage
    ldir
    call $d500
.probed:
    ; HL is the count of independent16KiB banks, not the largest port value.
    ; Standard power-of-two mappers let the allocator use count-1 as a mask.
    ld a,l
    dec a
    ld (GameAuto_MapperMask),a
    ld a,h
    or a
    jr nz,.expanded
    ld a,l
    cp 8
    jr nc,.expanded
    xor a
    jr .selected
.expanded:
    ld a,1
.selected:
    ; Choose only the existing64/128KiB cache strategies. More RAM does not
    ; allocate larger caches or change native world coordinates/game rules.
    ld (GameAuto_Expanded),a
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld (GameAuto_MemoryKiB),hl
    call GameAuto_FormatStatus
    xor a
    ld (GameAuto_FlagsValid),a
    ld a,(GameAuto_Expanded)
    or a
    ret z
    ld hl,GameAuto_Patches
.patch:
    ; Each table row is (public RAM entry, resident128KiB implementation).
    ; Replace three entry bytes once: the64KiB hot path keeps direct calls.
    ld e,(hl)
    inc hl
    ld d,(hl)
    inc hl
    ld a,d
    or e
    ret z
    ld a,$c3
    ld (de),a
    inc de
    ld a,(hl)
    inc hl
    ld (de),a
    inc de
    ld a,(hl)
    inc hl
    ld (de),a
    jr .patch

GameAuto_BuildFlags128:
    ; ColdLoad invalidates this byte. A challenge UI resume must reuse the
    ; current flag collection state instead of rebuilding an obsolete cache.
    ld a,(GameAuto_FlagsValid)
    or a
    ret nz
    call GameSession_BuildFlags128
    ld a,1
    ld (GameAuto_FlagsValid),a
    ret
GameAuto_NoEnsure:
    ret
GameAuto_ProbeImage:
    ; Position independent: all branches are relative; fixed RAM addresses only.
    in a,($fc)
    push af
    ld ix,$d600
    ld c,0
.save:
    ; Save before writing every candidate, including aliases of earlier banks.
    ; With aliases, later saved values are our own markers; see reverse restore.
    ld a,c
    out ($fc),a
    ld a,($3ff0)
    ld (ix+0),a
    ld a,c
    ld ($3ff0),a
    inc ix
    inc c
    jr nz,.save
    ld hl,0
    ld c,0
.count:
    ; After all writes, only the last alias of each physical bank retains its
    ; own index. Exactly one successful comparison counts each real bank.
    ld a,c
    out ($fc),a
    ld a,($3ff0)
    cp c
    jr nz,.next
    inc hl
.next:
    inc c
    jr nz,.count
    ld c,255
    dec ix
.restore:
    ; Undo in reverse write order. This first unwinds aliased markers and then
    ; reinstates the original byte, even when256 logical values share4 banks.
    ld a,c
    out ($fc),a
    ld a,(ix+0)
    ld ($3ff0),a
    dec ix
    dec c
    ld a,c
    cp 255
    jr nz,.restore
    pop af
    out ($fc),a
    ret
GameAuto_ProbeEnd:
    ASSERT GameAuto_ProbeEnd-GameAuto_ProbeImage <= $100
