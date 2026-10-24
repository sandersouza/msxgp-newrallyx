; Runs in fixed page 3 before any cartridge bank or CPU slot is changed.
Native_LoaderStart:
    ; Discover the active host segment using a changing marker, never port reads.
    ld hl,(NATIVE_TAG)
    ld (Native_TagSave),hl
    ld a,$55
    ld (NATIVE_TAG),a
    ld c,0
.host:
    ld a,c
    out ($fe),a
    ld a,($8700)
    cp $55
    jr nz,.next_host
    ld a,$aa
    ld (NATIVE_TAG),a
    ld a,($8700)
    cp $aa
    ld a,$55
    ld (NATIVE_TAG),a
    jr z,.found_host
.next_host:
    inc c
    jr nz,.host
    ld a,$e1
    jp Native_Fail
.found_host:
    ld a,c
    ld (Native_Segments),a
    ld hl,(Native_TagSave)
    ld (Native_SavedTags),hl
    ld hl,$00a5
    ld (NATIVE_TAG),hl
    ld a,1
    ld (Native_Count),a
    xor a
    ld (Native_Candidate),a
.candidate:
    ld a,(Native_Candidate)
    out ($fe),a
    ld hl,($8700)
    ld (Native_TagSave),hl
    ld a,(Native_Count)
    ld h,a
    ld l,$a5
    ld ($8700),hl
    ld hl,Native_Segments
    ld b,a
    ld c,0
.check:
    ld a,(hl)
    out ($fe),a
    ld a,($8700)
    cp $a5
    jr nz,.alias
    ld a,($8701)
    cp c
    jr nz,.alias
    inc hl
    inc c
    djnz .check
    ; All existing segments retained their markers: this is independent RAM.
    ld a,(Native_Candidate)
    ld (hl),a
    ld a,(Native_Count)
    add a,a
    ld e,a
    ld d,0
    ld hl,Native_SavedTags
    add hl,de
    ld de,(Native_TagSave)
    ld (hl),e
    inc hl
    ld (hl),d
    ld a,(Native_Count)
    inc a
    ld (Native_Count),a
    cp 8
    jr z,.allocated
    jr .next_candidate
.alias:
    ld a,(Native_Candidate)
    out ($fe),a
    ld hl,(Native_TagSave)
    ld ($8700),hl
.next_candidate:
    ld a,(Native_Candidate)
    inc a
    ld (Native_Candidate),a
    jr nz,.candidate
    ; Restore all tested marker bytes even when there is insufficient RAM.
    call Native_RestoreTags
    ld a,$e1
    jp Native_Fail
.allocated:
    call Native_RestoreTags
    ; Page 1 remains the cartridge source until all copies have completed.
    xor a
    ld c,1
    call Native_LoadBank
    ld a,1
    ld c,2
    call Native_LoadBank
    ld a,2
    ld c,4
.assets:
    push af
    push bc
    call Native_LoadBank
    pop bc
    pop af
    inc a
    inc c
    cp 6
    jr nz,.assets
    ld a,(Native_Segments+3)
    out ($fe),a
    ld (Native_Mapped),a
    ld hl,$8000
    ld de,$8001
    ld bc,$3fff
    ld (hl),0
    ldir
    ld a,$ff
    ld ($a200),a
    ld ($a201),a
    ld a,$c3
    ld ($a202),a
    ld a,(Native_Segments+1)
    out ($fd),a
    ld a,(Native_RAMSlot)
    ld h,$40
    call $0024              ; Final BIOS call; it only changes page 1.
    di
    ld a,(Native_Segments+2)
    out ($fc),a
    ; Switching page 0 from a BIOS routine would remove that routine mid-call.
    ; Page 3 already selects this same RAM slot, so its secondary register is
    ; accessible here. Preserve every other page's slot selection.
    ld a,(Native_RAMSlot)
    bit 7,a
    jr z,.primary_only
    and $0c
    rrca
    rrca
    ld b,a
    ld a,($ffff)
    cpl
    and $fc
    or b
    ld ($ffff),a
.primary_only:
    in a,($a8)
    and $fc
    ld b,a
    ld a,(Native_RAMSlot)
    and 3
    or b
    out ($a8),a
    ld hl,$d000
    ld de,$d001
    ld bc,256
    ld (hl),$d2
    ldir
    ld a,$c3
    ld ($d2d2),a
    ld hl,Native_HostIRQ
    ld ($d2d3),hl
    ld a,$d0
    ld i,a
    im 2
    ld a,1
    ld (Native_Suspended),a
    ld hl,$5aa5
    ld (Native_Canary),hl
    ld (NATIVE_IRQ_BOTTOM),hl
    ; VBlank IRQs on, line IRQs off; graphics/raster integration is later work.
    ld a,($f3df)           ; BIOS R0 shadow survives in host RAM.
    and $ef
    out ($99),a
    ld a,$80
    out ($99),a
    ld a,($f3e0)
    or $20
    out ($99),a
    ld a,$81
    out ($99),a
    ld a,NATIVE_R9
    out ($99),a
    ld a,$89
    out ($99),a
    IF NATIVE_FINE_IRQ
    ; Fine-clock comparisons use an unscrolled display line counter.
    xor a
    out ($99),a
    ld a,$97
    out ($99),a
    ENDIF
    in a,($99)
    jp Native_Reset

Native_RestoreTags:
    ld a,(Native_Count)
    ld b,a
    ld hl,Native_Segments
    ld de,Native_SavedTags
.loop:
    ld a,(hl)
    out ($fe),a
    ld a,(de)
    ld ($8700),a
    inc de
    ld a,(de)
    ld ($8701),a
    inc de
    inc hl
    djnz .loop
    ret

Native_LoadBank:
    ld ($6000),a
    ld b,0
    ld hl,Native_Segments
    add hl,bc
    ld a,(hl)
    out ($fe),a
    ld hl,$4000
    ld de,$8000
    ld bc,$4000
    ldir
    ret

; A=asset index 0..3. Main/alternate registers, flags and IFF are preserved.
; Only permitted while native execution is suspended; no nesting is allowed.
Native_MapAssets:
    push af
    push bc
    push hl
    ld b,a
    ld a,(Native_Suspended)
    or a
    jr z,.unsafe
    ld a,(Native_AssetMapped)
    or a
    jr nz,.unsafe
    ld a,b
    cp 4
    jr nc,.unsafe
    ld c,a
    ld b,0
    ld hl,Native_Segments+4
    add hl,bc
    ld a,(hl)
    out ($fe),a
    ld (Native_Mapped),a
    ld a,1
    ld (Native_AssetMapped),a
    jr .done
.unsafe:
    ld a,$e2
    ld (Native_Error),a
.done:
    pop hl
    pop bc
    pop af
    ret

Native_RestoreGame:
    push af
    ld a,(Native_Segments+3)
    out ($fe),a
    ld (Native_Mapped),a
    xor a
    ld (Native_AssetMapped),a
    pop af
    ret

; Host-only IRQ: switch away from the interrupted stack before any pushes.
; Hardware has already saved PC on that stack. No page-2 state, BIOS calls or
; mapping changes occur here. Delivering an original game IRQ is separate work.
Native_HostIRQ:
    ld (Native_InterruptedSP),sp
    ld sp,NATIVE_IRQ_STACK
    push af
    IF NATIVE_VIDEO
    ld a,b
    ld (Native_InterruptedB),a
    ENDIF
    push bc
    IF NATIVE_VIDEO
    call Native_RasterIRQ
    call Native_RestoreStream
    or a
    jr nz,.video_vertical
    pop bc
    pop af
    ld sp,(Native_InterruptedSP)
    ei
    reti
.video_vertical:
    ENDIF
    push de
    push hl
    push ix
    push iy
    ex af,af'
    push af
    exx
    push bc
    push de
    push hl
    IF NATIVE_FINE_IRQ
    call Native_FineClock
    ELSE
    IF !NATIVE_VIDEO
    in a,($99)
    ENDIF
    ENDIF
    IF NATIVE_VIDEO
    ; Sample physical devices once per real VBlank into fixed host RAM. The
    ; logical dispatcher only publishes that level snapshot, keeping its DI
    ; section short and never writing through a borrowed game window.
    call Native_ReadInputs
    ENDIF
    ld hl,(Native_IRQs)
    inc hl
    ld (Native_IRQs),hl
    IF NATIVE_SCHEDULER
    IF !NATIVE_FINE_IRQ
    call Native_HostClock
    ENDIF
    IF NATIVE_VIDEO + NATIVE_IRQ_PROBE
    ld a,(Native_SoftwareBusy)
    or a
    jr nz,Native_ReturnHostIRQ
    ENDIF
Native_DispatchIRQ:
    call Native_SelectIRQ
    or a
    jr nz,Native_EnterGameIRQ
    ENDIF
Native_ReturnHostIRQ:
    pop hl
    pop de
    pop bc
    exx
    pop af
    ex af,af'
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    ld sp,(Native_InterruptedSP)
    ei
    reti

    IF NATIVE_SCHEDULER
Native_EnterGameIRQ:
    pop hl
    pop de
    pop bc
    exx
    pop af
    ex af,af'
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    ld sp,(Native_InterruptedSP)
    ; Keep host interrupts available while the virtual game interrupt is busy.
    ei
    jp $01f0

Native_SoftwareIRQ:
    ; Empty foreground polls need no context switch. The caller has disabled
    ; physical IRQs, so the queue cannot change while testing its four bytes.
    push af
    push hl
    ld hl,(Native_Pending)
    ld a,h
    or l
    ld hl,(Native_Pending+2)
    or h
    or l
    pop hl
    jr nz,.pending
    pop af
    ei
    ret
.pending:
    pop af
    IF NATIVE_VIDEO + NATIVE_IRQ_PROBE
    ; Foreground dispatch has its own stack, separate from both the caller's
    ; host stack and physical IRQs, which can interrupt context restoration.
    ld (Native_SoftwareSP),sp
    ld sp,$f200
    ELSE
    ld (Native_InterruptedSP),sp
    ld sp,NATIVE_IRQ_STACK
    ENDIF
    push af
    push bc
    push de
    push hl
    push ix
    push iy
    ex af,af'
    push af
    exx
    push bc
    push de
    push hl
    IF NATIVE_VIDEO + NATIVE_IRQ_PROBE
    ld a,1
    ld (Native_SoftwareBusy),a
    ei
    call Native_SelectIRQ
    ei
    or a
    jr nz,Native_EnterSoftwareIRQ
Native_ReturnSoftwareIRQ:
    xor a
    ld (Native_SoftwareBusy),a
    pop hl
    pop de
    pop bc
    exx
    pop af
    ex af,af'
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    di
    ld sp,(Native_SoftwareSP)
    ei
    ret
Native_EnterSoftwareIRQ:
    xor a
    ld (Native_SoftwareBusy),a
    pop hl
    pop de
    pop bc
    exx
    pop af
    ex af,af'
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    di
    ld sp,(Native_SoftwareSP)
    ei
    jp $01f0
    ELSE
    jp Native_DispatchIRQ
    ENDIF
    ENDIF

Native_Fail:
    ld (Native_Status),a
    di
.halt:
    halt
    jr .halt
    IF NATIVE_VIDEO
    IF NATIVE_HWACTORS
    INCLUDE "native-hardware-actors.inc"
    ENDIF
    ENDIF
Native_LoaderEnd:
