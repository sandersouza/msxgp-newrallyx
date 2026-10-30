; Module contract: Pinned native PSG adapter; elapsed ticks, original request RAM, native bank restored.
; Detailed ABI, ownership and reuse limits: modules/README.md and contracts.json.
GameAudio_Init:
    xor a
    ld hl,$d150
    ld de,$d151
    ld bc,7
    ld (hl),a
    ldir
    ld a,1
    ld (Audio_NewScene),a
    ld a,(ticks)
    ld (Audio_LastUI),a
    ret
GameAudio_Tick:
    ld a,(ticks)
    ld hl,Audio_LastUI
    sub (hl)
    cp 2
    ret c
    srl a
    ld (Audio_Elapsed),a
    add a,a
    add a,(hl)
    ld (hl),a
    ld a,AUDIO_BANK
    ld ($7000),a
    call Audio_RuntimeStep
    ld a,GAME_NATIVE_BANK
    ld ($7000),a
    ret
GameAudio_Event:
    or a
    ret nz                  ; Shared worker observes original native requests.
    ld a,1
    ld (Audio_NewScene),a
    ret
GameAudio_EVENT_BACKGROUND EQU 0
GameAudio_EVENT_FLAG EQU 1
GameAudio_EVENT_SPECIAL_FLAG EQU 2
GameAudio_EVENT_SMOKE EQU 3
GameAudio_EVENT_DEATH EQU 4
GameAudio_EVENT_CLEAR EQU 5
GameAudio_EVENT_GAMEOVER EQU 6
Full_TurboOn:
Full_TurboOff:
    ret                     ; Fixed measured CPU frequency, no factory turbo.
