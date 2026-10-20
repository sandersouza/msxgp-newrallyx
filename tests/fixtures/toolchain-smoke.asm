; Synthetic 16 KiB MSX cartridge. No original game data.
    org $4000
    db "AB"
    dw start
    dw 0,0,0
    ds 6,0
start:
    di
    ld a,$42
    ld ($c000),a
    jp start
    ds $8000-$,$ff
