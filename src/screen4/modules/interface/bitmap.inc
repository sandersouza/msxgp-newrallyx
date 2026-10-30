; Native cold bitmap transfer. Caller owns SCREEN5 mode/palette and VDP latch.
; AF/BC/DE/HL clobbered; maps source image/data banks then leaves SESSION_BANK.
; Dependencies: upload, SESSION_IMAGE_BANK, SESSION_DATA_BANK, SESSION_BANK.
Session_CopyImage:
    xor a
    out ($99),a
    ld a,$40
    out ($99),a
    ld a,SESSION_IMAGE_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$4000
    call upload
    ld a,SESSION_DATA_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,$2a00
    call upload
    ld a,SESSION_BANK
    ld ($7000),a
    ret
