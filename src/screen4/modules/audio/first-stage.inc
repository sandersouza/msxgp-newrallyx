; Reuse contract: audio-first-stage (modules/contracts.json).
; Source organization only: this header emits no code or storage.
; Public API: GameAudio_Init, GameAudio_Tick, GameAudio_Event, GameAudio_Stop
; Inputs: Init then Tick once per elapsed nominal 60 Hz tick, A=current Page2 bank; Event
;   A=GameAudio_EVENT_*; generated music/noise data precedes code.
; Outputs: PSG serviced at 30 Hz; Tick restores its input bank. Stop silences channels and
;   clears requests.
; Registers: AF/BC/DE/HL caller-saved; IRQ must preserve live registers.
; Interrupts: No DI/EI; IFF preserved. IRQ must not write PSG or mapper during worker access.
; Memory / hardware: Resident 4000..7FFF code, generated score packets in GAME_AUDIO_BANK,
;   private DC00..DC52 state. No native state reads.
; Reuse boundary: Portable event/packet adapter with compatible generated tables. Mutually
;   exclusive with native session audio: identical label names do not imply identical event or
;   Tick semantics.
; Keep this summary synchronized with the registry and modules/README.md.

; Module contract: Resident event-driven PSG adapter and generated tables; distinct from native session ABI.
; Include once at the original code position. No loader or runtime dispatch.
    INCLUDE "../../game-audio-data.inc"
    INCLUDE "../../game-audio.inc"
