; Module contract: Cold entry from resident ROM; transfers control to UI, native seed/audio restored.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
GameSession_Boot:
    ld a,SESSION_COLD_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,GameSession_ColdStart
    ld bc,GameSession_ColdEnd-GameSession_ColdStart
    ldir
    call GameSession_ColdBoot
    ld a,SESSION_BOOT_BANK
    ld ($7000),a
    ld hl,$8000
    ld de,GameSession_StartupWorkers
    ld bc,GameSession_BootEnd-GameSession_StartupWorkers
    ldir
    IF SESSION_HARDWARE_CHECK
    call GameSession_BootShow
    ENDIF
    ; Boot bitmap scratch must not become native game/audio state.
    xor a
    ld hl,$d300
    ld de,$d301
    ld bc,$1fff
    ld (hl),a
    ldir
    ld a,PLAYER_DATA_BANK
    ld ($7000),a
    ld hl,$a000
    ld de,$e000
    ld bc,$1000
    ldir
    call GameAudio_Init
    jp GameSession_UI
