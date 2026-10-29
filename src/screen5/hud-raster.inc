; Inline ISR hooks: keep the measured VDP transaction order unchanged.
; Caller saves AF/BC. Both hooks preserve HL, DE, IX/IY and alternate registers.
; Active uploads leave R14=7 and advance the VDP pointer; see docs/hud.md.
    MACRO HUD_VBlankSprites
    IF RADAR_BLITTER
    ; The diagnostic full-copy loop can span multiple refreshes. Restore the
    ; shared body's fuel attributes every VBlank after the footer reused them.
    push hl
    vdp_write 14,7
    ld a,FUEL_ATTRIBUTES&255
    out ($99),a
    ld a,$40+((FUEL_ATTRIBUTES>>8)&$3f)
    out ($99),a
    ld hl,fuel_sat
    ld bc,$0c98
    otir
    pop hl
    ENDIF
    IF !HUD_STATIC_LIFE
    push hl
    IF HUD_ALERTS
    call HUD_FuelPublishIRQ
    ENDIF
    vdp_write 14,7
    ld a,FUEL_COLORS&255
    out ($99),a
    ld a,$40+((FUEL_COLORS>>8)&$3f)
    IF OUTLINE_FLICKER
    call Outline_ColorAddress
    ENDIF
    out ($99),a
    ld hl,sprite_colors+FUEL_SLOT*16
    IF HUD_ALERTS
    ld bc,$1098             ; Keep the pump white; recolor only the two bar sprites.
    otir
    ld a,(hud_fuel_color_drawn)
    ld b,32
.fuel_color:
    out ($98),a
    djnz .fuel_color
    ELSE
    ld bc,$3098
    otir
    ENDIF
    pop hl
    ENDIF
    ENDM
    MACRO HUD_FooterSprites
    push hl
    IF FULL_GAME
    push de
    ld a,(irq_scroll_y)
    call update_life_sat_value
    pop de
    ENDIF
    vdp_write 0,MAZE_R0
    vdp_write 14,7
    IF !HUD_STATIC_LIFE
    ld a,FUEL_COLORS&255      ; shared fuel/life slots 14..16
    out ($99),a
    ld a,$40+((FUEL_COLORS>>8)&$3f)
    IF OUTLINE_FLICKER
    call Outline_ColorAddress
    ENDIF
    out ($99),a
    ld hl,life_colors
    ld bc,$3098
    otir
    ENDIF
    ld a,FUEL_ATTRIBUTES&255
    out ($99),a
    ld a,$40+((FUEL_ATTRIBUTES>>8)&$3f)
    IF OUTLINE_FLICKER
    call Outline_ColorAddress
    ENDIF
    out ($99),a
    ld hl,life_sat
    ld bc,$0c98
    otir
    pop hl
    ENDM
