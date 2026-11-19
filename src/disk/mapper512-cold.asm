; Experimental stopped-game DOS1/Disk BASIC bridge; not a game bootstrap.
; Physical30, offset1000..3BFF is a declared hole in every packet family.
; Init A=0 DOS1/1 BASIC, BIOS Page0/OS Page3, RAM Page1=30, DI. Never returns.
; Read C=compiled resource index; Page0 main1, Page3 game0, Page1=30, DI.
; Return DI, CF=0 success/CF=1 failure, SP balanced, I restored, IM2 selected;
; all general registers/flags scratch. Page0=1, Page3=0, Page2=target on success.
; Caller must stop gameplay/audio/display and own the game/BIOS IRQ handoff.
; Rebuild world/cache segments2/3/4/5 before gameplay. EndBatch must run before
; leaving a successful group of reads; it persists OS changes and releases4/5.
; Code/data in bridge holes survive family copy.
; Two OS pages persist in declared common holes. Restore into borrowed4/5,
; keep4/5 until EndBatch, use2 for compressed disk input and3 for validated
; decoded output. No extra segment, active calls, VDP/PSG writes or NMI use.
; Private FCB/cursors/SP fields last through a nonreentrant cold transaction.
    OUTPUT "cold.bin"
    INCLUDE "cold-mode.inc"
    IFNDEF COLD_GAME
 DEFINE COLD_GAME 0
    ENDIF
    ORG $5000
    IF COLD_GAME
    jp Cold_Init
    jp Mapper512_GameCommand
    ENDIF
Cold_Init:
    ld (Cold_Mode),a
    ld a,i
    ld (Cold_OsI),a
    in a,($a8)
    ld (Cold_OsPrimary),a
    rlca
    rlca
    call Cold_RepeatSlot
    ld (Cold_RamPrimary),a
    ld a,($ffff)
    cpl
    ld (Cold_OsSecondary),a
    rlca
    rlca
    call Cold_RepeatSlot
    ld (Cold_RamSecondary),a
    ld a,(Cold_Mode)
    or a
    ld hl,$0005
    jr z,.bdos
    ld hl,$f37d
.bdos:
    ld (Cold_Bdos+1),hl
    call Cold_SaveOs
    call Cold_AllRam
    IF COLD_GAME
    jp Mapper512_GameBoot
    ELSE
    ; Destructive diagnostic work state only, not an initializer for the game.
    ; A Page1 stack survives replacing physical0/OS Page3 below.
    ld sp,$7d00
    xor a
    out ($fe),a
    ld hl,$8000
    ld de,$8001
    ld bc,$3fff
    ld (hl),a
    ldir
    ld a,1
    out ($fe),a
    ld hl,$8000
    ld de,$8001
    ld bc,$3fff
    ld (hl),$5a
    ldir
    xor a
    out ($ff),a
    ld a,1
    out ($fc),a
    ld ($c0ee),a             ; Lifetime marker; not a production F10 activation.
    ld sp,$f380
    ld a,$d2
    ld i,a
    im 2
    xor a
    ld (Cold_FixtureIndex),a
Cold_FixtureNext:
    ld a,(Cold_FixtureIndex)
    ld c,a
    call Cold_Read
Cold_FixtureStepDone:
    jp c,Cold_FixtureFailed
    ld a,(Cold_Target)
    cp 2
    jr nz,Cold_FixtureAdvance
    call Cold_EndBatch
Cold_FixtureBatchDone:
    jp Cold_FixtureAdvance
Cold_FixtureAdvance:
    ld a,(Cold_FixtureIndex)
    inc a
    ld (Cold_FixtureIndex),a
    cp Cold_ResourceCount
    jr c,Cold_FixtureNext
Cold_FixturePassed:
    di
    halt
    jr Cold_FixturePassed
Cold_FixtureFailed:
    di
    halt
    jr Cold_FixtureFailed
    ENDIF

; Repeat Page3's slot/subslot ID across all four CPU pages. AF/B scratch.
Cold_RepeatSlot:
    and 3
    ld b,a
    rlca
    rlca
    or b
    ld b,a
    rlca
    rlca
    rlca
    rlca
    or b
    ret
Cold_AllRam:
    ld a,(Cold_RamSecondary)
    ld ($ffff),a
    ld a,(Cold_RamPrimary)
    out ($a8),a
    ret

; OS Page0/Page3 remain mapped; scatter exactly32KiB to declared holes.
; AF/BC/DE/HL/IX scratch, IY preserved; DI, caller stack in OS Page3.
Cold_SaveOs:
    ld ix,Cold_Context
.loop:
    ld a,(ix+0)
    out ($fe),a
    ld l,(ix+1)
    ld h,(ix+2)
    ld e,(ix+3)
    ld d,(ix+4)
    ld c,(ix+5)
    ld b,(ix+6)
    ldir
    ld bc,7
    add ix,bc
    push ix
    pop hl
    ld de,Cold_ContextEnd
    or a
    sbc hl,de
    jr c,.loop
    ret

; All RAM visible, game Page3/stack still mapped. Restore OS into temporary
; flag-cache segments4/5 through Page0, leaving main1/game0 bytes intact.
Cold_RestoreOs:
    ld ix,Cold_Context
.loop:
    ld a,(ix+0)
    out ($fe),a
    ld l,(ix+3)
    ld h,(ix+4)
    ld e,(ix+1)
    ld a,(ix+2)
    ld d,a
    and $3f
    ld d,a
    ld a,(ix+2)
    and $c0
    ld a,4
    jr z,.destination
    inc a
.destination:
    out ($fc),a
    ld c,(ix+5)
    ld b,(ix+6)
    ldir
    ld bc,7
    add ix,bc
    push ix
    pop hl
    ld de,Cold_ContextEnd
    or a
    sbc hl,de
    jr c,.loop
    ret

Cold_Read:
    ld (Cold_GameSP),sp
    ld a,i
    ld (Cold_GameI),a
    ld a,c
    cp Cold_ResourceCount
    jp nc,.bad_early
    ; Nine-byte sealed metadata: bank,length,checksum,byte-file-offset.
    ld l,c
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    ld b,0
    add hl,bc
    ld de,Cold_Resources
    add hl,de
    ld de,Cold_Target
    ld bc,9
    ldir
    xor a
    ld (Cold_Map2Ready),a
    IF COLD_BATCH
    ld a,(Cold_OsLive)
    or a
    jr nz,.os_ready
    ENDIF
    call Cold_RestoreOs
    ld a,1
    ld (Cold_OsLive),a
.os_ready:
    call Cold_Page0Os
    ld a,5
    out ($ff),a
    ld sp,$cf00
    ld a,(Cold_OsI)
    ld i,a
    im 1
    IF COLD_GAME
    ; The restored OS must not generate key-click sound while F5/F10 is held.
    xor a
    ld ($f3db),a
    ENDIF
    ei
    IF COLD_BATCH
    ld a,(Cold_FileOpen)
    or a
    jr nz,.position
    ENDIF
    ld hl,Cold_Fcb
    ld de,Cold_Fcb+1
    ld bc,36
    ld (hl),0
    ldir
    ld hl,Cold_FileName
    ld de,Cold_Fcb+1
    ld bc,11
    ldir
    ld de,Cold_Fcb
    ld c,$0f
    call Cold_Bdos
    inc a
    jp z,.open_error
    ld a,1
    ld (Cold_FileOpen),a
    ld hl,1
    ld (Cold_Fcb+14),hl
    ld de,$c100
    ld c,$1a
    call Cold_Bdos
    ld de,Cold_Fcb
    ld hl,8
    ld c,$27
    call Cold_Bdos
    or a
    jr nz,.read_error
    ld a,h
    or a
    jr nz,.read_error
    ld a,l
    cp 8
    jr nz,.read_error
    ld hl,$c100
    ld de,Cold_Magic
    ld b,8
.magic:
    ld a,(de)
    cp (hl)
    jr nz,.read_error
    inc hl
    inc de
    djnz .magic
.position:
    ld hl,Cold_FileOffset
    ld de,Cold_Fcb+33
    ld bc,4
    ldir
    di
    ld a,2
    out ($fe),a
    ei
    ld de,$8000
    ld c,$1a
    call Cold_Bdos
    ld de,Cold_Fcb
    ld hl,(Cold_Length)
    ld c,$27
    call Cold_Bdos
    or a
    jr nz,.read_error
    ld de,(Cold_Length)
    or a
    sbc hl,de
    jr nz,.read_error
    di
    IF !COLD_BATCH
    call Cold_CloseOpen
    jp c,.return_error
    call Cold_SaveOs
    ENDIF
    jr .loaded
.read_error:
    di
    jp .return_error
.loaded:
    call Cold_AllRam
    ; OS4/5 remain intact throughout the batch. Both world segments are cold
    ; scratch; decode to3, leaving the filesystem's compressed input in2.
    ld a,3
    out ($fc),a
    ld a,2
    out ($fe),a
    ld hl,$8000
    ld bc,(Cold_Length)
    ld de,0
    call Cold_Decode
    jp c,.return_error
    ld hl,0
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
    ld hl,(Cold_Checksum)
    or a
    sbc hl,de
    jp nz,.return_error
    call Cold_CopyLive
    IF COLD_GAME
    jp c,.return_error
    ENDIF
    ld a,(Cold_Target)
    cp 3
    jr nz,.not_map3
    call Cold_SaveMap3
    ld a,1
    ld (Cold_MapPending),a
    ld a,3
    out ($fe),a
.not_map3:
    ld a,(Cold_Target)
    cp 2
    jr nz,.map_ready
    ld a,1
    ld (Cold_Map2Ready),a
.map_ready:
    xor a
    jp Cold_ReturnGame
.open_error:
    di
.return_error:
    call Cold_Page0Os
    call Cold_CloseOpen
    call Cold_SaveOs
    call Cold_AllRam
    xor a
    ld (Cold_OsLive),a
    ld (Cold_MapPending),a
    ld a,1
    jp Cold_ReturnGame
.bad_early:
    scf
    ret

; DI, same game mappings/stack as Read. Persist OS once per stopped phase,
; then release caches4/5 for reconstruction. Closing may block in BDOS;
; authored bridge code makes no VDP/PSG accesses.
Cold_EndBatch:
    ld a,(Cold_OsLive)
    or a
    ret z
    ld (Cold_GameSP),sp
    ld a,i
    ld (Cold_GameI),a
    call Cold_Page0Os
    ld a,5
    out ($ff),a
    ld sp,$cf00
    xor a
    ld (Cold_Result),a
    call Cold_CloseOpen
    jr nc,.closed
    ld a,1
    ld (Cold_Result),a
.closed:
    call Cold_SaveOs
    call Cold_AllRam
    ld a,(Cold_MapPending)
    or a
    jr nz,.pending
    ld a,(Cold_Target)
    cp 2
    jr z,.bad_maps
    jr .maps_done
.pending:
    ld a,(Cold_Map2Ready)
    or a
    jr z,.bad_maps
    call Cold_RestoreMap3
.maps_done:
    ld a,(Cold_Target)
    out ($fe),a
    xor a
    ld (Cold_OsLive),a
    ld (Cold_MapPending),a
    ld a,(Cold_Result)
    jp Cold_ReturnGame
.bad_maps:
    xor a
    ld (Cold_OsLive),a
    ld (Cold_MapPending),a
    ld a,1
    jp Cold_ReturnGame

; Page0=decoded map3 (physical3). Scatter to a separate declared16KiB cold
; shadow, disjoint from OS snapshots/bridge and all live fields. DI, OS stack.
Cold_SaveMap3:
    ld ix,Cold_MapStage
.loop:
    ld a,(ix+0)
    out ($fe),a
    ld l,(ix+1)
    ld h,(ix+2)
    ld e,(ix+3)
    ld d,(ix+4)
    ld c,(ix+5)
    ld b,(ix+6)
    ldir
    ld bc,7
    add ix,bc
    push ix
    pop hl
    ld de,Cold_MapStageEnd
    or a
    sbc hl,de
    jr c,.loop
    ret

; Restore the second world half only after the last disk/decode transaction.
; Page3 remains OS5/stack; output maps3 in Page0, all immutable hot fields kept.
Cold_RestoreMap3:
    ld a,3
    out ($fc),a
    ld ix,Cold_MapStage
.loop:
    ld a,(ix+0)
    out ($fe),a
    ld l,(ix+3)
    ld h,(ix+4)
    ld e,(ix+1)
    ld d,(ix+2)
    ld c,(ix+5)
    ld b,(ix+6)
    ldir
    ld bc,7
    add ix,bc
    push ix
    pop hl
    ld de,Cold_MapStageEnd
    or a
    sbc hl,de
    jr c,.loop
    ret

; Only Page0 changes slots; calling code/Page3 stack stay visible, DI.
Cold_Page0Os:
    ld a,4
    out ($fc),a
    ; Only Page0 is restored to its BIOS/DOS slot. Page1 bridge, Page2 DMA
    ; and Page3 relocated OS workspace remain in the main RAM slot.
    ld a,(Cold_RamSecondary)
    and $fc
    ld b,a
    ld a,(Cold_OsSecondary)
    and 3
    or b
    ld ($ffff),a
    ld a,(Cold_RamPrimary)
    and $fc
    ld b,a
    ld a,(Cold_OsPrimary)
    and 3
    or b
    out ($a8),a
    ret

; Only while OS5/CF00 and original OS Page0 are visible. No open file escapes
; EndBatch or an I/O/decode error. General registers/IFF scratch, return DI;
; CF=1 close failure, CF=0 closed/already closed. OS5 owns the persistent FCB.
Cold_CloseOpen:
    ld a,(Cold_FileOpen)
    or a
    ret z
    ld a,(Cold_OsI)
    ld i,a
    im 1
    ei
    ld de,Cold_Fcb
    ld c,$10
    call Cold_Bdos
    di
    inc a
    ld a,0
    ld (Cold_FileOpen),a
    jr nz,.ok
    scf
    ret
.ok:
    or a
    ret

Cold_ReturnGame:
    ld (Cold_Result),a
    ld a,1
    out ($fc),a
    xor a
    out ($ff),a
    ld sp,(Cold_GameSP)
    ld a,(Cold_GameI)
    ld i,a
    im 2
    ld a,(Cold_Result)
    or a
    ret z
    scf
    ret

Cold_Bdos:
    jp $0005

; Copy only the union of all declared live fields. Page0 decoded bank3,
; Page2 target; Page1 bridge and Page3 OS5/stack stay mapped, DI throughout.
; Persistent OS/bridge holes are never written, including when target=30.
Cold_CopyLive:
    ld a,(Cold_Target)
    IF COLD_GAME
    bit 7,a
    jr z,.masked
    and 31
    cp 20
    jr c,.invalid_full
    cp 30
    jr nc,.invalid_full
    ld (Cold_Target),a
    out ($fe),a
    ld hl,0
    ld de,$8000
    ld bc,$4000
    ldir
    or a
    ret
.invalid_full:
    scf
    ret
.masked:
    ENDIF
    out ($fe),a
    ld l,a
    ld h,0
    add hl,hl
    ld de,Cold_CopyDirectory
    add hl,de
    ld e,(hl)
    inc hl
    ld d,(hl)
    push de
    pop ix
.loop:
    ld c,(ix+2)
    ld b,(ix+3)
    ld a,b
    or c
    ret z
    ld l,(ix+0)
    ld h,(ix+1)
    ld e,l
    ld a,h
    or $80
    ld d,a
    ldir
    ld bc,4
    add ix,bc
    jr .loop

; Bounded LZ: Page2 HL+BC <= C000, Page0 output0000..3FFF.
; Exact16KiB and exact compressed exhaustion required. No hot output is
; installed before both decode and whole-page checksum succeed.
Cold_Decode:
    push hl
    pop ix
    add ix,bc
    jp c,.fail
    ld a,ixh
    cp $c0
    jr c,.loop
    jr nz,.fail
    ld a,ixl
    or a
    jr nz,.fail
.loop:
    ld a,d
    cp $40
    jr z,.done
    call Cold_GetByte
    jr c,.fail
    bit 7,a
    jr nz,.match
    ld c,a
    inc c
    ld b,0
    call Cold_OutputSpace
    jr c,.fail
    call Cold_InputSpace
    jr c,.fail
    ldir
    jr .loop
.match:
    and 127
    add a,3
    ld c,a
    ld b,0
    call Cold_OutputSpace
    jr c,.fail
    push bc
    call Cold_GetByte
    jr c,.pop_fail
    ld c,a
    call Cold_GetByte
    jr c,.pop_fail
    ld b,a
    ld a,b
    or c
    jr z,.pop_fail
    ld (Cold_Cursor),hl
    ld h,d
    ld l,e
    or a
    sbc hl,bc
    jr c,.pop_fail
    pop bc
    ldir
    ld hl,(Cold_Cursor)
    jr .loop
.done:
    ld a,h
    cp ixh
    jr nz,.fail
    ld a,l
    cp ixl
    jr nz,.fail
    or a
    ret
.pop_fail:
    pop bc
.fail:
    scf
    ret
Cold_GetByte:
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
Cold_OutputSpace:
    push hl
    ld h,d
    ld l,e
    add hl,bc
    ld a,h
    cp $40
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
Cold_InputSpace:
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

Cold_Mode: db 0
Cold_OsI: db 0
Cold_GameI: db 0
Cold_OsPrimary: db 0
Cold_OsSecondary: db 0
Cold_RamPrimary: db 0
Cold_RamSecondary: db 0
Cold_GameSP: dw 0
Cold_OsLive: db 0
Cold_FileOpen: db 0
Cold_MapPending: db 0
Cold_Map2Ready: db 0
Cold_Result: db 0
Cold_Cursor: dw 0
Cold_FixtureIndex: db 0
Cold_Target: db 0
Cold_Length: dw 0
Cold_Checksum: dw 0
Cold_FileOffset: dd 0
; Disk BASIC maps its disk ROM into Page1 during BDOS. FCB and DMA/header
; must therefore live outside the executing bridge page, not beside its code.
; These are borrowed OS-Page3 TPA bytes below kernelD606, not game state.
Cold_Fcb EQU $c200
Cold_FileName:
    IF COLD_GAME
    db "NRX512  DAT"
    ELSE
    db "NRXCOLD DAT"
    ENDIF
Cold_Magic: db "NRXCOLD1"
    IF COLD_GAME
    INCLUDE "mapper512-game-bridge.inc"
    ENDIF
    INCLUDE "cold-layout.inc"
Cold_CodeEnd:
    ASSERT $ < $7c00
    IF COLD_GAME
    defs $7d80-$,$ff
    INCLUDE "game-objects.inc"
    ASSERT $ <= $7e40
    ENDIF
Cold_End:
