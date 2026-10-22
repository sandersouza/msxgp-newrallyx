; Inline ISR hooks: keep the measured VDP transaction order unchanged.
; Caller saves AF/BC. Both hooks preserve HL, DE, IX/IY and alternate registers.
; They leave R14=7 and advance the VDP pointer; see docs/hud.md.
    MACRO HUD_VBlankSprites
    push hl
    vdp_write 14,7
    ld a,FUEL_COLORS&255
    out ($99),a
    ld a,$40+((FUEL_COLORS>>8)&$3f)
    out ($99),a
    ld hl,sprite_colors+FUEL_SLOT*16
    ld bc,$3098
    otir
    pop hl
    ENDM
    MACRO HUD_FooterSprites
    push hl
    vdp_write 0,6
    vdp_write 14,7
    ld a,FUEL_COLORS&255      ; shared fuel/life slots 14..16
    out ($99),a
    ld a,$40+((FUEL_COLORS>>8)&$3f)
    out ($99),a
    ld hl,life_colors
    ld bc,$3098
    otir
    ld a,FUEL_ATTRIBUTES&255
    out ($99),a
    ld a,$40+((FUEL_ATTRIBUTES>>8)&$3f)
    out ($99),a
    ld hl,life_sat
    ld bc,$0c98
    otir
    pop hl
    ENDM
