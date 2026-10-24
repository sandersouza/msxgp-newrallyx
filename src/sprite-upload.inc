; HL=source, DE=write-pointer in VRAM bank7, B=1..128 bytes. Advance both.
; Raster handlers restore the data pointer from actual OTIR source progress.
; No control-port pair is interruptible; the data stream is interruptible.
Sprite_UploadSource EQU $c7c4
Sprite_UploadDestination EQU $c7c6
Sprite_UploadActive EQU $c7c8
Sprite_UploadCount EQU $c7c2
Sprite_Upload:
    ei
    nop
    ld (Sprite_UploadSource),hl
    ld (Sprite_UploadDestination),de
    ld a,b
    ld (Sprite_UploadCount),a
    ld a,1
    ld (Sprite_UploadActive),a
    di
    vdp_write 14,7
    ld a,e
    out ($99),a
    ld a,d
    out ($99),a
    ld c,$98
    ei
    nop
    otir
    di
    xor a
    ld (Sprite_UploadActive),a
    ld a,(Sprite_UploadCount)
    add a,e
    ld e,a
    jr nc,.done
    inc d
.done:
    ret

; ISR-only, after its own uploads. Preserve foreground HL/DE; outer ISR saves
; AF/BC. Z80 accepts interrupts between complete OUTI iterations, so HL already
; points immediately after the last byte written to the foreground stream.
Sprite_ResumeUpload:
    push hl
    push de
    ld de,(Sprite_UploadSource)
    or a
    sbc hl,de
    ld de,(Sprite_UploadDestination)
    add hl,de
    vdp_write 14,7
    ld a,l
    out ($99),a
    ld a,h
    out ($99),a
    pop de
    pop hl
    ret
Sprite_EnemyColors:
    defs 16,$26
    defs 16,$6a
    defs 16,$a6
    defs 16,$ea
