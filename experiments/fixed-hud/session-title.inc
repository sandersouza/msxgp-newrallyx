; Cast-only footer. 32 physical refreshes per half-period; no gameplay hook.
; One byte of UI-only RAM, shared blit scratch, AF/BC/DE/HL caller-saved.
UI_CastBlink EQU $dfe3
UI_CastFooter_Init:
    ld a,$ff
    ld (UI_CastBlink),a
UI_CastFooter_Tick:
    ld a,(ticks)
    and 32
    ld hl,UI_CastBlink
    cp (hl)
    ret z
    ld (hl),a
    or a
    ld hl,UI_CastKey0_on
    jr z,.first
    ld hl,UI_CastKey0_off
.first:
    call UI_CastFooter_Key0
    ld a,(UI_CastBlink)
    or a
    ld hl,UI_CastKey1_on
    jr z,.second
    ld hl,UI_CastKey1_off
.second:
    jp UI_CastFooter_Key1
    INCLUDE "session-title-blit.inc"
    INCLUDE "session-title-data.inc"
