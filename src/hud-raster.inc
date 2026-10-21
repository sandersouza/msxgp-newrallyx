; Inline ISR hooks: keep the measured VDP transaction order unchanged.
; Caller saves AF/BC. Both hooks preserve HL, DE, IX/IY and alternate registers.
; They leave R14=7 and advance the VDP pointer; see docs/hud.md.
    MACRO HUD_VBlankSprites
    push hl
    vdp_write 14,7
    ld a,$b0
    out ($99),a
    ld a,$75
    out ($99),a
    ld hl,sprite_colors+27*16
    ld bc,$3098
    otir
    pop hl
    ENDM
    MACRO HUD_FooterSprites
    push hl
    vdp_write 0,6
    vdp_write 14,7
    ld a,$b0                  ; slots 27..29: yellow car, black outline, white count
    out ($99),a
    ld a,$75
    out ($99),a
    ld hl,life_colors
    ld bc,$3098
    otir
    ld a,$6c
    out ($99),a
    ld a,$76
    out ($99),a
    ld hl,life_sat
    ld bc,$0c98
    otir
    pop hl
    ENDM
