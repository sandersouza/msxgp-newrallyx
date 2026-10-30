; Reuse contract: audio-session (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameAudio_Init, GameAudio_Tick, GameAudio_Event, Full_TurboOn, Full_TurboOff
; Inputs: Main Page0. Tick derives elapsed ticks from clock_ticks/Audio_LastUI, not an A bank
;   argument. Event only handles the established background request; native request RAM drives
;   other sounds.
; Outputs: Pinned PSG worker runs at elapsed 30 Hz cadence; worker calls restore
;   GAME_NATIVE_BANK. Turbo entries remain no-op RETs.
; Registers: Common caller-saved ABI across mapped Audio_RuntimeStep; Event AF scratch.
; Interrupts: No new DI/EI; IRQ must not write PSG or change Page2 mapping while the worker
;   runs.
; Memory / hardware: Existing D150 audio timing state and E9xx native audio requests/caches;
;   score bytes in AUDIO_BANK.
; Reuse boundary: Native WSG-to-PSG binding. Mutually exclusive with audio-first-stage; these
;   public label names have different input/event semantics.
; Keep this summary synchronized with the registry and modules/README.md.

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
