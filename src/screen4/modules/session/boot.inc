; Reuse contract: session-boot (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameSession_Boot
; Inputs: Resident entry; generated cold/startup banks, player seed and main Page0 segment
;   available.
; Outputs: Loads existing Page0 cold/startup code, optionally replays boot, restores native
;   bitmap scratch/seed/audio and tail-enters GameSession_UI.
; Registers: Common caller-saved ABI; a lifecycle transition, not a short returning helper.
; Interrupts: Cold initialization owns display/IRQ state; no active-frame invocation.
; Memory / hardware: Existing cold 1400..1FFF, startup 2900..2FFF and native D300..F2FF
;   lifetimes; no extra segment or buffer.
; Reuse boundary: Game-specific bootstrap binding. Retain relocation sizes, seed and scratch
;   restoration; it is not a generic loader.
; Keep this summary synchronized with the registry and modules/README.md.

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
