; Native-only shared-HUD adaptation. Retain a private logical VRAM cursor so
; raster handlers may replace the hardware cursor between bounded packets.
Native_HUDByteValue EQU $e670
Native_HUDWriteBank EQU $e671
Native_HUDWriteLatch EQU $e672
Native_HUDWriteAddress EQU $e673
Native_StreamAddress EQU $e675
Native_StreamBank EQU $e677
Native_StreamCount EQU $e678
Native_StreamActive EQU $e679
Native_InterruptedB EQU $e67a

Native_HUDSetBank:
    ld (Native_HUDWriteBank),a
    ret
Native_HUDRegister:
    push af
    ld a,b
    cp 14
    jr nz,.other
    pop af
    jp Native_HUDSetBank
.other:
    pop af
    di
    call register
    jp Native_RenderEI

Native_HUDAddressByte:
    push af
    ld a,(Native_HUDWriteLatch)
    or a
    jr nz,.high
    pop af
    ld (Native_HUDWriteAddress),a
    push af
    ld a,1
    ld (Native_HUDWriteLatch),a
    pop af
    ret
.high:
    pop af
    push af
    and $3f
    ld (Native_HUDWriteAddress+1),a
    xor a
    ld (Native_HUDWriteLatch),a
    pop af
    ret

Native_HUDSelectAddress:
    di
    vdp_write 14,(Native_HUDWriteBank)
    ld a,(Native_HUDWriteAddress)
    out ($99),a
    ld a,(Native_HUDWriteAddress+1)
    or $40
    out ($99),a
    ret

; Boot-only long uploader. Preserve the shared implementation's DE/HL result.
Native_HUDInitUpload:
    call Native_HUDSelectAddress
    push hl
    ld hl,(Native_HUDWriteAddress)
    add hl,de
    ld (Native_HUDWriteAddress),hl
    pop hl
    jp upload

; BC=count/98, HL=source, with B=0 meaning256 as for OTIR. Preserve DE;
; consume HL and return B=0. AF is renderer scratch. Each packet reselects its
; full address, so no pointer continuity is assumed across a raster interrupt.
Native_HUDOTIR:
    push de
    ld d,b
.packet:
    ld e,32
    ld a,d
    or a
    jr z,.count
    cp 32
    jr nc,.count
    ld e,a
.count:
    ld b,e
    call Native_StageStream
    call Native_HUDSelectAddress
    ld a,1
    ld (Native_StreamActive),a
    call Native_RenderEI
    otir
    xor a
    ld (Native_StreamActive),a
    call Native_RenderEI
    push hl
    ld hl,(Native_HUDWriteAddress)
    ld b,0
    ld c,e
    add hl,bc
    bit 6,h
    jr z,.address
    res 6,h
    ld a,(Native_HUDWriteBank)
    inc a
    and 7
    ld (Native_HUDWriteBank),a
.address:
    ld (Native_HUDWriteAddress),hl
    pop hl
    ld c,$98
    ld a,d
    sub e
    ld d,a
    jr nz,.packet
    pop de
    ret

Native_HUDByte:
    push af
    push bc
    push de
    push hl
    ld (Native_HUDByteValue),a
    ld hl,Native_HUDByteValue
    ld bc,$0198
    call Native_HUDOTIR
    pop hl
    pop de
    pop bc
    pop af
    ret

Native_StageStream:
    push hl
    ld hl,(Native_HUDWriteAddress)
    ld (Native_StreamAddress),hl
    pop hl
    ld a,(Native_HUDWriteBank)
    ld (Native_StreamBank),a
    ld a,b
    ld (Native_StreamCount),a
    ret

; A raster interrupt can replace R14 and the CPU VRAM pointer during OTIR.
; The interrupted B counter identifies exactly how many bytes were written.
; Restore the next address after the ISR's own uploads, preserving all registers.
Native_RestoreStream:
    push af
    ld a,(Native_StreamActive)
    or a
    jr z,.inactive
    push bc
    push de
    push hl
    ld a,(Native_InterruptedB)
    ld b,a
    ld a,(Native_StreamCount)
    sub b
    ld e,a
    ld d,0
    ld hl,(Native_StreamAddress)
    add hl,de
    ld a,(Native_StreamBank)
    bit 6,h
    jr z,.bank
    res 6,h
    inc a
    and 7
.bank:
    out ($99),a
    ld a,$8e
    out ($99),a
    ld a,l
    out ($99),a
    ld a,h
    or $40
    out ($99),a
    pop hl
    pop de
    pop bc
.inactive:
    pop af
    ret
