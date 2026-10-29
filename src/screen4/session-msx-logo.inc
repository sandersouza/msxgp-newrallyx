; Optional SCREEN5 title label. Caller: UI bank selected, display off, main RAM.
; No persistent RAM. Clobbers AF/BC/DE/HL; uses existing UI blit scratch.
; Exactly54x20 at194,8: both top/right margins8px, uniform source scale1/3.
; Called once per cast draw, never from active gameplay or the IRQ.
    DEFINE UI_MSX_LOGO_ENABLED 1
UI_MSXLogo_Draw:
    ld hl,8*128+194/2
    ld (Full_UIDestination),hl
    ld a,27
    ld (Full_UIWidth),a
    ld a,20
    ld (Full_UIRows),a
    ld hl,UI_MSXLogo_Pixels
    jp Full_UIBlit
UI_MSXLogo_Pixels:
    INCBIN "session-msx-logo.bin"
